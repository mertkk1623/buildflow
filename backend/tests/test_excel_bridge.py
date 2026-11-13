"""Excel → domain köprüsü ve uçtan uca entegrasyon testleri — Aşama 4.3.

Amaç: Excel okumasının **mevcut** eşleştirme ve hesaplama motoruyla
uyumluluğunu kanıtlamak. Köprü kendi başına eşleştirme yapmaz; durum ve kod
her zaman ``match_row`` / ``apply_decisions`` çıktısından gelir.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.calculation import (
    CalculationInputRow,
    SkipReason,
    WasteRate,
    calculate_purchase_list,
)
from app.domain.catalog import load_catalog
from app.domain.decisions import apply_decisions
from app.domain.models import (
    ExclusionReason,
    InvalidReason,
    MatchStatus,
)
from app.excel import read_metraj, to_domain
from tests.fixtures.demo_boq import DEMO_ROWS, PREDEFINED_DECISIONS
from tests.fixtures.excel_files import build_demo_workbook, write_workbook


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def demo_batch(tmp_path_factory: pytest.TempPathFactory):
    directory = tmp_path_factory.mktemp("demo_bridge")
    return to_domain(read_metraj(build_demo_workbook(directory / "demo.xlsx")))


# ---------------------------------------------------------------------------
# Kaynak satır → domain satır
# ---------------------------------------------------------------------------


class TestBridgeBasics:
    def test_all_demo_rows_bridge(self, demo_batch) -> None:
        assert len(demo_batch.sources) == 18
        assert demo_batch.rejected == ()

    def test_source_row_and_boq_no_kept(self, demo_batch) -> None:
        first = demo_batch.sources[0]
        assert first.source_row == 2
        assert first.boq_no == "BOQ-001"

    def test_waste_percent_is_converted_to_rate(self, demo_batch) -> None:
        """Excel ``Fire (%)`` = 5 → domain oranı 0,05."""
        first = demo_batch.sources[0]
        assert first.waste_percent == Decimal("5")
        assert first.waste_rate == WasteRate.from_percent("5")
        assert first.to_match_waste() == Decimal("0.05")

    def test_missing_waste_stays_none(self, demo_batch) -> None:
        row = next(source for source in demo_batch.sources if source.boq_no == "BOQ-012")
        assert row.waste_percent is None
        assert row.waste_rate is None
        assert row.to_match_waste() is None

    def test_bridge_does_not_match(self, demo_batch) -> None:
        """Köprü satırı eşleştirmez; kod/status taşımaz."""
        for source in demo_batch.sources:
            assert not hasattr(source, "matched_code")
            assert not hasattr(source, "status")

    def test_quantity_is_decimal(self, demo_batch) -> None:
        for source in demo_batch.sources:
            assert isinstance(source.quantity, Decimal)


# ---------------------------------------------------------------------------
# Eşleştirme çıktısı 4.1 ile aynı olmalı
# ---------------------------------------------------------------------------


class TestMatchingParity:
    def test_demo_matching_matches_fixture(self, demo_batch, catalog) -> None:
        """Excel'den gelen satırlar fixture ile aynı durum/kodu vermeli."""
        from tests.fixtures.demo_boq import EXPECTED_DETERMINISTIC

        for source in demo_batch.sources:
            outcome = source.match(catalog)
            expected_status, expected_code = EXPECTED_DETERMINISTIC[source.boq_no]
            assert outcome.status.value == expected_status, source.boq_no
            assert outcome.matched_code == expected_code, source.boq_no

    def test_excluded_units_are_not_invalid(self, demo_batch, catalog) -> None:
        source = next(item for item in demo_batch.sources if item.boq_no == "BOQ-014")
        assert source.unit_text == "adet"
        outcome = source.match(catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.UNIT

    def test_missing_waste_gives_waste_exclusion(self, demo_batch, catalog) -> None:
        source = next(item for item in demo_batch.sources if item.boq_no == "BOQ-012")
        outcome = source.match(catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.WASTE

    def test_calculation_row_uses_outcome_status(self, demo_batch, catalog) -> None:
        source = demo_batch.sources[0]
        outcome = source.match(catalog)
        row = source.to_calculation_row(outcome)
        assert isinstance(row, CalculationInputRow)
        assert row.status is outcome.status
        assert row.matched_code == outcome.matched_code
        assert row.row_no == source.boq_no


# ---------------------------------------------------------------------------
# Uçtan uca: Excel → eşleştirme → kararlar → hesaplama
# ---------------------------------------------------------------------------


class TestEndToEnd:
    @pytest.fixture(scope="class")
    @classmethod
    def calculation(cls, tmp_path_factory: pytest.TempPathFactory, catalog):
        directory = tmp_path_factory.mktemp("demo_calc")
        result = read_metraj(build_demo_workbook(directory / "demo.xlsx"))
        batch = to_domain(result)

        outcomes = {source.boq_no: source.match(catalog) for source in batch.sources}
        finalised = apply_decisions(outcomes, list(PREDEFINED_DECISIONS), catalog)

        rows = [
            source.to_calculation_row(finalised[source.boq_no])
            for source in batch.sources
        ]
        return calculate_purchase_list(rows, catalog)

    def test_same_shape_as_python_demo(self, calculation) -> None:
        assert calculation.input_row_count == 18
        assert calculation.calculated_row_count == 13
        assert calculation.group_count == 8
        assert calculation.merge_count == 5

    def test_skipped_rows_are_the_same_five(self, calculation) -> None:
        skipped = {item.row_no: item.reason for item in calculation.skipped}
        assert skipped == {
            "BOQ-009": SkipReason.PENDING,
            "BOQ-012": SkipReason.EXCLUDED,
            "BOQ-014": SkipReason.EXCLUDED,
            "BOQ-015": SkipReason.EXCLUDED,
            "BOQ-018": SkipReason.REJECTED,
        }

    def test_order_total_matches_locked_demo(self, calculation) -> None:
        assert calculation.known_weight_kg == Decimal("18005.820000")

    def test_all_groups_are_full(self, calculation) -> None:
        assert len(calculation.full_groups) == 8
        assert calculation.partial_groups == ()

    def test_box_100_group_is_the_same(self, calculation) -> None:
        group = calculation.group("BOX-100-4-S235-B")
        assert group.source_row_numbers == ("BOQ-001", "BOQ-013")
        assert group.order_length_m == Decimal("192.00000")
        assert group.weight_kg == Decimal("2246.400000")


# ---------------------------------------------------------------------------
# Karışık dosya hesaba girmez
# ---------------------------------------------------------------------------


class TestInvalidRowsNeverReachCalculation:
    def test_invalid_rows_are_excluded_from_sources(self, tmp_path: Path) -> None:
        path = write_workbook(
            tmp_path / "karisik.xlsx",
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-002", None, 48, "m", 5],
                ["BOQ-003", "IPE 200 S235 siyah", -1, "kg", 3],
            ],
        )
        batch = to_domain(read_metraj(path))
        assert [source.boq_no for source in batch.sources] == ["BOQ-001"]
        reasons = {rejected.boq_no: rejected.reasons for rejected in batch.rejected}
        assert InvalidReason.MISSING_DESCRIPTION in reasons["BOQ-002"]
        assert InvalidReason.NON_POSITIVE_QUANTITY in reasons["BOQ-003"]

    def test_rejected_rows_do_not_break_calculation(
        self, tmp_path: Path, catalog
    ) -> None:
        path = write_workbook(
            tmp_path / "karisik2.xlsx",
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-002", None, 48, "m", 5],
                ["BOQ-003", "UPN 160 S235 siyah", 54, "m", 4],
            ],
        )
        batch = to_domain(read_metraj(path))
        rows = [
            source.to_calculation_row(source.match(catalog))
            for source in batch.sources
        ]
        result = calculate_purchase_list(rows, catalog)

        # Hatalı satır motora hiç ulaşmaz: 3 satırlık dosyada 2 geçerli satır.
        assert result.input_row_count == 2
        assert result.group_count == 2
        assert result.skipped == ()
        assert {group.code for group in result.groups} == {
            "BOX-100-4-S235-B",
            "UPN-160-S235",
        }
        # Kayıp değil: hatalı satır ayrı raporda, kaynak satır numarasıyla.
        assert [rejected.boq_no for rejected in batch.rejected] == ["BOQ-002"]
        assert batch.rejected[0].source_row == 3

    def test_invalid_match_status_is_skipped(self, catalog) -> None:
        """``invalid`` durumu hesaplama motorunda atlanmalı, sessizce hesaba
        girmemeli."""
        from app.domain.models import MatchOutcome, MaterialAttributes

        outcome = MatchOutcome(
            status=MatchStatus.INVALID,
            attributes=MaterialAttributes(),
            message="test",
        )
        row = CalculationInputRow.from_outcome(
            row_no="X-1",
            description="BOX 100×100×4 S235 siyah",
            quantity=Decimal("96"),
            unit="m",
            waste_rate=WasteRate.from_percent("5"),
            outcome=outcome,
        )
        result = calculate_purchase_list([row], catalog)
        assert result.group_count == 0
        assert result.skipped[0].reason is SkipReason.INVALID
        assert result.skipped[0].match_status is MatchStatus.INVALID


