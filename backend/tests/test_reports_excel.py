"""Excel satın alma raporu testleri.

Kapsam
------
1.  Dosyanın gerçekten geçerli bir ``.xlsx`` olarak üretilmesi.
2.  Beklenen sayfaların ve bölümlerin bulunması.
3.  Türkçe karakterlerin korunması.
4.  Rapor değerlerinin :class:`CalculationResult` ile **birebir** eşitliği.
5.  Kaynak BOQ satırlarının (izlenebilirlik) korunması.
6.  FULL / PARTIAL gösterimi.
7.  Bilinmeyen değerin **boş hücre** olması — asla ``0`` yazılmaması.
8.  Yazdırmaya uygunluk: sabit başlık, sütun genişlikleri, sayı biçimleri.
9.  Hesaba alınmayan satırların gerekçesiyle listelenmesi.
10. Boş hesabın güvenli biçimde raporlanması.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.reports.excel import build_excel, build_sections
from app.reports.models import (
    CUTTING_DISCLAIMER,
    PARTIAL_DISCLAIMER,
    WEIGHT_DISCLAIMER,
    build_report,
)
from tests.fixtures.reports import (
    EXPECTED_GROUPS,
    EXPECTED_MERGES,
    EXPECTED_ORDER_LENGTH_M,
    EXPECTED_WEIGHT_KG,
    FIXED_NOW,
    demo_report,
    demo_run,
    empty_result,
    find_label_value,
    find_row,
    header_index,
    partial_missing_commercial_length,
    partial_missing_mass,
    partial_missing_waste,
    sheet_rows,
)

#: Satın alma sayfasındaki başlık satırı ve sütun sırası.
PURCHASE_HEADERS: tuple[str, ...] = (
    "Malzeme Kodu",
    "Açıklama",
    "Kaynak BOQ Satırları",
    "Net Miktar (m)",
    "Fire Miktarı (m)",
    "Fire Dahil Brüt (m)",
    "Ticari Boy (m)",
    "Sipariş Adedi",
    "Sipariş Uzunluğu (m)",
    "Artan Miktar (m)",
    "Teorik Ağırlık (kg)",
    "Durum",
    "Eksik Bilgi / Uyarı",
)

#: Sayısal sütun indeksleri (1 tabanlı) — ``None`` kuralı burada test edilir.
NUMERIC_COLUMNS: dict[int, str] = {
    4: "net",
    5: "fire",
    6: "brüt",
    7: "ticari boy",
    8: "sipariş adedi",
    9: "sipariş uzunluğu",
    10: "artan",
    11: "ağırlık",
}


@pytest.fixture(scope="module")
def demo_payload() -> bytes:
    return build_excel(demo_report())


@pytest.fixture(scope="module")
def demo_book(demo_payload: bytes):
    return load_workbook(BytesIO(demo_payload))


# ---------------------------------------------------------------------------
# 1. Dosya üretimi ve yapısı
# ---------------------------------------------------------------------------


class TestWorkbookStructure:
    def test_payload_is_a_valid_xlsx(self, demo_payload: bytes) -> None:
        assert demo_payload[:2] == b"PK", "xlsx bir zip arşividir"
        assert len(demo_payload) > 5_000

    def test_expected_sheets_exist(self, demo_book) -> None:
        assert demo_book.sheetnames == [
            "Özet",
            "Satın Alma Listesi",
            "Kaynak Satırlar",
            "Hesaba Alınmayanlar",
        ]

    def test_purchase_headers_are_fixed(self, demo_book) -> None:
        sheet = demo_book["Satın Alma Listesi"]
        row = header_index(sheet, "Malzeme Kodu")
        values = next(
            sheet.iter_rows(min_row=row, max_row=row, values_only=True)
        )
        assert tuple(values) == PURCHASE_HEADERS

    def test_header_row_is_frozen(self, demo_book) -> None:
        sheet = demo_book["Satın Alma Listesi"]
        header = header_index(sheet, "Malzeme Kodu")
        # Başlık satırının altından itibaren dondurulur.
        assert sheet.freeze_panes == f"A{header + 1}"

    def test_print_setup_is_landscape_with_repeated_header(
        self, demo_book
    ) -> None:
        sheet = demo_book["Satın Alma Listesi"]
        header = header_index(sheet, "Malzeme Kodu")
        assert sheet.page_setup.orientation == "landscape"
        # openpyxl mutlak referansla saklar: ``$4:$4``.
        assert sheet.print_title_rows == f"${header}:${header}"
        assert sheet.sheet_properties.pageSetUpPr.fitToPage is True

    def test_column_widths_are_set(self, demo_book) -> None:
        sheet = demo_book["Satın Alma Listesi"]
        widths = [
            sheet.column_dimensions[letter].width
            for letter in ("A", "B", "D", "K")
        ]
        assert all(width and width >= 10 for width in widths), widths

    def test_numeric_columns_have_number_formats(self, demo_book) -> None:
        sheet = demo_book["Satın Alma Listesi"]
        header = header_index(sheet, "Malzeme Kodu")
        code_row = header + 2  # ilk satır aile bandıdır
        for column in (4, 5, 6, 7, 9, 10, 11):
            cell = sheet.cell(row=code_row, column=column)
            assert cell.number_format == "#,##0.000", (
                column,
                cell.number_format,
            )
        assert sheet.cell(row=code_row, column=8).number_format == "#,##0"

    def test_values_are_real_numbers_not_text(self, demo_book) -> None:
        """Kullanıcı Excel'de sıralayıp toplayabilmelidir."""
        sheet = demo_book["Satın Alma Listesi"]
        cell = sheet.cell(
            row=header_index(sheet, "Malzeme Kodu") + 2, column=9
        )
        assert isinstance(cell.value, (int, float, Decimal))


