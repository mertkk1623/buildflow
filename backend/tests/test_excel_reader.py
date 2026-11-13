"""Excel metraj okuyucu testleri — Aşama 4.3.

Kapsanan senaryolar (istenen 22 senaryo + kenar durumlar):

1.  Şablon oluşturma                                → ``test_excel_template.py``
2.  Şablonun tekrar okunması                        → ``test_excel_template.py``
3.  18 satırlık demo dosyası                        → ``TestDemoFile``
4.  Eksik zorunlu kolon                             → ``TestFileLevelErrors``
5.  Yinelenen kolon                                 → ``TestFileLevelErrors``
6.  Boş satırlar                                    → ``TestBlankRows``
7.  Boş BOQ No                                      → ``TestRowValidation``
8.  Boş açıklama                                    → ``TestRowValidation``
9.  Boş miktar                                      → ``TestRowValidation``
10. Sayısal olmayan miktar                          → ``TestRowValidation``
11. Negatif miktar                                  → ``TestRowValidation``
12. Sıfır miktar                                    → ``TestRowValidation``
13. Desteklenmeyen birim                            → ``TestRowValidation``
14. Eksik fire                                      → ``TestWasteRules``
15. Geçersiz fire                                   → ``TestWasteRules``
16. Yinelenen BOQ No                                → ``TestDuplicates``
17. Formül ve önbellek                              → ``TestFormulas``
18. Bozuk Excel dosyası                             → ``TestFileLevelErrors``
19. Kaynak satır numarası korunur                   → ``TestSourceRows``
20. Türkçe karakterler                              → ``TestTurkishText``
21. Ondalık / binlik ayırıcılar                     → ``TestNumbers``
22. Geçerli + geçersiz satır aynı dosyada           → ``TestMixedFile``
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.models import InvalidReason, MatchStatus
from app.excel import MetrajFileError, MetrajFileErrorCode, read_metraj
from app.excel.models import MetrajColumn
from app.excel.numbers import (
    NumberParseError,
    decimal_from_number,
    parse_decimal_text,
    parse_percent_text,
)
from tests.fixtures.excel_files import (
    build_demo_workbook,
    inject_cached_value,
    write_multi_sheet_workbook,
    write_workbook,
)

VALID_ROW = ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]


def make(tmp_path: Path, rows, name: str = "metraj.xlsx", **kwargs) -> Path:
    return write_workbook(tmp_path / name, rows, **kwargs)


def reasons(row) -> set[InvalidReason]:
    return set(row.invalid_reasons)


def scope_reasons(row) -> set:
    return set(row.exclusion_reasons)


# ---------------------------------------------------------------------------
# 3. 18 satırlık demo dosyası
# ---------------------------------------------------------------------------


class TestDemoFile:
    @pytest.fixture(scope="class")
    @classmethod
    def result(cls, tmp_path_factory: pytest.TempPathFactory):
        directory = tmp_path_factory.mktemp("demo")
        return read_metraj(build_demo_workbook(directory / "demo_metraj.xlsx"))

    def test_reads_eighteen_rows(self, result) -> None:
        assert len(result.rows) == 18
        assert result.valid_count == 18
        assert result.invalid_count == 0

    def test_row_numbers_are_two_to_nineteen(self, result) -> None:
        assert [row.source_row for row in result.rows] == list(range(2, 20))

    def test_boq_numbers_are_preserved(self, result) -> None:
        assert [row.boq_no for row in result.rows] == [
            f"BOQ-{index:03d}" for index in range(1, 19)
        ]

    def test_quantities_are_exact_decimals(self, result) -> None:
        assert result.row_for("BOQ-001").quantity == Decimal("96")
        assert result.row_for("BOQ-003").quantity == Decimal("1240")
        assert result.row_for("BOQ-004").quantity == Decimal("0.84")
        assert result.row_for("BOQ-010").quantity == Decimal("0.32")

    def test_units_are_parsed(self, result) -> None:
        assert result.row_for("BOQ-001").unit_value.value == "m"
        assert result.row_for("BOQ-003").unit_value.value == "kg"
        assert result.row_for("BOQ-004").unit_value.value == "t"

    def test_waste_is_percent_not_fraction(self, result) -> None:
        """Excel'deki ``Fire (%)`` yüzdedir: 5 yazıldıysa %5."""
        assert result.row_for("BOQ-001").waste_percent == Decimal("5")
        assert result.row_for("BOQ-003").waste_percent == Decimal("3")

    def test_missing_waste_stays_none(self, result) -> None:
        row = result.row_for("BOQ-012")
        assert row.waste_percent is None
        assert row.has_waste is False

    def test_non_string_units_are_not_invalid(self, result) -> None:
        """Demo'daki ``adet`` satırı okuma hatası değildir; kapsam dışıdır.

        Aşama 4.1 sözleşmesi ``adet`` için ``excluded: unit`` der; okuyucu bu
        kararı vermez, yalnızca satırı geçerli tutar.
        """
        from app.domain.models import ExclusionReason

        row = result.row_for("BOQ-014")
        assert row.unit == "adet"
        assert row.unit_value is None
        assert row.is_valid is True
        assert InvalidReason.MISSING_UNIT not in reasons(row)
        assert scope_reasons(row) == {ExclusionReason.UNIT}

    def test_descriptions_keep_turkish_characters(self, result) -> None:
        assert result.row_for("BOQ-011").description == "kutu profil 150×100×5 S235 siyah"


