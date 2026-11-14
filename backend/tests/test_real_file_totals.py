"""Gerçek demo dosyası üzerinde **bağımsız** hesap doğrulaması.

Neden ayrı dosya
----------------
Mevcut ``TestDemoScenario`` senaryosu ``PREDEFINED_DECISIONS`` ile dört
``pending`` satırı **onaylar**; bu yüzden 13 satır hesaplanır. Canlı akışta
kullanıcı henüz karar vermemiştir: dosya yüklendiğinde 4 satır onay bekler ve
hesaba **10 satır** girer.

Bu testler o gerçek durumu kilitler. Beklenen değerler motordan okunmaz;
``test_calculated_values_match_hand_arithmetic`` içinde katalogdaki kg/m ve
ticari boy değerleriyle **Decimal** üzerinden elle yeniden hesaplanır. Böylece
motor ile test aynı hatayı paylaşamaz.

Varsayımlar (açık)
------------------
* Yalnızca ``catalog.json`` değerleri kullanılır; hiçbir değer uydurulmaz.
* Aynı ölçüde farklı kaplama (siyah/galvaniz) ayrı katalog kodu → ayrı grup.
* Fire yüzdesi yalnızca BOQ satırından gelir (``default_waste`` tüm kalemlerde
  ``null``); fire boş olan satır kapsam dışıdır, varsayım yapılmaz.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.api.schemas import CalculateRequest, ClientRow
from app.api.service import analyze_file, run_calculation

D = Decimal

#: Depo kökündeki gerçek örnek dosya.
DEMO_FILE = Path(__file__).resolve().parents[2] / "templates" / "ornek_metraj.xlsx"

#: Katalogdaki teorik kg/m ve ticari boy (kaynaktan birebir).
#: Elle hesapta kullanılır; motordan okunmaz.
REFERENCE = {
    "BOX-100-4-S235-B": (D("11.70"), D("6")),
    "BOX-100-4-S235-G": (D("11.70"), D("6")),
    "BOX-150-100-5-S235-B": (D("18.30"), D("6")),
    "HEA-200-S235": (D("42.30"), D("12")),
    "UPN-160-S235": (D("18.80"), D("12")),
    "FLAT-40x5-S235-B": (D("1.570"), D("6")),
    "IPE-240-S355": (D("30.70"), D("12")),
}

#: (BOQ, katalog kodu, miktar, birim, fire%) — kaynak Excel'den birebir.
EXPECTED_ROWS = [
    ("BOQ-001", "BOX-100-4-S235-B", "96", "m", "5"),
    ("BOQ-002", "BOX-100-4-S235-G", "48", "m", "5"),
    ("BOQ-005", "HEA-200-S235", "132", "m", "4"),
    ("BOQ-007", "UPN-160-S235", "54", "m", "4"),
    ("BOQ-008", "FLAT-40x5-S235-B", "210", "kg", "5"),
    ("BOQ-010", "UPN-160-S235", "0.32", "t", "4"),
    ("BOQ-011", "BOX-150-100-5-S235-B", "60", "m", "5"),
    ("BOQ-013", "BOX-100-4-S235-B", "84", "m", "5"),
    ("BOQ-016", "FLAT-40x5-S235-B", "150", "kg", "5"),
    ("BOQ-017", "IPE-240-S355", "0.45", "t", "3"),
]

#: Bu dosyada AI'nın değerlendirmesi gereken satırlar (onay bekleyen).
PENDING = {"BOQ-003", "BOQ-004", "BOQ-006", "BOQ-009"}


def _metres(quantity: Decimal, unit: str, kg_per_m: Decimal) -> Decimal:
    """Kaynak miktarı metreye çevirir (motoru kullanmadan)."""
    if unit == "m":
        return quantity
    if unit == "kg":
        return quantity / kg_per_m
    if unit == "t":
        return quantity * D("1000") / kg_per_m
    raise AssertionError(f"beklenmeyen birim: {unit}")


def _ceil_div(value: Decimal, divisor: Decimal) -> int:
    quotient = value / divisor
    whole = int(quotient)
    return whole if quotient == whole else whole + 1


@pytest.fixture(scope="module")
def demo_file_exists() -> None:
    if not DEMO_FILE.is_file():  # pragma: no cover - depo bütünlüğü
        pytest.skip(f"örnek dosya yok: {DEMO_FILE}")


@pytest.fixture(scope="module")
def run(demo_file_exists):
    """Dosyayı okur ve **karar vermeden** hesaplar (canlı akışın aynısı)."""
    analysis = analyze_file(DEMO_FILE)
    request = CalculateRequest(
        rows=[
            ClientRow(
                source_row=row.source_row,
                boq_no=row.boq_no,
                description=row.description,
                quantity=row.quantity,
                unit=row.unit,
                waste_percent=row.waste_percent,
            )
            for row in analysis.rows
            if row.boq_no
        ]
    )
    return run_calculation(request)


def test_row_distribution_is_locked(run) -> None:
    """18 girdi → 10 hesaplanan, 8 hesap dışı, 7 satın alma kalemi."""
    assert run.result.input_row_count == 18
    assert run.result.calculated_row_count == 10
    assert run.result.skipped_count == 8
    assert run.result.group_count == 7


def test_pending_rows_are_the_four_ambiguous_ones(run) -> None:
    pending = {
        item.row_no
        for item in run.result.skipped
        if item.reason.value == "pending"
    }

    assert pending == PENDING


def test_total_order_length_is_810_metres(run) -> None:
    """PDF'teki 810 m toplamı — bağımsız toplamla karşılaştırılır."""
    total = sum(group.order_length_m for group in run.result.groups)

    assert total == D("810")