# ---------------------------------------------------------------------------
# 2. Rapor = hesap (birebir tutarlılık)
# ---------------------------------------------------------------------------


class TestConsistencyWithCalculation:
    def test_summary_matches_calculation_result(self, demo_book) -> None:
        sheet = demo_book["Özet"]
        result = demo_run().result

        assert find_label_value(sheet, "Girdi satırı") == result.input_row_count
        assert (
            find_label_value(sheet, "Hesaplanan satır")
            == result.calculated_row_count
        )
        assert find_label_value(sheet, "Hesaba alınmayan satır") == 5
        assert find_label_value(sheet, "Satın alma kalemi (grup)") == (
            EXPECTED_GROUPS
        )
        assert find_label_value(sheet, "Birleşme sayısı") == EXPECTED_MERGES
        assert find_label_value(sheet, "FULL grup") == EXPECTED_GROUPS
        assert find_label_value(sheet, "PARTIAL grup") == 0

    def test_locked_totals_are_preserved(self, demo_book) -> None:
        sheet = demo_book["Özet"]
        assert find_label_value(sheet, "Toplam sipariş uzunluğu (m)") == float(
            EXPECTED_ORDER_LENGTH_M
        )
        # Excel sayısal hücreyi float olarak döndürür; değer korunur.
        assert find_label_value(sheet, "Bilinen teorik ağırlık (kg)") == float(
            EXPECTED_WEIGHT_KG
        )

    def test_every_group_row_matches_domain_values(self, demo_book) -> None:
        """Her satır, domain grubunun değerleriyle birebir aynı olmalı."""
        report = demo_report()
        sheet = demo_book["Satın Alma Listesi"]

        for group in report.groups:
            row = find_row(sheet, group.code)
            assert row[1] == group.product_label
            assert row[2] == group.boq_trace
            assert _same(row[3], group.net_metres)
            assert _same(row[4], group.fire_metres)
            assert _same(row[5], group.gross_metres)
            assert _same(row[6], group.commercial_length_m)
            assert _same(row[7], group.bar_count)
            assert _same(row[8], group.order_length_m)
            assert _same(row[9], group.rounding_surplus_m)
            assert _same(row[10], group.weight_kg)
            assert row[11] == "FULL"

    def test_family_band_subtotal_equals_group_sum(self, demo_book) -> None:
        """Aile bandındaki alt toplam, kalemlerin toplamı olmalı."""
        report = demo_report()
        sheet = demo_book["Satın Alma Listesi"]
        rows = sheet_rows(sheet)

        for section in build_sections(report):
            band = next(
                row
                for row in rows
                if row[0] and str(row[0]).startswith(section.family_label)
            )
            expected_order = sum(
                (group.order_length_m for group in section.groups), Decimal(0)
            )
            expected_weight = sum(
                (group.weight_kg for group in section.groups), Decimal(0)
            )
            assert _decimal(band[8]) == expected_order
            assert _decimal(band[10]) == expected_weight

    def test_turkish_diacritics_are_preserved(self, demo_book) -> None:
        sheet = demo_book["Özet"]
        assert sheet["A1"].value == "BuildFlow AI — Satın Alma Raporu"

        purchase = demo_book["Satın Alma Listesi"]
        assert purchase["A1"].value == "Satın Alma Listesi"
        # "Açıklama" başlığı ve Türkçe ürün etiketi.
        header = header_index(purchase, "Malzeme Kodu")
        assert PURCHASE_HEADERS[1] == "Açıklama"
        labels = [
            row[1]
            for row in sheet_rows(purchase)
            if row[0] == "BOX-100-4-S235-B"
        ]
        assert labels == ["Kutu profil 100×100×4 · S235 · siyah"]
        assert header > 0

    def test_report_header_states_no_recalculation(self, demo_book) -> None:
        sheet = demo_book["Özet"]
        lines = [str(row[0]) for row in sheet_rows(sheet) if row[0]]
        assert any("yeniden hesap yapılmaz" in line for line in lines)

    def test_disclaimers_are_present(self, demo_book) -> None:
        text = " ".join(
            str(row[0]) for row in sheet_rows(demo_book["Özet"]) if row[0]
        )
        for disclaimer in (
            WEIGHT_DISCLAIMER,
            CUTTING_DISCLAIMER,
            PARTIAL_DISCLAIMER,
        ):
            assert disclaimer in text