# ---------------------------------------------------------------------------
# 4-5, 18. Dosya düzeyi hatalar
# ---------------------------------------------------------------------------


class TestFileLevelErrors:
    def test_missing_required_column(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4", 96, 5]],
            headers=("BOQ No", "Açıklama", "Miktar", "Fire (%)"),
        )
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        error = excinfo.value
        assert error.code is MetrajFileErrorCode.MISSING_COLUMN
        assert "Birim" in error.message
        assert error.suggestion

    def test_missing_several_columns_lists_all(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", 96]], headers=("BOQ No", "Miktar"))
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert "Açıklama" in excinfo.value.message
        assert "Birim" in excinfo.value.message

    def test_duplicate_column(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX", 96, 96, "m"]],
            headers=("BOQ No", "Açıklama", "Miktar", "Miktar", "Birim"),
        )
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.DUPLICATE_COLUMN
        assert "Miktar" in excinfo.value.message

    def test_duplicate_column_with_case_variation(self, tmp_path: Path) -> None:
        """``boq no`` ile ``BOQ No`` aynı kolondur; ikisi birlikte olamaz."""
        path = make(
            tmp_path,
            [["BOQ-001", "BOQ-002", "BOX", 96, "m"]],
            headers=("BOQ No", "boq no", "Açıklama", "Miktar", "Birim"),
        )
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.DUPLICATE_COLUMN

    def test_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "bozuk.xlsx"
        path.write_bytes(b"bu bir excel dosyasi degil")
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.CORRUPT
        assert excinfo.value.suggestion

    def test_truncated_zip(self, tmp_path: Path) -> None:
        path = tmp_path / "yarim.xlsx"
        header = b"PK\x03\x04"
        path.write_bytes(header + b"\x00" * 40)
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.CORRUPT

    def test_unsupported_format_xls(self, tmp_path: Path) -> None:
        path = tmp_path / "metraj.xls"
        path.write_bytes(b"eski format")
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.UNSUPPORTED_FORMAT
        assert ".xlsx" in excinfo.value.suggestion

    def test_unsupported_format_csv(self, tmp_path: Path) -> None:
        path = tmp_path / "metraj.csv"
        path.write_text("BOQ No,Açıklama\n", encoding="utf-8")
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.UNSUPPORTED_FORMAT

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(tmp_path / "yok.xlsx")
        assert excinfo.value.code is MetrajFileErrorCode.NOT_FOUND

    def test_missing_sheet(self, tmp_path: Path) -> None:
        path = write_multi_sheet_workbook(
            tmp_path / "sayfalar.xlsx",
            {"Liste": [VALID_ROW], "Notlar": [["x"]]},
        )
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.MISSING_SHEET
        assert "Liste" in excinfo.value.detail

    def test_headerless_sheet_in_single_sheet_file(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["a", "b", "c"]],
            headers=None,
            sheet="Sayfa1",
        )
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.NO_HEADER

    def test_no_recognised_header_in_named_sheet(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["a", "b"]], headers=("Ad", "Soyad"))
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.NO_HEADER


# ---------------------------------------------------------------------------
# Başlık toleransı
# ---------------------------------------------------------------------------


