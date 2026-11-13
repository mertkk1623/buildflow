"""Analyze ve Calculate iş akışı — HTTP'den bağımsız servis katmanı.

Bu modül FastAPI'ye bağlı değildir; router yalnızca ince bir kabuktur. Böylece
iki aşamalı akış HTTP olmadan da test edilebilir.

Statelesslik
------------
Sunucu hiçbir analiz sonucunu saklamaz. ``analyze`` çıktısı istemciye gider,
``calculate`` ise satırları **yeniden** alır ve eşleştirmeyi/hesabı sıfırdan
yapar. Aynı süreçte eşzamanlı iki istek birbirinin verisini göremez: her
istek kendi yerel sözlükleriyle çalışır, modül düzeyinde değiştirilebilir
durum yoktur (katalog ``lru_cache`` ile salt-okunur paylaşılır).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.api.errors import ApiError, make_issue
from app.api.mapping import (
    ai_evaluation_to_out,
    ai_summary_to_out,
    analyze_summary,
    calculation_summary,
    group_to_out,
    metraj_row_to_analyze,
    skipped_row_to_out,
)
from app.api.schemas import (
    AiOut,
    AnalyzeResponse,
    CalculateRequest,
    CalculateResponse,
)
from app.ai.engine import evaluate_rows
from app.ai.models import AiRunResult, AiSkipReason
from app.ai.providers import AiProvider
from app.domain.calculation import (
    CalculationInputRow,
    CalculationResult,
    WasteRate,
    calculate_purchase_list,
)
from app.domain.catalog import Catalog, get_catalog
from app.domain.decisions import Decision, DecisionAction, apply_decisions
from app.domain.matching import match_row
from app.domain.models import (
    MatchOutcome,
    MatchStatus,
    MaterialAttributes,
    Unit,
)
from app.excel.bridge import to_domain
from app.excel.reader import read_metraj

#: Karar nedeni alanının API'de izin verilen en büyük uzunluğu.
_MAX_REASON = 500

logger = logging.getLogger(__name__)


def analyze_file(
    path: Path,
    *,
    catalog: Catalog | None = None,
    provider: AiProvider | None = None,
) -> AnalyzeResponse:
    """Excel dosyasını okur, geçerli satırları eşleştirir ve rapor üretir.

    Invariant: ``rows`` içindeki her satır ya geçerli (``rule``/``pending``/
    ``excluded``) ya da ``invalid``'dir; hatalı satırlar **silinmez**.

    AI yalnızca **pending** satırlar için ve yalnızca ``provider`` verildiğinde
    çalışır. Sonuç ``ai`` alanında ayrı taşınır; eşleştirme durumu
    (``match``) AI'dan etkilenmez.
    """
    active_catalog = catalog or get_catalog()

    result = read_metraj(path)
    batch = to_domain(result)

    # Geçerli satırlar eşleştirmeye girer; hatalı satırlar eşleştirilmez.
    outcomes: dict[int, MatchOutcome] = {}
    for source in batch.sources:
        outcomes[source.source_row] = source.match(active_catalog)

    ai_result = _run_ai(result, outcomes, active_catalog, provider)

    rows = []
    for row in result.rows:
        outcome = outcomes.get(row.source_row)
        if outcome is None:
            outcome = MatchOutcome(
                status=MatchStatus.INVALID,
                attributes=MaterialAttributes(),
                message=_invalid_message(row),
            )
        rows.append(
            metraj_row_to_analyze(
                row,
                outcome,
                active_catalog,
                _ai_for_row(ai_result, row),
            )
        )

    warnings = list(result.warnings) + list(ai_result.warnings)

    return AnalyzeResponse(
        rows=rows,
        summary=analyze_summary(rows, result),
        ai=ai_summary_to_out(ai_result),
        warnings=warnings,
        ignored_columns=list(result.ignored_columns),
        sheet_name=result.sheet_name,
    )


def _run_ai(
    result,
    outcomes: dict[int, MatchOutcome],
    catalog: Catalog,
    provider: AiProvider | None,
) -> AiRunResult:
    """Yalnızca pending ve BOQ No taşıyan satırları AI'ya gönderir.

    Boş ``boq_no`` satırı AI'ya gitmez: sonuç istemcide izlenemez ve karar
    verilemez. Bu satırlar zaten ``invalid`` durumundadır (4.3 kuralı).
    """
    if provider is None:
        return AiRunResult(enabled=False, provider="none")

    pending_rows: list[tuple[str, str, MatchOutcome]] = []
    pending_seen = False
    for row in result.rows:
        outcome = outcomes.get(row.source_row)
        if outcome is None or outcome.status is not MatchStatus.PENDING:
            continue
        pending_seen = True
        if not row.boq_no or not row.description:
            continue
        pending_rows.append((row.boq_no, row.description, outcome))

    if not pending_rows:
        # Pending satır var ama kimliği yok → AI'ya gönderilemez.
        # Hiç pending yok → zaten iş yok. İkisi ayrı nedenle raporlanır.
        return AiRunResult(
            enabled=True,
            provider=getattr(provider, "name", "unknown"),
            skipped_reason=(
                AiSkipReason.MISSING_ROW_IDENTITY.value
                if pending_seen
                else AiSkipReason.NO_PENDING_ROWS.value
            ),
        )

    try:
        return evaluate_rows(pending_rows, catalog, provider)
    except Exception:  # noqa: BLE001 - AI analizi asla durdurmamalı
        # Beklenmeyen bir hata olsa bile analiz deterministik sonuçla döner.
        logger.exception("AI değerlendirmesi çalıştırılamadı; AI atlanıyor.")
        return AiRunResult(
            enabled=True,
            provider=getattr(provider, "name", "unknown"),
            warnings=(
                "AI değerlendirmesi çalıştırılamadı; satırlar kullanıcı onayı "
                "beklemeye devam ediyor.",
            ),
        )


def _ai_for_row(ai_result: AiRunResult, row) -> AiOut | None:
    """Satırın AI çıktısını döndürür; satır pending değilse ``None``."""
    if not row.boq_no:
        return None
    evaluation = ai_result.evaluations.get(row.boq_no)
    if evaluation is None:
        return None
    return ai_evaluation_to_out(evaluation)


def _invalid_message(row) -> str:
    reasons = ", ".join(issue.message for issue in row.issues) or "Veri okunamadı."
    return f"Satır geçersiz: {reasons}"


def calculate(request: CalculateRequest, *, catalog: Catalog | None = None) -> CalculateResponse:
    """Ham satırları ve kullanıcı kararlarını sunucuda yeniden değerlendirir.

    Güvenlik sırası
    ---------------
    1. Her satır için **sunucu** eşleştirmesi yapılır (istemciden gelen durum
       veya kod yok sayılır — şemada zaten yoktur).
    2. Kararlar satır sahipliğine göre doğrulanır: bilinmeyen veya başka
       satıra ait karar reddedilir.
    3. ``apply_decisions`` kodu katalogla ve açıklamayla çelişki yönünden
       doğrular.
    4. Hesap motoru yalnızca ``rule``/``ai-approved`` satırları hesaba alır.
    """
    outcome = run_calculation(request, catalog=catalog)
    result = outcome.result

    return CalculateResponse(
        groups=[
            group_to_out(group, outcome.source_rows) for group in result.groups
        ],
        skipped=[
            skipped_row_to_out(row, outcome.source_rows)
            for row in result.skipped
        ],
        summary=calculation_summary(result),
        warnings=list(outcome.warnings),
    )


@dataclass(frozen=True, slots=True)
class CalculationRun:
    """Bir hesaplama isteğinin doğrulanmış çekirdek çıktısı.

    API yanıtı ve raporlar **aynı** nesneyi kullanır; böylece rapor katmanı
    hesabı yeniden yapmaz ve iki çıktı birbirinden ayrışamaz.
    """

    result: CalculationResult
    source_rows: dict[str, int]
    descriptions: dict[str, str]
    warnings: tuple[str, ...]


def run_calculation(
    request: CalculateRequest, *, catalog: Catalog | None = None
) -> CalculationRun:
    """İsteği doğrular ve hesap motorunu çalıştırır (tek giriş noktası).

    Bu fonksiyon **hesap yapmaz**; yalnızca eşleştirme, karar doğrulama ve
    mevcut hesap motorunu çağırır. Raporlar da bu çıktıyı kullanır.
    """
    active_catalog = catalog or get_catalog()

    outcomes: dict[str, MatchOutcome] = {}
    rows: list[CalculationInputRow] = []

    # Fire oranı ve birim satır başına **bir kez** çözülür; eşleştirme ve
    # hesap aynı değerleri görür.
    waste_rates = {
        client_row.boq_no: _waste_rate(client_row.waste_percent)
        for client_row in request.rows
    }

    for client_row in request.rows:
        waste_rate = waste_rates[client_row.boq_no]
        outcomes[client_row.boq_no] = match_row(
            client_row.description,
            client_row.unit,
            waste_rate.fraction if waste_rate is not None else None,
            active_catalog,
        )

    decisions = _build_decisions(request, outcomes)
    finalised = apply_decisions(outcomes, decisions, active_catalog)

    for client_row in request.rows:
        outcome = finalised[client_row.boq_no]
        rows.append(
            CalculationInputRow.from_outcome(
                row_no=client_row.boq_no,
                description=client_row.description,
                quantity=client_row.quantity,
                unit=_parse_unit(client_row.unit) or client_row.unit,
                waste_rate=waste_rates[client_row.boq_no],
                outcome=outcome,
            )
        )

    result = calculate_purchase_list(rows, active_catalog)

    # Excel satır numaraları domain'e taşınmaz; API katmanında BOQ No ile
    # eşlenir. Böylece kullanıcı hem "BOQ-001" hem "2. satır" diyebilir.
    source_rows = {row.boq_no: row.source_row for row in request.rows}
    descriptions = {row.boq_no: row.description for row in request.rows}

    warnings: list[str] = []
    if result.partial_groups:
        warnings.append(
            f"{len(result.partial_groups)} grup kısmi hesaplandı "
            "(PARTIAL): eksik alanlar null döner, sıfır sayılmaz."
        )
    if not result.weight_complete and result.groups:
        warnings.append(
            "Toplam ağırlık kısmi: ağırlığı hesaplanamayan gruplar toplama "
            "dahil edilmedi."
        )

    return CalculationRun(
        result=result,
        source_rows=source_rows,
        descriptions=descriptions,
        warnings=tuple(warnings),
    )


def _parse_unit(value: str) -> Unit | None:
    try:
        return Unit(value.strip().lower())
    except ValueError:
        return None


def _waste_rate(percent: Decimal | None) -> WasteRate | None:
    """Yüzdeyi ``WasteRate``'a çevirir. ``None`` **sıfır değildir**."""
    return WasteRate.from_percent(percent) if percent is not None else None