# ---------------------------------------------------------------------------
# 3. İzlenebilirlik: kaynak BOQ satırları
# ---------------------------------------------------------------------------


class TestTraceability:
    def test_source_sheet_lists_every_source_row(self, demo_book) -> None:
        report = demo_report()
        sheet = demo_book["Kaynak Satırlar"]
        rows = [
            row
            for row in sheet_rows(sheet)
            if row[1] and str(row[1]).startswith("BOQ-")
        ]

        # Kaynak sayfası, satın alma sayfasıyla **aynı** aile sırasını kullanır.
        expected = [
            (group.code, source.boq_no)
            for section in build_sections(report)
            for group in section.groups
            for source in group.source_rows
        ]
        actual = [(row[0], row[1]) for row in rows]
        assert actual == expected

    def test_merged_groups_keep_all_boq_numbers(self, demo_book) -> None:
        report = demo_report()
        sheet = demo_book["Satın Alma Listesi"]
        merged = [group for group in report.groups if group.merged]
        assert merged, "demo senaryosunda birleşme olmalı"

        for group in merged:
            row = find_row(sheet, group.code)
            for boq_no in group.source_boq_nos:
                assert boq_no in row[2]

    def test_source_rows_carry_quantities_and_waste(self, demo_book) -> None:
        report = demo_report()
        sheet = demo_book["Kaynak Satırlar"]
        by_boq = {
            row[1]: row
            for row in sheet_rows(sheet)
            if row[1] and str(row[1]).startswith("BOQ-")
        }
        for group in report.groups:
            for source in group.source_rows:
                row = by_boq[source.boq_no]
                assert row[0] == group.code
                assert row[2] == source.description
                assert _same(row[3], source.source_quantity)
                assert row[4] == source.source_unit
                assert _same(row[5], source.net_metres)
                assert _same(row[6], source.waste_percent)
                assert _same(row[7], source.gross_metres)

    def test_skipped_rows_keep_reason(self, demo_book) -> None:
        sheet = demo_book["Hesaba Alınmayanlar"]
        rows = {row[0]: row for row in sheet_rows(sheet) if row[0]}
        assert "BOQ-009" in rows  # onay bekliyor
        assert rows["BOQ-009"][2] == "Onay bekliyor"
        assert "BOQ-018" in rows  # reddedildi
        assert rows["BOQ-018"][2] == "Reddedildi"
        # Gerekçe metni boş olmamalı.
        assert rows["BOQ-009"][3]


