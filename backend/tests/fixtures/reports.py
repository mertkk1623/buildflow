"""Rapor testleri için ortak yardımcılar.

Test verisi **gerçek** hesap motorundan geçer: rapor katmanına sahte
``CalculationResult`` verilmez. Böylece "rapor, hesapla birebir tutarlı"
testi anlamlı olur.

Üç senaryo vardır:

1. :func:`demo_run` — demo metrajın kilitli sonucu (8 grup, 966 m,
   18.005,820 kg, tümü FULL).
2. :func:`partial_run` — ticari boyu bilinmeyen tek satır (PARTIAL).
3. :func:`empty_run` — hiç onaylanmış satır yok (rapor üretilmemeli).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from openpyxl import load_workbook

from app.api.schemas import CalculateRequest, ClientDecision, ClientRow
from app.api.service import CalculationRun, run_calculation
from app.domain.calculation import (
    CalculationInputRow,
    CalculationResult,
    WasteRate,
    calculate_purchase_list,
)
from app.domain.catalog import Catalog, get_catalog
from app.domain.matching import match_row
from app.reports.models import Report, build_report
from tests.fixtures.demo_boq import DEMO_ROWS, PREDEFINED_DECISIONS

#: Testlerde sabit rapor zamanı — dosya adı ve altbilgi deterministik olur.
FIXED_NOW = datetime(2026, 11, 13, 14, 5)

#: Demo senaryosunun kilitli değerleri (Aşama 4.2/4.3 ile birebir).
EXPECTED_GROUPS = 8
EXPECTED_MERGES = 5
EXPECTED_ORDER_LENGTH_M = Decimal("966")
EXPECTED_WEIGHT_KG = Decimal("18005.820")


def demo_request() -> CalculateRequest:
    """Demo metrajın ``/api/calculate`` isteği (18 satır + 4 karar)."""
    rows = [
        ClientRow(
            source_row=index + 2,
            boq_no=row.no,
            description=row.description,
            quantity=row.quantity,
            unit=row.unit,
            waste_percent=(
                row.waste_rate * Decimal(100)
                if row.waste_rate is not None
                else None
            ),
        )
        for index, row in enumerate(DEMO_ROWS)
    ]
    decisions = [
        ClientDecision(
            boq_no=decision.row_no,
            action=decision.action.value,
            code=decision.code,
            reason=decision.reason,
        )
        for decision in PREDEFINED_DECISIONS
    ]
    return CalculateRequest(rows=rows, decisions=decisions)


def demo_run() -> CalculationRun:
    """Demo senaryosunun doğrulanmış çekirdek çıktısı."""
    return run_calculation(demo_request())


def demo_report() -> Report:
    """Demo senaryosunun raporu (sabit zaman)."""
    return build_run(demo_run())


def build_run(run: CalculationRun) -> Report:
    from app.reports.service import build_run_report

    return build_run_report(run, generated_at=FIXED_NOW)


# ---------------------------------------------------------------------------
# PARTIAL senaryoları
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PartialCase:
    """Tek satırlık PARTIAL hesabı ve ondan türeyen rapor."""

    result: CalculationResult
    report: Report


def partial_missing_commercial_length() -> PartialCase:
    """Ticari boy bilinmiyor → sipariş/artan/ağırlık **None**.

    Fire tanımlı olduğu için brüt miktar hesaplanabilir; ancak ticari boy
    olmadığı için sipariş miktarı yuvarlanamaz. Bu ayrım test edilir.
    """
    catalog = get_catalog()
    outcome = match_row(
        "BOX 100×100×4 S235 siyah", "m", Decimal("0.05"), catalog
    )
    assert outcome.matched_code is not None
    row = CalculationInputRow.from_outcome(
        row_no="BOQ-100",
        description="BOX 100×100×4 S235 siyah",
        quantity=Decimal("60"),
        unit="m",
        waste_rate=WasteRate.from_percent(Decimal("5")),
        outcome=outcome,
    )
    result = calculate_purchase_list(
        [row],
        catalog,
        commercial_length_overrides={outcome.matched_code: None},
    )
    return PartialCase(result=result, report=_report_of(result))


def partial_missing_mass() -> PartialCase:
    """Birim kütle bilinmiyor → metre dönüşümü ve ağırlık **None**."""
    catalog = get_catalog()
    outcome = match_row(
        "BOX 100×100×4 S235 siyah", "kg", Decimal("0.05"), catalog
    )
    assert outcome.matched_code is not None
    row = CalculationInputRow.from_outcome(
        row_no="BOQ-101",
        description="BOX 100×100×4 S235 siyah",
        quantity=Decimal("500"),
        unit="kg",
        waste_rate=WasteRate.from_percent(Decimal("5")),
        outcome=outcome,
    )
    result = calculate_purchase_list(
        [row], catalog, mass_overrides={outcome.matched_code: None}
    )
    return PartialCase(result=result, report=_report_of(result))


def partial_missing_waste() -> PartialCase:
    """Fire tanımsız → brüt/sipariş/ağırlık **hiçbiri** üretilemez.

    Bu, PARTIAL'in en ağır hâlidir: raporda brüt, sipariş, artan ve ağırlık
    alanlarının dördü de boş kalmalı; hiçbiri ``0`` görünmemelidir.
    """
    catalog = get_catalog()
    outcome = match_row(
        "BOX 100×100×4 S235 siyah", "m", Decimal("0.05"), catalog
    )
    assert outcome.matched_code is not None
    row = CalculationInputRow.from_outcome(
        row_no="BOQ-102",
        description="BOX 100×100×4 S235 siyah",
        quantity=Decimal("60"),
        unit="m",
        # Eşleştirme fire oranını gördü (satır hesaba girdi) ama miktar
        # hesabına fire **verilmedi**: domain bunu eksik veri sayar.
        waste_rate=None,
        outcome=outcome,
    )
    result = calculate_purchase_list([row], catalog)
    return PartialCase(result=result, report=_report_of(result))


def empty_result() -> CalculationResult:
    """Hiç grup üretmeyen hesap (tüm satırlar hesaba alınmadı)."""
    return CalculationResult(groups=(), skipped=(), input_row_count=0)


def _report_of(result: CalculationResult) -> Report:
    return build_report(result, generated_at=FIXED_NOW)


# ---------------------------------------------------------------------------
# Excel yardımcıları
# ---------------------------------------------------------------------------


def excel_sheets(payload: bytes) -> dict[str, Any]:
    """Baytlardan ``{sayfa adı: worksheet}`` üretir."""
    from io import BytesIO

    workbook = load_workbook(BytesIO(payload))
    return {name: workbook[name] for name in workbook.sheetnames}


def sheet_rows(sheet: Any) -> list[tuple[Any, ...]]:
    """Sayfadaki tüm satırları değer olarak döndürür."""
    return list(sheet.iter_rows(values_only=True))


def find_row(sheet: Any, code: str) -> tuple[Any, ...]:
    """Malzeme kodu sütununda ``code`` içeren satırı döndürür."""
    for row in sheet.iter_rows(values_only=True):
        if row and row[0] == code:
            return row
    raise AssertionError(f"{code!r} satırı bulunamadı")


def find_label_value(sheet: Any, label: str) -> Any:
    """``A`` sütununda etiketi bulup ``B`` sütunundaki değeri döndürür."""
    for row in sheet.iter_rows(values_only=True):
        if row and row[0] == label:
            return row[1] if len(row) > 1 else None
    raise AssertionError(f"{label!r} etiketi bulunamadı")


def header_index(sheet: Any, title: str) -> int:
    """Başlık satırının 1 tabanlı numarasını döndürür."""
    for index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if row and row[0] == title:
            return index
    raise AssertionError(f"{title!r} başlığı bulunamadı")


def column_names(sheet: Any, header_row: int) -> list[str]:
    """Başlık satırının sütun adları."""
    row = list(sheet.iter_rows(min_row=header_row, max_row=header_row, values_only=True))[0]
    return [str(value) for value in row if value is not None]


def catalog() -> Catalog:
    return get_catalog()