class TestHeaderTolerance:
    def test_case_and_spacing_tolerated(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
            headers=("boq no", "  AÇIKLAMA ", "MİKTAR", "BİRİM", "fire  (%)"),
        )
        result = read_metraj(path)
        assert result.valid_count == 1
        row = result.rows[0]
        assert row.boq_no == "BOQ-001"
        assert row.quantity == Decimal("96")
        assert row.waste_percent == Decimal("5")

    def test_columns_in_different_order(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOX 100×100×4 S235 siyah", "BOQ-001", "m", 96, 5]],
            headers=("Açıklama", "BOQ No", "Birim", "Miktar", "Fire (%)"),
        )
        result = read_metraj(path)
        row = result.rows[0]
        assert row.boq_no == "BOQ-001"
        assert row.quantity == Decimal("96")
        assert row.unit_value.value == "m"

    def test_header_below_title_rows(self, tmp_path: Path) -> None:
        path = write_workbook(
            tmp_path / "baslikli.xlsx",
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
            title_rows=(
                ["ACME İnşaat A.Ş. — Metraj Listesi"],
                ["Proje: Depo 2"],
            ),
            header_row=3,
        )
        result = read_metraj(path)
        assert result.rows[0].source_row == 4
        assert result.rows[0].boq_no == "BOQ-001"

    def test_extra_columns_are_ignored_not_misread(self, tmp_path: Path) -> None:
        """Yanlış kolon sessizce doğru kolon sayılmamalı."""
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5, "not"]],
            headers=(
                "BOQ No",
                "Açıklama",
                "Miktar",
                "Birim",
                "Fire (%)",
                "Açıklama 2",
            ),
        )
        result = read_metraj(path)
        assert result.ignored_columns == ("Açıklama 2",)
        assert result.rows[0].description == "BOX 100×100×4 S235 siyah"

    def test_data_only_in_unmapped_column_warns(self, tmp_path: Path) -> None:
        """Veri yalnızca tanınmayan kolonda ise satır sessizce kaybolmamalı."""
        path = make(
            tmp_path,
            [[None, None, None, None, None, "BOQ-999"]],
            headers=(
                "BOQ No",
                "Açıklama",
                "Miktar",
                "Birim",
                "Fire (%)",
                "Numara",
            ),
        )
        result = read_metraj(path)
        assert result.valid_count == 0
        assert any("tanınmayan" in warning for warning in result.warnings)

    def test_similar_but_wrong_header_is_not_accepted(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX", 96, "m", 5]],
            headers=("BOQ No", "Açıklama", "Miktar (m)", "Birim", "Fire (%)"),
        )
        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)
        assert excinfo.value.code is MetrajFileErrorCode.MISSING_COLUMN
        assert "Miktar" in excinfo.value.message

    def test_trailing_colon_in_header_tolerated(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
            headers=("BOQ No:", "Açıklama:", "Miktar:", "Birim:", "Fire (%):"),
        )
        result = read_metraj(path)
        assert result.valid_count == 1

    def test_optional_waste_column_can_be_absent(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m"]],
            headers=("BOQ No", "Açıklama", "Miktar", "Birim"),
        )
        result = read_metraj(path)
        assert result.valid_count == 1
        assert result.rows[0].waste_percent is None
        assert any("Fire (%)" in warning for warning in result.warnings)

    def test_single_sheet_without_name_is_accepted(self, tmp_path: Path) -> None:
        path = make(tmp_path, [VALID_ROW], sheet="Sayfa1")
        result = read_metraj(path)
        assert result.sheet_name == "Sayfa1"
        assert result.valid_count == 1
        assert result.warnings


# ---------------------------------------------------------------------------
# 6. Boş satırlar
# ---------------------------------------------------------------------------


