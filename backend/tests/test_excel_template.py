"""Şablon üretimi testleri — Aşama 4.3.

Şablonun varlığı yetmez: okuyucunun beklediği kolonlarla **birebir** aynı
olmalı ve okuyucu tarafından tekrar okunabilmelidir.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.excel import (
    REQUIRED_COLUMNS,
    TEMPLATE_COLUMNS,
    TEMPLATE_SHEET_NAME,
    build_metraj_template,
    read_metraj,
    template_headers,
)
from app.excel.models import GUIDE_SHEET_NAME
from app.excel.template import TEMPLATE_EXAMPLE_ROWS


@pytest.fixture(scope="module")
def template_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("sablon")
    return build_metraj_template(directory / "metraj_sablonu.xlsx")


class TestTemplateStructure:
    def test_file_is_created(self, template_path: Path) -> None:
        assert template_path.exists()
        assert template_path.suffix == ".xlsx"
        assert template_path.stat().st_size > 0

    def test_main_sheet_is_named_metraj(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        assert TEMPLATE_SHEET_NAME in workbook.sheetnames
        assert workbook.sheetnames[0] == TEMPLATE_SHEET_NAME
        workbook.close()

    def test_guide_sheet_exists(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        assert GUIDE_SHEET_NAME in workbook.sheetnames
        guide = workbook[GUIDE_SHEET_NAME]
        text = " ".join(
            str(cell.value) for row in guide.iter_rows() for cell in row if cell.value
        )
        assert "Metraj" in text
        assert "Fire" in text
        # Fire boş bırakılırsa sıfır sayılmadığı açıkça yazılmalı.
        assert "sıfır" in text.lower()
        workbook.close()

    def test_headers_match_reader_contract_exactly(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        sheet = workbook[TEMPLATE_SHEET_NAME]
        headers = [cell.value for cell in sheet[1]]
        assert headers == [column.value for column in TEMPLATE_COLUMNS]
        assert headers == [
            "BOQ No",
            "Açıklama",
            "Miktar",
            "Birim",
            "Fire (%)",
        ]
        workbook.close()

    def test_header_helper_matches_written_headers(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        sheet = workbook[TEMPLATE_SHEET_NAME]
        written = tuple(cell.value for cell in sheet[1])
        assert written == tuple(template_headers())
        workbook.close()

    def test_required_columns_are_in_template(self) -> None:
        for column in REQUIRED_COLUMNS:
            assert column in TEMPLATE_COLUMNS

    def test_example_rows_present(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        sheet = workbook[TEMPLATE_SHEET_NAME]
        values = [
            sheet.cell(row=2 + offset, column=1).value
            for offset in range(len(TEMPLATE_EXAMPLE_ROWS))
        ]
        assert values == [example.boq_no for example in TEMPLATE_EXAMPLE_ROWS]
        workbook.close()

    def test_examples_cover_different_units(self) -> None:
        units = {example.unit for example in TEMPLATE_EXAMPLE_ROWS}
        assert units == {"m", "kg", "t"}

    def test_at_least_one_example_has_empty_waste(self) -> None:
        assert any(example.waste_percent is None for example in TEMPLATE_EXAMPLE_ROWS)

    def test_example_values_are_numeric(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        sheet = workbook[TEMPLATE_SHEET_NAME]
        for offset in range(len(TEMPLATE_EXAMPLE_ROWS)):
            cell = sheet.cell(row=2 + offset, column=3)
            assert isinstance(cell.value, (int, float)), cell.value
            # Örnek miktarlar sayı biçiminde yazılmalı; metin olmamalı.
            assert not isinstance(cell.value, str)
        workbook.close()

    def test_header_is_styled_and_frozen(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        sheet = workbook[TEMPLATE_SHEET_NAME]
        header = sheet.cell(row=1, column=1)
        assert header.font.bold is True
        assert sheet.freeze_panes == "A2"
        assert sheet.auto_filter.ref is not None
        workbook.close()

    def test_unit_column_has_dropdown_validation(self, template_path: Path) -> None:
        workbook = load_workbook(template_path)
        sheet = workbook[TEMPLATE_SHEET_NAME]
        validations = list(sheet.data_validations.dataValidation)
        assert any(
            "m,kg,t" in str(validation.formula1) for validation in validations
        )
        workbook.close()

    def test_template_rejects_non_xlsx_extension(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="xlsx"):
            build_metraj_template(tmp_path / "metraj.xls")

    def test_template_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "tekrar.xlsx"
        build_metraj_template(target)
        first = target.stat().st_size
        build_metraj_template(target)
        assert target.exists()
        assert target.stat().st_size > 0
        assert first > 0


class TestTemplateRoundTrip:
    """Şablon → okuyucu: iki taraf aynı sözleşmeyi kullanmalı."""

    def test_template_can_be_read_back(self, template_path: Path) -> None:
        result = read_metraj(template_path)
        assert result.sheet_name == TEMPLATE_SHEET_NAME
        assert set(result.column_index) == set(TEMPLATE_COLUMNS)

    def test_template_examples_are_all_valid(self, template_path: Path) -> None:
        result = read_metraj(template_path)
        assert result.invalid_count == 0
        assert result.valid_count == len(TEMPLATE_EXAMPLE_ROWS)

    def test_template_examples_keep_values(self, template_path: Path) -> None:
        result = read_metraj(template_path)
        first = result.row_for("ORNEK-001")
        assert first is not None
        assert first.quantity == Decimal("96")
        assert first.unit_value is not None
        assert first.unit_value.value == "m"
        assert first.waste_percent == Decimal("5")

    def test_template_empty_waste_stays_none(self, template_path: Path) -> None:
        """Boş fire sıfır olarak okunmamalı."""
        result = read_metraj(template_path)
        row = result.row_for("ORNEK-004")
        assert row is not None
        assert row.waste_percent is None
        assert row.has_waste is False

    def test_template_has_no_ignored_columns(self, template_path: Path) -> None:
        result = read_metraj(template_path)
        assert result.ignored_columns == ()

    def test_template_rows_start_at_row_two(self, template_path: Path) -> None:
        result = read_metraj(template_path)
        assert [row.source_row for row in result.rows] == [2, 3, 4, 5]