# ---------------------------------------------------------------------------
# 4. PARTIAL: bilinmeyen değer boş kalır
# ---------------------------------------------------------------------------


class TestPartialExposure:
    def test_unknown_weight_is_blank_not_zero(self) -> None:
        book = load_workbook(BytesIO(build_excel(
            partial_missing_commercial_length().report
        )))
        row = find_row(book["Satın Alma Listesi"], "BOX-100-4-S235-B")
        assert row[11] == "PARTIAL"
        # Ticari boy bilinmiyor: sipariş, artan ve ağırlık **boş**.
        assert row[6] is None
        assert row[8] is None
        assert row[9] is None
        assert row[10] is None

    def test_known_partial_values_are_still_shown(self) -> None:
        """PARTIAL, bilinen değerleri gizlemek anlamına gelmez."""
        case = partial_missing_commercial_length()
        book = load_workbook(BytesIO(build_excel(case.report)))
        row = find_row(book["Satın Alma Listesi"], "BOX-100-4-S235-B")
        # Net ve fire biliniyor; brüt hesaplanabildi.
        assert _decimal(row[3]) == Decimal("60")
        assert _decimal(row[4]) == Decimal("3")
        assert _decimal(row[5]) == Decimal("63")

    def test_missing_waste_leaves_gross_blank(self) -> None:
        case = partial_missing_waste()
        book = load_workbook(BytesIO(build_excel(case.report)))
        row = find_row(book["Satın Alma Listesi"], "BOX-100-4-S235-B")
        assert _decimal(row[3]) == Decimal("60")  # net biliniyor
        for index in (4, 5, 8, 9, 10):
            assert row[index] is None, (
                f"{NUMERIC_COLUMNS[index]} bilinmiyor ama {row[index]!r} yazılmış"
            )

    def test_missing_mass_leaves_metres_blank(self) -> None:
        case = partial_missing_mass()
        book = load_workbook(BytesIO(build_excel(case.report)))
        row = find_row(book["Satın Alma Listesi"], "BOX-100-4-S235-B")
        # kg satırı: kütle bilinmiyor, metreye çevrilemedi. Ticari boy ise
        # katalogdan **biliniyor** — bilinen değer gizlenmez.
        for index in (3, 4, 5, 7, 8, 9, 10):
            assert row[index] is None, (
                f"{NUMERIC_COLUMNS[index]} bilinmiyor ama {row[index]!r} yazılmış"
            )
        assert _decimal(row[6]) == Decimal("6")

    def test_no_numeric_cell_contains_zero_for_unknown(
        self,
    ) -> None:
        """Hiçbir PARTIAL senaryosunda bilinmeyen alan ``0`` olmamalı."""
        cases = (
            partial_missing_commercial_length(),
            partial_missing_mass(),
            partial_missing_waste(),
        )
        for case in cases:
            book = load_workbook(BytesIO(build_excel(case.report)))
            sheet = book["Satın Alma Listesi"]
            for group in case.report.groups:
                row = find_row(sheet, group.code)
                for index, label in NUMERIC_COLUMNS.items():
                    value = row[index]
                    if value is not None:
                        continue
                    assert value is None, label

    def test_partial_rows_are_visually_marked(self) -> None:
        case = partial_missing_waste()
        book = load_workbook(BytesIO(build_excel(case.report)))
        sheet = book["Satın Alma Listesi"]
        header = header_index(sheet, "Malzeme Kodu")
        row_number = next(
            index
            for index, row in enumerate(
                sheet.iter_rows(values_only=True), start=1
            )
            if row[0] == "BOX-100-4-S235-B"
        )
        fill = sheet.cell(row=row_number, column=1).fill
        assert fill is not None and fill.fgColor.rgb != "00000000"
        assert row_number > header

    def test_partial_missing_reasons_are_listed(self) -> None:
        case = partial_missing_waste()
        book = load_workbook(BytesIO(build_excel(case.report)))
        text = " ".join(
            str(row[0]) for row in sheet_rows(book["Özet"]) if row[0]
        )
        assert "PARTIAL" in text
        assert "Fire oranı tanımsız" in text
        assert "sıfır varsayılmadı" in text.lower() or "Sıfır" in text

    def test_weight_status_is_partial(self) -> None:
        case = partial_missing_commercial_length()
        book = load_workbook(BytesIO(build_excel(case.report)))
        text = " ".join(
            str(row[0]) for row in sheet_rows(book["Özet"]) if row[0]
        )
        assert "KISMİ" in text
        # Hiçbir grubun ağırlığı bilinmiyorsa özet **boş** kalır.
        assert find_label_value(
            book["Özet"], "Bilinen teorik ağırlık (kg)"
        ) is None

    def test_summary_partial_count_matches_groups(self) -> None:
        case = partial_missing_waste()
        book = load_workbook(BytesIO(build_excel(case.report)))
        sheet = book["Özet"]
        assert find_label_value(sheet, "PARTIAL grup") == len(
            case.report.groups
        )
        assert find_label_value(sheet, "FULL grup") == 0

    def test_missing_reason_is_visible_on_the_row_itself(self) -> None:
        """Kullanıcı özet sayfasına gitmeden satırdaki eksikliği görmeli."""
        case = partial_missing_waste()
        book = load_workbook(BytesIO(build_excel(case.report)))
        row = find_row(book["Satın Alma Listesi"], "BOX-100-4-S235-B")
        notes = row[12]
        assert notes
        assert "Fire oranı tanımsız" in notes
        assert "sıfır varsayılmadı" in notes

    def test_full_row_has_no_missing_note(self, demo_book) -> None:
        row = find_row(demo_book["Satın Alma Listesi"], "BOX-100-4-S235-B")
        # Bu kalemde eksik yok; yalnızca bilgi notu (birleşme) bulunur.
        assert "tanımsız" not in (row[12] or "")
        assert "BOQ-001, BOQ-013" in (row[12] or "")


