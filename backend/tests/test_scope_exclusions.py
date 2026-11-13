"""Kapsam dışı satırların **gerçek** nedeninin korunması — regresyon.

Bağlam
------
Canlı testte satırlar hesap dışı kaldı ve kullanıcı raporlarda yalnızca
"Satır hesap kapsamı dışında bırakıldı" mesajını gördü. Oysa nedenleri
birbirinden tamamen farklıydı:

* ``HEA 200 S235 galvaniz`` → katalogda HEA yalnız ``siyah`` kaplamada var.
* ``BOX 100×100×4 S235 siyah`` → fire (%) boş bırakılmış (demo: BOQ-012).
* ``profil 100×100`` → desteklenmeyen birim (demo: BOQ-014).
* ``muhtelif bağlantı elemanı`` → katalogda karşılığı yok (demo: BOQ-015).

Dört ayrı neden raporda **aynı** jenerik metne düşüyordu. Ayrıca ``lama``
ailesi kapsam sorunu değildi: ``lama 40×5 S235 siyah`` kural ile eşleşir,
yalnızca kaplama/kalite eksik olan ``lama 40×5`` onay bekler. Bu testler
nedeni kaybetmediğimizi ve ailelerin elemeli olmadığını kilitler.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.calculation import (
    EXCLUSION_REASON_LABELS,
    CalculationInputRow,
    SkipReason,
    WasteRate,
    calculate_purchase_list,
)
from app.domain.catalog import Catalog, load_catalog
from app.domain.models import ExclusionReason, MatchStatus
from app.reports.service import build_run_report

D = Decimal


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog()


@pytest.fixture(scope="module")
def demo_skipped():
    """Gerçek demo dosyasının hesap dışı satırları (BOQ No → SkippedRow)."""
    from pathlib import Path

    from app.api.schemas import CalculateRequest, ClientRow
    from app.api.service import analyze_file, run_calculation

    template = (
        Path(__file__).resolve().parents[2] / "templates" / "ornek_metraj.xlsx"
    )
    analysis = analyze_file(template)
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
    run = run_calculation(request)
    return {row.row_no: row for row in run.result.skipped}


def _row(
    no: str,
    quantity: str,
    unit: str,
    *,
    description: str,
    reason: ExclusionReason,
    waste: str | None = "5",
) -> CalculationInputRow:
    return CalculationInputRow(
        row_no=no,
        description=description,
        quantity=D(quantity),
        unit=unit,
        waste_rate=WasteRate.from_percent(waste) if waste is not None else None,
        status=MatchStatus.EXCLUDED,
        matched_code=None,
        exclusion_reason=reason,
    )


# ---------------------------------------------------------------------------
# 1. V1 aileleri: BOX, IPE, HEA, UPN, lama
# ---------------------------------------------------------------------------


class TestV1FamilyCoverage:
    """Beş ailenin tamamı eşleşip hesaplanabilmeli."""

    @pytest.mark.parametrize(
        ("description", "unit", "code"),
        [
            ("BOX 100×100×4 S235 siyah", "m", "BOX-100-4-S235-B"),
            ("BOX 100×100×4 S235 galvaniz", "m", "BOX-100-4-S235-G"),
            ("IPE 200 S235 siyah", "kg", "IPE-200-S235"),
            ("HEA 200 S235 siyah", "m", "HEA-200-S235"),
            ("UPN 160 S235 siyah", "m", "UPN-160-S235"),
            ("lama 40×5 S235 siyah", "kg", "FLAT-40x5-S235-B"),
        ],
    )
    def test_family_matches_rule(
        self, catalog: Catalog, description: str, unit: str, code: str
    ) -> None:
        from app.domain.matching import match_row

        outcome = match_row(description, unit, D("0.05"), catalog)

        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == code

    @pytest.mark.parametrize(
        ("description", "unit", "code"),
        [
            ("BOX 100×100×4", "m", "BOX-100-4-S235-B"),
            ("IPE 200", "kg", "IPE-200-S235"),
            ("HEA 200", "m", "HEA-200-S235"),
            ("UPN 160", "m", "UPN-160-S235"),
            ("lama 40×5", "kg", "FLAT-40x5-S235-B"),
        ],
    )
    def test_family_becomes_pending_without_coating(
        self, catalog: Catalog, description: str, unit: str, code: str
    ) -> None:
        """Kaplama eksikse satır pending olur — aile ayrımcılığı yok."""
        from app.domain.matching import match_row

        outcome = match_row(description, unit, D("0.05"), catalog)

        assert outcome.status is MatchStatus.PENDING
        assert code in outcome.candidate_codes


# ---------------------------------------------------------------------------
# 2. HEA galvaniz: kapsam dışı **kalıcıdır**, sessizce düşürülmez
# ---------------------------------------------------------------------------


class TestHeaGalvanizedIsExcluded:
    def test_catalog_has_no_galvanized_hea(self, catalog: Catalog) -> None:
        """Katalog gerçeği: HEA yalnız siyah kaplamada var."""
        hea = [item for item in catalog if item.family.value == "HEA"]

        assert hea, "katalogda en az bir HEA kalemi olmalı"
        assert {item.coating.value for item in hea} == {"siyah"}

    def test_galvanized_hea_is_excluded_not_downgraded(
        self, catalog: Catalog
    ) -> None:
        """Benzer siyah HEA'ya düşürme **yapılmaz**; neden katalogdur."""
        from app.domain.matching import match_row

        outcome = match_row(
            "HEA 200 S235 galvaniz", "t", D("0.04"), catalog
        )

        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.CATALOG
        # Sessiz düşürme olsaydı burada HEA-200-S235 olurdu.
        assert outcome.matched_code is None
        assert outcome.candidate_codes == ()

    def test_black_hea_still_matches_as_rule(self, catalog: Catalog) -> None:
        """Aynı ölçünün siyahı eşleşir: aile kapsam dışı değildir."""
        from app.domain.matching import match_row

        outcome = match_row("HEA 200 S235 siyah", "t", D("0.04"), catalog)

        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "HEA-200-S235"