class TestBlankRows:
    def test_blank_rows_are_skipped_and_counted(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                VALID_ROW,
                [None, None, None, None, None],
                ["", "   ", None, "", None],
                ["BOQ-002", "IPE 200 S235 siyah", 10, "m", 5],
            ],
        )
        result = read_metraj(path)
        assert len(result.rows) == 2
        assert result.blank_rows_skipped == 2

    def test_blank_rows_do_not_shift_source_rows(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                VALID_ROW,
                [None, None, None, None, None],
                [None, None, None, None, None],
                ["BOQ-002", "IPE 200 S235 siyah", 10, "m", 5],
            ],
        )
        result = read_metraj(path)
        assert [row.source_row for row in result.rows] == [2, 5]

    def test_trailing_blank_rows_are_not_reported(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [VALID_ROW],
            title_rows=(),
        )
        result = read_metraj(path)
        assert len(result.rows) == 1
        assert result.blank_rows_skipped == 0

    def test_formatted_but_empty_rows_are_not_scanned(self, tmp_path: Path) -> None:
        """Excel tüm kolonu biçimlendirince ``max_row`` binlerce olur; okuyucu
        yalnızca **değer taşıyan** satırları taramalı."""
        from openpyxl import load_workbook

        path = make(tmp_path, [VALID_ROW])
        workbook = load_workbook(path)
        sheet = workbook["Metraj"]
        for row in range(1, 5000):
            sheet.cell(row=row, column=3).number_format = "#,##0.00"
        workbook.save(path)
        workbook.close()

        result = read_metraj(path)
        assert len(result.rows) == 1
        assert result.blank_rows_skipped == 0

    def test_large_gap_with_late_row_is_handled(self, tmp_path: Path) -> None:
        """Seyrek doldurulmuş dosyada aradaki boşluk atlanır, satır no korunur."""
        from openpyxl import load_workbook

        path = make(tmp_path, [VALID_ROW])
        workbook = load_workbook(path)
        sheet = workbook["Metraj"]
        sheet.cell(row=500, column=1, value="BOQ-500")
        sheet.cell(row=500, column=2, value="IPE 200 S235 siyah")
        sheet.cell(row=500, column=3, value=10)
        sheet.cell(row=500, column=4, value="m")
        sheet.cell(row=500, column=5, value=5)
        workbook.save(path)
        workbook.close()

        result = read_metraj(path)
        assert [row.source_row for row in result.rows] == [2, 500]
        assert result.blank_rows_skipped == 497

    def test_row_with_only_boq_no_is_not_blank(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", None, None, None, None]])
        result = read_metraj(path)
        assert len(result.rows) == 1
        assert result.rows[0].is_valid is False
        assert InvalidReason.MISSING_DESCRIPTION in reasons(result.rows[0])
        assert InvalidReason.MISSING_QUANTITY in reasons(result.rows[0])


# ---------------------------------------------------------------------------
# 7-13. Satır doğrulama
# ---------------------------------------------------------------------------


class TestRowValidation:
    @pytest.mark.parametrize(
        ("boq", "expected"),
        [(None, InvalidReason.MISSING_BOQ_NO), ("", InvalidReason.MISSING_BOQ_NO),
         ("   ", InvalidReason.MISSING_BOQ_NO)],
    )
    def test_empty_boq_no(self, tmp_path: Path, boq, expected) -> None:
        path = make(tmp_path, [[boq, "BOX 100×100×4 S235 siyah", 96, "m", 5]])
        row = read_metraj(path).rows[0]
        assert row.is_valid is False
        assert expected in reasons(row)
        assert row.status is MatchStatus.INVALID

    def test_empty_description(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", None, 96, "m", 5]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.MISSING_DESCRIPTION in reasons(row)
        assert row.description is None

    def test_whitespace_description(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "   ", 96, "m", 5]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.MISSING_DESCRIPTION in reasons(row)

    def test_empty_quantity(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", None, "m", 5]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.MISSING_QUANTITY in reasons(row)
        assert row.quantity is None

    def test_non_numeric_quantity(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", "yüz", "m", 5]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.INVALID_QUANTITY in reasons(row)
        assert "yüz" in row.issues[0].message

    def test_negative_quantity(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", -5, "m", 5]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.NON_POSITIVE_QUANTITY in reasons(row)

    def test_zero_quantity(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 0, "m", 5]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.NON_POSITIVE_QUANTITY in reasons(row)

    @pytest.mark.parametrize("unit", ["adet", "lt", "mm", "paket", "M2"])
    def test_unsupported_unit_is_out_of_scope_not_invalid(self, tmp_path: Path, unit: str) -> None:
        """Okunabilen birim ``invalid`` değil ``excluded`` (kapsam dışı) olur.

        Bozuk veri ile kapsam dışı veri karıştırılmamalıdır (Aşama 4.3 kuralı).
        """
        from app.domain.models import ExclusionReason

        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, unit, 5]])
        row = read_metraj(path).rows[0]
        assert row.unit == unit
        assert row.unit_value is None
        assert row.is_valid is True
        assert scope_reasons(row) == {ExclusionReason.UNIT}
        assert "hesap kapsamı dışında" in row.scope_issues[0].message

    @pytest.mark.parametrize("unit", ["adet", "lt"])
    def test_unsupported_unit_yields_excluded_in_matching(
        self, tmp_path: Path, unit: str
    ) -> None:
        """Kapsam dışı birim eşleştirmede ``excluded: unit`` üretmeli."""
        from app.domain.catalog import load_catalog
        from app.domain.models import ExclusionReason, MatchStatus
        from app.excel import to_domain

        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, unit, 5]])
        batch = to_domain(read_metraj(path))
        source = batch.sources[0]
        assert source.is_out_of_scope is True
        outcome = source.match(load_catalog())
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.UNIT

    def test_empty_unit(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, None, 5]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.MISSING_UNIT in reasons(row)

    @pytest.mark.parametrize("unit", ["m", "M", "metre", "kg", "KG", "t", "ton"])
    def test_supported_unit_aliases(self, tmp_path: Path, unit: str) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, unit, 5]])
        row = read_metraj(path).rows[0]
        assert row.is_valid is True
        assert row.unit_value is not None

    def test_boolean_quantity_is_invalid(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", True, "m", 5]])
        row = read_metraj(path).rows[0]
        assert row.is_valid is False

    def test_row_reports_column_names(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", None, None, "adet", 5]])
        row = read_metraj(path).rows[0]
        columns = {issue.column for issue in row.issues}
        assert MetrajColumn.DESCRIPTION in columns
        assert MetrajColumn.QUANTITY in columns
        # Birim kapsam dışı ama okunabilir: hata listesinde yer almaz.
        assert MetrajColumn.UNIT not in columns
        assert MetrajColumn.UNIT in {issue.column for issue in row.scope_issues}

    def test_every_issue_has_suggestion(self, tmp_path: Path) -> None:
        path = make(tmp_path, [[None, None, None, "adet", "abc"]])
        row = read_metraj(path).rows[0]
        assert row.issues
        for issue in row.issues:
            assert issue.message
            assert issue.suggestion
            assert issue.column is not None

    def test_valid_row_has_no_status(self, tmp_path: Path) -> None:
        """Okuyucu kullanıcı onayı vermiş gibi davranmamalı."""
        path = make(tmp_path, [VALID_ROW])
        row = read_metraj(path).rows[0]
        assert row.status is None
        assert row.is_valid is True


# ---------------------------------------------------------------------------
# 14-15. Fire kuralları
# ---------------------------------------------------------------------------


class TestWasteRules:
    def test_missing_waste_is_not_zero(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", None]])
        row = read_metraj(path).rows[0]
        assert row.is_valid is True
        assert row.waste_percent is None
        assert row.has_waste is False

    def test_explicit_zero_waste_is_kept(self, tmp_path: Path) -> None:
        """%0 açıkça girilirse sıfır olarak korunur; None ile karışmaz."""
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 0]])
        row = read_metraj(path).rows[0]
        assert row.waste_percent == Decimal("0")
        assert row.has_waste is True

    def test_negative_waste(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", -2]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.NEGATIVE_WASTE in reasons(row)

    def test_waste_over_100(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 250]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.WASTE_OVER_100 in reasons(row)
        assert "100" in row.issues[0].message

    def test_waste_exactly_100_is_allowed(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 100]])
        row = read_metraj(path).rows[0]
        assert row.is_valid is True
        assert row.waste_percent == Decimal("100")

    def test_non_numeric_waste(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", "beş"]])
        row = read_metraj(path).rows[0]
        assert InvalidReason.INVALID_WASTE in reasons(row)

    def test_waste_with_percent_text(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", "%5"]])
        row = read_metraj(path).rows[0]
        assert row.waste_percent == Decimal("5")

    def test_waste_percent_number_format_is_scaled(self, tmp_path: Path) -> None:
        """Excel ``%`` biçimli hücrede 0.05 saklar; bu %5 demektir."""
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 0.05]])
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        workbook["Metraj"]["E2"].number_format = "0%"
        workbook.save(path)
        workbook.close()

        row = read_metraj(path).rows[0]
        assert row.waste_percent == Decimal("5")

    def test_waste_fraction_text_is_not_guessed(self, tmp_path: Path) -> None:
        """Metin hücrede 0,05 yazarsa bu %0,05'tir; oran olduğu varsayılmaz."""
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", "0,05"]])
        row = read_metraj(path).rows[0]
        assert row.waste_percent == Decimal("0.05")


