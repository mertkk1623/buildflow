"""Testler için Excel dosyası kurma yardımcıları.

Gerçek dosyalar ``openpyxl`` ile üretilir; böylece okuyucu, Excel'in
kaydettiği biçime karşı test edilir. Formül önbelleği gibi openpyxl'in
yazamadığı durumlar için :func:`inject_cached_value` XML düzeyinde çalışır.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable, Sequence
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from app.excel.models import GUIDE_SHEET_NAME, TEMPLATE_SHEET_NAME, MetrajColumn

DEFAULT_HEADERS: tuple[str, ...] = (
    MetrajColumn.BOQ_NO.value,
    MetrajColumn.DESCRIPTION.value,
    MetrajColumn.QUANTITY.value,
    MetrajColumn.UNIT.value,
    MetrajColumn.WASTE.value,
)


def write_workbook(
    path: str | Path,
    rows: Iterable[Sequence[object]],
    *,
    headers: Sequence[str] | None = DEFAULT_HEADERS,
    sheet: str = TEMPLATE_SHEET_NAME,
    header_row: int = 1,
    title_rows: Sequence[Sequence[object]] = (),
) -> Path:
    """Tek sayfalık test çalışma kitabı yazar.

    ``title_rows`` başlıktan önce yazılacak satırlardır (ör. şirket adı);
    başlığın 1. satırda olmadığı dosyaları taklit etmek için kullanılır.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet

    current = 1
    for title in title_rows:
        for position, value in enumerate(title, start=1):
            worksheet.cell(row=current, column=position, value=value)
        current += 1

    if current < header_row:
        current = header_row

    if headers is not None:
        for position, value in enumerate(headers, start=1):
            worksheet.cell(row=current, column=position, value=value)
        current += 1

    for row in rows:
        for position, value in enumerate(row, start=1):
            worksheet.cell(row=current, column=position, value=value)
        current += 1

    workbook.save(target)
    workbook.close()
    return target


def write_multi_sheet_workbook(
    path: str | Path,
    sheets: dict[str, Sequence[Sequence[object]]],
    *,
    headers: Sequence[str] = DEFAULT_HEADERS,
) -> Path:
    target = Path(path)
    workbook = Workbook()
    workbook.remove(workbook.active)

    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(name)
        worksheet.append(list(headers))
        for row in rows:
            worksheet.append(list(row))

    workbook.save(target)
    workbook.close()
    return target


def inject_cached_value(
    path: str | Path,
    *,
    cell: str,
    value: str,
    sheet_index: int = 1,
) -> Path:
    """Formül hücresine Excel'in yazacağı önbellek değerini ekler.

    openpyxl formülü yazarken ``<f>...</f><v />`` üretir: önbellek yoktur.
    Gerçek Excel dosyasında ise ``<v>12</v>`` bulunur. Bu yardımcı, o durumu
    birebir taklit eder (formül metni korunur).
    """
    target = Path(path)
    temporary = target.with_suffix(".tmp.xlsx")
    source = target.with_suffix(".src.xlsx")
    target.replace(source)

    entry = f"xl/worksheets/sheet{sheet_index}.xml"
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == entry:
                text = data.decode("utf-8")
                pattern = f'<c r="{cell}"'
                start = text.index(pattern)
                end = text.index("</c>", start)
                chunk = text[start:end]
                if "<f>" not in chunk:
                    raise AssertionError(f"{cell} hücresinde formül yok: {chunk!r}")
                if "<v />" in chunk:
                    chunk = chunk.replace("<v />", f"<v>{value}</v>")
                elif "<v/>" in chunk:
                    chunk = chunk.replace("<v/>", f"<v>{value}</v>")
                else:
                    chunk = f"{chunk}<v>{value}</v>"
                text = text[:start] + chunk + text[end:]
                data = text.encode("utf-8")
            zout.writestr(item, data)

    temporary.replace(target)
    source.unlink()
    return target


def demo_excel_rows() -> list[list[object]]:
    """18 satırlık demo metrajın Excel satırları.

    Fire, şablonun sözleşmesine uygun olarak **yüzde** olarak yazılır
    (0.05 oranı → 5). Miktar ``Decimal`` olarak verilir ki float yuvarlaması
    test verisine sızmasın.
    """
    from tests.fixtures.demo_boq import DEMO_ROWS

    rows: list[list[object]] = []
    for row in DEMO_ROWS:
        waste: Decimal | float | None
        if row.waste_rate is None:
            waste = None
        else:
            waste = row.waste_rate * Decimal(100)
        rows.append([row.no, row.description, row.quantity, row.unit, waste])
    return rows


def build_demo_workbook(path: str | Path) -> Path:
    return write_workbook(path, demo_excel_rows())


def guide_sheet_names() -> tuple[str, str]:
    return TEMPLATE_SHEET_NAME, GUIDE_SHEET_NAME