# ---------------------------------------------------------------------------
# 3. Dışlama nedeni raporda korunuyor mu?
# ---------------------------------------------------------------------------


class TestExclusionReasonReachesReport:
    def test_every_reason_has_a_user_label(self) -> None:
        for reason in ExclusionReason:
            assert reason in EXCLUSION_REASON_LABELS
            assert EXCLUSION_REASON_LABELS[reason].strip()

    def test_catalog_exclusion_keeps_reason_and_label(
        self, catalog: Catalog
    ) -> None:
        """Gerçek akış: ``match_row`` → ``from_outcome`` → hesaplama."""
        from app.domain.matching import match_row

        outcome = match_row(
            "HEA 200 S235 galvaniz", "t", D("0.04"), catalog
        )
        assert outcome.status is MatchStatus.EXCLUDED  # ön koşul

        result = calculate_purchase_list(
            [
                CalculationInputRow.from_outcome(
                    row_no="BOQ-005",
                    description="HEA 200 S235 galvaniz",
                    quantity=D("3.2"),
                    unit="t",
                    waste_rate=WasteRate.from_percent("4"),
                    outcome=outcome,
                )
            ],
            catalog,
        )

        skipped = result.skipped[0]
        assert skipped.reason is SkipReason.EXCLUDED
        assert skipped.exclusion_reason is ExclusionReason.CATALOG
        assert skipped.exclusion_label == "Katalogda karşılığı yok"
        # Jenerik metin tek başına kalmamalı: tanınan özellikler görünür.
        assert "katalogda bu kombinasyon yok" in skipped.message
        assert "HEA" in skipped.message
        assert "galvaniz" in skipped.message

    def test_waste_exclusion_keeps_reason_and_action(
        self, catalog: Catalog
    ) -> None:
        result = calculate_purchase_list(
            [
                _row(
                    "BOQ-012",
                    "60",
                    "m",
                    description="BOX 100×100×4 S235 siyah",
                    reason=ExclusionReason.WASTE,
                    waste=None,
                )
            ],
            catalog,
        )

        skipped = result.skipped[0]
        assert skipped.exclusion_reason is ExclusionReason.WASTE
        assert skipped.exclusion_label == "Fire tanımsız"
        assert "Fire (%)" in skipped.message

    def test_unit_exclusion_keeps_reason_and_action(
        self, catalog: Catalog
    ) -> None:
        result = calculate_purchase_list(
            [
                _row(
                    "BOQ-014",
                    "12",
                    "adet",
                    description="profil 100×100",
                    reason=ExclusionReason.UNIT,
                )
            ],
            catalog,
        )

        skipped = result.skipped[0]
        assert skipped.exclusion_reason is ExclusionReason.UNIT
        assert skipped.exclusion_label == "Birim desteklenmiyor"
        assert "m, kg, t" in skipped.message

    def test_pending_row_has_no_exclusion_reason(
        self, catalog: Catalog
    ) -> None:
        """``pending`` bir dışlama değildir; nedeni olmamalı."""
        result = calculate_purchase_list(
            [
                CalculationInputRow(
                    row_no="BOQ-009",
                    description="lama 40×5",
                    quantity=D("180"),
                    unit="kg",
                    waste_rate=WasteRate.from_percent("5"),
                    status=MatchStatus.PENDING,
                    matched_code=None,
                )
            ],
            catalog,
        )

        skipped = result.skipped[0]
        assert skipped.reason is SkipReason.PENDING
        assert skipped.exclusion_reason is None
        assert skipped.exclusion_label is None

    def test_report_carries_reason_to_output(self, catalog: Catalog) -> None:
        """Rapor nesnesi (Excel/PDF ortak) nedeni taşımalı."""
        from app.api.schemas import CalculateRequest, ClientRow
        from app.api.service import run_calculation

        request = CalculateRequest(
            rows=[
                ClientRow(
                    source_row=2,
                    boq_no="BOQ-005",
                    description="HEA 200 S235 galvaniz",
                    quantity="3.2",
                    unit="t",
                    waste_percent="4",
                )
            ]
        )
        run = run_calculation(request)
        report = build_run_report(run)

        assert len(report.skipped) == 1
        row = report.skipped[0]
        assert row.exclusion_reason == "catalog"
        assert row.exclusion_reason_label == "Katalogda karşılığı yok"
        assert "katalogda bu kombinasyon yok" in row.message

    def test_api_exposes_reason(self, catalog: Catalog) -> None:
        from app.api.schemas import CalculateRequest, ClientRow
        from app.api.service import run_calculation

        request = CalculateRequest(
            rows=[
                ClientRow(
                    source_row=2,
                    boq_no="BOQ-012",
                    description="BOX 100×100×4 S235 siyah",
                    quantity="60",
                    unit="m",
                    waste_percent=None,
                )
            ]
        )
        run = run_calculation(request)
        from app.api.mapping import skipped_row_to_out

        out = skipped_row_to_out(run.result.skipped[0], run.source_rows)

        assert out.status == "excluded"
        assert out.exclusion_reason == "waste"
        assert out.exclusion_reason_label == "Fire tanımsız"