# ---------------------------------------------------------------------------
# 16. Yinelenen BOQ No
# ---------------------------------------------------------------------------


class TestDuplicates:
    def test_duplicate_marks_all_rows(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 12, "m", 5],
            ],
        )
        result = read_metraj(path)
        assert result.invalid_count == 2
        for row in result.rows:
            assert InvalidReason.DUPLICATE_BOQ_NO in reasons(row)

    def test_duplicate_message_names_both_rows(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-002", "IPE 200 S235 siyah", 10, "m", 5],
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 12, "m", 5],
            ],
        )
        result = read_metraj(path)
        duplicate = result.row_for("BOQ-001")
        assert duplicate is not None
        assert "2" in duplicate.issues[-1].message
        assert "4" in duplicate.issues[-1].message

    def test_duplicate_detection_ignores_case(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["boq-001", "BOX 100×100×4 S235 siyah", 12, "m", 5],
            ],
        )
        result = read_metraj(path)
        assert result.invalid_count == 2

    def test_other_rows_survive_duplicates(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 12, "m", 5],
                ["BOQ-003", "IPE 200 S235 siyah", 10, "m", 5],
            ],
        )
        result = read_metraj(path)
        assert [row.boq_no for row in result.valid_rows] == ["BOQ-003"]

    def test_duplicate_is_not_merged_silently(self, tmp_path: Path) -> None:
        """İlk satırı geçerli sayıp toplamak sessiz bir seçim olurdu."""
        path = make(
            tmp_path,
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
            ],
        )
        result = read_metraj(path)
        assert result.valid_count == 0

    def test_invalid_row_does_not_invalidate_a_valid_row(self, tmp_path: Path) -> None:
        """Hatalı satırın numarası, kullanılabilir satırı düşürmemeli."""
        path = make(
            tmp_path,
            [
                ["BOQ-001", None, 96, "m", 5],
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
            ],
        )
        result = read_metraj(path)
        assert result.valid_count == 1
        assert result.valid_rows[0].source_row == 3
        assert result.invalid_count == 1
        assert InvalidReason.MISSING_DESCRIPTION in reasons(result.invalid_rows[0])


# ---------------------------------------------------------------------------
# 17. Formül hücreleri
# ---------------------------------------------------------------------------


