"""Standart metraj şablonu (``.xlsx``) üretimi — Aşama 4.3.

Şablon ile okuyucu **aynı** kolon adlarını kullanır
(:class:`app.excel.models.MetrajColumn`). Adlar tek yerden geldiği için
şablonla okuyucunun ayrışması mümkün değildir.

Sayfalar
--------
``Metraj``
    1. satır başlık, 2. satırdan itibaren örnek satırlar.
``Kullanım``
    Kısa doldurma kılavuzu, birim listesi ve fire kuralı.

Fire kuralı şablonda açıkça yazılır: boş fire **sıfır değildir**; satır
hesaplamaya girmez.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.excel.models import (
    GUIDE_SHEET_NAME,
    TEMPLATE_SHEET_NAME,
    MetrajColumn,
)

#: Kolon sırası — şablonun sol→sağ düzeni.
TEMPLATE_COLUMNS: tuple[MetrajColumn, ...] = (
    MetrajColumn.BOQ_NO,
    MetrajColumn.DESCRIPTION,
    MetrajColumn.QUANTITY,
    MetrajColumn.UNIT,
    MetrajColumn.WASTE,
)

#: Kolon genişlikleri (Excel karakter birimi).
COLUMN_WIDTHS: dict[MetrajColumn, float] = {
    MetrajColumn.BOQ_NO: 14,
    MetrajColumn.DESCRIPTION: 46,
    MetrajColumn.QUANTITY: 14,
    MetrajColumn.UNIT: 10,
    MetrajColumn.WASTE: 12,
}

#: Başlık açıklamaları — şablonun alt bilgisinde tek satır olarak yazılır.
COLUMN_HELP: dict[MetrajColumn, str] = {
    MetrajColumn.BOQ_NO: "Satırın benzersiz numarası (zorunlu, tekrar edemez)",
    MetrajColumn.DESCRIPTION: "Malzeme / imalat açıklaması (zorunlu)",
    MetrajColumn.QUANTITY: "Metraj miktarı, sayı (zorunlu, sıfırdan büyük)",
    MetrajColumn.UNIT: "m, kg veya t (zorunlu)",
    MetrajColumn.WASTE: "Fire yüzdesi, örn. 5 (boş bırakılırsa satır hesaba girmez)",
}

_HEADER_FILL = PatternFill("solid", fgColor="1F3864")
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_EXAMPLE_FILL = PatternFill("solid", fgColor="F2F5FA")
_OPTIONAL_FONT = Font(italic=True, size=9, color="5A6472")
_THIN = Side(style="thin", color="BFC7D5")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


@dataclass(frozen=True, slots=True)
class TemplateExampleRow:
    """Şablona yazılan örnek satır."""

    boq_no: str
    description: str
    quantity: Decimal
    unit: str
    waste_percent: Decimal | None


#: Şablondaki örnek satırlar.
#:
#: Kasten çeşitlidir: metre, kilogram ve ton satırı; galvaniz kaplama; fire
#: dolu ve **boş** satır. Son satır fire boş bırakıldığında ne olacağını
#: gösterir (hesaba girmez, sıfır sayılmaz).
TEMPLATE_EXAMPLE_ROWS: tuple[TemplateExampleRow, ...] = (
    TemplateExampleRow(
        "ORNEK-001", "BOX 100×100×4 S235 siyah", Decimal("96"), "m", Decimal("5")
    ),
    TemplateExampleRow(
        "ORNEK-002", "IPE 200 S235 siyah", Decimal("1240"), "kg", Decimal("3")
    ),
    TemplateExampleRow(
        "ORNEK-003", "HEA 200 S235 galvaniz", Decimal("3.2"), "t", Decimal("4")
    ),
    TemplateExampleRow(
        "ORNEK-004", "lama 40×5 S235 siyah", Decimal("210"), "kg", None
    ),
)

#: Kullanım sayfasındaki kılavuz satırları.
GUIDE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Nasıl doldurulur?",
        (
            "1. Metraj sayfasındaki başlık satırını değiştirmeyin.",
            "2. Her malzeme/imalat için bir satır yazın.",
            "3. BOQ No alanına kendi metraj numaranızı girin; tekrar etmemeli.",
            "4. Açıklamaya profil tipi, ölçü, kalite ve kaplamayı yazın. "
            "Örn. 'BOX 100×100×4 S235 siyah'.",
            "5. Miktarı sayı olarak, birimini m / kg / t olarak girin.",
            "6. Fire yüzdesini yazın (örn. 5). Boş bırakılırsa satır hesaba "
            "girmez: eksik fire sıfır sayılmaz.",
        ),
    ),
    (
        "Kurallar",
        (
            "• BOQ No, Açıklama, Miktar ve Birim zorunludur.",
            "• Miktar sıfırdan büyük olmalıdır; negatif ve sıfır kabul edilmez.",
            "• Desteklenen birimler: m, kg, t. 'adet' desteklenmez.",
            "• Fire negatif olamaz ve %100'ü geçemez.",
            "• Boş fire sıfır değildir: satır hesaplamaya alınmaz, karar "
            "bekler.",
            "• Formül yazılan hücrelerin Excel'de hesaplanmış değeri yoksa "
            "satır geçersiz sayılır.",
        ),
    ),
    (
        "Hatalar",
        (
            "Dosya okunduğunda her hatalı satır ayrı raporlanır: Excel satır "
            "numarası, BOQ No, hatalı kolon, neden ve düzeltme önerisi.",
            "Bir satır hatalı diye dosyanın tamamı reddedilmez; geçerli "
            "satırlar korunur.",
            "Dosya yapısı okunamıyorsa (eksik/yinelenen başlık, bozuk dosya) "
            "dosya düzeyinde hata bildirilir.",
        ),
    ),
)


def build_metraj_template(path: str | Path) -> Path:
    """Standart metraj şablonunu yazar ve dosya yolunu döndürür."""
    target = Path(path)
    if target.suffix.lower() != ".xlsx":
        raise ValueError(f"Şablon dosyası .xlsx olmalı: {target.name}")

    target.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = TEMPLATE_SHEET_NAME

    _write_header(sheet)
    _write_examples(sheet)
    _write_guide(workbook)
    _apply_layout(sheet)

    workbook.save(target)
    workbook.close()
    return target


def _write_header(sheet) -> None:
    for position, column in enumerate(TEMPLATE_COLUMNS, start=1):
        cell = sheet.cell(row=1, column=position, value=column.value)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.border = _BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")
        sheet.column_dimensions[get_column_letter(position)].width = COLUMN_WIDTHS[column]

    sheet.row_dimensions[1].height = 24


def _write_examples(sheet) -> None:
    for offset, example in enumerate(TEMPLATE_EXAMPLE_ROWS):
        row_number = 2 + offset
        quantity = (
            Decimal(example.quantity)
            if isinstance(example.quantity, Decimal)
            else Decimal(str(example.quantity))
        )

        values = {
            MetrajColumn.BOQ_NO: example.boq_no,
            MetrajColumn.DESCRIPTION: example.description,
            MetrajColumn.QUANTITY: quantity,
            MetrajColumn.UNIT: example.unit,
            MetrajColumn.WASTE: example.waste_percent,
        }
        for position, column in enumerate(TEMPLATE_COLUMNS, start=1):
            cell = sheet.cell(row=row_number, column=position, value=values[column])
            cell.border = _BORDER
            cell.fill = _EXAMPLE_FILL
            if column is MetrajColumn.QUANTITY:
                cell.number_format = "#,##0.####"
                cell.alignment = Alignment(horizontal="right")
            elif column is MetrajColumn.WASTE:
                cell.number_format = "0.##"
                cell.alignment = Alignment(horizontal="right")
            elif column is MetrajColumn.UNIT:
                cell.alignment = Alignment(horizontal="center")


def _write_guide(workbook: Workbook) -> None:
    guide = workbook.create_sheet(GUIDE_SHEET_NAME)
    guide.column_dimensions["A"].width = 4
    guide.column_dimensions["B"].width = 96

    title = guide.cell(row=1, column=2, value="BuildFlow AI — Metraj Şablonu Kullanımı")
    title.font = Font(bold=True, size=14, color="1F3864")

    row = 3
    for heading, lines in GUIDE_SECTIONS:
        heading_cell = guide.cell(row=row, column=2, value=heading)
        heading_cell.font = Font(bold=True, size=11)
        row += 1
        for line in lines:
            cell = guide.cell(row=row, column=2, value=line)
            cell.alignment = Alignment(wrap_text=False, vertical="top")
            row += 1
        row += 1

    unit_cell = guide.cell(row=row, column=2, value="Desteklenen birimler: m · kg · t")
    unit_cell.font = Font(italic=True, color="5A6472")

    sheet_note = guide.cell(
        row=row + 2,
        column=2,
        value="Verileri 'Metraj' sayfasına girin; bu sayfa yalnızca açıklamadır.",
    )
    sheet_note.font = Font(italic=True, color="5A6472")


def _apply_layout(sheet) -> None:
    sheet.freeze_panes = "A2"
    last_row = 1 + len(TEMPLATE_EXAMPLE_ROWS)
    sheet.auto_filter.ref = f"A1:E{last_row}"

    # Birim kolonu için açılır liste: yanlış birim yazımını azaltır.
    validation = DataValidation(
        type="list",
        formula1='"m,kg,t"',
        allow_blank=False,
        showDropDown=False,
    )
    validation.error = "Birim m, kg veya t olmalıdır."
    validation.errorTitle = "Desteklenmeyen birim"
    validation.prompt = "m, kg veya t girin."
    validation.promptTitle = "Birim"
    validation.showErrorMessage = True
    validation.showInputMessage = True

    unit_letter = get_column_letter(
        TEMPLATE_COLUMNS.index(MetrajColumn.UNIT) + 1
    )
    # Örnek satırların ötesinde de geçerli olsun diye geniş aralık verilir.
    validation.add(f"{unit_letter}2:{unit_letter}1000")
    sheet.add_data_validation(validation)

    quantity_letter = get_column_letter(
        TEMPLATE_COLUMNS.index(MetrajColumn.QUANTITY) + 1
    )
    # Yalnızca örnek satırlar biçimlendirilir; 1000 satırı önceden oluşturmak
    # dosyayı şişirir ve okuyucuda binlerce boş satır bırakır.
    for row in range(2, 2 + len(TEMPLATE_EXAMPLE_ROWS)):
        sheet[f"{quantity_letter}{row}"].number_format = "#,##0.####"


def template_headers() -> Sequence[str]:
    """Şablonun yazacağı başlıklar — testler ve dokümantasyon için."""
    return tuple(column.value for column in TEMPLATE_COLUMNS)
