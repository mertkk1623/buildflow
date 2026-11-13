"""Metraj ``.xlsx`` okuyucu — Aşama 4.3.

Tasarım kararları
-----------------
1. **Dosya düzeyi hata ≠ satır düzeyi hata.** Dosya yapısı okunamıyorsa
   (bozuk dosya, eksik/yinelenen başlık) :class:`MetrajFileError` yükselir ve
   hiçbir satır döndürülmez. Yapı okunuyorsa hatalı satırlar ``invalid``
   olarak işaretlenir, geçerli satırlar korunur.
2. **Kaynak satır numarası korunur.** ``source_row`` Excel'in 1 tabanlı
   gerçek satır numarasıdır; boş satırlar atlansa bile yeniden numaralandırma
   yapılmaz. Kullanıcı "7. satırda hata var" diyebilmelidir.
3. **Formül ≠ veri.** Formül hücresinin önbelleğe alınmış sonucu yoksa değer
   ``0`` veya boş sayılmaz; satır ``formula-without-cache`` ile ``invalid``
   olur. Okuyucu formülleri **hesaplamaz**.
4. **Eksik fire sıfır değildir.** Fire kolonu boşsa ``waste_percent=None``
   kalır; eşleştirme katmanı bunu "fire tanımsız" olarak değerlendirir.
5. **Okuyucu eşleştirme yapmaz.** Ürün kodu, eşleştirme durumu veya kullanıcı
   onayı üretmez. Yalnızca doğrulanmış kaynak veriyi taşır.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.domain.models import ExclusionReason, InvalidReason, Unit
from app.domain.normalize import tr_lower
from app.excel.models import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    TEMPLATE_SHEET_NAME,
    CellIssue,
    MetrajColumn,
    MetrajReadResult,
    MetrajRow,
    ScopeIssue,
)
from app.excel.numbers import (
    NumberParseError,
    decimal_from_number,
    looks_empty,
    parse_decimal_text,
    parse_percent_text,
    scale_percent,
)

#: Başlık satırını ararken taranacak en fazla satır sayısı. Bazı gerçek
#: dosyalarda başlıktan önce şirket adı/başlık satırı bulunur.
HEADER_SEARCH_LIMIT = 10

#: Açılmış (decompressed) içerik için üst sınır: 200 MB.
#:
#: Yükleme boyutu sınırı (10 MB) **sıkıştırılmış** dosyayı sınırlar; bir ZIP
#: arşivi kolayca çok daha büyük bir içeriğe açılabilir ("zip bomb"). Bu
#: kontrol, arşiv openpyxl'e verilmeden **önce** toplam açılmış boyutu ve
#: giriş sayısını denetler. Gerçek metraj dosyaları bu sınırın çok altındadır.
MAX_EXPANDED_BYTES = 200 * 1024 * 1024

#: Arşivdeki en fazla giriş (dosya) sayısı.
MAX_ARCHIVE_ENTRIES = 10_000

#: Bir sayfada okunacak en fazla veri satırı. Gerçek metrajlar binlerle
#: ölçülür; bu sınır yalnızca patolojik dosyaları durdurur.
MAX_DATA_ROWS = 50_000

#: Başlık metnini karşılaştırma anahtarına çevirir.
#:
#: Büyük/küçük harf, Türkçe harfler ve **tüm** boşluklar yok sayılır; böylece
#: ``BOQ No``, ``boq no`` ve ``BOQNo`` aynı kolonu bulur. Buna karşılık
#: ``Miktar (m)`` gibi farklı bir başlık ``Miktar`` sayılmaz — yanlış kolon
#: sessizce doğru kolon gibi yorumlanmaz.
def header_key(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ")
    text = text.strip().rstrip(":").strip()
    # Türkçe büyük ``I`` ile küçük ``ı`` aynı harfe indirgenir: başlıkta
    # ``AÇIKLAMA`` yazması ``Açıklama`` ile aynı kolondur. (Gövde metninde
    # bu eşleme yapılmaz; orada normalize modülünün kuralı geçerlidir.)
    lowered = tr_lower(text).replace("ı", "i")
    return "".join(lowered.split())


_HEADER_LOOKUP: dict[str, MetrajColumn] = {
    header_key(column.value): column for column in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS)
}


class MetrajFileErrorCode(str, Enum):
    """Dosya düzeyinde hata türü — API katmanı bunu HTTP'ye eşleyecek."""

    NOT_FOUND = "not-found"
    UNSUPPORTED_FORMAT = "unsupported-format"
    CORRUPT = "corrupt-file"
    FILE_TOO_COMPLEX = "file-too-complex"
    MISSING_SHEET = "missing-sheet"
    NO_HEADER = "no-header-row"
    MISSING_COLUMN = "missing-column"
    DUPLICATE_COLUMN = "duplicate-column"


