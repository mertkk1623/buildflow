"""Zengin örnek proje metrajı (``.xlsx``) üretimi.

Amaç
----
Kullanıcının dosya hazırlamadan ürünü deneyebilmesi. Örnek, **gerçek** bir
metraj dosyasıdır: şablonla aynı sütunları kullanır ve okuyucudan geçer.
Bu yüzden "şablon" (boş başlangıç) ile karıştırılmamalıdır.

Veri seti neyi gösterir
-----------------------
* 40 satır, 14 katalog kaleminin tamamı,
* aynı katalog kodunu isteyen farklı iş kalemleri (birleştirme),
* onay bekleyen (``pending``) satırlar — AI yalnızca bunlarda çalışır,
* üç ayrı kapsam dışı nedeni: katalog dışı kaplama, boş fire, ``adet`` birimi,
* yüksek fire oranlı pozlar: sipariş miktarını net metrajın belirgin üzerine
  çıkarır (bütçe riski göstergesi),
* açıklamasında kritik tedarik olarak işaretlenmiş pozlar.

Açıklama metinleri bilinçli olarak **ölçü dışında sayı içermez**: normalizasyon
ölçüyü metindeki ilk sayıdan çıkarır, bu yüzden "2. kat" gibi bir ifade
eşleştirmeyi bozardı.

Sayfalar
--------
``Metraj``
    Okuyucunun beklediği sayfa; 1. satır başlık, 2. satırdan itibaren veri.
``Senaryo``
    Veri setinin neyi gösterdiğini anlatan kısa notlar (okunmaz).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.excel.models import TEMPLATE_SHEET_NAME, MetrajColumn

#: Örnek dosyanın kullanıcıya gösterilen adı.
SAMPLE_FILENAME = "proje_ornek_metraj.xlsx"

#: Senaryo notlarının yazıldığı yardımcı sayfa.
SCENARIO_SHEET_NAME = "Senaryo"

#: Üretimin tekrarlanabilir olması için sabitlenen zaman damgası.
#: Dosya bir kez commit'lendiğinde içerik değişmedikçe baytları değişmemeli.
_FIXED_MOMENT = datetime(2026, 1, 1)

#: ZIP girdileri için sabit tarih (ZIP biçiminin en erken tarihi).
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

_COLUMNS: tuple[MetrajColumn, ...] = (
    MetrajColumn.BOQ_NO,
    MetrajColumn.DESCRIPTION,
    MetrajColumn.QUANTITY,
    MetrajColumn.UNIT,
    MetrajColumn.WASTE,
)

_COLUMN_WIDTHS: dict[MetrajColumn, float] = {
    MetrajColumn.BOQ_NO: 14,
    MetrajColumn.DESCRIPTION: 56,
    MetrajColumn.QUANTITY: 14,
    MetrajColumn.UNIT: 10,
    MetrajColumn.WASTE: 12,
}

_HEADER_FILL = PatternFill("solid", fgColor="1F3864")
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_BAND_FILL = PatternFill("solid", fgColor="F2F5FA")
_THIN = Side(style="thin", color="BFC7D5")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


@dataclass(frozen=True, slots=True)
class SampleRow:
    """Tek örnek satır — yalnızca kaynak veri, hesap yok."""

    boq_no: str
    description: str
    quantity: Decimal
    unit: str
    #: Yüzde (``6`` = %6). ``None`` = fire tanımsız → satır hesaba girmez.
    waste_percent: Decimal | None


def _row(
    boq_no: str,
    description: str,
    quantity: str,
    unit: str,
    waste_percent: str | None,
) -> SampleRow:
    return SampleRow(
        boq_no=boq_no,
        description=description,
        quantity=Decimal(quantity),
        unit=unit,
        waste_percent=Decimal(waste_percent) if waste_percent is not None else None,
    )


#: 40 satırlık örnek proje metrajı.
#:
#: BOQ numaraları iş paketini taşır: ``STR`` taşıyıcı sistem, ``CEP`` cephe,
#: ``ANK`` ankraj, ``MER`` merdiven/korkuluk, ``LEV`` levha.
SAMPLE_ROWS: tuple[SampleRow, ...] = (
    _row("STR-001", "A Blok kolon — kutu profil 60×60×3 S235 siyah", "540", "m", "6"),
    _row("STR-002", "A Blok kolon — kutu profil 60×60×3 S235 siyah", "1.86", "t", "6"),
    _row("STR-003", "B Blok kiriş — kutu profil 80×80×3 S235 siyah", "320", "m", "5"),
    _row("STR-004", "Konsol kirişi — kutu profil 80×80×3 S235 siyah", "96", "m", "8"),
    _row("STR-005", "Ana kiriş — kutu profil 100×100×4 S235 siyah", "480", "m", "5"),
    _row("STR-006", "Ana kiriş — kutu profil 100×100×4 S235 siyah", "2240", "kg", "12"),
    _row("STR-007", "Tali kiriş — kutu profil 100×100×4 S235 siyah", "540", "m", "5"),
    _row("CEP-001", "Cephe kaplaması — kutu profil 100×100×4 S235 galvaniz", "260", "m", "7"),
    _row("CEP-002", "Cephe kaplaması — kutu profil 100×100×4 S235 galvaniz", "1.2", "t", "7"),
    _row("CEP-003", "Merdiven korkuluğu — kutu profil 100×100×4 S235 galvaniz", "84", "m", "10"),
    _row("STR-008", "Makas alt başlığı — kutu profil 150×100×5 S235 siyah", "240", "m", "6"),
    _row("STR-009", "Makas üst başlığı — kutu profil 150×100×5 S235 siyah", "240", "m", "6"),
    _row("STR-010", "Makas alt başlığı — IPE 200 S235 siyah", "120", "m", "4"),
    _row("STR-011", "Makas üst başlığı — IPE 200 S235 siyah", "116", "m", "4"),
    _row("STR-012", "Kritik yol — çatı makası IPE 200", "2800", "kg", "5"),
    _row("STR-013", "Kolon gövdesi — IPE 240 S355 siyah", "4.8", "t", "4"),
    _row("STR-014", "Kiriş gövdesi — IPE 240 S355 siyah", "2150", "kg", "4"),
    _row("STR-015", "Tali kiriş — IPE 240", "1.4", "t", "4"),
    _row("STR-016", "A Blok kolon — HEA 160 S235 siyah", "288", "m", "5"),
    _row("STR-017", "B Blok kolon — HEA 160 S235 siyah", "1.9", "t", "5"),
    _row("STR-018", "Ana kiriş — HEA 200 S235 siyah", "216", "m", "5"),
    _row("CEP-008", "Cephe kirişi — HEA 200 S235 siyah", "900", "kg", "6"),
    _row("ANK-001", "Zemin ankrajı — HEA 200", "2.4", "t", "5"),
    _row("CEP-004", "Cephe kuşağı — HEA 200 S235 galvaniz", "120", "m", "5"),
    _row("STR-020", "Aşı kirişi — UPN 100 S235 siyah", "180", "m", "6"),
    _row("STR-021", "Aşı kirişi — UPN 100 S235 siyah", "640", "kg", "6"),
    _row("STR-022", "Döşeme kirişi — UPN 160 S235 siyah", "168", "m", "5"),
    _row("STR-023", "Döşeme kirişi — UPN 160 S235 siyah", "0.62", "t", "5"),
    _row("STR-024", "Kritik yol — merdiven kirişi UPN 100", "96", "m", "5"),
    _row("MER-001", "Korkuluk dikmesi — lama 40×5 S235 siyah", "420", "kg", "8"),
    _row("MER-002", "Korkuluk dikmesi — lama 40×5 S235 siyah", "96", "m", "8"),
    _row("MER-003", "Merdiven korkuluğu — lama 40×5 S235 siyah", "260", "kg", "8"),
    _row("CEP-005", "Cephe kaplaması — lama 40×5 S235 galvaniz", "150", "m", "7"),
    _row("CEP-006", "Cephe kaplaması — lama 40×5 S235 galvaniz", "310", "kg", "7"),
    _row("CEP-007", "Cephe kuşağı — lama 40×5 galvaniz", "180", "kg", "7"),
    _row("LEV-001", "Bağlantı levhası — lama 50×6 S235 siyah", "3600", "kg", "9"),
    _row("LEV-002", "Bağlantı levhası — lama 50×6 S235 siyah", "190", "m", "9"),
    _row("LEV-003", "Ankraj levhası — lama 50×6 S235 siyah", "540", "kg", "9"),
    _row(
        "LEV-004",
        "Bağlantı levhası — kutu profil 100×100×4 S235 siyah",
        "75",
        "m",
        None,
    ),
    _row("LEV-005", "Ankraj levhası — lama 60×6 S235 siyah", "24", "adet", "5"),
)

#: ``Senaryo`` sayfasında yazılan notlar.
SCENARIO_NOTES: tuple[str, ...] = (
    "Bu dosya gerçek bir metraj dosyasıdır; şablon (boş başlangıç) değildir.",
    "40 satır · 14 katalog kalemi · 5 onay bekleyen satır · 3 kapsam dışı satır.",
    "Onay bekleyen satırlar: STR-012, STR-015, ANK-001, STR-024, CEP-007. "
    "AI yalnızca bu satırlarda öneri üretir; öneri otomatik onaylanmaz.",
    "Kapsam dışı: CEP-004 (katalogda HEA galvaniz yok), LEV-004 (fire boş), "
    "LEV-005 (birim 'adet').",
    "Bütçe riski: STR-006 (%12) ve LEV-001 (%9) yüksek fire taşır; sipariş "
    "miktarı net metrajın belirgin üzerine çıkar.",
    "Kaynak çakışması: aynı katalog kodunu isteyen farklı blok ve iş kalemleri "
    "tek satın alma kaleminde birleşir.",
    "Kritik yol: STR-012 ve STR-024 açıklamasında kritik tedarik olarak "
    "işaretlenmiştir.",
)


def build_sample_workbook(path: str | Path) -> Path:
    """Örnek proje metrajını yazar ve dosya yolunu döndürür."""
    target = Path(path)
    if target.suffix.lower() != ".xlsx":
        raise ValueError(f"Örnek dosya .xlsx olmalı: {target.name}")

    target.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = TEMPLATE_SHEET_NAME

    _write_header(sheet)
    _write_rows(sheet)
    _write_scenario(workbook)
    _apply_layout(sheet, last_row=1 + len(SAMPLE_ROWS))

    workbook.properties.creator = "BuildFlow AI"
    workbook.properties.created = _FIXED_MOMENT
    workbook.properties.modified = _FIXED_MOMENT

    workbook.save(target)
    workbook.close()
    _normalize_archive(target)
    return target


def _normalize_archive(path: Path) -> None:
    """ZIP üst verisindeki zaman damgalarını sabitler.

    ``openpyxl`` hem ``docProps/core.xml`` içine hem de ZIP girdilerine o anki
    saati yazar — ``modified`` alanı kaydetme sırasında yeniden üretilir.
    Sabitlenmezse aynı veri kümesi her çalıştırmada farklı bayt üretir ve
    commit'lenmiş dosya gereksiz yere değişir.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(path) as source:
        entries = [(info, source.read(info)) for info in source.infolist()]

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for info, data in entries:
            if info.filename == "docProps/core.xml":
                data = _pin_modified(data)
            fixed = zipfile.ZipInfo(info.filename, date_time=_ZIP_EPOCH)
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            fixed.create_system = info.create_system
            target.writestr(fixed, data)

    path.write_bytes(buffer.getvalue())


