"""Örnek proje metrajı üretimi — veri seti sözleşmesi.

Örnek dosyanın varlığı yetmez: şablonla **aynı** sütunları kullanmalı,
okuyucudan geçmeli ve iddia ettiği senaryoyu gerçekten taşımalıdır. Buradaki
testler, dosyanın üzerine yazıldığı fikri sabitler:

* 40 satır, 14 katalog kaleminin tamamı,
* 5 onay bekleyen satır (AI'nın çalıştığı tek yer),
* üç ayrı kapsam dışı nedeni,
* aynı katalog kodunu isteyen farklı iş kalemleri (birleştirme),
* ölçüyü bozmayan açıklama metinleri.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.api.schemas import CalculateRequest, ClientRow
from app.api.service import analyze_file, run_calculation
from app.domain.catalog import load_catalog
from app.domain.matching import match_row
from app.domain.models import ExclusionReason, MatchStatus
from app.excel import TEMPLATE_COLUMNS, TEMPLATE_SHEET_NAME, read_metraj
from app.excel.sample import (
    SAMPLE_ROWS,
    SCENARIO_SHEET_NAME,
    SampleRow,
    build_sample_workbook,
    sample_headers,
)

EXPECTED_ROWS = 40
EXPECTED_PENDING = 5
EXPECTED_EXCLUDED = 3


@pytest.fixture(scope="module")
def sample_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("ornek")
    return build_sample_workbook(directory / "proje_ornek_metraj.xlsx")


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def outcomes(catalog):
    return {
        row.boq_no: match_row(row.description, row.unit, row.waste_percent, catalog)
        for row in SAMPLE_ROWS
    }


@pytest.fixture(scope="module")
def analysis(sample_path: Path):
    return analyze_file(sample_path)


class TestFileStructure:
    def test_file_is_created(self, sample_path: Path) -> None:
        assert sample_path.exists()
        assert sample_path.suffix == ".xlsx"
        assert sample_path.stat().st_size > 0

    def test_main_sheet_is_metraj(self, sample_path: Path) -> None:
        workbook = load_workbook(sample_path)
        assert workbook.sheetnames[0] == TEMPLATE_SHEET_NAME
        workbook.close()

    def test_scenario_sheet_exists(self, sample_path: Path) -> None:
        workbook = load_workbook(sample_path)
        assert SCENARIO_SHEET_NAME in workbook.sheetnames
        workbook.close()

    def test_headers_match_template_contract(self, sample_path: Path) -> None:
        """Örnek dosya şablondan **farklı** sütun kullanmamalı."""
        workbook = load_workbook(sample_path)
        sheet = workbook[TEMPLATE_SHEET_NAME]
        headers = [cell.value for cell in sheet[1]]
        assert headers == list(sample_headers())
        assert headers == [column.value for column in TEMPLATE_COLUMNS]
        workbook.close()

    def test_rejects_non_xlsx_extension(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="xlsx"):
            build_sample_workbook(tmp_path / "ornek.csv")

    def test_is_readable_by_reader(self, sample_path: Path) -> None:
        result = read_metraj(sample_path)
        assert result.sheet_name == TEMPLATE_SHEET_NAME
        assert result.invalid_count == 0
        assert result.blank_rows_skipped == 0
        assert result.ignored_columns == ()
        assert result.warnings == ()

    def test_reader_returns_every_row(self, sample_path: Path) -> None:
        result = read_metraj(sample_path)
        assert len(result.rows) == EXPECTED_ROWS
        assert [row.boq_no for row in result.rows] == [
            row.boq_no for row in SAMPLE_ROWS
        ]

    def test_output_is_byte_reproducible(self, tmp_path: Path) -> None:
        """Aynı veri kümesi aynı baytları üretmeli.

        Dosya commit'lendiği için zaman damgası sızarsa her yeniden üretim
        depoyu gereksiz yere kirletir ve inceleme gürültüye boğulur.
        """
        first = build_sample_workbook(tmp_path / "birinci.xlsx").read_bytes()
        second = build_sample_workbook(tmp_path / "ikinci.xlsx").read_bytes()
        assert first == second

    def test_timestamps_are_pinned(self, sample_path: Path) -> None:
        workbook = load_workbook(sample_path)
        assert workbook.properties.modified.year == 2026
        assert workbook.properties.created.year == 2026
        workbook.close()


class TestDatasetShape:
    def test_row_count(self) -> None:
        assert len(SAMPLE_ROWS) == EXPECTED_ROWS

    def test_row_numbers_are_unique(self) -> None:
        numbers = [row.boq_no for row in SAMPLE_ROWS]
        assert len(numbers) == len(set(numbers))

    def test_quantities_are_positive(self) -> None:
        assert all(row.quantity > 0 for row in SAMPLE_ROWS)

    def test_waste_is_percentage_range(self) -> None:
        for row in SAMPLE_ROWS:
            if row.waste_percent is None:
                continue
            assert Decimal("0") <= row.waste_percent <= Decimal("100"), row.boq_no

    def test_all_catalog_codes_are_used(self, outcomes) -> None:
        """14 kalemin tamamı örnekte geçmeli: kütüphane tam görünsün."""
        used = {outcome.matched_code for outcome in outcomes.values() if outcome.matched_code}
        catalog_codes = {item.code for item in load_catalog()}
        assert used == catalog_codes

    def test_units_cover_m_kg_and_t(self) -> None:
        assert {row.unit for row in SAMPLE_ROWS} >= {"m", "kg", "t"}

    def test_at_least_one_empty_waste(self) -> None:
        assert any(row.waste_percent is None for row in SAMPLE_ROWS)

    def test_at_least_one_unsupported_unit(self) -> None:
        assert any(row.unit == "adet" for row in SAMPLE_ROWS)


class TestMatchingOutcome:
    def test_counts(self, outcomes) -> None:
        counts = Counter(outcome.status.value for outcome in outcomes.values())
        assert counts["rule"] == EXPECTED_ROWS - EXPECTED_PENDING - EXPECTED_EXCLUDED
        assert counts["pending"] == EXPECTED_PENDING
        assert counts["excluded"] == EXPECTED_EXCLUDED
        assert counts["invalid"] == 0

    def test_pending_rows_are_the_expected_ones(self, outcomes) -> None:
        pending = sorted(
            no
            for no, outcome in outcomes.items()
            if outcome.status is MatchStatus.PENDING
        )
        assert pending == ["ANK-001", "CEP-007", "STR-012", "STR-015", "STR-024"]

    def test_every_pending_row_has_a_candidate(self, outcomes) -> None:
        """Onay bekleyen satır çıkmaza düşmemeli: en az bir aday olmalı."""
        for no, outcome in outcomes.items():
            if outcome.status is not MatchStatus.PENDING:
                continue
            assert outcome.candidate_codes, no

    def test_exclusion_reasons_are_all_represented(self, outcomes) -> None:
        """Üç kapsam dışı nedeni de görünmeli; jenerik tek nedene düşmemeli."""
        reasons = {
            outcome.exclusion_reason
            for outcome in outcomes.values()
            if outcome.status is MatchStatus.EXCLUDED
        }
        assert reasons == {
            ExclusionReason.CATALOG,
            ExclusionReason.WASTE,
            ExclusionReason.UNIT,
        }

    def test_excluded_rows_are_the_expected_ones(self, outcomes) -> None:
        excluded = {
            no: outcome.exclusion_reason
            for no, outcome in outcomes.items()
            if outcome.status is MatchStatus.EXCLUDED
        }
        assert excluded == {
            "CEP-004": ExclusionReason.CATALOG,
            "LEV-004": ExclusionReason.WASTE,
            "LEV-005": ExclusionReason.UNIT,
        }

    def test_merges_happen_across_distinct_work_items(self, outcomes) -> None:
        """Birleştirme iddiası gerçek: aynı kod, farklı iş kalemleri."""
        by_code: dict[str, list[str]] = {}
        for no, outcome in outcomes.items():
            if outcome.status is MatchStatus.RULE and outcome.matched_code:
                by_code.setdefault(outcome.matched_code, []).append(no)

        merged = {code: rows for code, rows in by_code.items() if len(rows) > 1}
        assert merged, "en az bir katalog kodu birleşmeli"

        # Onay bekleyen satırlar da aynı kodu istiyor: kaynak çakışması
        # gerçek, karar verildiğinde gruplar daha da birleşir.
        requested: dict[str, set[str]] = {}
        for no, outcome in outcomes.items():
            if outcome.status is MatchStatus.EXCLUDED:
                continue
            for code in outcome.candidate_codes:
                requested.setdefault(code, set()).add(no.split("-")[0])

        assert any(len(prefixes) > 1 for prefixes in requested.values())

    def test_high_waste_rows_carry_budget_risk(self) -> None:
        """Fire riski iddiası metinde durmalı: %10 ve üzeri pozlar var."""
        heavy = [row for row in SAMPLE_ROWS if (row.waste_percent or 0) >= 10]
        assert len(heavy) >= 2

    def test_critical_path_is_named_in_descriptions(self) -> None:
        critical = [row for row in SAMPLE_ROWS if "Kritik yol" in row.description]
        assert len(critical) >= 2

    def test_descriptions_do_not_leak_stray_numbers(self, catalog) -> None:
        """Açıklamadaki sayılar ölçüyle sınırlı olmalı; aksi hâlde ölçü bozulur.

        Her satırda normalizasyonun bulduğu ölçü, katalog kaleminin ölçüsüyle
        birebir aynı olmalı (bulanık eşleştirme yok).
        """
        items = {item.code: item for item in catalog}
        for row in SAMPLE_ROWS:
            outcome = match_row(row.description, row.unit, row.waste_percent, catalog)
            if outcome.matched_code:
                assert outcome.attributes.size == items[outcome.matched_code].size


class TestEndToEndFlow:
    def test_analyze_summary(self, analysis) -> None:
        assert analysis.summary.total_rows == EXPECTED_ROWS
        assert analysis.summary.valid_rows == EXPECTED_ROWS
        assert analysis.summary.invalid_rows == 0
        assert analysis.summary.rule == 32
        assert analysis.summary.pending == EXPECTED_PENDING
        assert analysis.summary.excluded == EXPECTED_EXCLUDED
        assert analysis.warnings == []
        assert analysis.ai.enabled is False
        assert analysis.ai.evaluated_rows == 0

    def test_calculates_fourteen_groups(self, analysis) -> None:
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

        assert len(run.result.groups) == 14
        assert all(group.status.value == "FULL" for group in run.result.groups)
        # Onay bekleyen + kapsam dışı: hiçbiri sessizce kaybolmaz.
        assert len(run.result.skipped) == EXPECTED_PENDING + EXPECTED_EXCLUDED
        assert run.result.input_row_count == EXPECTED_ROWS

    def test_no_row_silently_disappears(self, analysis) -> None:
        """Her BOQ No ya bir grupta ya da atlananlarda görünmeli."""
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

        grouped = {
            no for group in run.result.groups for no in group.source_row_numbers
        }
        skipped = {row.row_no for row in run.result.skipped}
        assert grouped | skipped == {row.boq_no for row in SAMPLE_ROWS}
        assert not (grouped & skipped)

    def test_report_renders_for_sample(self, analysis) -> None:
        from app.reports.service import build_run_report, render_report

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
        report = build_run_report(run_calculation(request))
        assert render_report(report, kind="excel").startswith(b"PK")
        assert render_report(report, kind="pdf").startswith(b"%PDF")


class TestCommittedFiles:
    """Depodaki dosyalar üreticiyle **birebir** aynı olmalı."""

    REPO_ROOT = Path(__file__).resolve().parents[2]

    @pytest.mark.parametrize(
        "relative",
        [
            "templates/proje_ornek_metraj.xlsx",
            "frontend/public/examples/proje-ornek-metraj.xlsx",
        ],
    )
    def test_file_exists(self, relative: str) -> None:
        assert (self.REPO_ROOT / relative).is_file(), relative

    def test_kopyalar_ayni_baytlari_tasir(self) -> None:
        """README: `public/examples/` kopyası `templates/` ile birebir aynıdır.

        Üretim sabit zaman damgası kullandığı için bayt karşılaştırması
        güvenilirdir; içerik karşılaştırması da okunabilirlik için korunur.
        """
        source_path = self.REPO_ROOT / "templates/proje_ornek_metraj.xlsx"
        copy_path = self.REPO_ROOT / "frontend/public/examples/proje-ornek-metraj.xlsx"

        assert source_path.read_bytes() == copy_path.read_bytes()

        source = read_metraj(source_path)
        copy = read_metraj(copy_path)

        def rows(result):
            return [
                (
                    row.boq_no,
                    row.description,
                    row.quantity,
                    row.unit,
                    row.waste_percent,
                )
                for row in result.rows
            ]

        assert rows(source) == rows(copy)
        assert source.sheet_name == copy.sheet_name

    def test_committed_file_matches_generator(self, tmp_path: Path) -> None:
        """Depodaki dosya bayatlamamalı: üretici aynı baytları vermeli."""
        rebuilt = build_sample_workbook(tmp_path / "yeniden.xlsx")
        committed = self.REPO_ROOT / "templates/proje_ornek_metraj.xlsx"
        assert rebuilt.read_bytes() == committed.read_bytes(), (
            "templates/proje_ornek_metraj.xlsx bayat. "
            "`python tools/make_sample_fixtures.py` çalıştırın."
        )


def test_sample_row_dataclass_is_frozen() -> None:
    row = SampleRow(
        boq_no="X-1",
        description="lama 40×5 S235 siyah",
        quantity=Decimal("1"),
        unit="m",
        waste_percent=Decimal("5"),
    )
    with pytest.raises(Exception):
        row.boq_no = "X-2"  # type: ignore[misc]