def test_total_weight_is_12879_420_kg(run) -> None:
    """PDF'teki 12.879,420 kg toplamı."""
    assert run.result.known_weight_kg == D("12879.420")
    assert run.result.weight_complete


def test_calculated_values_match_hand_arithmetic(run) -> None:
    """Her satır elle hesaplanır; motorun ürettiği değerlerle karşılaştırılır.

    Bu test motoru **referans almaz**: beklenen net/brüt/sipariş/ağırlık
    değerleri katalogdaki kg/m ve boy ile burada yeniden üretilir.
    """
    # 1) Satır bazında net → brüt, kod bazında topla.
    gross_by_code: dict[str, Decimal] = {}
    for _, code, quantity, unit, waste in EXPECTED_ROWS:
        kg_per_m, _ = REFERENCE[code]
        net = _metres(D(quantity), unit, kg_per_m)
        gross = net * (D("1") + D(waste) / D("100"))
        gross_by_code[code] = gross_by_code.get(code, D("0")) + gross

    # 2) Kod bazında ticari boya yuvarla (tek yuvarlama kuralı).
    expected_order: dict[str, int] = {}
    expected_weight: dict[str, Decimal] = {}
    for code, gross in gross_by_code.items():
        kg_per_m, length = REFERENCE[code]
        bars = _ceil_div(gross, length)
        expected_order[code] = bars
        expected_weight[code] = length * bars * kg_per_m

    # 3) Motorla karşılaştır.
    actual = {group.code: group for group in run.result.groups}
    assert set(actual) == set(expected_order)

    for code, bars in expected_order.items():
        group = actual[code]
        _, length = REFERENCE[code]
        assert group.bar_count == bars, f"{code}: adet"
        assert group.order_length_m == length * bars, f"{code}: sipariş boyu"
        assert group.weight_kg == expected_weight[code], f"{code}: ağırlık"

    # 4) Toplamlar da elle toplamla aynı olmalı.
    assert sum(g.order_length_m for g in run.result.groups) == sum(
        REFERENCE[code][1] * bars for code, bars in expected_order.items()
    )
    assert run.result.known_weight_kg == sum(expected_weight.values())


def test_merged_groups_match_source_rows(run) -> None:
    """Birleşme yalnızca aynı katalog kodunda olur."""
    merged = {
        group.code: group.source_row_numbers
        for group in run.result.groups
        if group.merged
    }

    assert merged == {
        "BOX-100-4-S235-B": ("BOQ-001", "BOQ-013"),
        "UPN-160-S235": ("BOQ-007", "BOQ-010"),
        "FLAT-40x5-S235-B": ("BOQ-008", "BOQ-016"),
    }


def test_no_row_is_automatically_approved(run) -> None:
    """Pending satırların hiçbiri kendiliğinden ``matched_code`` almaz."""
    for item in run.result.skipped:
        if item.reason.value == "pending":
            assert item.matched_code is None