class MetrajFileError(Exception):
    """Dosya bir bütün olarak okunamadı."""

    def __init__(
        self,
        code: MetrajFileErrorCode,
        message: str,
        *,
        detail: str = "",
        suggestion: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.suggestion = suggestion


@dataclass(frozen=True, slots=True)
class _HeaderLayout:
    row: int
    column_index: dict[MetrajColumn, int]
    ignored_columns: tuple[str, ...]


# ---------------------------------------------------------------------------
# Genel giriş noktası
# ---------------------------------------------------------------------------


def read_metraj(path: str | Path) -> MetrajReadResult:
    """Metraj dosyasını okur, doğrular ve satır sonuçlarını döndürür.

    Raises
    ------
    MetrajFileError
        Dosya bulunamadı, format desteklenmiyor, bozuk, beklenen sayfa yok,
        başlık satırı bulunamadı, zorunlu kolon eksik veya yinelenen.
    """
    target = Path(path)
    _assert_readable_file(target)
    _assert_archive_within_limits(target)

    formulas = _load_workbook(target, data_only=False)
    cached = _load_workbook(target, data_only=True)

    try:
        # openpyxl, erişilen hücreleri oluşturur ve ``max_row`` büyür. Gerçek
        # veri sınırını **herhangi bir hücreye dokunmadan** donduruyoruz; aksi
        # hâlde boş satırlar hayalet satır olarak sayılır.
        boundaries = {
            name: max(
                _last_value_row(formulas[name]),
                _last_value_row(cached[name]),
            )
            for name in formulas.sheetnames
            if name in cached.sheetnames
        }

        sheet_name, warnings = _resolve_sheet(formulas)
        formula_sheet = formulas[sheet_name]
        cached_sheet = cached[sheet_name]
        last_row = boundaries[sheet_name]

        layout = _read_header(formula_sheet, sheet_name, last_row=last_row)
        rows, blank_rows, row_warnings = _read_rows(
            formula_sheet,
            cached_sheet,
            layout,
            last_row=last_row,
        )
        rows = _flag_duplicates(rows)

        return MetrajReadResult(
            path=str(target),
            sheet_name=sheet_name,
            column_index=dict(layout.column_index),
            rows=rows,
            ignored_columns=layout.ignored_columns,
            blank_rows_skipped=blank_rows,
            warnings=(*warnings, *row_warnings),
        )
    finally:
        formulas.close()
        cached.close()


# ---------------------------------------------------------------------------
# Dosya düzeyi kontroller
# ---------------------------------------------------------------------------


def _assert_readable_file(path: Path) -> None:
    if not path.exists():
        raise MetrajFileError(
            MetrajFileErrorCode.NOT_FOUND,
            f"Dosya bulunamadı: {path}",
            suggestion="Dosya yolunu kontrol edin.",
        )
    if not path.is_file():
        raise MetrajFileError(
            MetrajFileErrorCode.NOT_FOUND,
            f"Yol bir dosya değil: {path}",
            suggestion="Bir .xlsx dosyası seçin.",
        )
    if path.suffix.lower() != ".xlsx":
        raise MetrajFileError(
            MetrajFileErrorCode.UNSUPPORTED_FORMAT,
            f"Desteklenmeyen dosya biçimi: {path.suffix or '(uzantısız)'}",
            detail=f"Yalnızca .xlsx dosyaları okunur: {path.name}",
            suggestion=(
                "Dosyayı Excel'de 'Excel Çalışma Kitabı (*.xlsx)' olarak "
                "kaydedin. .xls, .xlsm ve .csv bu sürümde desteklenmez."
            ),
        )


def _assert_archive_within_limits(path: Path) -> None:
    """Arşivi açmadan önce açılmış boyut ve giriş sayısını denetler.

    Yükleme sınırı sıkıştırılmış boyutu sınırlar; açılmış içerik bundan çok
    daha büyük olabilir. Kontrol **merkezi dizinden** yapılır: hiçbir giriş
    açılmaz, yalnızca bildirilen boyutlar toplanır. Bozuk/eksik merkezi dizin
    burada hata vermez — openpyxl'in kendi ``corrupt-file`` yoluna bırakılır.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
    except (zipfile.BadZipFile, OSError, ValueError):
        # Bozuk arşiv: ayrıntılı hata ``_load_workbook`` içinde üretilir.
        return

    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise MetrajFileError(
            MetrajFileErrorCode.FILE_TOO_COMPLEX,
            "Dosya yapısı beklenenden karmaşık.",
            detail=(
                f"Arşivde {len(entries)} giriş var; en fazla "
                f"{MAX_ARCHIVE_ENTRIES} desteklenir."
            ),
            suggestion=(
                "Dosyayı Excel'de açıp 'Farklı Kaydet' ile temiz bir .xlsx "
                "olarak yeniden oluşturun."
            ),
        )

    expanded = sum(entry.file_size for entry in entries)
    if expanded > MAX_EXPANDED_BYTES:
        raise MetrajFileError(
            MetrajFileErrorCode.FILE_TOO_COMPLEX,
            "Dosyanın açılmış boyutu sınırı aşıyor.",
            detail=(
                f"Açılmış içerik {expanded // (1024 * 1024)} MB; en fazla "
                f"{MAX_EXPANDED_BYTES // (1024 * 1024)} MB desteklenir."
            ),
            suggestion=(
                "Gereksiz sayfaları/kolonları kaldırın veya dosyayı bölerek "
                "yükleyin."
            ),
        )


def _load_workbook(path: Path, *, data_only: bool):
    try:
        return load_workbook(path, data_only=data_only, read_only=False)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
        # İstisna **sınıf adı** istemciye taşınmaz: iç tip adı ve mesajı
        # kullanıcıya bilgi vermez, sunucu uygulamasının ayrıntısını sızdırır.
        # Ayrıntı yalnızca sunucu log'unda kalır.
        raise MetrajFileError(
            MetrajFileErrorCode.CORRUPT,
            f"Dosya okunamadı veya bozuk: {path.name}",
            detail=(
                "Dosya geçerli bir Excel çalışma kitabı olarak açılamadı. "
                "Dosya bozuk, parola korumalı veya Excel dışı bir araçla "
                "üretilmiş olabilir."
            ),
            suggestion=(
                "Dosyayı Excel'de açıp yeniden kaydedin. Parola korumalı veya "
                "bozuk dosyalar okunamaz."
            ),
        ) from exc


def _resolve_sheet(workbook) -> tuple[str, tuple[str, ...]]:
    """Beklenen sayfayı bulur.

    Sıra: tam ad → normalize ad → tek sayfalı dosyada o sayfa (uyarı ile).
    Aksi hâlde açık hata. Tek sayfa kabul edilirken başlık denetimi
    :func:`_read_header`'a bırakılır; orada ``NO_HEADER`` daha açıklayıcıdır.
    """
    names = list(workbook.sheetnames)
    if TEMPLATE_SHEET_NAME in names:
        return TEMPLATE_SHEET_NAME, ()

    wanted = header_key(TEMPLATE_SHEET_NAME)
    for name in names:
        if header_key(name) == wanted:
            return name, (
                f"'{TEMPLATE_SHEET_NAME}' sayfası '{name}' adıyla bulundu.",
            )

    if len(names) == 1:
        # Tek sayfalı dosyada sayfa adı ne olursa olsun veri sayfası odur.
        # Başlık sorunu varsa ``_read_header`` açık hata verir (NO_HEADER).
        name = names[0]
        if name != TEMPLATE_SHEET_NAME:
            return name, (
                f"'{TEMPLATE_SHEET_NAME}' sayfası yok; tek sayfa '{name}' "
                "kullanıldı.",
            )
        return name, ()

    raise MetrajFileError(
        MetrajFileErrorCode.MISSING_SHEET,
        f"'{TEMPLATE_SHEET_NAME}' çalışma sayfası bulunamadı.",
        detail=f"Dosyadaki sayfalar: {', '.join(names) if names else '(yok)'}",
        suggestion=(
            f"Sayfa adını '{TEMPLATE_SHEET_NAME}' yapın veya standart şablonu "
            "kullanın."
        ),
    )


# ---------------------------------------------------------------------------
# Başlık okuma
# ---------------------------------------------------------------------------


def _detect_header_row(sheet, *, last_row: int | None = None) -> int | None:
    """İlk :data:`HEADER_SEARCH_LIMIT` satır içinde en iyi başlık satırını bulur."""
    limit = HEADER_SEARCH_LIMIT if last_row is None else min(HEADER_SEARCH_LIMIT, last_row)
    best_row: int | None = None
    best_score = 0
    for row_number in range(1, limit + 1):
        score = 0
        for cell in sheet[row_number]:
            if header_key(cell.value) in _HEADER_LOOKUP:
                score += 1
        if score > best_score:
            best_score = score
            best_row = row_number
    return best_row


def _read_header(sheet, sheet_name: str, *, last_row: int | None = None) -> _HeaderLayout:
    header_row = _detect_header_row(sheet, last_row=last_row)
    if header_row is None:
        first = [
            str(cell.value).strip()
            for cell in sheet[1]
            if not looks_empty(cell.value)
        ]
        raise MetrajFileError(
            MetrajFileErrorCode.NO_HEADER,
            f"'{sheet_name}' sayfasında başlık satırı bulunamadı.",
            detail=(
                "Beklenen başlıklar: "
                + ", ".join(column.value for column in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS))
                + (f" | İlk satırda bulunanlar: {', '.join(first)}" if first else "")
            ),
            suggestion=(
                "1. satıra şablon başlıklarını birebir yazın veya standart "
                "şablonu kullanın."
            ),
        )

    column_index: dict[MetrajColumn, int] = {}
    duplicates: dict[MetrajColumn, list[str]] = {}
    ignored: list[str] = []

    for cell in sheet[header_row]:
        if looks_empty(cell.value):
            continue
        column = _HEADER_LOOKUP.get(header_key(cell.value))
        if column is None:
            ignored.append(str(cell.value).strip())
            continue
        if column in column_index:
            duplicates.setdefault(column, [str(cell.value).strip()]).append(
                str(cell.value).strip()
            )
            continue
        column_index[column] = cell.column

    if duplicates:
        names_by_column = {
            column: ", ".join(f"{name!r}" for name in names)
            for column, names in duplicates.items()
        }
        detail = "; ".join(
            f"{column.value}: {names_by_column[column]}" for column in duplicates
        )
        repeated = ", ".join(column.value for column in duplicates)
        raise MetrajFileError(
            MetrajFileErrorCode.DUPLICATE_COLUMN,
            f"Aynı kolon birden fazla kez tanımlanmış: {repeated}.",
            detail=detail,
            suggestion=(
                "Yinelenen kolonlardan birini silin. Hangi kolonun geçerli "
                "olduğu tahmin edilmez."
            ),
        )

    missing = [column for column in REQUIRED_COLUMNS if column not in column_index]
    if missing:
        raise MetrajFileError(
            MetrajFileErrorCode.MISSING_COLUMN,
            "Zorunlu kolon(lar) eksik: " + ", ".join(column.value for column in missing),
            detail=(
                "Bulunan kolonlar: "
                + (
                    ", ".join(column.value for column in column_index)
                    or "(tanınan kolon yok)"
                )
            ),
            suggestion=(
                "Şablondaki başlıkları kullanın: "
                + ", ".join(column.value for column in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS))
            ),
        )

    return _HeaderLayout(
        row=header_row,
        column_index=column_index,
        ignored_columns=tuple(ignored),
    )


# ---------------------------------------------------------------------------
# Satır okuma
# ---------------------------------------------------------------------------


def _last_value_row(sheet) -> int:
    """Değer taşıyan **son** satır numarası.

    ``sheet.max_row`` biçimlendirilmiş ama boş satırlar yüzünden milyonlara
    çıkabilir (Excel tüm kolonu biçimlendirdiğinde ``A1:E1048576`` yazar).
    Bu yüzden sınır, hücre değerlerinden hesaplanır: yalnızca biçim taşıyan
    hücreler sayılmaz. Hesap O(dolu hücre) ve boş satır taraması yapmaz.
    """
    cells = getattr(sheet, "_cells", None)  # openpyxl iç deposu; yoksa yedek
    if not cells:
        return sheet.max_row or 1

    last = 0
    for (row, _column), cell in cells.items():
        if cell.value is not None:
            if row > last:
                last = row
    return last or (sheet.max_row or 1)


def _read_rows(
    formula_sheet,
    cached_sheet,
    layout: _HeaderLayout,
    *,
    last_row: int | None = None,
) -> tuple[tuple[MetrajRow, ...], int, tuple[str, ...]]:
    rows: list[MetrajRow] = []
    blank = 0
    unmapped_only: list[int] = []
    warnings: list[str] = []

    if MetrajColumn.WASTE not in layout.column_index:
        warnings.append(
            "Fire (%) kolonu yok. Tüm satırlarda fire tanımsız kalır; "
            "eksik fire sıfır sayılmaz."
        )

    boundary = last_row if last_row is not None else _last_value_row(formula_sheet)

    # Patolojik dosyaları erken durdur: milyonlarca satırı satır satır
    # işlemek hem yavaş hem gereksizdir. Gerçek metrajlar bu sınırın çok
    # altındadır; sınır aşılırsa dosya düzeyinde hata verilir.
    data_rows = boundary - layout.row
    if data_rows > MAX_DATA_ROWS:
        raise MetrajFileError(
            MetrajFileErrorCode.FILE_TOO_COMPLEX,
            "Dosya çok fazla satır içeriyor.",
            detail=(
                f"Veri satırı sayısı {data_rows}; en fazla "
                f"{MAX_DATA_ROWS} desteklenir."
            ),
            suggestion=(
                "Gereksiz satırları kaldırın veya dosyayı birden fazla metraj "
                "dosyasına bölün."
            ),
        )

    for row_number in range(layout.row + 1, boundary + 1):
        values = {
            column: _cell_value(formula_sheet, cached_sheet, row_number, index)
            for column, index in layout.column_index.items()
        }
        # Formül hücresi önbelleksizse değeri ``None`` görünür; böyle bir satır
        # **boş sayılmaz** — ``invalid`` olarak raporlanmalıdır.
        if all(
            looks_empty(raw) and not raw_cell.is_formula
            for raw, raw_cell in values.values()
        ):
            blank += 1
            if (
                formula_sheet.max_column > max(layout.column_index.values(), default=0)
                and _row_has_unmapped_content(formula_sheet, row_number, layout)
            ):
                unmapped_only.append(row_number)
            continue
        rows.append(_build_row(row_number, values))

    if unmapped_only:
        listed = ", ".join(str(number) for number in unmapped_only[:10])
        suffix = "" if len(unmapped_only) <= 10 else f" (+{len(unmapped_only) - 10})"
        warnings.append(
            f"{len(unmapped_only)} satırda yalnızca tanınmayan kolonlarda veri var; "
            f"bu satırlar okunmadı: {listed}{suffix}. Veri kaybı olmasın diye "
            "sütunları şablon başlıklarıyla eşleştirin."
        )

    return tuple(rows), blank, tuple(warnings)


def _row_has_unmapped_content(sheet, row_number: int, layout: _HeaderLayout) -> bool:
    """Tanınan kolonların dışında veri var mı? (sessiz veri kaybını önler)"""
    known = set(layout.column_index.values())
    # ``sheet[row_number]`` çağrısı hücre **oluşturur** ve boş satırları
    # şişirir; doğrudan iç depoya bakılır.
    cells = getattr(sheet, "_cells", None)
    if cells:
        for (row, column), cell in cells.items():
            if row != row_number or column in known:
                continue
            if not looks_empty(cell.value):
                return True
        return False

    for cell in sheet[row_number]:
        if cell.column in known:
            continue
        if not looks_empty(cell.value):
            return True
    return False


@dataclass(frozen=True, slots=True)
class _RawCell:
    """Hücrenin hem formül hem önbellek görünümü."""

    formula_value: object
    cached_value: object
    is_formula: bool
    number_format: str

    @property
    def has_cached_result(self) -> bool:
        if not looks_empty(self.cached_value):
            return True
        # Boş metin önbellek değildir; ama 0 geçerli bir önbellektir.
        return self.cached_value == 0

    @property
    def value(self) -> object:
        return self.cached_value if self.is_formula else self.formula_value


def _cell_value(formula_sheet, cached_sheet, row: int, column: int) -> tuple[object, _RawCell]:
    formula_cell = formula_sheet.cell(row=row, column=column)
    cached_cell = cached_sheet.cell(row=row, column=column)

    formula_value = formula_cell.value
    is_formula = formula_cell.data_type == "f" or (
        isinstance(formula_value, str) and formula_value.startswith("=")
    )

    raw = _RawCell(
        formula_value=formula_value,
        cached_value=cached_cell.value,
        is_formula=is_formula,
        number_format=formula_cell.number_format or "General",
    )
    return raw.value, raw


def _build_row(row_number: int, values: dict[MetrajColumn, tuple[object, _RawCell]]) -> MetrajRow:
    issues: list[CellIssue] = []
    scope_issues: list[ScopeIssue] = []
    notes: list[str] = []

    boq_raw, boq_cell = values.get(MetrajColumn.BOQ_NO, (None, None))
    desc_raw, desc_cell = values.get(MetrajColumn.DESCRIPTION, (None, None))
    qty_raw, qty_cell = values.get(MetrajColumn.QUANTITY, (None, None))
    unit_raw, unit_cell = values.get(MetrajColumn.UNIT, (None, None))
    waste_raw, waste_cell = values.get(MetrajColumn.WASTE, (None, None))

    # --- BOQ No ---
    boq_no: str | None = None
    if boq_cell is not None and _formula_without_cache(boq_cell):
        issues.append(_formula_issue(MetrajColumn.BOQ_NO))
    elif looks_empty(boq_raw):
        issues.append(
            CellIssue(
                column=MetrajColumn.BOQ_NO,
                reason=InvalidReason.MISSING_BOQ_NO,
                message="BOQ No boş.",
                suggestion="Satıra benzersiz bir BOQ numarası girin (örn. BOQ-001).",
            )
        )
    else:
        boq_no = str(boq_raw).strip()
        if not boq_no:
            boq_no = None
            issues.append(
                CellIssue(
                    column=MetrajColumn.BOQ_NO,
                    reason=InvalidReason.MISSING_BOQ_NO,
                    message="BOQ No yalnızca boşluk içeriyor.",
                    suggestion="Satıra benzersiz bir BOQ numarası girin.",
                )
            )

    # --- Açıklama ---
    description: str | None = None
    if desc_cell is not None and _formula_without_cache(desc_cell):
        issues.append(_formula_issue(MetrajColumn.DESCRIPTION))
    elif looks_empty(desc_raw):
        issues.append(
            CellIssue(
                column=MetrajColumn.DESCRIPTION,
                reason=InvalidReason.MISSING_DESCRIPTION,
                message="Açıklama boş.",
                suggestion=(
                    "Malzemeyi yazın: profil tipi, ölçü, kalite ve kaplama "
                    "(örn. IPE 200 S235 siyah)."
                ),
            )
        )
    else:
        text = str(desc_raw).strip()
        if text:
            description = text
        else:
            issues.append(
                CellIssue(
                    column=MetrajColumn.DESCRIPTION,
                    reason=InvalidReason.MISSING_DESCRIPTION,
                    message="Açıklama yalnızca boşluk içeriyor.",
                    suggestion="Malzeme açıklamasını girin.",
                )
            )

    # --- Miktar ---
    quantity: Decimal | None = None
    if qty_cell is not None and _formula_without_cache(qty_cell):
        issues.append(_formula_issue(MetrajColumn.QUANTITY))
    elif looks_empty(qty_raw):
        issues.append(
            CellIssue(
                column=MetrajColumn.QUANTITY,
                reason=InvalidReason.MISSING_QUANTITY,
                message="Miktar boş.",
                suggestion="Sıfırdan büyük bir miktar girin (örn. 96 veya 1,24).",
            )
        )
    else:
        quantity, quantity_issue = _read_quantity(qty_raw, qty_cell)
        if quantity_issue is not None:
            issues.append(quantity_issue)

    # --- Birim ---
    unit_text: str | None = None
    unit_value: Unit | None = None
    if unit_cell is not None and _formula_without_cache(unit_cell):
        issues.append(_formula_issue(MetrajColumn.UNIT))
    elif looks_empty(unit_raw):
        issues.append(
            CellIssue(
                column=MetrajColumn.UNIT,
                reason=InvalidReason.MISSING_UNIT,
                message="Birim boş.",
                suggestion="Birim girin: m, kg veya t.",
            )
        )
    else:
        unit_text, unit_value, unit_issue = _read_unit(unit_raw)
        if unit_issue is not None:
            issues.append(unit_issue)
        elif unit_value is None:
            # Birim okundu ama bu sürümün hesap kapsamı dışında (ör. ``adet``).
            # Satır bozuk değildir: ``excluded`` olarak eşleştirmeye girer.
            scope_issues.append(
                ScopeIssue(
                    column=MetrajColumn.UNIT,
                    reason=ExclusionReason.UNIT,
                    message=f"Birim {unit_text!r} bu sürümde hesap kapsamı dışında.",
                    suggestion=(
                        "Satır korunur ve 'kapsam dışı' olarak raporlanır. "
                        "Hesaplamak için birimi m, kg veya t olarak girin."
                    ),
                )
            )

    # --- Fire ---
    waste_percent: Decimal | None = None
    if waste_cell is not None:
        if _formula_without_cache(waste_cell):
            issues.append(_formula_issue(MetrajColumn.WASTE))
        elif not looks_empty(waste_raw):
            waste_percent, waste_issue = _read_waste(waste_raw, waste_cell)
            if waste_issue is not None:
                issues.append(waste_issue)

    # --- Formül önbelleği bilgisi (yalnızca bilgi notu) ---
    for column, cell in (
        (MetrajColumn.BOQ_NO, boq_cell),
        (MetrajColumn.DESCRIPTION, desc_cell),
        (MetrajColumn.QUANTITY, qty_cell),
        (MetrajColumn.UNIT, unit_cell),
        (MetrajColumn.WASTE, waste_cell),
    ):
        if cell is not None and cell.is_formula and cell.has_cached_result:
            notes.append(
                f"{column.value}: formül sonucu Excel önbelleğinden okundu."
            )

    return MetrajRow(
        source_row=row_number,
        boq_no=boq_no,
        description=description,
        quantity=quantity,
        unit=unit_text,
        unit_value=unit_value,
        waste_percent=waste_percent,
        issues=tuple(issues),
        scope_issues=tuple(scope_issues),
        notes=tuple(notes),
    )


def _formula_without_cache(cell: _RawCell) -> bool:
    return cell.is_formula and not cell.has_cached_result


def _formula_issue(column: MetrajColumn) -> CellIssue:
    return CellIssue(
        column=column,
        reason=InvalidReason.FORMULA_WITHOUT_CACHE,
        message=(
            "Hücrede formül var ancak önbelleğe alınmış sonuç yok. "
            "Formül sonucu sıfır/boş kabul edilmez."
        ),
        suggestion=(
            "Dosyayı Excel'de açıp hesaplamasını bekleyin ve kaydedin; ya da "
            "hücreye hesaplanmış değeri yazın."
        ),
    )


def _read_quantity(raw: object, cell: _RawCell | None) -> tuple[Decimal | None, CellIssue | None]:
    """Miktarı okur; okunamazsa ``None`` + açık hata döndürür."""
    is_percent_format = cell is not None and "%" in (cell.number_format or "")

    if isinstance(raw, str):
        try:
            value = parse_decimal_text(raw)
        except NumberParseError as exc:
            reason = (
                InvalidReason.AMBIGUOUS_NUMBER if exc.ambiguous else InvalidReason.INVALID_QUANTITY
            )
            suggestion = (
                "Ondalık ayırıcıyı netleştirin: 1240 için '1.240' veya 1,24 "
                "için '1,24' yazın."
                if exc.ambiguous
                else "Miktarı sayı olarak girin (örn. 96 veya 1,24)."
            )
            return None, CellIssue(
                column=MetrajColumn.QUANTITY,
                reason=reason,
                message=f"Miktar okunamadı: {exc.message}",
                suggestion=suggestion,
            )
    else:
        try:
            value = decimal_from_number(raw)
        except NumberParseError as exc:
            return None, CellIssue(
                column=MetrajColumn.QUANTITY,
                reason=InvalidReason.INVALID_QUANTITY,
                message=f"Miktar okunamadı: {exc.message}",
                suggestion="Miktarı sayı olarak girin (örn. 96 veya 1,24).",
            )

    if is_percent_format:
        return None, CellIssue(
            column=MetrajColumn.QUANTITY,
            reason=InvalidReason.UNREADABLE_VALUE,
            message=(
                "Miktar hücresi yüzde biçiminde. Saklanan değer gerçek "
                "miktarın yüzde biri olduğu için okunamaz."
            ),
            suggestion="Miktar hücresinin biçimini 'Sayı' yapın.",
        )

    if value <= 0:
        return None, CellIssue(
            column=MetrajColumn.QUANTITY,
            reason=InvalidReason.NON_POSITIVE_QUANTITY,
            message=f"Miktar sıfır veya negatif: {value}.",
            suggestion="Miktar sıfırdan büyük olmalıdır.",
        )

    return value, None


#: Birim eş anlamlıları. Kapalı liste; tanınmayan birim sessizce çevrilmez.
_UNIT_ALIASES: dict[str, Unit] = {
    "m": Unit.M,
    "metre": Unit.M,
    "meter": Unit.M,
    "kg": Unit.KG,
    "kilogram": Unit.KG,
    "t": Unit.T,
    "ton": Unit.T,
    "tonne": Unit.T,
}


def _read_unit(raw: object) -> tuple[str | None, Unit | None, CellIssue | None]:
    if not isinstance(raw, str):
        return None, None, CellIssue(
            column=MetrajColumn.UNIT,
            reason=InvalidReason.MISSING_UNIT,
            message=f"Birim metin olmalı (bulunan: {type(raw).__name__}).",
            suggestion="Birim girin: m, kg veya t.",
        )

    text = raw.strip()
    key = tr_lower(text)
    unit = _UNIT_ALIASES.get(key)
    if unit is None:
        # Desteklenmeyen ama okunabilir birim: hata değil, kapsam dışı.
        return text, None, None
    return text, unit, None


def _read_waste(raw: object, cell: _RawCell) -> tuple[Decimal | None, CellIssue | None]:
    is_percent_format = "%" in (cell.number_format or "")

    if isinstance(raw, str):
        try:
            value = parse_percent_text(raw)
        except NumberParseError as exc:
            reason = (
                InvalidReason.AMBIGUOUS_NUMBER if exc.ambiguous else InvalidReason.INVALID_WASTE
            )
            return None, CellIssue(
                column=MetrajColumn.WASTE,
                reason=reason,
                message=f"Fire oranı okunamadı: {exc.message}",
                suggestion="Fire yüzdesini sayı olarak girin (örn. 5 veya 2,5).",
            )
    else:
        try:
            value = decimal_from_number(raw)
        except NumberParseError as exc:
            return None, CellIssue(
                column=MetrajColumn.WASTE,
                reason=InvalidReason.INVALID_WASTE,
                message=f"Fire oranı okunamadı: {exc.message}",
                suggestion="Fire yüzdesini sayı olarak girin (örn. 5).",
            )

    if is_percent_format:
        # Excel "%5" hücresinde 0.05 saklar: bu kullanıcının girdiği değerdir.
        value = scale_percent(value)

    if value < 0:
        return None, CellIssue(
            column=MetrajColumn.WASTE,
            reason=InvalidReason.NEGATIVE_WASTE,
            message=f"Fire negatif olamaz: {value}.",
            suggestion="Fire yüzdesini 0 ile 100 arasında girin.",
        )

    if value > 100:
        return None, CellIssue(
            column=MetrajColumn.WASTE,
            reason=InvalidReason.WASTE_OVER_100,
            message=f"Fire %100'ü geçemez: {value}.",
            suggestion=(
                "Fire'ı yüzde olarak girin (%5 için 5). Oran olarak girdiyseniz "
                "100 ile çarpın."
            ),
        )

    return value, None


def _flag_duplicates(rows: tuple[MetrajRow, ...]) -> tuple[MetrajRow, ...]:
    """Aynı BOQ No'yu kullanan satırları ``duplicate-boq-no`` ile işaretler.

    İlk satırı geçerli sayıp sonrakini ezmek sessiz bir seçim olurdu; kullanıcı
    hangi satırın doğru olduğunu kendisi belirlemelidir.

    Ancak hatalı bir satırın numarası, **kullanılabilir** bir satırı geçersiz
    kılmaz: hatalı satır zaten hesaba giremez, geçerli satırı da düşürmek
    veriyi boşa harcar. Bu yüzden geçerli satır yalnızca **başka bir geçerli**
    satırla çakıştığında geçersiz olur; hatalı satırlar ise çakışmayı her
    durumda bilgi olarak taşır.
    """
    groups: dict[str, list[int]] = {}
    for position, row in enumerate(rows):
        if row.boq_no is None:
            continue
        groups.setdefault(tr_lower(row.boq_no).strip(), []).append(position)

    duplicated = {
        key: positions for key, positions in groups.items() if len(positions) > 1
    }
    if not duplicated:
        return rows

    result = list(rows)
    for positions in duplicated.values():
        row_numbers = [rows[position].source_row for position in positions]
        valid_positions = [position for position in positions if rows[position].is_valid]

        for position in positions:
            row = rows[position]
            # Geçerli satır yalnızca **başka bir geçerli** satırla çakışıyorsa
            # geçersiz olur; hatalı satırlarla çakışması veriyi boşa harcamaz.
            if row.is_valid and len(valid_positions) <= 1:
                continue

            others = [number for number in row_numbers if number != row.source_row]
            extra = CellIssue(
                column=MetrajColumn.BOQ_NO,
                reason=InvalidReason.DUPLICATE_BOQ_NO,
                message=(
                    f"BOQ No {row.boq_no!r} birden fazla satırda kullanılmış "
                    f"(satırlar: {', '.join(str(number) for number in row_numbers)})."
                ),
                suggestion=(
                    f"Bu satıra veya {', '.join(str(number) for number in others)}. "
                    "satıra benzersiz bir BOQ No verin; hangisinin geçerli olduğu "
                    "tahmin edilmez."
                ),
            )
            result[position] = MetrajRow(
                source_row=row.source_row,
                boq_no=row.boq_no,
                description=row.description,
                quantity=row.quantity,
                unit=row.unit,
                unit_value=row.unit_value,
                waste_percent=row.waste_percent,
                issues=(*row.issues, extra),
                scope_issues=row.scope_issues,
                notes=row.notes,
            )

    return tuple(result)