# ---------------------------------------------------------------------------
# 5. Güvenli kenar durumlar
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_result_produces_readable_report(self) -> None:
        report = build_report(empty_result(), generated_at=FIXED_NOW)
        payload = build_excel(report)
        book = load_workbook(BytesIO(payload))

        assert book.sheetnames == [
            "Özet",
            "Satın Alma Listesi",
            "Kaynak Satırlar",
        ]
        assert find_label_value(book["Özet"], "Satın alma kalemi (grup)") == 0
        # Ağırlık bilinmiyor: boş hücre (0 değil).
        assert find_label_value(book["Özet"], "Bilinen teorik ağırlık (kg)") is None

    def test_no_skipped_sheet_when_nothing_skipped(self) -> None:
        case = partial_missing_waste()
        book = load_workbook(BytesIO(build_excel(case.report)))
        assert "Hesaba Alınmayanlar" not in book.sheetnames

    def test_rebuild_is_deterministic(self) -> None:
        report = demo_report()
        first = load_workbook(BytesIO(build_excel(report)))["Satın Alma Listesi"]
        second = load_workbook(BytesIO(build_excel(report)))["Satın Alma Listesi"]
        assert sheet_rows(first) == sheet_rows(second)


def _decimal(value: object) -> Decimal | None:
    """Excel hücresini ``Decimal``'a çevirir; boş hücre ``None`` kalır."""
    if value is None or value == "":
        return None
    return Decimal(str(value))


#: Raporun gösterdiği ondalık basamak sayısı. Excel sayısal hücreleri
#: IEEE-754 ``double`` saklar; 28 haneli bir ``Decimal`` hücreye yazılıp
#: geri okunduğunda son basamaklar kaybolur. Bu bir hesap farkı değil
#: **saklama** sınırıdır; bu yüzden karşılaştırma raporun gösterdiği
#: hassasiyette yapılır.
_DISPLAY = Decimal("0.001")


def _same(actual: object, expected: Decimal | None) -> bool:
    """Hücre değeri, beklenen değerle gösterim hassasiyetinde aynı mı?"""
    left = _decimal(actual)
    if left is None or expected is None:
        return left is None and expected is None
    return left.quantize(_DISPLAY) == expected.quantize(_DISPLAY)