# ---------------------------------------------------------------------------
# Fire sözleşmesi: Excel yüzde, domain oran
# ---------------------------------------------------------------------------


class TestWasteContract:
    def test_excel_percent_is_not_reinterpreted_as_fraction(
        self, tmp_path: Path, catalog
    ) -> None:
        """Excel'de 5 yazıyorsa %5'tir; 0,05 oranı diye okunmaz."""
        path = write_workbook(
            tmp_path / "fire.xlsx",
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
        )
        batch = to_domain(read_metraj(path))
        source = batch.sources[0]
        assert source.waste_rate is not None
        assert source.waste_rate.percent == Decimal("5")
        assert source.waste_rate.factor == Decimal("1.05")

    def test_waste_gross_quantity(self, tmp_path: Path, catalog) -> None:
        path = write_workbook(
            tmp_path / "fire2.xlsx",
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
        )
        batch = to_domain(read_metraj(path))
        source = batch.sources[0]
        result = calculate_purchase_list(
            [source.to_calculation_row(source.match(catalog))], catalog
        )
        group = result.group("BOX-100-4-S235-B")
        assert group.sources[0].waste_percent == Decimal("5")
        assert group.sources[0].gross_quantity == Decimal("100.8")

    def test_explicit_zero_waste_reaches_calculation(
        self, tmp_path: Path, catalog
    ) -> None:
        path = write_workbook(
            tmp_path / "fire3.xlsx",
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 0]],
        )
        batch = to_domain(read_metraj(path))
        source = batch.sources[0]
        assert source.waste_rate is not None
        outcome = source.match(catalog)
        assert outcome.status is MatchStatus.RULE
        result = calculate_purchase_list([source.to_calculation_row(outcome)], catalog)
        assert result.group("BOX-100-4-S235-B").sources[0].waste_percent == Decimal("0")


# ---------------------------------------------------------------------------
# Kaynak izlenebilirliği
# ---------------------------------------------------------------------------


class TestTraceability:
    def test_boq_numbers_are_the_trace_key(self, demo_batch, catalog) -> None:
        rows = [
            source.to_calculation_row(source.match(catalog))
            for source in demo_batch.sources
        ]
        result = calculate_purchase_list(rows, catalog)
        for source in result.groups[0].sources:
            assert source.row_no.startswith("BOQ-")

    def test_source_row_is_not_lost_for_invalid(self, tmp_path: Path) -> None:
        path = write_workbook(
            tmp_path / "iz.xlsx",
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                [None, None, None, None, None],
                ["BOQ-003", None, 12, "m", 5],
            ],
        )
        batch = to_domain(read_metraj(path))
        assert batch.rejected[0].source_row == 4
        assert batch.rejected[0].boq_no == "BOQ-003"
        assert batch.rejected[0].issues[0].column_label == "Açıklama"

    def test_fixture_and_excel_agree_on_row_order(self, demo_batch) -> None:
        assert [source.boq_no for source in demo_batch.sources] == [
            row.no for row in DEMO_ROWS
        ]
