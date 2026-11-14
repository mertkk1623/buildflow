"""PDF satın alma raporu üretimi.

Neden fpdf2?
------------
* Saf Python; Windows/macOS/Linux'ta derleme gerektirmez (``reportlab`` gibi
  ağır bağımlılık yok, ``weasyprint`` gibi sistem kütüphanesi istemez).
* Gömülü TTF desteği vardır: Türkçe karakterler için projeye dahil edilmiş
  DejaVu Sans kullanılır, sistem fontlarına bağımlı kalınmaz.
* Lisansı LGPL (fpdf2) / serbest font (DejaVu, Bitstream Vera türevi).

Tasarım
-------
1. **Tek veri kaynağı** :class:`app.reports.models.Report`. Hesaplama yok.
2. **Bilinmeyen değer** hücrede ``—`` olarak gösterilir; ``0`` yazılmaz.
3. Tablo başlıkları her sayfada yinelenir, sayfa numarası altta verilir.
4. PARTIAL kalemler sarı zeminle ve ``PARTIAL`` etiketiyle işaretlenir.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Final

from fpdf import FPDF

from app.reports.formatting import (
    METRE_PLACES,
    WEIGHT_PLACES,
    display_or_placeholder,
    format_decimal,
    format_datetime,
    format_integer,
)
from app.reports.models import Report, ReportGroup

#: Gömülü font dizini (paket içinde taşınır; sistem fontu kullanılmaz).
FONT_DIR: Final = Path(__file__).resolve().parent / "fonts"

_REGULAR = "DejaVu"
_BOLD = "DejaVuBold"

# --- Renkler (R, G, B) -----------------------------------------------------
_NAVY: Final = (31, 56, 100)
_ACCENT: Final = (46, 92, 138)
_MUTED: Final = (90, 100, 114)
_RULE: Final = (185, 195, 209)
_BAND: Final = (232, 237, 245)
_PARTIAL_BG: Final = (255, 242, 204)
_PARTIAL_INK: Final = (150, 90, 0)
_WARN_INK: Final = (166, 67, 26)
_WHITE: Final = (255, 255, 255)

#: A4 yatay gövde genişliği (mm) ve kenar boşluğu.
_MARGIN: Final = 12.0
_PAGE_WIDTH: Final = 297.0
_BODY_WIDTH: Final = _PAGE_WIDTH - 2 * _MARGIN

#: Satın alma tablosunda tek satır yüksekliği (mm) — sayfa bölünmesi bu
#: değere göre hesaplanır.
_ROW_HEIGHT: Final = 6.2

#: "Hesaba Alınmayan Satırlar" tablosu için satır ölçüleri (mm).
#: Satır yüksekliği sabit değildir: içeriğe göre ölçülür.
_SKIPPED_LINE_HEIGHT: Final = 4.2
_SKIPPED_MIN_ROW_HEIGHT: Final = 6.0
#: Hücre içi dikey nefes payı — metin çizgilere değmesin.
_SKIPPED_CELL_PAD: Final = 1.6


class ReportPdf(FPDF):
    """Sayfa altbilgisi (sayfa numarası) ve başlık tekrarı ekleyen PDF.

    ``fpdf2`` altbilgiyi her sayfa eklendiğinde çağırır; böylece sayfa sayısı
    bilinmeden "3 / 7" gibi bir numara üretilebilir.
    """

    def __init__(self, *, title: str, generated_at_text: str) -> None:
        super().__init__(orientation="landscape", unit="mm", format="A4")
        self._doc_title = title
        self._generated_at_text = generated_at_text
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.alias_nb_pages()

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(_REGULAR, size=7.5)
        self.set_text_color(*_MUTED)
        # Sol: belge kimliği. Sağ: sayfa numarası. İkisi çakışmasın diye
        # sabit genişlikler kullanılır (``set_x(-n)`` taşmaya yol açıyordu).
        page_label = f"Sayfa {self.page_no()} / {{nb}}"
        label_width = 32.0
        self.cell(
            _BODY_WIDTH - label_width,
            5,
            f"{self._doc_title} · {self._generated_at_text}",
            align="L",
        )
        self.cell(label_width, 5, page_label, align="R")


def build_pdf(report: Report) -> bytes:
    """Raporu PDF baytlarına çevirir."""
    generated_text = format_datetime(report.generated_at)
    pdf = ReportPdf(
        title="BuildFlow AI — Satın Alma Raporu",
        generated_at_text=generated_text,
    )
    pdf.add_font(_REGULAR, "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font(_BOLD, "", str(FONT_DIR / "DejaVuSans-Bold.ttf"))

    pdf.add_page()
    _write_title(pdf, report, generated_text)
    _write_summary(pdf, report)
    _write_notes(pdf, report)
    _write_purchase_table(pdf, report)

    if report.skipped:
        pdf.add_page()
        _write_skipped(pdf, report)

    _write_disclaimers(pdf, report)

    buffer = BytesIO()
    output = pdf.output()
    # ``fpdf2`` sürümüne göre ``bytearray`` veya ``bytes`` döner.
    buffer.write(bytes(output))
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Bölümler
# ---------------------------------------------------------------------------


def _write_title(pdf: ReportPdf, report: Report, generated_text: str) -> None:
    pdf.set_font(_BOLD, size=17)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 9, "Satın Alma Raporu", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(_REGULAR, size=8.5)
    pdf.set_text_color(*_MUTED)
    pdf.cell(
        0,
        4.5,
        f"Rapor tarihi: {generated_text} · BuildFlow AI",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        4.5,
        "Tüm değerler sunucudaki doğrulanmış hesaplama sonucundan alınmıştır; "
        "PDF üretiminde yeniden hesap yapılmaz.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)


def _write_summary(pdf: ReportPdf, report: Report) -> None:
    summary = report.summary
    _section(pdf, "Özet")

    # 4 sütunlu özet bloğu: etiket/değer çiftleri.
    pairs: tuple[tuple[str, str], ...] = (
        ("Girdi satırı", str(summary.input_rows)),
        ("Hesaplanan satır", str(summary.calculated_rows)),
        ("Hesaba alınmayan", str(summary.skipped_rows)),
        ("Satın alma kalemi", str(summary.group_count)),
        ("Birleşen grup", str(summary.merged_group_count)),
        ("Birleşme", str(summary.merge_count)),
        ("FULL grup", str(summary.full_groups)),
        ("PARTIAL grup", str(summary.partial_groups)),
        (
            "Toplam sipariş uzunluğu",
            f"{display_or_placeholder(format_decimal(summary.total_order_length_m, METRE_PLACES))} m",
        ),
        (
            "Bilinen teorik ağırlık",
            (
                f"{format_decimal(summary.known_weight_kg, WEIGHT_PLACES)} kg"
                if summary.has_known_weight
                else "—"
            ),
        ),
        (
            "Ağırlık durumu",
            "Tam" if summary.weight_complete else "KISMİ",
        ),
    )

    column_width = _BODY_WIDTH / 4
    row_height = 7.2
    index = 0
    for _ in range((len(pairs) + 3) // 4):
        for _ in range(4):
            if index >= len(pairs):
                break
            label, value = pairs[index]
            x = _MARGIN + (index % 4) * column_width
            y = pdf.get_y()
            pdf.set_xy(x, y)
            pdf.set_font(_REGULAR, size=7.4)
            pdf.set_text_color(*_MUTED)
            pdf.cell(column_width, 3.8, label, align="L")
            pdf.set_xy(x, y + 3.4)
            pdf.set_font(_BOLD, size=9.6)
            pdf.set_text_color(*_NAVY)
            pdf.cell(column_width, 4.4, value, align="L")
            index += 1
        pdf.set_y(pdf.get_y() + row_height)

    if not summary.weight_complete:
        pdf.set_font(_REGULAR, size=8)
        pdf.set_text_color(*_PARTIAL_INK)
        pdf.multi_cell(
            0,
            4.2,
            "Ağırlık toplamı KISMİ: ağırlığı hesaplanamayan gruplar toplama "
            "dahil edilmemiştir.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.ln(1.5)


def _write_notes(pdf: ReportPdf, report: Report) -> None:
    """Uyarılar ve PARTIAL gerekçeleri — görünür biçimde."""
    if not report.warnings and not report.has_partial:
        return

    _section(pdf, "Uyarılar ve eksik bilgiler")
    pdf.set_font(_REGULAR, size=7.8)

    if report.warnings:
        pdf.set_text_color(*_WARN_INK)
        for text in report.warnings:
            pdf.multi_cell(
                0,
                4.0,
                f"• {text}",
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.ln(0.8)

    for group in report.groups:
        if group.is_full:
            continue
        pdf.set_text_color(*_PARTIAL_INK)
        pdf.set_font(_BOLD, size=7.8)
        pdf.multi_cell(
            0,
            4.0,
            f"{group.code} — PARTIAL",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_font(_REGULAR, size=7.6)
        for message in group.missing_messages:
            pdf.multi_cell(
                0,
                3.8,
                f"   {message}",
                new_x="LMARGIN",
                new_y="NEXT",
            )
    pdf.ln(1.5)


def _write_purchase_table(pdf: ReportPdf, report: Report) -> None:
    _section(pdf, "Satın Alma Listesi")

    columns = _purchase_columns()
    header_height = 9.0

    def header() -> None:
        pdf.set_font(_BOLD, size=6.9)
        pdf.set_text_color(*_WHITE)
        pdf.set_fill_color(*_NAVY)
        for title, width, align in columns:
            pdf.cell(width, header_height, title, border=0, align=align, fill=True)
        pdf.ln(header_height)
        pdf.set_draw_color(*_RULE)
        pdf.set_line_width(0.15)

    header()

    for group in report.groups:
        # Sayfa sonunda satırı bölmemek için önce yer kontrolü. Yeni sayfaya
        # geçildiğinde tablo başlığı **yinelenir**; aksi hâlde devam eden
        # sayfadaki sütunlar başlıksız kalır ve tablo okunamaz.
        if pdf.get_y() + _ROW_HEIGHT > pdf.h - 20:
            pdf.add_page()
            header()
        _purchase_row(pdf, group, columns)

    # Tablo altı çizgisi
    y = pdf.get_y()
    pdf.set_draw_color(*_RULE)
    pdf.line(_MARGIN, y, _MARGIN + _BODY_WIDTH, y)
    pdf.ln(2)


def _purchase_columns() -> tuple[tuple[str, float, str], ...]:
    """(başlık, genişlik, hizalama) — toplam gövde genişliğine eşit.

    En uzun katalog kodu (``BOX-150-100-5-S235-B`` ≈ 31 mm, 6.8 pt bold)
    kesilmemelidir: malzeme kodu kimliğin kendisidir. Bu yüzden kod sütunu
    ölçülerek geniş tutulur.
    """
    return (
        ("Malzeme Kodu", 34.0, "L"),
        ("Açıklama", 62.0, "L"),
        ("Kaynak BOQ", 29.0, "L"),
        ("Net (m)", 16.0, "R"),
        ("Fire (m)", 16.0, "R"),
        ("Brüt (m)", 17.0, "R"),
        ("Boy (m)", 12.0, "R"),
        ("Adet", 10.0, "R"),
        ("Sipariş (m)", 20.0, "R"),
        ("Artan (m)", 15.0, "R"),
        ("Ağırlık (kg)", 25.0, "R"),
        ("Durum", 17.0, "C"),
    )


def _fit_text(pdf: ReportPdf, text: str, width: float) -> str:
    """Metni hücre genişliğine sığdırır; taşarsa sonuna ``…`` koyar.

    Bu bir hesap değil **yerleşim** kuralıdır: uzun bir ürün açıklaması
    komşu sütuna taşarak tabloyu okunamaz hâle getirmemelidir.
    """
    if not text:
        return text
    available = width - 2.0  # hücre içi nefes payı
    if pdf.get_string_width(text) <= available:
        return text
    ellipsis = "…"
    trimmed = text
    while trimmed and pdf.get_string_width(trimmed + ellipsis) > available:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis


def _purchase_row(
    pdf: ReportPdf, group: ReportGroup, columns: tuple[tuple[str, float, str], ...]
) -> None:
    height = _ROW_HEIGHT
    fill = not group.is_full
    if fill:
        pdf.set_fill_color(*_PARTIAL_BG)
    else:
        pdf.set_fill_color(*_WHITE)

    values: tuple[str, ...] = (
        group.code,
        group.product_label,
        group.boq_trace,
        display_or_placeholder(format_decimal(group.net_metres, METRE_PLACES)),
        display_or_placeholder(format_decimal(group.fire_metres, METRE_PLACES)),
        display_or_placeholder(format_decimal(group.gross_metres, METRE_PLACES)),
        display_or_placeholder(
            format_decimal(group.commercial_length_m, METRE_PLACES)
        ),
        display_or_placeholder(format_integer(group.bar_count)),
        display_or_placeholder(format_decimal(group.order_length_m, METRE_PLACES)),
        display_or_placeholder(
            format_decimal(group.rounding_surplus_m, METRE_PLACES)
        ),
        display_or_placeholder(format_decimal(group.weight_kg, WEIGHT_PLACES)),
        group.status_label,
    )

    for (_, width, align), value in zip(columns, values, strict=True):
        is_code = value is group.code
        is_status = value == group.status_label
        if fill and is_status:
            ink = _PARTIAL_INK
        elif is_code:
            ink = _NAVY
        else:
            ink = (0, 0, 0)
        pdf.set_font(_BOLD if is_code else _REGULAR, size=6.8)
        pdf.set_text_color(*ink)
        # Sığdırma, yazı tipi **ayarlandıktan sonra** yapılmalı: metin
        # genişliği seçili fonta göre ölçülür.
        pdf.cell(
            width,
            height,
            _fit_text(pdf, value, width),
            border=0,
            align=align,
            fill=fill,
        )
    pdf.ln(height)


def _write_skipped(pdf: ReportPdf, report: Report) -> None:
    _section(pdf, "Hesaba Alınmayan Satırlar")
    pdf.set_font(_REGULAR, size=7.6)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        4.0,
        "Bu satırlar satın alma listesine girmez; nedenleri izlenebilirlik "
        "için korunmuştur.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(1)

    columns = _skipped_columns()
    header_height = 8.0

    def header() -> None:
        pdf.set_font(_BOLD, size=7.2)
        pdf.set_text_color(*_WHITE)
        pdf.set_fill_color(*_NAVY)
        for title, width, align in columns:
            pdf.cell(width, header_height, title, align=align, fill=True)
        pdf.ln(header_height)
        pdf.set_draw_color(*_RULE)
        pdf.set_line_width(0.15)

    header()

    # Alt sınır: tablo gövdesinin son satırı bu çizgiyi geçmemeli.
    bottom_limit = pdf.h - 20

    for item in report.skipped:
        values = (
            item.boq_no,
            item.description or "—",
            item.reason_label,
            item.exclusion_reason_label or "—",
            item.message,
        )
        height = _skipped_row_height(pdf, columns, values)

        # Satır sığmıyorsa yeni sayfaya geç ve başlığı **yineler**. Böylece
        # devam eden sayfada sütunlar başlıksız kalmaz. Döngü satır başına bir
        # kez döndüğü için sonsuz döngü riski yoktur; tek satır tam sayfaya
        # sığmasa bile yeni sayfadan başlamak en fazla yeri verir.
        if pdf.get_y() + height > bottom_limit:
            pdf.add_page()
            header()

        _skipped_row(pdf, columns, values, height)


def _skipped_columns() -> tuple[tuple[str, float, str], ...]:
    """Hesaba alınmayan satırlar tablosunun sütunları.

    Genişlikler toplamı gövde genişliğine eşittir:
    ``20 + 58 + 28 + 34 + (BODY - 140) == BODY``.
    """
    return (
        ("BOQ No", 20.0, "L"),
        ("Açıklama", 58.0, "L"),
        ("Durum", 28.0, "L"),
        ("Neden kodu", 34.0, "L"),
        ("Neden", _BODY_WIDTH - 140.0, "L"),
    )


def _skipped_row_height(
    pdf: ReportPdf,
    columns: tuple[tuple[str, float, str], ...],
    values: tuple[str, ...],
) -> float:
    """Satır yüksekliğini **içeriğe göre** hesaplar.

    Her hücre kendi genişliğinde, gerçek fontla ve kuru çalıştırmayla
    (``dry_run``) ölçülür; en uzun hücre satırın yüksekliğini belirler.
    Böylece uzun bir neden metni komşu satırın üzerine binmez.
    """
    pdf.set_font(_REGULAR, size=7.2)
    tallest = _SKIPPED_MIN_ROW_HEIGHT
    for (_, width, _), value in zip(columns, values, strict=True):
        text = str(value) if value else ""
        if not text:
            continue
        measured = pdf.multi_cell(
            width,
            _SKIPPED_LINE_HEIGHT,
            text,
            dry_run=True,
            output="HEIGHT",
            max_line_height=_SKIPPED_LINE_HEIGHT,
        )
        tallest = max(tallest, float(measured) + _SKIPPED_CELL_PAD)
    return tallest


def _skipped_row(
    pdf: ReportPdf,
    columns: tuple[tuple[str, float, str], ...],
    values: tuple[str, ...],
    height: float,
) -> None:
    """Tek satırı çizer: her hücre kendi içinde kaydırılır, satır yüksekliği ortak."""
    x = pdf.l_margin
    y = pdf.get_y()
    pdf.set_font(_REGULAR, size=7.2)
    pdf.set_text_color(0, 0, 0)
    for (_, width, align), value in zip(columns, values, strict=True):
        pdf.set_xy(x, y)
        pdf.multi_cell(
            width,
            _SKIPPED_LINE_HEIGHT,
            str(value or ""),
            align=align,
            border=0,
            new_x="RIGHT",
            # ``new_y="TOP"`` yalnızca hücre içinde kullanılır: imleci hücre
            # tepesinde tutar, satır sonunda konum aşağıda açıkça ayarlanır.
            new_y="TOP",
            max_line_height=_SKIPPED_LINE_HEIGHT,
        )
        x += width
    pdf.set_y(y + height)


def _write_disclaimers(pdf: ReportPdf, report: Report) -> None:
    if pdf.get_y() + 26 > pdf.h - 20:
        pdf.add_page()
    _section(pdf, "Açıklamalar ve sınırlar")
    pdf.set_font(_REGULAR, size=7.2)
    pdf.set_text_color(*_MUTED)
    for text in report.disclaimers:
        pdf.multi_cell(0, 3.8, f"• {text}", new_x="LMARGIN", new_y="NEXT")


def _section(pdf: ReportPdf, title: str) -> None:
    pdf.set_font(_BOLD, size=10.5)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.3)
    pdf.line(_MARGIN, y, _MARGIN + _BODY_WIDTH, y)
    pdf.ln(2.4)


__all__ = ["FONT_DIR", "ReportPdf", "build_pdf"]