class TestFormulas:
    def test_formula_without_cache_is_invalid(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 12, "m", 5]])
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        workbook["Metraj"]["C2"] = "=10+2"
        workbook.save(path)
        workbook.close()

        row = read_metraj(path).rows[0]
        assert row.is_valid is False
        assert InvalidReason.FORMULA_WITHOUT_CACHE in reasons(row)
        assert row.quantity is None

    def test_formula_without_cache_is_not_zero(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 12, "m", 5]])
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        workbook["Metraj"]["C2"] = "=10+2"
        workbook.save(path)
        workbook.close()

        row = read_metraj(path).rows[0]
        assert row.quantity != Decimal("0")
        assert row.quantity is None

    def test_formula_with_cached_value_is_read(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 12, "m", 5]])
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        workbook["Metraj"]["C2"] = "=10+2"
        workbook.save(path)
        workbook.close()

        inject_cached_value(path, cell="C2", value="12")

        row = read_metraj(path).rows[0]
        assert row.is_valid is True
        assert row.quantity == Decimal("12")
        assert any("önbelle" in note for note in row.notes)

    def test_formula_cache_does_not_compute(self, tmp_path: Path) -> None:
        """Önbellek 11 ise 12 hesaplanmaz; Excel'in değeri esas alınır."""
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 12, "m", 5]])
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        workbook["Metraj"]["C2"] = "=10+2"
        workbook.save(path)
        workbook.close()

        inject_cached_value(path, cell="C2", value="11")
        assert read_metraj(path).rows[0].quantity == Decimal("11")

    def test_formula_in_waste_without_cache(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]])
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        workbook["Metraj"]["E2"] = "=2+3"
        workbook.save(path)
        workbook.close()

        row = read_metraj(path).rows[0]
        assert InvalidReason.FORMULA_WITHOUT_CACHE in reasons(row)
        assert row.waste_percent is None

    def test_formula_row_is_not_treated_as_blank(self, tmp_path: Path) -> None:
        from openpyxl import load_workbook

        path = make(tmp_path, [VALID_ROW])
        workbook = load_workbook(path)
        workbook["Metraj"]["C2"] = "=10+2"
        workbook.save(path)
        workbook.close()

        result = read_metraj(path)
        assert len(result.rows) == 1
        assert result.invalid_count == 1


# ---------------------------------------------------------------------------
# 19. Kaynak satır numarası
# ---------------------------------------------------------------------------


class TestSourceRows:
    def test_source_row_matches_excel_row(self, tmp_path: Path) -> None:
        path = make(tmp_path, [VALID_ROW])
        row = read_metraj(path).rows[0]
        assert row.source_row == 2  # başlık 1. satır

    def test_source_row_survives_gaps(self, tmp_path: Path) -> None:
        rows: list[list[object]] = []
        for index in range(1, 6):
            rows.append([f"BOQ-{index:03d}", "BOX 100×100×4 S235 siyah", 10, "m", 5])
            rows.append([None, None, None, None, None])
        path = make(tmp_path, rows)
        result = read_metraj(path)
        assert [row.source_row for row in result.rows] == [2, 4, 6, 8, 10]

    def test_source_row_in_bridge_kept(self, tmp_path: Path) -> None:
        from app.excel import to_domain

        path = make(
            tmp_path,
            [
                [None, None, None, None, None],
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
            ],
        )
        result = read_metraj(path)
        batch = to_domain(result)
        assert batch.sources[0].source_row == 3

    def test_error_message_includes_row_number(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-002", "BOX 100×100×4 S235 siyah", "abc", "m", 5],
            ],
        )
        result = read_metraj(path)
        invalid = result.invalid_rows[0]
        assert invalid.source_row == 3


# ---------------------------------------------------------------------------
# 20. Türkçe karakterler
# ---------------------------------------------------------------------------


class TestTurkishText:
    def test_turkish_characters_round_trip(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [
                [
                    "BOQ-001",
                    "Kutu profil 150×100×5 ÇELİK S235 — galvaniz kaplama",
                    60,
                    "m",
                    5,
                ]
            ],
        )
        row = read_metraj(path).rows[0]
        assert row.description == "Kutu profil 150×100×5 ÇELİK S235 — galvaniz kaplama"

    def test_turkish_header_case(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "IPE 200 S235 siyah", 10, "m", 5]],
            headers=("BOQ NO", "AÇIKLAMA", "MİKTAR", "BİRİM", "FİRE (%)"),
        )
        result = read_metraj(path)
        assert result.valid_count == 1

    def test_turkish_dotless_i_in_unit(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "IPE 200 S235 siyah", 10, "METRE", 5]],
            headers=("BOQ No", "Açıklama", "Miktar", "BİRİM", "Fire (%)"),
        )
        row = read_metraj(path).rows[0]
        assert row.unit_value is not None
        assert row.unit_value.value == "m"

    def test_boq_no_keeps_turkish_text(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["MTR-Ç1-01", "IPE 200 S235 siyah", 10, "m", 5]])
        assert read_metraj(path).rows[0].boq_no == "MTR-Ç1-01"


# ---------------------------------------------------------------------------
# 21. Sayılar: ondalık ve binlik ayırıcı
# ---------------------------------------------------------------------------