def _build_decisions(
    request: CalculateRequest,
    outcomes: dict[str, MatchOutcome],
) -> list[Decision]:
    """İstemci kararlarını sunucu tarafında doğrulanmış ``Decision``'a çevirir.

    * Aynı BOQ No için iki karar → hata (sessizce biri seçilmez).
    * Kararlar yalnızca **istekte gönderilen** satırlara ait olabilir.
    * Onay kararı kod ister; kod doğruluğu ``apply_decisions``'ta denetlenir.
    """
    seen: set[str] = set()
    decisions: list[Decision] = []

    for item in request.decisions:
        if item.boq_no in seen:
            raise ApiError(
                422,
                "duplicate-decision",
                "Aynı satır için birden fazla karar gönderildi.",
                detail=f"BOQ No {item.boq_no!r} iki kez karar taşıyor.",
                suggestion="Her satır için tek karar gönderin.",
                issues=[
                    make_issue(
                        boq_no=item.boq_no,
                        message="Yinelenen karar.",
                        suggestion="Her satır için tek karar gönderin.",
                    )
                ],
            )
        seen.add(item.boq_no)

        if item.boq_no not in outcomes:
            raise ApiError(
                409,
                "unknown-row",
                "Karar, istekte bulunmayan bir satıra ait.",
                detail=f"BOQ No {item.boq_no!r} satır listesinde yok.",
                suggestion=(
                    "Kararları yalnızca analizde dönen satırlar için gönderin; "
                    "satır listesi ile kararlar aynı istekte taşınmalıdır."
                ),
                issues=[
                    make_issue(
                        boq_no=item.boq_no,
                        message="Satır istekte yok.",
                        suggestion="Kararı yalnızca gönderilen satırlar için verin.",
                    )
                ],
            )

        action = (
            DecisionAction.APPROVE
            if item.action == "approve"
            else DecisionAction.REJECT
        )
        decisions.append(
            Decision(
                row_no=item.boq_no,
                action=action,
                code=item.code,
                reason=item.reason[:_MAX_REASON],
            )
        )

    return decisions
