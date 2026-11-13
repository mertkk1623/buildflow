"""Domain ↔ API dönüşümü.

Tek yön ve tek yer: domain modelleri API'ye burada çevrilir, API modelleri
domaine burada çevrilir. Domain nesneleri değiştirilmez; API modeli domain'in
yerine geçmez.

Sayısal sözleşme
----------------
Domain ``Decimal`` taşır. API'de de ``Decimal`` kalır ve yalnızca JSON'a
yazılırken metne çevrilir (``PlainSerializer``). Ara adımda ``float`` yoktur —
tarayıcıda ``0.1`` hatası oluşmaz.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from app.api.schemas import (
    AiErrorOut,
    AiOut,
    AiSuggestionOut,
    AiSummaryOut,
    AnalyzeRow,
    AnalyzeSummary,
    CandidateOut,
    CalculationSummaryOut,
    FieldIssue,
    GroupOut,
    MatchOut,
    MissingFieldOut,
    SkippedRowOut,
    SourceRowOut,
)
from app.ai.models import AiErrorKind, AiRunResult, AiSuggestion
from app.domain.calculation import (
    CalculationResult,
    GroupCalculation,
    SourceRowCalculation,
)
from app.domain.catalog import Catalog
from app.domain.models import CatalogItem, MatchOutcome, MatchStatus, Unit
from app.excel.models import MetrajRow
from app.excel.reader import MetrajReadResult


def candidate_to_out(item: CatalogItem) -> CandidateOut:
    """Katalog kalemini kullanıcıya gösterilecek adaya çevirir."""
    return CandidateOut(
        code=item.code,
        family=item.family.value,
        family_label=item.family_label,
        size=item.size,
        grade=item.grade.value,
        coating=item.coating.value,
        label=item.describe,
        mass_kg_per_m=item.mass_kg_per_m,
        commercial_length_m=item.commercial_length_m,
    )


def match_to_out(outcome: MatchOutcome, catalog: Catalog | None = None) -> MatchOut:
    """Eşleştirme sonucunu API modeline çevirir.

    Aday kodlar her zaman katalogdan **zenginleştirilir**; istemci yalnızca
    kod listesi değil, seçim yapabilmek için ölçü/kalite/kaplama görür.
    """
    candidates: list[CandidateOut] = []
    if catalog is not None:
        for code in outcome.candidate_codes:
            item = catalog.get(code)
            if item is not None:
                candidates.append(candidate_to_out(item))

    status = outcome.status
    if status not in (
        MatchStatus.RULE,
        MatchStatus.PENDING,
        MatchStatus.EXCLUDED,
        MatchStatus.INVALID,
    ):
        # Analyze aşamasında onay/rejection kararı yoktur; savunmacı davranış.
        status = MatchStatus.PENDING

    return MatchOut(
        status=status.value,  # type: ignore[arg-type]
        matched_code=outcome.matched_code,
        candidate_codes=list(outcome.candidate_codes),
        candidates=candidates,
        exclusion_reason=(
            outcome.exclusion_reason.value if outcome.exclusion_reason else None
        ),
        message=outcome.message,
    )


def suggestion_to_out(suggestion: AiSuggestion) -> AiSuggestionOut:
    """Doğrulanmış AI önerisini API modeline çevirir."""
    return AiSuggestionOut(
        status=suggestion.status.value,
        suggested_code=suggestion.suggested_code,
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        candidate_codes=list(suggestion.candidate_codes),
    )


def ai_evaluation_to_out(evaluation) -> AiOut:
    """Satırın AI değerlendirmesini API modeline çevirir."""
    if evaluation.suggestion is not None:
        return AiOut(suggestion=suggestion_to_out(evaluation.suggestion))
    kind: AiErrorKind = evaluation.error or AiErrorKind.PROVIDER_ERROR
    return AiOut(
        error=AiErrorOut(code=kind.value, message=evaluation.error_message)
    )


#: ``skipped_reason`` kodlarının kullanıcıya dönük açıklamaları.
_AI_SKIP_MESSAGES: dict[str, str] = {
    "no-pending-rows": (
        "AI açık ancak bu dosyada onay bekleyen satır yok. Tüm satırlar "
        "deterministik kural ile eşleşti veya fire/birim/katalog nedeniyle "
        "kapsam dışı kaldı; bu yüzden hiçbir AI çağrısı yapılmadı."
    ),
    "missing-row-identity": (
        "Onay bekleyen satırlar var ancak BOQ No veya açıklama eksik olduğu "
        "için AI'ya gönderilemedi. Bu satırlar kullanıcı onayı bekliyor."
    ),
}


def ai_summary_to_out(result: AiRunResult) -> AiSummaryOut:
    """AI çalışmasının özeti."""
    return AiSummaryOut(
        enabled=result.enabled,
        provider=result.provider,
        evaluated_rows=result.evaluated_rows,
        suggested=result.suggested,
        ambiguous=result.ambiguous,
        no_match=result.no_match,
        errors=result.errors,
        skipped_reason=result.skipped_reason,
        skipped_message=(
            _AI_SKIP_MESSAGES.get(result.skipped_reason)
            if result.skipped_reason
            else None
        ),
    )


def metraj_row_to_analyze(
    row: MetrajRow,
    outcome: MatchOutcome,
    catalog: Catalog,
    ai: AiOut | None = None,
) -> AnalyzeRow:
    """Excel satırı + eşleştirme sonucu → analiz satırı.

    ``ai`` yalnızca pending satırlarda doludur ve **karar değildir**: bu
    fonksiyon ``outcome``'u değiştirmez, ``matched_code`` alanına dokunmaz.
    """
    issues = [
        FieldIssue(
            source_row=row.source_row,
            boq_no=row.boq_no,
            column=issue.column_label,
            code=issue.reason.value,
            message=issue.message,
            suggestion=issue.suggestion,
        )
        for issue in row.issues
    ]
    # Kapsam dışı birim (ör. ``adet``) hata değildir ama kullanıcı bilmeli.
    for scope in row.scope_issues:
        issues.append(
            FieldIssue(
                source_row=row.source_row,
                boq_no=row.boq_no,
                column=scope.column_label,
                code=scope.reason.value,
                message=scope.message,
                suggestion=scope.suggestion,
            )
        )

    return AnalyzeRow(
        source_row=row.source_row,
        boq_no=row.boq_no,
        description=row.description,
        quantity=row.quantity,
        unit=row.unit,
        waste_percent=row.waste_percent,
        status=outcome.status.value,  # type: ignore[arg-type]
        match=match_to_out(outcome, catalog),
        ai=ai,
        issues=issues,
        notes=list(row.notes),
    )


def analyze_summary(rows: list[AnalyzeRow], result: MetrajReadResult) -> AnalyzeSummary:
    counts = {"rule": 0, "pending": 0, "excluded": 0, "invalid": 0}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return AnalyzeSummary(
        total_rows=len(rows),
        valid_rows=result.valid_count,
        invalid_rows=result.invalid_count,
        blank_rows_skipped=result.blank_rows_skipped,
        rule=counts["rule"],
        pending=counts["pending"],
        excluded=counts["excluded"],
        invalid=counts["invalid"],
    )


# ---------------------------------------------------------------------------
# Hesaplama
# ---------------------------------------------------------------------------


def _unit_value(unit: Unit | None) -> str | None:
    return unit.value if unit is not None else None


def _conversion_labels(source: SourceRowCalculation) -> list[str]:
    return [
        f"{step.label}: {step.expression} = {_format_decimal(step.result)}"
        for step in source.conversion_steps
    ]


def _format_decimal(value: Decimal) -> str:
    """Ara hesabı gösterim için yuvarlamaz; yalnızca biçimlendirir."""
    text = format(value, "f")
    if "." in text:
        trimmed = text.rstrip("0").rstrip(".")
        return trimmed or "0"
    return text


def source_row_to_out(
    source: SourceRowCalculation,
    source_rows: Mapping[str, int] | None = None,
) -> SourceRowOut:
    fire = source.fire_quantity
    return SourceRowOut(
        source_row=None if source_rows is None else source_rows.get(source.row_no),
        boq_no=source.row_no,
        description=source.description,
        source_quantity=source.source_quantity,
        source_unit=_unit_value(source.source_unit),
        net_metres=source.net_metres,
        waste_percent=source.waste_percent,
        gross_metres=source.gross_metres,
        gross_quantity=source.gross_quantity,
        fire_quantity=fire,
        waste_source=source.waste_source.value,
        conversion_steps=_conversion_labels(source),
    )


def group_to_out(
    group: GroupCalculation,
    source_rows: Mapping[str, int] | None = None,
) -> GroupOut:
    return GroupOut(
        code=group.code,
        family=group.family.value,
        family_label=group.family_label,
        size=group.size,
        grade=group.grade.value,
        coating=group.coating.value,
        product_label=group.product_label,
        status=group.status.value,
        missing_fields=[field.value for field in group.missing_fields],
        missing=[
            MissingFieldOut(
                field=item.field.value,
                message=item.message,
                boq_no=item.row_no,
                source_row=(
                    None
                    if source_rows is None or item.row_no is None
                    else source_rows.get(item.row_no)
                ),
            )
            for item in group.missing
        ],
        mass_kg_per_m=group.mass_kg_per_m,
        commercial_length_m=group.commercial_length_m,
        bar_count=group.bar_count,
        total_gross_metres=group.total_gross_metres,
        order_length_m=group.order_length_m,
        rounding_surplus_m=group.rounding_surplus_m,
        weight_kg=group.weight_kg,
        weight_label=group.weight_label,
        weight_note=group.weight_note,
        merged=group.merged,
        source_boq_nos=list(group.source_row_numbers),
        source_rows=(
            []
            if source_rows is None
            else [
                row
                for row in (
                    source_rows.get(row_no)
                    for row_no in group.source_row_numbers
                )
                if row is not None
            ]
        ),
        sources=[
            source_row_to_out(source, source_rows) for source in group.sources
        ],
        notes=list(group.notes),
    )


def skipped_row_to_out(
    row,
    source_rows: Mapping[str, int] | None = None,
) -> SkippedRowOut:
    return SkippedRowOut(
        source_row=None if source_rows is None else source_rows.get(row.row_no),
        boq_no=row.row_no,
        status=row.reason.value,
        match_status=row.match_status.value if row.match_status else None,
        matched_code=row.matched_code,
        message=row.message,
        exclusion_reason=(
            row.exclusion_reason.value if row.exclusion_reason else None
        ),
        exclusion_reason_label=row.exclusion_label,
    )


def calculation_summary(result: CalculationResult) -> CalculationSummaryOut:
    order_total = _sum_known(group.order_length_m for group in result.groups)
    return CalculationSummaryOut(
        input_rows=result.input_row_count,
        calculated_rows=result.calculated_row_count,
        skipped_rows=result.skipped_count,
        groups=result.group_count,
        merged_groups=result.merged_group_count,
        merges=result.merge_count,
        full_groups=len(result.full_groups),
        partial_groups=len(result.partial_groups),
        total_order_length_m=order_total,
        known_weight_kg=result.known_weight_kg,
        weight_complete=result.weight_complete,
    )


def _sum_known(values) -> Decimal | None:
    """Bilinen değerlerin toplamı; hiçbiri yoksa ``None``.

    Kısmi toplam, tam toplam gibi sunulmaz: en az bir değer varsa toplanır ve
    ``None`` olan alanlar sessizce sıfır sayılmaz — bu yüzden çağıran taraf
    ``weight_complete``/``missing_fields`` ile birlikte okumalıdır.
    """
    total: Decimal | None = None
    for value in values:
        if value is None:
            continue
        total = value if total is None else total + value
    return total