class TestNumbers:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("96", "96"),
            ("1,24", "1.24"),
            ("0,84", "0.84"),
            ("1.240", "1240"),
            ("1.240,50", "1240.50"),
            ("1,240.50", "1240.50"),
            ("1.234.567,89", "1234567.89"),
            ("1 240", "1240"),
            ("-5", "-5"),
            ("\u22125", "-5"),
            ("  12,5  ", "12.5"),
        ],
    )
    def test_text_numbers(self, text: str, expected: str) -> None:
        assert parse_decimal_text(text) == Decimal(expected)

    @pytest.mark.parametrize("text", ["1,240", "12,345", "1,2,3", "1.2.3", "1.240.50"])
    def test_ambiguous_or_malformed_numbers_are_rejected(self, text: str) -> None:
        with pytest.raises(NumberParseError) as excinfo:
            parse_decimal_text(text)
        assert excinfo.value.ambiguous is True

    def test_turkish_dot_is_thousands_unambiguously(self) -> None:
        """Türkçe yazımda nokta ondalık ayırıcı **değildir**: 1.240 = 1240."""
        assert parse_decimal_text("1.240") == Decimal("1240")
        assert parse_decimal_text("12.345") == Decimal("12345")

    def test_comma_with_three_digits_is_ambiguous(self) -> None:
        """Virgül Türkçe'de ondalıktır; üç haneli kuyruk 1,240 ≠ 1240."""
        with pytest.raises(NumberParseError) as excinfo:
            parse_decimal_text("12,345")
        assert excinfo.value.ambiguous is True
        assert "üç hane" in excinfo.value.message

    def test_ambiguous_number_marks_row_invalid(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4 S235 siyah", "1,240", "m", 5]],
        )
        row = read_metraj(path).rows[0]
        assert InvalidReason.AMBIGUOUS_NUMBER in reasons(row)
        assert row.quantity is None

    def test_text_quantity_with_turkish_decimal(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4 S235 siyah", "1,24", "t", 5]],
        )
        row = read_metraj(path).rows[0]
        assert row.is_valid is True
        assert row.quantity == Decimal("1.24")

    def test_text_quantity_with_thousands_separator(self, tmp_path: Path) -> None:
        path = make(
            tmp_path,
            [["BOQ-001", "IPE 200 S235 siyah", "1.240", "kg", 5]],
        )
        row = read_metraj(path).rows[0]
        assert row.quantity == Decimal("1240")

    def test_numeric_cell_is_exact(self, tmp_path: Path) -> None:
        """Float hücreden Decimal kurulurken ikili kesir hatası taşınmamalı."""
        path = make(
            tmp_path,
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 0.1, "t", 5]],
        )
        row = read_metraj(path).rows[0]
        assert row.quantity == Decimal("0.1")
        assert str(row.quantity) == "0.1"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(96, "96"), (0.1, "0.1"), (1.570, "1.57"), (1234567890, "1234567890")],
    )
    def test_decimal_from_number_is_exact(self, value, expected) -> None:
        assert decimal_from_number(value) == Decimal(expected)

    def test_float_zero_point_three(self) -> None:
        assert decimal_from_number(0.3) == Decimal("0.3")

    def test_percent_text(self) -> None:
        assert parse_percent_text("%5") == Decimal("5")
        assert parse_percent_text("5%") == Decimal("5")
        assert parse_percent_text("2,5") == Decimal("2.5")

    def test_quantity_result_is_decimal_not_float(self, tmp_path: Path) -> None:
        path = make(tmp_path, [["BOQ-001", "BOX 100×100×4 S235 siyah", 96.5, "m", 5]])
        row = read_metraj(path).rows[0]
        assert isinstance(row.quantity, Decimal)


# ---------------------------------------------------------------------------
# 22. Geçerli + geçersiz satırlar aynı dosyada
# ---------------------------------------------------------------------------