def _pin_modified(core_xml: bytes) -> bytes:
    """``core.xml`` içindeki ``modified`` zaman damgasını sabitler."""
    stamp = _FIXED_MOMENT.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    return re.sub(
        rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
        lambda match: match.group(1) + stamp + match.group(2),
        core_xml,
    )


def _write_header(sheet) -> None:
    for position, column in enumerate(_COLUMNS, start=1):
        cell = sheet.cell(row=1, column=position, value=column.value)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.border = _BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")
        sheet.column_dimensions[get_column_letter(position)].width = _COLUMN_WIDTHS[column]
    sheet.row_dimensions[1].height = 24


def _write_rows(sheet) -> None:
    for offset, row in enumerate(SAMPLE_ROWS):
        row_number = 2 + offset
        values = {
            MetrajColumn.BOQ_NO: row.boq_no,
            MetrajColumn.DESCRIPTION: row.description,
            MetrajColumn.QUANTITY: row.quantity,
            MetrajColumn.UNIT: row.unit,
            MetrajColumn.WASTE: row.waste_percent,
        }
        for position, column in enumerate(_COLUMNS, start=1):
            cell = sheet.cell(row=row_number, column=position, value=values[column])
            cell.border = _BORDER
            # Okunabilirlik için satır bandı; veri anlamı taşımaz.
            if offset % 2 == 1:
                cell.fill = _BAND_FILL
            if column is MetrajColumn.QUANTITY:
                cell.number_format = "#,##0.####"
                cell.alignment = Alignment(horizontal="right")
            elif column is MetrajColumn.WASTE:
                cell.number_format = "0.##"
                cell.alignment = Alignment(horizontal="right")
            elif column is MetrajColumn.UNIT:
                cell.alignment = Alignment(horizontal="center")


def _write_scenario(workbook: Workbook) -> None:
    scenario = workbook.create_sheet(SCENARIO_SHEET_NAME)
    scenario.column_dimensions["A"].width = 4
    scenario.column_dimensions["B"].width = 100
    scenario.cell(row=1, column=2, value="BuildFlow AI — Örnek Proje Metrajı").font = Font(
        bold=True, size=14, color="1F3864"
    )
    for offset, note in enumerate(SCENARIO_NOTES):
        cell = scenario.cell(row=3 + offset, column=2, value=note)
        cell.alignment = Alignment(wrap_text=False, vertical="top")


def _apply_layout(sheet, *, last_row: int) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:E{last_row}"

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
    validation.add(f"D2:D{last_row}")
    sheet.add_data_validation(validation)


def sample_headers() -> tuple[str, ...]:
    """Örnek dosyanın yazacağı başlıklar — testler için."""
    return tuple(column.value for column in _COLUMNS)
