"""Excel satın alma raporu üretimi.

Tasarım kararları
-----------------
1. **Tek veri kaynağı** :class:`app.reports.models.Report` nesnesidir. Bu modül
   hiçbir miktar, fire, ağırlık veya ticari boy hesabı yapmaz; yalnızca yazar.
2. **Bilinmeyen değer = boş hücre.** ``None`` hücreye yazılmaz. ``0`` yazmak
   PARTIAL sonucu yanlış gösterirdi; bu yüzden asla sıfır konmaz.
3. **Malzemeler aile bazında gruplanır.** Her aile bir bant satırıyla başlar ve
   altında o ailenin kalemleri listelenir; bant satırında aile alt toplamı
   (sipariş metresi ve ağırlık) bulunur.
4. **Sayılar gerçek sayı hücresidir** (metin değil), böylece kullanıcı Excel'de
   sıralayabilir ve toplayabilir. Görünen basamak sayısı ``number_format`` ile
   belirlenir.
5. **Yazdırmaya uygun:** yatay yönlendirme, tekrarlanan başlık satırı,
   sabitlenmiş üst bölme, sığdırılmış genişlik.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from typing import Final

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.reports.formatting import (
    MASS_PLACES,
    METRE_PLACES,
    PERCENT_PLACES,
    WEIGHT_PLACES,
    format_datetime,
)
from app.reports.models import Report, ReportGroup

# --- Görsel sabitler -------------------------------------------------------
_NAVY: Final = "1F3864"
_ACCENT: Final = "2E5C8A"
_BAND: Final = "E8EDF5"
_PARTIAL: Final = "FFF2CC"
_MUTED: Final = "5A6472"
_RULE: Final = "B9C3D1"
_SECTION: Final = "DCE4F0"

_THIN = Side(style="thin", color=_RULE)
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

_TITLE_FONT = Font(name="Calibri", size=16, bold=True, color=_NAVY)
_SUBTITLE_FONT = Font(name="Calibri", size=10, color=_MUTED)
_HEADER_FONT = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
_BAND_FONT = Font(name="Calibri", size=9, bold=True, color=_NAVY)
_BODY_FONT = Font(name="Calibri", size=9)
_BODY_BOLD = Font(name="Calibri", size=9, bold=True)
_NOTE_FONT = Font(name="Calibri", size=8, italic=True, color=_MUTED)

_HEADER_FILL = PatternFill("solid", fgColor=_NAVY)
_BAND_FILL = PatternFill("solid", fgColor=_BAND)
_PARTIAL_FILL = PatternFill("solid", fgColor=_PARTIAL)
_SECTION_FILL = PatternFill("solid", fgColor=_SECTION)

_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
_RIGHT = Alignment(horizontal="right", vertical="center")

# --- Sayı biçimleri (Türkçe Excel görünümü) --------------------------------
_FMT_M = "#,##0.000"
_FMT_KG = "#,##0.000"
_FMT_INT = "#,##0"
_FMT_PCT = "0.00"

#: Satın alma listesi sütunları: (başlık, genişlik, hizalama, biçim).
_PURCHASE_COLUMNS: Final[tuple[tuple[str, float, str, str | None], ...]] = (
    ("Malzeme Kodu", 24, "left", None),
    ("Açıklama", 40, "left", None),
    ("Kaynak BOQ Satırları", 22, "left", None),
    ("Net Miktar (m)", 13, "right", _FMT_M),
    ("Fire Miktarı (m)", 13, "right", _FMT_M),
    ("Fire Dahil Brüt (m)", 15, "right", _FMT_M),
    ("Ticari Boy (m)", 12, "right", _FMT_M),
    ("Sipariş Adedi", 12, "right", _FMT_INT),
    ("Sipariş Uzunluğu (m)", 17, "right", _FMT_M),
    ("Artan Miktar (m)", 14, "right", _FMT_M),
    ("Teorik Ağırlık (kg)", 17, "right", _FMT_KG),
    ("Durum", 10, "center", None),
    ("Eksik Bilgi / Uyarı", 52, "left", None),
)

_SOURCE_COLUMNS: Final[tuple[tuple[str, float, str, str | None], ...]] = (
    ("Malzeme Kodu", 24, "left", None),
    ("BOQ No", 12, "left", None),
    ("Açıklama", 42, "left", None),
    ("Kaynak Miktar", 13, "right", _FMT_M),
    ("Birim", 8, "center", None),
    ("Net (m)", 12, "right", _FMT_M),
    ("Fire (%)", 10, "right", _FMT_PCT),
    ("Brüt (m)", 12, "right", _FMT_M),
)

_SKIPPED_COLUMNS: Final[tuple[tuple[str, float, str, str | None], ...]] = (
    ("BOQ No", 12, "left", None),
    ("Açıklama", 42, "left", None),
    ("Durum", 16, "left", None),
    ("Neden kodu", 22, "left", None),
    ("Neden", 56, "left", None),
)


@dataclass(frozen=True, slots=True)
class FamilySection:
    """Bir malzeme ailesinin satın alma kalemleri ve alt toplamı."""

    family_label: str
    groups: tuple[ReportGroup, ...]

    @property
    def order_length_total(self) -> Decimal | None:
        """Aile alt toplamı. Bir kalemin değeri eksikse toplam bilinmiyor."""
        return _sum_or_none(tuple(group.order_length_m for group in self.groups))

    @property
    def weight_total(self) -> Decimal | None:
        return _sum_or_none(tuple(group.weight_kg for group in self.groups))


def build_sections(report: Report) -> tuple[FamilySection, ...]:
    """Kalemleri malzeme ailesine göre gruplar.

    Sıra **deterministik**: aileler ilk görülme sırasına göre, aile içinde
    katalog kodu alfabetik. Böylece aynı hesap her zaman aynı raporu üretir.
    """
    order: list[str] = []
    buckets: dict[str, list[ReportGroup]] = {}
    for group in report.groups:
        if group.family_label not in buckets:
            buckets[group.family_label] = []
            order.append(group.family_label)
        buckets[group.family_label].append(group)

    return tuple(
        FamilySection(
            family_label=label,
            groups=tuple(sorted(buckets[label], key=lambda item: item.code)),
        )
        for label in order
    )


def build_excel(report: Report) -> bytes:
    """Raporu ``.xlsx`` baytlarına çevirir."""
    workbook = Workbook()

    summary_sheet = workbook.active
    summary_sheet.title = "Özet"
    _write_summary(summary_sheet, report)

    purchase_sheet = workbook.create_sheet("Satın Alma Listesi")
    sections = build_sections(report)
    _write_purchase_list(purchase_sheet, report, sections)

    source_sheet = workbook.create_sheet("Kaynak Satırlar")
    _write_source_rows(source_sheet, report, sections)

    if report.skipped:
        skipped_sheet = workbook.create_sheet("Hesaba Alınmayanlar")
        _write_skipped(skipped_sheet, report)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Özet sayfası
# ---------------------------------------------------------------------------


def _write_summary(sheet: Worksheet, report: Report) -> None:
    sheet.sheet_view.showGridLines = False
    sheet.column_dimensions["A"].width = 34
    sheet.column_dimensions["B"].width = 26
    sheet.column_dimensions["C"].width = 3
    sheet.column_dimensions["D"].width = 60

    sheet["A1"] = "BuildFlow AI — Satın Alma Raporu"
    sheet["A1"].font = _TITLE_FONT
    sheet["A2"] = f"Rapor tarihi: {format_datetime(report.generated_at)}"
    sheet["A2"].font = _SUBTITLE_FONT
    sheet["A3"] = (
        "Aşağıdaki değerler sunucudaki doğrulanmış hesaplama sonucundan "
        "alınmıştır; raporda yeniden hesap yapılmaz."
    )
    sheet["A3"].font = _SUBTITLE_FONT

    summary = report.summary
    rows: tuple[tuple[str, str | Decimal | None, str | None], ...] = (
        ("Girdi satırı", summary.input_rows, _FMT_INT),
        ("Hesaplanan satır", summary.calculated_rows, _FMT_INT),
        ("Hesaba alınmayan satır", summary.skipped_rows, _FMT_INT),
        ("Satın alma kalemi (grup)", summary.group_count, _FMT_INT),
        ("Birleşen grup", summary.merged_group_count, _FMT_INT),
        ("Birleşme sayısı", summary.merge_count, _FMT_INT),
        ("FULL grup", summary.full_groups, _FMT_INT),
        ("PARTIAL grup", summary.partial_groups, _FMT_INT),
        ("Toplam sipariş uzunluğu (m)", summary.total_order_length_m, _FMT_M),
        (
            "Bilinen teorik ağırlık (kg)",
            summary.known_weight_kg if summary.has_known_weight else None,
            _FMT_KG,
        ),
    )

    row = 5
    sheet.cell(row=row, column=1, value="Özet").font = Font(
        name="Calibri", size=11, bold=True, color=_NAVY
    )
    row += 1

    for label, value, number_format in rows:
        label_cell = sheet.cell(row=row, column=1, value=label)
        label_cell.font = _BODY_FONT
        label_cell.border = _BORDER

        value_cell = sheet.cell(row=row, column=2, value=value)
        value_cell.font = _BODY_BOLD
        value_cell.border = _BORDER
        value_cell.alignment = _RIGHT
        if number_format is not None:
            value_cell.number_format = number_format
        row += 1

    # Ağırlık bütünlüğü açıkça yazılır: kısmi toplam tam gibi sunulmaz.
    weight_cell = sheet.cell(
        row=row,
        column=1,
        value=(
            "Ağırlık durumu: tam"
            if summary.weight_complete
            else "Ağırlık durumu: KISMİ (ağırlığı hesaplanamayan gruplar toplama dahil edilmedi)"
        ),
    )
    weight_cell.font = _BODY_FONT
    if not summary.weight_complete:
        weight_cell.fill = _PARTIAL_FILL
    row += 2

    # --- Durum dağılımı ---
    sheet.cell(row=row, column=1, value="Durum dağılımı").font = Font(
        name="Calibri", size=11, bold=True, color=_NAVY
    )
    row += 1
    for group in report.groups:
        sheet.cell(row=row, column=1, value=group.code).font = _BODY_FONT
        status_cell = sheet.cell(row=row, column=2, value=group.status_label)
        status_cell.font = _BODY_BOLD
        if not group.is_full:
            status_cell.fill = _PARTIAL_FILL
        row += 1

    # --- Açıklamalar ve uyarılar ---
    row += 1
    sheet.cell(row=row, column=1, value="Açıklamalar ve sınırlar").font = Font(
        name="Calibri", size=11, bold=True, color=_NAVY
    )
    row += 1
    for text in report.disclaimers:
        cell = sheet.cell(row=row, column=1, value=f"• {text}")
        cell.font = _NOTE_FONT
        cell.alignment = _LEFT
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        row += 1

    if report.warnings:
        row += 1
        sheet.cell(row=row, column=1, value="Uyarılar").font = Font(
            name="Calibri", size=11, bold=True, color="A6431A"
        )
        row += 1
        for text in report.warnings:
            cell = sheet.cell(row=row, column=1, value=f"• {text}")
            cell.font = Font(name="Calibri", size=9, color="A6431A")
            cell.alignment = _LEFT
            sheet.merge_cells(
                start_row=row, start_column=1, end_row=row, end_column=4
            )
            row += 1

    if report.has_partial:
        row += 1
        sheet.cell(
            row=row, column=1, value="Eksik bilgi nedeniyle PARTIAL olan kalemler"
        ).font = Font(name="Calibri", size=11, bold=True, color="A6431A")
        row += 1
        for group in report.groups:
            if group.is_full:
                continue
            for message in group.missing_messages:
                cell = sheet.cell(
                    row=row, column=1, value=f"• {group.code}: {message}"
                )
                cell.font = Font(name="Calibri", size=9, color="A6431A")
                cell.alignment = _LEFT
                sheet.merge_cells(
                    start_row=row, start_column=1, end_row=row, end_column=4
                )
                row += 1

    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.sheet_properties.pageSetUpPr.fitToPage = True


# ---------------------------------------------------------------------------
# Satın alma listesi
# ---------------------------------------------------------------------------


def _write_purchase_list(
    sheet: Worksheet, report: Report, sections: tuple[FamilySection, ...]
) -> None:
    last_column = len(_PURCHASE_COLUMNS)

    sheet["A1"] = "Satın Alma Listesi"
    sheet["A1"].font = _TITLE_FONT
    sheet["A2"] = (
        f"{report.group_count} kalem · {len(sections)} malzeme ailesi · "
        f"rapor {format_datetime(report.generated_at)}"
    )
    sheet["A2"].font = _SUBTITLE_FONT

    header_row = 4
    _write_header(sheet, header_row, _PURCHASE_COLUMNS)

    row = header_row + 1
    for section in sections:
        # --- Aile bandı ---
        label = f"{section.family_label} ({len(section.groups)} kalem)"
        band_cell = sheet.cell(row=row, column=1, value=label)
        band_cell.font = _BAND_FONT
        band_cell.fill = _BAND_FILL
        band_cell.alignment = _LEFT
        for column in range(1, last_column + 1):
            sheet.cell(row=row, column=column).fill = _BAND_FILL
            sheet.cell(row=row, column=column).border = _BORDER
        # Alt toplamlar bant satırında: eksikse boş kalır (sıfır yazılmaz).
        _set_number(
            sheet, row, 9, section.order_length_total, _FMT_M, bold=True
        )
        _set_number(sheet, row, 11, section.weight_total, _FMT_KG, bold=True)
        row += 1

        for group in section.groups:
            _write_group_row(sheet, row, group)
            row += 1

    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = (
        f"A{header_row}:{get_column_letter(last_column)}{row - 1}"
    )
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = f"{header_row}:{header_row}"
    sheet.print_options.horizontalCentered = True


def _write_group_row(sheet: Worksheet, row: int, group: ReportGroup) -> None:
    """Tek satın alma kalemini yazar. ``None`` değerler boş hücre olur."""
    values: tuple[object, ...] = (
        group.code,
        group.product_label,
        group.boq_trace,
    )
    for index, value in enumerate(values, start=1):
        cell = sheet.cell(row=row, column=index, value=value)
        cell.font = _BODY_BOLD if index == 1 else _BODY_FONT
        cell.alignment = _LEFT
        cell.border = _BORDER

    _set_number(sheet, row, 4, group.net_metres, _FMT_M)
    _set_number(sheet, row, 5, group.fire_metres, _FMT_M)
    _set_number(sheet, row, 6, group.gross_metres, _FMT_M)
    _set_number(sheet, row, 7, group.commercial_length_m, _FMT_M)
    _set_number(sheet, row, 8, group.bar_count, _FMT_INT)
    _set_number(sheet, row, 9, group.order_length_m, _FMT_M)
    _set_number(sheet, row, 10, group.rounding_surplus_m, _FMT_M)
    _set_number(sheet, row, 11, group.weight_kg, _FMT_KG)

    status_cell = sheet.cell(row=row, column=12, value=group.status_label)
    status_cell.font = _BODY_BOLD
    status_cell.alignment = _CENTER
    status_cell.border = _BORDER

    # Eksik bilgi ve uyarılar satırın kendisinde görünür: kullanıcı özet
    # sayfasına gitmeden hangi kalemin neden eksik olduğunu okuyabilir.
    notes = _group_notes(group)
    notes_cell = sheet.cell(row=row, column=13, value=notes or None)
    notes_cell.font = _NOTE_FONT if group.is_full else Font(
        name="Calibri", size=8, color="A6431A"
    )
    notes_cell.alignment = _LEFT
    notes_cell.border = _BORDER

    if not group.is_full:
        # PARTIAL satır görsel olarak ayırt edilir.
        for column in range(1, len(_PURCHASE_COLUMNS) + 1):
            sheet.cell(row=row, column=column).fill = _PARTIAL_FILL


def _group_notes(group: ReportGroup) -> str:
    """Kalemin eksik bilgilerini ve notlarını tek hücrede birleştirir.

    Metinler **domain'den** geldiği gibi aktarılır; burada üretilmez.
    """
    parts: list[str] = list(group.missing_messages)
    parts.extend(group.notes)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Kaynak satırlar (izlenebilirlik)
# ---------------------------------------------------------------------------


def _write_source_rows(
    sheet: Worksheet, report: Report, sections: tuple[FamilySection, ...]
) -> None:
    sheet["A1"] = "Kaynak BOQ Satırları"
    sheet["A1"].font = _TITLE_FONT
    sheet["A2"] = (
        "Her satın alma kaleminin hangi BOQ satırlarından oluştuğunu gösterir. "
        "Değerler hesaplama sonucundan alınmıştır."
    )
    sheet["A2"].font = _SUBTITLE_FONT

    header_row = 4
    _write_header(sheet, header_row, _SOURCE_COLUMNS)

    row = header_row + 1
    for section in sections:
        for group in section.groups:
            for source in group.source_rows:
                sheet.cell(row=row, column=1, value=group.code).font = _BODY_FONT
                sheet.cell(row=row, column=2, value=source.boq_no).font = _BODY_FONT
                sheet.cell(
                    row=row, column=3, value=source.description
                ).font = _BODY_FONT
                _set_number(sheet, row, 4, source.source_quantity, _FMT_M)
                unit_cell = sheet.cell(
                    row=row, column=5, value=source.source_unit or None
                )
                unit_cell.font = _BODY_FONT
                unit_cell.alignment = _CENTER
                _set_number(sheet, row, 6, source.net_metres, _FMT_M)
                _set_number(sheet, row, 7, source.waste_percent, _FMT_PCT)
                _set_number(sheet, row, 8, source.gross_metres, _FMT_M)
                for column in range(1, len(_SOURCE_COLUMNS) + 1):
                    sheet.cell(row=row, column=column).border = _BORDER
                row += 1

    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = (
        f"A{header_row}:{get_column_letter(len(_SOURCE_COLUMNS))}{row - 1}"
    )
    sheet.page_setup.orientation = "landscape"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = f"{header_row}:{header_row}"


# ---------------------------------------------------------------------------
# Hesaba alınmayanlar
# ---------------------------------------------------------------------------


def _write_skipped(sheet: Worksheet, report: Report) -> None:
    sheet["A1"] = "Hesaba Alınmayan Satırlar"
    sheet["A1"].font = _TITLE_FONT
    sheet["A2"] = (
        "Bu satırlar satın alma listesine girmez; nedenleri izlenebilirlik için "
        "korunur."
    )
    sheet["A2"].font = _SUBTITLE_FONT

    header_row = 4
    _write_header(sheet, header_row, _SKIPPED_COLUMNS)

    row = header_row + 1
    for item in report.skipped:
        sheet.cell(row=row, column=1, value=item.boq_no).font = _BODY_BOLD
        sheet.cell(
            row=row, column=2, value=item.description or None
        ).font = _BODY_FONT
        sheet.cell(row=row, column=3, value=item.reason_label).font = _BODY_FONT
        # "Durum" jeneriktir ("Kapsam dışı"); gerçek neden burada ayrışır.
        sheet.cell(
            row=row, column=4, value=item.exclusion_reason_label or "—"
        ).font = _BODY_FONT
        sheet.cell(row=row, column=5, value=item.message).font = _BODY_FONT
        for column in range(1, len(_SKIPPED_COLUMNS) + 1):
            sheet.cell(row=row, column=column).border = _BORDER
            sheet.cell(row=row, column=column).alignment = _LEFT
        row += 1

    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.page_setup.orientation = "landscape"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _write_header(
    sheet: Worksheet,
    row: int,
    columns: tuple[tuple[str, float, str, str | None], ...],
) -> None:
    for index, (title, width, alignment, _) in enumerate(columns, start=1):
        cell = sheet.cell(row=row, column=index, value=title)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER if alignment != "right" else _CENTER
        cell.border = _BORDER
        sheet.column_dimensions[get_column_letter(index)].width = width

    sheet.row_dimensions[row].height = 30


def _set_number(
    sheet: Worksheet,
    row: int,
    column: int,
    value: Decimal | None,
    number_format: str,
    *,
    bold: bool = False,
) -> None:
    """Sayısal hücre yazar. ``None`` **hiç yazılmaz** (boş kalır).

    Bilinmeyen değere ``0`` yazmak PARTIAL sonucu yanlış gösterirdi.
    """
    cell = sheet.cell(row=row, column=column)
    cell.font = _BODY_BOLD if bold else _BODY_FONT
    cell.alignment = _RIGHT
    cell.border = _BORDER
    if value is None:
        cell.value = None
        return
    cell.value = value
    cell.number_format = number_format


def _sum_or_none(values: tuple[Decimal | None, ...]) -> Decimal | None:
    if not values:
        return None
    total = Decimal(0)
    for value in values:
        if value is None:
            return None
        total += value
    return total


#: Raporun görünen basamak sayıları — PDF ve testler aynı değerleri kullanır.
DISPLAY_PLACES: Final[dict[str, int]] = {
    "metre": METRE_PLACES,
    "agirlik": WEIGHT_PLACES,
    "kutle": MASS_PLACES,
    "yuzde": PERCENT_PLACES,
}


__all__ = [
    "DISPLAY_PLACES",
    "FamilySection",
    "build_excel",
    "build_sections",
]