class TestMixedFile:
    @pytest.fixture()
    def result(self, tmp_path: Path):
        path = make(
            tmp_path,
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-002", None, 48, "m", 5],
                ["BOQ-003", "IPE 200 S235 siyah", "abc", "kg", 3],
                ["BOQ-004", "HEA 200 S235 siyah", 132, "m", 4],
                ["BOQ-005", "UPN 160 S235 siyah", 54, None, 4],
                ["BOQ-006", "UPN 160 S235 siyah", 54, "adet", 4],
            ],
        )
        return read_metraj(path)

    def test_valid_rows_are_kept(self, result) -> None:
        assert [row.boq_no for row in result.valid_rows] == [
            "BOQ-001",
            "BOQ-004",
            "BOQ-006",
        ]

    def test_invalid_rows_are_reported(self, result) -> None:
        assert [row.boq_no for row in result.invalid_rows] == [
            "BOQ-002",
            "BOQ-003",
            "BOQ-005",
        ]

    def test_file_is_not_rejected(self, result) -> None:
        assert result.valid_count + result.invalid_count == len(result.rows) == 6

    def test_bridge_separates_valid_and_rejected(self, result) -> None:
        from app.excel import to_domain

        batch = to_domain(result)
        assert [source.boq_no for source in batch.sources] == [
            "BOQ-001",
            "BOQ-004",
            "BOQ-006",
        ]
        assert [rejected.boq_no for rejected in batch.rejected] == [
            "BOQ-002",
            "BOQ-003",
            "BOQ-005",
        ]
        assert batch.total == 6

    def test_out_of_scope_rows_are_not_rejected(self, result) -> None:
        """``adet`` satırı silinmemeli; kapsam dışı olarak korunmalı."""
        from app.excel import to_domain

        batch = to_domain(result)
        assert [source.boq_no for source in batch.out_of_scope] == ["BOQ-006"]

    def test_rejected_rows_carry_invalid_status(self, result) -> None:
        from app.excel import to_domain

        batch = to_domain(result)
        for rejected in batch.rejected:
            assert rejected.status is MatchStatus.INVALID

    def test_rejected_rows_keep_reasons_and_issues(self, result) -> None:
        from app.excel import to_domain

        batch = to_domain(result)
        by_no = {rejected.boq_no: rejected for rejected in batch.rejected}
        assert InvalidReason.MISSING_DESCRIPTION in by_no["BOQ-002"].reasons
        assert InvalidReason.INVALID_QUANTITY in by_no["BOQ-003"].reasons
        assert InvalidReason.MISSING_UNIT in by_no["BOQ-005"].reasons
        assert by_no["BOQ-003"].issues[0].column is MetrajColumn.QUANTITY
        assert by_no["BOQ-005"].issues[0].column is MetrajColumn.UNIT


# ---------------------------------------------------------------------------
# 23. Kaynak tükenmesi sınırları (zip bomb / patolojik satır sayısı)
# ---------------------------------------------------------------------------


class TestResourceLimits:
    """Açılmış boyut, arşiv giriş sayısı ve satır sayısı sınırları.

    Bu sınırlar **normal dosyaları etkilemez**; yalnızca patolojik girdileri
    openpyxl'e ulaşmadan durdurur.
    """

    def test_normal_demo_file_is_within_limits(self) -> None:
        """Sınırlar gerçek dosyaları engellememeli — regresyon güvencesi."""
        from app.excel.reader import MAX_DATA_ROWS, MAX_EXPANDED_BYTES

        assert MAX_EXPANDED_BYTES >= 10 * 1024 * 1024
        assert MAX_DATA_ROWS >= 10_000

    def test_expanded_size_over_limit_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = make(tmp_path, [VALID_ROW])

        # Sınırı yapay olarak 1 bayta indir: gerçek bir zip bomb üretmeden
        # aynı kod yolunu doğrularız.
        import app.excel.reader as reader_module

        monkeypatch.setattr(reader_module, "MAX_EXPANDED_BYTES", 1)

        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)

        assert excinfo.value.code is MetrajFileErrorCode.FILE_TOO_COMPLEX
        assert "açılmış" in excinfo.value.message.lower()
        assert excinfo.value.suggestion

    def test_archive_entry_count_over_limit_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = make(tmp_path, [VALID_ROW])

        import app.excel.reader as reader_module

        monkeypatch.setattr(reader_module, "MAX_ARCHIVE_ENTRIES", 1)

        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)

        assert excinfo.value.code is MetrajFileErrorCode.FILE_TOO_COMPLEX
        assert "karmaşık" in excinfo.value.message.lower()

    def test_row_count_over_limit_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = make(tmp_path, [VALID_ROW])

        import app.excel.reader as reader_module

        monkeypatch.setattr(reader_module, "MAX_DATA_ROWS", 0)

        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)

        assert excinfo.value.code is MetrajFileErrorCode.FILE_TOO_COMPLEX
        assert "satır" in excinfo.value.message.lower()

    def test_corrupt_archive_still_reports_corrupt_not_limits(
        self, tmp_path: Path
    ) -> None:
        """Bozuk arşiv sınır hatası değil, ``corrupt-file`` üretmeli."""
        path = tmp_path / "bozuk.xlsx"
        path.write_bytes(b"bu bir excel dosyasi degil")

        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)

        assert excinfo.value.code is MetrajFileErrorCode.CORRUPT

    def test_corrupt_file_detail_has_no_exception_class_name(
        self, tmp_path: Path
    ) -> None:
        """İstisna sınıf adı kullanıcıya taşınmamalı."""
        path = tmp_path / "bozuk.xlsx"
        path.write_bytes(b"bu bir excel dosyasi degil")

        with pytest.raises(MetrajFileError) as excinfo:
            read_metraj(path)

        detail = excinfo.value.detail
        for leaked in ("BadZipFile", "InvalidFileException", "KeyError", "Error:"):
            assert leaked not in detail
