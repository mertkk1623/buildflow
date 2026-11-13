"""Satın alma miktarı hesaplama motoru — Aşama 4.2.

Akış
----
BOQ satırı → birim dönüşümü (metre ekseni) → fire → aynı katalog kodunda
birleştirme → ticari boy ile **tek** yuvarlama → ``kg/m`` ile teorik ağırlık.

Değişmez kurallar
-----------------
1. **Fire satır bazındadır.** Yüzde olarak tanımlanır ve
   ``brüt = net × (1 + fire / 100)`` ile uygulanır. Satırda fire yoksa
   katalog varsayılanı (*oran* olarak) kullanılır ve kaynağı izde görünür.
   İkisi de yoksa fire **sıfır varsayılmaz**: fireli miktar ``None`` kalır ve
   grup ``PARTIAL`` olur.
2. **Birimler doğrudan toplanmaz.** Önce metre eksenine inilir
   (:mod:`app.domain.units`). ``kg`` ve ``t`` satırları ``kg/m`` üzerinden
   metreye çevrilir; ``kg/m`` yoksa satırın metresi bilinmiyor kalır.
3. **Yalnızca aynı katalog kodu birleşir.** Farklı kodlar hiçbir koşulda
   birleştirilmez; ölçü/kalite/kaplama farkı ayrı gruptur.
4. **Ticari boy yuvarlaması birleştirmeden sonra ve yalnızca bir kez**
   yapılır: ``ceil(toplam / ticari boy) × ticari boy``. Satır bazında
   yuvarlama yapılmaz. Ticari boy yoksa varsayılan kullanılmaz → ``PARTIAL``.
5. **Eksik veri sıfır değildir.** Hesaplanamayan alan ``None`` kalır ve
   gerekçesi :class:`MissingData` olarak kaydedilir.
6. **Alan bazlı sonuç.** Ağırlık hesaplanamasa bile sipariş miktarı
   hesaplanmış olabilir; her alan ayrı taşınır, grup yalnızca gerçekten
   eksik olan alan için ``PARTIAL`` olur.
7. **Sayı tipi.** Hesaplar ``Decimal`` ile yürür. ``float`` sessizce
   dönüştürülmez: float gelen miktar **geçersiz satır** sayılır.

Ağırlık etiketi
---------------
``weight_kg`` daima **teorik çıplak çelik kütlesidir**. Galvaniz kaplama
kütlesi dahil değildir; gerçek sevkiyat veya tedarikçi kantar ağırlığı olarak
sunulmamalıdır (bkz. :attr:`GroupCalculation.weight_note`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from enum import Enum

from app.domain.catalog import Catalog
from app.domain.models import (
    CatalogItem,
    Coating,
    Grade,
    MatchOutcome,
    MatchStatus,
    MaterialFamily,
    Unit,
)
from app.domain.units import (
    DIVISION_PRECISION,
    ConversionStatus,
    ConversionStep,
    convert_to_metres,
)

#: İç hesap hassasiyeti. Toplama/çarpma bu hassasiyetle yürür; gösterim
#: yuvarlaması bundan ayrıdır (ROADMAP §7: "round only for display").
CALC_PRECISION = 50

#: Boy sayısı oranı için bölme artığı toleransı.
#:
#: ``kg ÷ kg/m`` tekrarlayan ondalık üretir (ör. 1240 ÷ 22.4). Birkaç satırın
#: toplamı tam bir boy sayısına denk geldiğinde, bölme artıkları toplamı
#: ``19.99999999999999999999999999`` yapabilir ve ``ceil`` gereksizce bir
#: fazla boy verir. Orana bu eşikten yakın sonuçlar tam sayı kabul edilir.
#:
#: Eşik, 28 haneli bölmenin üretebileceği artıktan (≈1E-22 mertebesi) çok
#: büyük, gerçek bir kesirden ise ayırt edilemeyecek kadar küçüktür. Bu bir
#: *bölme artığı temizliğidir*; ölçü eşleştirmesinde tolerans değildir ve
#: gerçek bir kesir asla aşağı yuvarlanmaz.
BAR_RATIO_QUANTUM = Decimal("1E-15")

#: Fire oranı üst sınırı (yüzde). %100'ün üzeri metraj hatası sayılır
#: (ör. Excel'e yüzde yerine oran girilmesi) ve sessizce hesaba katılmaz.
MAX_WASTE_PERCENT = Decimal("100")

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")
_PERCENT_SHIFT = Decimal("0.01")


class CalculationError(Exception):
    """Hesap girdisi sözleşmesi ihlal edildi (ör. yinelenen satır no)."""


class WasteRateError(ValueError):
    """Fire oranı geçersiz (aralık dışı, sonsuz veya float)."""


# ---------------------------------------------------------------------------
# Fire oranı
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WasteRate:
    """Fire oranı — **yüzde** olarak taşınır.

    Tek kanonik alan :attr:`percent`'tir. İki kurucu vardır ve hangi ölçeğin
    kullanıldığı böylece açık olur:

    * :meth:`from_percent` — ``WasteRate.from_percent("5")`` = %5
    * :meth:`from_fraction` — ``WasteRate.from_fraction("0.05")`` = %5
      (V1 BOQ/Excel ve frontend sözleşmesi fire'ı 0–1 oranı olarak taşır)

    "%5 mi 0.05 mi" sorusu çağrı yerinde açıkça cevaplanır; tahmin edilmez.
    ``float`` kabul edilmez.
    """

    percent: Decimal

    def __post_init__(self) -> None:
        value = _as_decimal(self.percent)
        if value is None:
            raise WasteRateError(
                f"Fire oranı sonlu bir Decimal olmalı: {self.percent!r}"
            )
        if value < _ZERO:
            raise WasteRateError(f"Fire oranı negatif olamaz: {value}")
        if value > MAX_WASTE_PERCENT:
            raise WasteRateError(
                f"Fire oranı %{MAX_WASTE_PERCENT} üstüne çıkamaz: {value}. "
                "Yüzde yerine oran girilmiş olabilir."
            )
        object.__setattr__(self, "percent", value)

    @classmethod
    def from_percent(cls, value: Decimal | int | str) -> "WasteRate":
        """Yüzde değerinden kurar: ``5`` → %5."""
        return cls(percent=value)  # type: ignore[arg-type]

    @classmethod
    def from_fraction(cls, value: Decimal | int | str) -> "WasteRate":
        """0–1 aralığındaki orandan kurar: ``0.05`` → %5."""
        fraction = _as_decimal(value)
        if fraction is None:
            raise WasteRateError(f"Fire oranı sonlu bir Decimal olmalı: {value!r}")
        if fraction < _ZERO or fraction > _ONE:
            raise WasteRateError(
                f"Fire oranı 0–1 aralığında olmalı (oran): {fraction}. "
                "Yüzde girilmiş olabilir."
            )
        return cls(percent=fraction * _HUNDRED)

    @property
    def fraction(self) -> Decimal:
        """0–1 aralığındaki karşılığı (gösterim/karşılaştırma için)."""
        return self.percent * _PERCENT_SHIFT

    @property
    def factor(self) -> Decimal:
        """``1 + fire/100`` çarpanı."""
        return _ONE + self.percent * _PERCENT_SHIFT

    def apply(self, net: Decimal) -> Decimal:
        """Net miktara fire uygular: ``net × (1 + fire/100)``."""
        return net * self.factor

    def __str__(self) -> str:  # pragma: no cover - kolaylık
        return f"%{self.percent}"


def _as_decimal(value: object) -> Decimal | None:
    """Değeri **sonlu** ``Decimal``'a çevirir; çevrilemiyorsa ``None``.

    ``float`` bilinçli olarak reddedilir: ``Decimal(0.1)`` ikili kesir hatasını
    içeri taşır. ``bool`` de reddedilir (``True == 1`` tuzağı).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except (InvalidOperation, ValueError):
            return None
    else:
        return None
    return result if result.is_finite() else None


def _positive_decimal(value: object) -> Decimal | None:
    """Pozitif ve sonlu ``Decimal``; aksi hâlde ``None`` (sıfır varsayılmaz)."""
    result = _as_decimal(value)
    if result is None or result <= _ZERO:
        return None
    return result


# ---------------------------------------------------------------------------
# Girdi satırı
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CalculationInputRow:
    """Hesaba girecek tek BOQ satırı — kaynak veri + eşleştirme sonucu.

    ``quantity`` kaynak birimindedir (``unit``). Dönüşüm, fire ve ticari boy
    hesabı bu sınıfın dışında yapılır; satır yalnızca *girdiyi* taşır.

    Fire oranı satırda yoksa ``None`` bırakılmalıdır; katalog varsayılanı
    (varsa) motor tarafından uygulanır. İkisi de yoksa hesap ``PARTIAL`` olur.
    """

    row_no: str
    description: str
    quantity: Decimal
    unit: Unit | str | None
    waste_rate: WasteRate | None = None
    status: MatchStatus = MatchStatus.RULE
    matched_code: str | None = None

    def __post_init__(self) -> None:
        # Birim metni geldiyse normalize et; desteklenmeyen birim ``None`` olur
        # ve motor satırı "geçersiz" olarak ayırır (sessizce m'ye çevrilmez).
        unit = self.unit
        if isinstance(unit, str):
            try:
                object.__setattr__(self, "unit", Unit(unit.strip().lower()))
            except ValueError:
                object.__setattr__(self, "unit", None)

        if self.waste_rate is not None and not isinstance(self.waste_rate, WasteRate):
            raise CalculationError(
                f"{self.row_no}: waste_rate bir WasteRate olmalı "
                f"(bulunan: {type(self.waste_rate).__name__}). Oran/yüzde "
                "belirsizliği sessizce çözülmez; WasteRate.from_percent veya "
                "WasteRate.from_fraction kullanın."
            )

        if not isinstance(self.status, MatchStatus):
            raise CalculationError(
                f"{self.row_no}: status bir MatchStatus olmalı "
                f"(bulunan: {type(self.status).__name__})."
            )

    @classmethod
    def from_outcome(
        cls,
        *,
        row_no: str,
        description: str,
        quantity: Decimal,
        unit: Unit | str | None,
        waste_rate: WasteRate | None,
        outcome: MatchOutcome,
    ) -> "CalculationInputRow":
        """Eşleştirme sonucundan satır kurar (4.4 API'si için tek yol).

        Durum ve kod **her zaman** ``outcome``'dan alınır; istemciden gelen
        bir değere güvenilmez.
        """
        return cls(
            row_no=row_no,
            description=description,
            quantity=quantity,
            unit=unit,
            waste_rate=waste_rate,
            status=outcome.status,
            matched_code=outcome.matched_code,
        )


# ---------------------------------------------------------------------------
# Sonuç modelleri
# ---------------------------------------------------------------------------


class CalculationStatus(str, Enum):
    """Grup düzeyinde hesaplama durumu."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"


class SkipReason(str, Enum):
    """Satırın neden hesaba girmediği."""

    PENDING = "pending"
    REJECTED = "rejected"
    EXCLUDED = "excluded"
    INVALID = "invalid"
    UNKNOWN_CODE = "unknown-code"


class CalculationField(str, Enum):
    """Eksik veri nedeniyle hesaplanamayan alan."""

    FIRE = "fire"
    CONVERSION = "conversion"
    COMMERCIAL_LENGTH = "commercial-length"
    MASS = "mass"


class WasteSource(str, Enum):
    """Fire oranının kaynağı — izlenebilirlik."""

    ROW = "row"
    CATALOG = "catalog"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class MissingData:
    """Hesaplanamayan alanın gerekçesi. ``row_no`` varsa satıra özeldir."""

    field: CalculationField
    message: str
    row_no: str | None = None


@dataclass(frozen=True, slots=True)
class SourceRowCalculation:
    """Kaynak BOQ satırının izi — satın alma grubunun içinde taşınır."""

    row_no: str
    description: str
    source_quantity: Decimal
    source_unit: Unit | None
    net_metres: Decimal | None
    waste_percent: Decimal | None
    gross_metres: Decimal | None
    gross_quantity: Decimal | None
    waste_source: WasteSource = WasteSource.NONE
    conversion_steps: tuple[ConversionStep, ...] = ()

    @property
    def has_waste(self) -> bool:
        return self.waste_percent is not None

    @property
    def fire_quantity(self) -> Decimal | None:
        """Fire nedeniyle eklenen miktar (kaynak biriminde)."""
        if self.gross_quantity is None:
            return None
        return self.gross_quantity - self.source_quantity


@dataclass(frozen=True, slots=True)
class SkippedRow:
    """Hesaba alınmayan satır ve nedeni — izlenebilirlik için korunur."""

    row_no: str
    reason: SkipReason
    message: str
    matched_code: str | None = None
    match_status: MatchStatus | None = None


@dataclass(frozen=True, slots=True)
class GroupCalculation:
    """Tek katalog kodunun satın alma hesabı — alan bazlı sonuç."""

    code: str
    family: MaterialFamily
    family_label: str
    size: str
    grade: Grade
    coating: Coating
    mass_kg_per_m: Decimal | None
    commercial_length_m: Decimal | None
    bar_count: Decimal | None
    total_gross_metres: Decimal | None
    order_length_m: Decimal | None
    rounding_surplus_m: Decimal | None
    weight_kg: Decimal | None
    sources: tuple[SourceRowCalculation, ...]
    missing: tuple[MissingData, ...]
    status: CalculationStatus
    notes: tuple[str, ...] = field(default_factory=tuple)

    # --- Durum ---
    @property
    def is_full(self) -> bool:
        return self.status is CalculationStatus.FULL

    @property
    def source_row_numbers(self) -> tuple[str, ...]:
        return tuple(source.row_no for source in self.sources)

    @property
    def merged(self) -> bool:
        """Birden fazla BOQ satırı bu grupta birleşti mi?"""
        return len(self.sources) > 1

    @property
    def missing_fields(self) -> tuple[CalculationField, ...]:
        seen: list[CalculationField] = []
        for item in self.missing:
            if item.field not in seen:
                seen.append(item.field)
        return tuple(seen)

    @property
    def product_label(self) -> str:
        return f"{self.family_label} {self.size} · {self.grade.value} · {self.coating.value}"

    # --- Ağırlık etiketi (K2 kararı) ---
    @property
    def weight_label(self) -> str:
        return "Teorik çıplak çelik ağırlığı"

    @property
    def weight_note(self) -> str:
        if self.coating is Coating.GALVANIZED:
            return (
                "Çıplak çelik kütlesi. Galvaniz kaplama kütlesi dahil değildir; "
                "gerçek sevkiyat veya tedarikçi kantar ağırlığı değildir."
            )
        return (
            "Çıplak çelik kütlesi. Gerçek sevkiyat veya tedarikçi kantar "
            "ağırlığı değildir."
        )


@dataclass(frozen=True, slots=True)
class CalculationResult:
    """Tüm BOQ için hesap sonucu."""

    groups: tuple[GroupCalculation, ...]
    skipped: tuple[SkippedRow, ...]
    input_row_count: int

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def calculated_row_count(self) -> int:
        return sum(len(group.sources) for group in self.groups)

    @property
    def merged_group_count(self) -> int:
        """Birden fazla satırı birleştiren grup sayısı."""
        return sum(1 for group in self.groups if group.merged)

    @property
    def merge_count(self) -> int:
        """Birleşme sayısı: ``hesap satırı − grup``."""
        return self.calculated_row_count - self.group_count

    @property
    def full_groups(self) -> tuple[GroupCalculation, ...]:
        return tuple(group for group in self.groups if group.is_full)

    @property
    def partial_groups(self) -> tuple[GroupCalculation, ...]:
        return tuple(group for group in self.groups if not group.is_full)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def known_weight_kg(self) -> Decimal:
        """Ağırlığı hesaplanabilen grupların toplamı (kısmi toplam)."""
        total = _ZERO
        for group in self.groups:
            if group.weight_kg is not None:
                total += group.weight_kg
        return total

    @property
    def weight_complete(self) -> bool:
        """Tüm grupların ağırlığı hesaplandı mı?"""
        return all(group.weight_kg is not None for group in self.groups)

    def group(self, code: str) -> GroupCalculation:
        """Koda göre grubu döndürür; yoksa ``KeyError``."""
        for group in self.groups:
            if group.code == code:
                return group
        raise KeyError(code)


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

_ELIGIBLE_STATUSES = (MatchStatus.RULE, MatchStatus.AI_APPROVED)

_SKIP_REASON_BY_STATUS: dict[MatchStatus, SkipReason] = {
    MatchStatus.PENDING: SkipReason.PENDING,
    MatchStatus.REJECTED: SkipReason.REJECTED,
    MatchStatus.EXCLUDED: SkipReason.EXCLUDED,
    # Excel okumasında veri hatalı/okunamadı: ``excluded`` ile karıştırılmaz.
    MatchStatus.INVALID: SkipReason.INVALID,
}

_SKIP_MESSAGES: dict[SkipReason, str] = {
    SkipReason.PENDING: "Satır henüz onaylanmadı (pending); hesaplamaya alınmaz.",
    SkipReason.REJECTED: "Satır reddedildi; hesaplamaya alınmaz.",
    SkipReason.EXCLUDED: "Satır hesap kapsamı dışında bırakıldı; hesaplamaya alınmaz.",
    SkipReason.INVALID: "Satır geçersiz; hesaplamaya alınmaz.",
}


def calculate_purchase_list(
    rows: Sequence[CalculationInputRow],
    catalog: Catalog,
    *,
    commercial_length_overrides: Mapping[str, Decimal | None] | None = None,
    mass_overrides: Mapping[str, Decimal | None] | None = None,
) -> CalculationResult:
    """BOQ satırlarından satın alma listesi üretir.

    Parameters
    ----------
    rows:
        Kaynak satırlar. Sıra korunur; gruplar ilk görülme sırasına göre
        döner (deterministik çıktı).
    catalog:
        Doğrulanmış katalog. ``mass_kg_per_m`` ve ``commercial_length_m``
        buradan okunur.
    commercial_length_overrides:
        Tedarikçi bazlı ticari boy geçersiz kılması (K1 kararı). Anahtar
        katalog kodu, değer metre cinsinden boy **veya** ``None``.
        ``None`` "bu kod için ticari boy bilinmiyor" demektir: varsayılana
        düşülmez, grup ``PARTIAL`` olur.
    mass_overrides:
        Tedarikçi/parti bazlı ``kg/m`` geçersiz kılması. Değer ``None`` ise
        "bu kod için birim kütle bilinmiyor" demektir: ``kg``/``t`` satırları
        metreye çevrilemez ve ağırlık hesaplanmaz. Sıfır **varsayılmaz**.

    Raises
    ------
    CalculationError
        Yinelenen satır numarası (izlenebilirlik bozulur).
    """
    ordered_rows = tuple(rows)
    _assert_unique_row_numbers(ordered_rows)

    groups: dict[str, list[SourceRowCalculation]] = {}
    skipped: list[SkippedRow] = []

    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        for row in ordered_rows:
            skip = _classify(row)
            if skip is not None:
                skipped.append(skip)
                continue

            code = row.matched_code
            assert code is not None  # _classify garanti eder
            item = catalog.get(code)
            if item is None:
                skipped.append(
                    SkippedRow(
                        row_no=row.row_no,
                        reason=SkipReason.UNKNOWN_CODE,
                        message=(
                            f"Eşleşen kod katalogda bulunmuyor: {code!r}. "
                            "Satır hesaba alınmadı."
                        ),
                        matched_code=code,
                        match_status=row.status,
                    )
                )
                continue

            groups.setdefault(code, []).append(
                _evaluate_source_row(row, item, _resolve_mass(code, item, mass_overrides))
            )

        calculations = tuple(
            _calculate_group(
                code,
                sources,
                catalog,
                commercial_length_overrides,
                mass_overrides,
            )
            for code, sources in groups.items()
        )

    return CalculationResult(
        groups=calculations,
        skipped=tuple(skipped),
        input_row_count=len(ordered_rows),
    )


def _assert_unique_row_numbers(rows: Sequence[CalculationInputRow]) -> None:
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row.row_no, str) or not row.row_no.strip():
            raise CalculationError("Boş BOQ satır numarası: izlenebilirlik kurulamaz.")
        if row.row_no in seen:
            raise CalculationError(
                f"Yinelenen BOQ satır numarası: {row.row_no!r}. "
                "İzlenebilirlik için satır numaraları tekil olmalıdır."
            )
        seen.add(row.row_no)


def _classify(row: CalculationInputRow) -> SkippedRow | None:
    """Satır hesaba girmeyecekse nedenini döndürür."""
    if row.status not in _ELIGIBLE_STATUSES:
        reason = _SKIP_REASON_BY_STATUS.get(row.status, SkipReason.INVALID)
        return SkippedRow(
            row_no=row.row_no,
            reason=reason,
            message=_SKIP_MESSAGES[reason],
            matched_code=row.matched_code,
            match_status=row.status,
        )

    if not row.matched_code:
        return SkippedRow(
            row_no=row.row_no,
            reason=SkipReason.INVALID,
            message=(
                f"Satır {row.status.value} durumunda ama katalog kodu yok. "
                "Kod olmadan miktar hesaplanamaz; satır hesaba alınmadı."
            ),
            matched_code=None,
            match_status=row.status,
        )

    if row.unit is None or not isinstance(row.unit, Unit):
        return SkippedRow(
            row_no=row.row_no,
            reason=SkipReason.INVALID,
            message=(
                "Birim desteklenmiyor (m, kg, t dışında). Satır hesaba alınmadı; "
                "miktar sessizce dönüştürülmez."
            ),
            matched_code=row.matched_code,
            match_status=row.status,
        )

    quantity = _as_decimal(row.quantity)
    if quantity is None:
        return SkippedRow(
            row_no=row.row_no,
            reason=SkipReason.INVALID,
            message=(
                f"Miktar geçersiz: {row.quantity!r}. Sayısal, sonlu ve Decimal "
                "olmalı; float kabul edilmez."
            ),
            matched_code=row.matched_code,
            match_status=row.status,
        )

    if quantity <= _ZERO:
        return SkippedRow(
            row_no=row.row_no,
            reason=SkipReason.INVALID,
            message=(
                f"Miktar pozitif olmalı (bulunan: {quantity}). Sıfır/negatif "
                "miktar hesaba alınmaz."
            ),
            matched_code=row.matched_code,
            match_status=row.status,
        )

    return None


def _catalog_mass(item: CatalogItem) -> Decimal | None:
    """Katalogdaki kg/m — geçersizse ``None`` (sıfır varsayılmaz)."""
    return _positive_decimal(getattr(item, "mass_kg_per_m", None))


def _resolve_mass(
    code: str,
    item: CatalogItem,
    overrides: Mapping[str, Decimal | None] | None,
) -> Decimal | None:
    """Birim kütleyi çözer: geçersiz kılma varsa o, yoksa katalog değeri."""
    if overrides is not None and code in overrides:
        return _positive_decimal(overrides[code])
    return _catalog_mass(item)


def _resolve_waste(
    row: CalculationInputRow,
    item: CatalogItem,
) -> tuple[WasteRate | None, WasteSource]:
    """Fire oranını ve kaynağını çözer.

    Sıra: satır fire'ı → katalog varsayılanı. Katalogdaki ``default_waste``
    **oran** olarak saklanır (0–1); yüzdeye çevrilir. İkisi de yoksa
    ``(None, NONE)`` döner ve sıfır varsayılmaz.
    """
    if row.waste_rate is not None:
        return row.waste_rate, WasteSource.ROW

    default = _as_decimal(getattr(item, "default_waste", None))
    if default is None or default < _ZERO or default > _ONE:
        return None, WasteSource.NONE

    return WasteRate.from_fraction(default), WasteSource.CATALOG


def _evaluate_source_row(
    row: CalculationInputRow,
    item: CatalogItem,
    mass_kg_per_m: Decimal | None,
) -> SourceRowCalculation:
    """Tek satırı metre eksenine indirir ve fireyi **satır bazında** uygular."""
    quantity = _as_decimal(row.quantity)
    assert quantity is not None  # _classify garanti eder
    unit = row.unit
    assert unit is not None

    conversion = convert_to_metres(quantity, unit, mass_kg_per_m)
    net_metres = conversion.metres if conversion.status is ConversionStatus.OK else None

    waste, waste_source = _resolve_waste(row, item)

    gross_metres: Decimal | None = None
    gross_quantity: Decimal | None = None
    if waste is not None:
        gross_quantity = waste.apply(quantity)
        if net_metres is not None:
            gross_metres = waste.apply(net_metres)

    return SourceRowCalculation(
        row_no=row.row_no,
        description=row.description,
        source_quantity=quantity,
        source_unit=unit,
        net_metres=net_metres,
        waste_percent=waste.percent if waste is not None else None,
        gross_metres=gross_metres,
        gross_quantity=gross_quantity,
        waste_source=waste_source,
        conversion_steps=conversion.steps,
    )


def _calculate_group(
    code: str,
    sources: list[SourceRowCalculation],
    catalog: Catalog,
    overrides: Mapping[str, Decimal | None] | None,
    mass_overrides: Mapping[str, Decimal | None] | None,
) -> GroupCalculation:
    """Birleştirilmiş grup toplamına ticari boy yuvarlamasını **bir kez** uygular."""
    item = catalog.require(code)
    mass = _resolve_mass(code, item, mass_overrides)
    length = _commercial_length(code, item, overrides)

    missing: list[MissingData] = []
    notes: list[str] = []

    # --- Satır bazlı eksikler ---
    for source in sources:
        if source.waste_percent is None:
            missing.append(
                MissingData(
                    field=CalculationField.FIRE,
                    row_no=source.row_no,
                    message=(
                        "Fire oranı tanımsız (satırda ve katalogda yok). Fireli "
                        "miktar hesaplanamadı; sıfır varsayılmadı."
                    ),
                )
            )
        if source.net_metres is None:
            missing.append(
                MissingData(
                    field=CalculationField.CONVERSION,
                    row_no=source.row_no,
                    message=(
                        "Birim kütle (kg/m) tanımlı olmadığı için miktar metreye "
                        "çevrilemedi; sıfır varsayılmadı."
                    ),
                )
            )
        if source.waste_source is WasteSource.CATALOG:
            notes.append(
                f"{source.row_no}: fire oranı satırda yok, katalog varsayılanı "
                f"%{source.waste_percent} kullanıldı."
            )

    # --- Birleşik toplam (yalnızca metre ekseninde) ---
    total_gross: Decimal | None = _ZERO
    for source in sources:
        if source.gross_metres is None:
            total_gross = None
            break
        total_gross += source.gross_metres

    # --- Ticari boy ---
    if length is None:
        missing.append(
            MissingData(
                field=CalculationField.COMMERCIAL_LENGTH,
                message=(
                    "Ticari boy tanımlı değil. Varsayılan boy kullanılmaz; sipariş "
                    "miktarı yuvarlanamadı."
                ),
            )
        )

    # --- Tek yuvarlama ---
    bar_count: Decimal | None = None
    order_length: Decimal | None = None
    surplus: Decimal | None = None
    if total_gross is not None and length is not None:
        bar_count = _bar_count(total_gross, length)
        order_length = bar_count * length
        surplus = order_length - total_gross
        rounded_surplus = surplus.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        if rounded_surplus > _ZERO:
            notes.append(
                "Yuvarlama nedeniyle "
                f"{rounded_surplus} m fazla sipariş edildi."
            )

    if len(sources) > 1:
        notes.append(
            f"{len(sources)} kaynak satır aynı katalog kodunda birleştirildi: "
            + ", ".join(source.row_no for source in sources)
        )

    # --- Ağırlık: sipariş uzunluğu × kg/m (teorik çıplak çelik) ---
    weight: Decimal | None = None
    if mass is None:
        missing.append(
            MissingData(
                field=CalculationField.MASS,
                message=(
                    "Birim kütle (kg/m) tanımlı değil; teorik ağırlık "
                    "hesaplanamadı. Sıfır varsayılmadı."
                ),
            )
        )
    elif order_length is not None:
        weight = order_length * mass
    elif total_gross is None:
        notes.append(
            "Teorik ağırlık hesaplanmadı: fireli toplam miktar üretilemediği "
            "için sipariş uzunluğu bilinmiyor."
        )
    else:
        notes.append(
            "Teorik ağırlık hesaplanmadı: ticari boy bilinmediği için sipariş "
            "uzunluğu üretilemedi."
        )

    # --- Durum: yalnızca gerçekten eksik alan PARTIAL yapar ---
    complete = (
        not missing
        and total_gross is not None
        and order_length is not None
        and surplus is not None
        and weight is not None
    )
    status = CalculationStatus.FULL if complete else CalculationStatus.PARTIAL

    return GroupCalculation(
        code=item.code,
        family=item.family,
        family_label=item.family_label,
        size=item.size,
        grade=item.grade,
        coating=item.coating,
        mass_kg_per_m=mass,
        commercial_length_m=length,
        bar_count=bar_count,
        total_gross_metres=total_gross,
        order_length_m=order_length,
        rounding_surplus_m=surplus,
        weight_kg=weight,
        sources=tuple(sources),
        missing=tuple(missing),
        status=status,
        notes=tuple(notes),
    )


def _bar_count(total_metres: Decimal, length_m: Decimal) -> Decimal:
    """``ceil(toplam / ticari boy)`` — grup başına yalnızca bir kez çağrılır.

    ``kg ÷ kg/m`` bölmesi tekrarlayan ondalık üretir. Birkaç satırın toplamı
    tam bir boy sayısına denk geldiğinde (ör. 20 m), 28 haneli bölme
    artıkları toplamı ``19.99999999999999999999999999`` yapabilir ve ``ceil``
    gereksizce bir fazla boy verir. Tam sayıya ``BAR_RATIO_QUANTUM`` kadar
    yakın oranlar tam sayı kabul edilir. Bu yalnızca bölme artığını temizler;
    gerçek bir kesir **asla** aşağı yuvarlanmaz.
    """
    with localcontext() as ctx:
        ctx.prec = DIVISION_PRECISION
        raw = total_metres / length_m

    nearest = raw.to_integral_value(rounding=ROUND_HALF_UP)
    if abs(raw - nearest) <= BAR_RATIO_QUANTUM:
        return nearest
    return raw.to_integral_value(rounding=ROUND_CEILING)


def _commercial_length(
    code: str,
    item: CatalogItem,
    overrides: Mapping[str, Decimal | None] | None,
) -> Decimal | None:
    """Ticari boyu çözer: tedarikçi geçersiz kılması → katalog değeri.

    ``None`` "bilinmiyor" demektir; hiçbir varsayılan uygulanmaz.
    """
    if overrides is not None and code in overrides:
        return _positive_decimal(overrides[code])
    return _positive_decimal(getattr(item, "commercial_length_m", None))


#: Gösterim için varsayılan ondalık hane (ROADMAP §7: "round only for display").
DISPLAY_PLACES = 3


def display_decimal(value: Decimal | None, places: int = DISPLAY_PLACES) -> Decimal | None:
    """Değeri **yalnızca gösterim** için yuvarlar.

    Hesap zincirinde bu fonksiyon kullanılmaz; ara değerler tam hassasiyetle
    taşınır. ``None`` (hesaplanamayan alan) ``None`` kalır — sıfıra çevrilmez.
    """
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)

