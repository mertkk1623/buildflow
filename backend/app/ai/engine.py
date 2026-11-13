"""AI eşleştirme motoru — orkestrasyon.

Akış
----
1. Yalnızca ``pending`` satırlar seçilir. ``rule`` satırları için AI **hiç**
   çağrılmaz (ağ trafiği yok, maliyet yok).
2. Her pending satır için adaylar katalogdan okunur; AI'ya yalnızca tanıma
   bilgisi gider (açıklama + dört özellik + aday özellikleri).
3. Sağlayıcı yanıtı :func:`app.ai.validate.parse_suggestion` ile doğrulanır.
4. Doğrulama başarısızsa satır için ``AiEvaluation(error=...)`` döner ve
   **öneri kullanılmaz**; satır ``pending`` kalır.
5. Sonuçlar yalnızca sunucu içinde taşınır; hiçbir durumda
   ``matched_code`` alanına yazılmaz.

Hata izolasyonu
---------------
Tek bir satırın AI hatası diğer satırları veya genel analizi durdurmaz.
Sağlayıcı tümden erişilemezse her satır aynı hatayı taşır ve kullanıcıya tek
bir uyarı gösterilir.
"""

from __future__ import annotations

import logging

from app.ai.models import (
    AiCandidate,
    AiErrorKind,
    AiEvaluation,
    AiMatchRequest,
    AiRunResult,
    AiStatus,
    AiSuggestion,
)
from app.ai.prompt import SYSTEM_PROMPT, build_user_prompt
from app.ai.providers import AiProvider, AiProviderError, NoneProvider
from app.ai.validate import AiValidationError, parse_suggestion
from app.domain.catalog import Catalog
from app.domain.models import MatchOutcome, MatchStatus

logger = logging.getLogger(__name__)

#: Tek bir analizde AI'ya gönderilecek en fazla satır. Kaza veya kötüye
#: kullanımda maliyetin kontrolden çıkmasını engeller.
MAX_ROWS_PER_REQUEST = 100


def build_request(boq_no: str, description: str, outcome: MatchOutcome, catalog: Catalog) -> AiMatchRequest:
    """``pending`` satırı AI isteğine çevirir.

    Aday kodları yeniden süzülür: ``outcome`` içinde katalogda bulunmayan bir
    kod olsa bile AI'ya gönderilmez. Böylece AI hiçbir zaman katalog dışı kod
    görmez (görse bile doğrulama reddeder).
    """
    candidates: list[AiCandidate] = []
    for code in outcome.candidate_codes:
        item = catalog.get(code)
        if item is None:
            continue
        candidates.append(
            AiCandidate(
                code=item.code,
                family=item.family.value,
                family_label=item.family_label,
                size=item.size,
                grade=item.grade.value,
                coating=item.coating.value,
                production_standard=item.production_standard,
                manufacturing=item.manufacturing.value,
            )
        )

    return AiMatchRequest(
        boq_no=boq_no,
        description=description,
        attributes=outcome.attributes,
        candidates=tuple(candidates),
    )


def evaluate_rows(
    rows: list[tuple[str, str, MatchOutcome]],
    catalog: Catalog,
    provider: AiProvider | None = None,
) -> AiRunResult:
    """Bekleyen satırları AI'ya gönderir ve doğrulanmış sonuçları döndürür.

    Parameters
    ----------
    rows:
        ``(boq_no, description, outcome)`` üçlüleri. ``outcome.status``
        ``pending`` değilse satır **atlanır** — deterministik sonuç varsa AI
        devreye girmez.
    provider:
        ``None`` ise :class:`NoneProvider` kullanılır (AI kapalı).
    """
    active = provider or NoneProvider()
    name = getattr(active, "name", "unknown")

    # ``enabled`` yapılandırmayı anlatır, "kaç satır işlendi"yi değil: AI açık
    # ama dosyada pending satır yoksa yanıt yine ``enabled=True`` olmalıdır.
    enabled = not isinstance(active, NoneProvider)

    pending = [
        (boq_no, description, outcome)
        for boq_no, description, outcome in rows
        if outcome.status is MatchStatus.PENDING
    ]

    if not enabled or not pending:
        return AiRunResult(enabled=enabled, provider=name)

    evaluations: dict[str, AiEvaluation] = {}
    warnings: list[str] = []

    for index, (boq_no, description, outcome) in enumerate(pending):
        if index >= MAX_ROWS_PER_REQUEST:
            warnings.append(
                f"AI değerlendirmesi ilk {MAX_ROWS_PER_REQUEST} bekleyen satırla "
                "sınırlandırıldı; kalan satırlar kullanıcı onayı bekler."
            )
            break

        request = build_request(boq_no, description, outcome, catalog)

        # Aday yoksa AI'ya sormak anlamsız: sonuç zaten "eşleşme yok".
        if not request.candidates:
            evaluations[boq_no] = AiEvaluation(
                boq_no=boq_no,
                suggestion=AiSuggestion(
                    status=AiStatus.NO_MATCH,
                    suggested_code=None,
                    confidence=None,
                    reason="Katalogda değerlendirilecek aday yok.",
                    candidate_codes=(),
                ),
            )
            continue

        try:
            raw = active.suggest(SYSTEM_PROMPT, build_user_prompt(request))
        except AiProviderError as exc:
            logger.warning(
                "AI sağlayıcı hatası (%s) — satır %s: %s",
                exc.kind.value,
                boq_no,
                exc.detail,
            )
            evaluations[boq_no] = AiEvaluation(
                boq_no=boq_no, error=exc.kind, error_detail=exc.detail
            )
            continue
        except Exception as exc:  # noqa: BLE001 - AI analizi asla durdurmamalı
            # Sağlayıcı beklenmeyen bir hata fırlatırsa (ör. adaptör hatası)
            # kullanıcıya yalnızca güvenli kod döner; deterministik sonuç
            # etkilenmez.
            logger.exception("AI sağlayıcısında beklenmeyen hata — satır %s", boq_no)
            evaluations[boq_no] = AiEvaluation(
                boq_no=boq_no,
                error=AiErrorKind.PROVIDER_ERROR,
                error_detail=type(exc).__name__,
            )
            continue

        try:
            suggestion = parse_suggestion(raw, candidates=request.candidate_codes)
        except AiValidationError as exc:
            logger.warning(
                "AI yanıtı reddedildi (%s) — satır %s: %s",
                exc.kind.value,
                boq_no,
                exc.detail,
            )
            evaluations[boq_no] = AiEvaluation(
                boq_no=boq_no, error=exc.kind, error_detail=exc.detail
            )
            continue

        evaluations[boq_no] = AiEvaluation(boq_no=boq_no, suggestion=suggestion)

    if any(not evaluation.ok for evaluation in evaluations.values()):
        warnings.append(
            "Bazı satırlar için AI önerisi kullanılamadı; bu satırlar kullanıcı "
            "onayı beklemeye devam ediyor."
        )

    return AiRunResult(
        enabled=True,
        provider=name,
        evaluations=evaluations,
        warnings=tuple(warnings),
    )