# ---------------------------------------------------------------------------
# 4. Hesaplama motoru bozulmadı: dışlanan satır gruba girmez
# ---------------------------------------------------------------------------


class TestExcludedRowsDoNotEnterGroups:
    def test_excluded_row_produces_no_group(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                _row(
                    "BOQ-005",
                    "3.2",
                    "t",
                    description="HEA 200 S235 galvaniz",
                    reason=ExclusionReason.CATALOG,
                )
            ],
            catalog,
        )

        assert result.groups == ()
        assert result.calculated_row_count == 0
        assert result.skipped_count == 1


# ---------------------------------------------------------------------------
# 5. Gerçek demo dosyası: nedenler satır bazında ayrışıyor mu?
# ---------------------------------------------------------------------------


class TestRealDemoFileExclusions:
    """``templates/ornek_metraj.xlsx`` üzerinde uçtan uca doğrulama.

    Birim testleri sentetik satır kurar; bu sınıf **gerçek dosyanın**
    nedenleri doğru ürettiğini kilitler, böylece docstring'deki iddialar
    ile dosya davranışı ayrışamaz.
    """

    def test_pending_rows_are_the_four_ambiguous_ones(self, demo_skipped) -> None:
        skipped = demo_skipped
        pending = {no for no, row in skipped.items() if row.reason is SkipReason.PENDING}

        assert pending == {"BOQ-003", "BOQ-004", "BOQ-006", "BOQ-009"}

    def test_pending_rows_have_no_exclusion_reason(self, demo_skipped) -> None:
        """Onay beklemek bir dışlama değildir."""
        skipped = demo_skipped
        for no in ("BOQ-003", "BOQ-004", "BOQ-006", "BOQ-009"):
            assert skipped[no].exclusion_reason is None
            assert skipped[no].exclusion_label is None

    def test_each_excluded_row_has_its_own_reason(self, demo_skipped) -> None:
        skipped = demo_skipped
        expected = {
            "BOQ-012": ExclusionReason.WASTE,
            "BOQ-014": ExclusionReason.UNIT,
            "BOQ-015": ExclusionReason.CATALOG,
            "BOQ-018": ExclusionReason.CATALOG,
        }
        actual = {
            no: row.exclusion_reason
            for no, row in skipped.items()
            if row.reason is SkipReason.EXCLUDED
        }

        assert actual == expected

    def test_excluded_rows_do_not_share_one_message(self, demo_skipped) -> None:
        """Regresyonun özü: dört farklı neden tek metne düşmemeli."""
        skipped = demo_skipped
        messages = {
            row.message
            for row in skipped.values()
            if row.reason is SkipReason.EXCLUDED
        }

        # Katalog dışı iki satır aynı metni paylaşabilir; fire ve birim
        # nedenleri ayrı olmalı.
        assert len(messages) >= 3

    def test_lama_family_is_not_excluded(self, demo_skipped) -> None:
        """``lama`` kapsam sorunu değildir: pending'dir, elenmez."""
        skipped = demo_skipped
        lama = [row for no, row in skipped.items() if no == "BOQ-009"]

        assert lama, "BOQ-009 (lama 40×5) skipped listesinde olmalı"
        assert lama[0].reason is SkipReason.PENDING
        assert lama[0].exclusion_reason is not ExclusionReason.CATALOG
