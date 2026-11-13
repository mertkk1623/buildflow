"""Birim dönüşümü — kanonik hesap ekseni metre.

Tasarım kararları
-----------------
1. **Kanonik eksen metredir.** ``kg`` ve ``t``, ``kg/m`` üzerinden metreye indirilir.
2. **``kg/m`` yoksa dönüşüm yapılmaz.** ``kg``/``t`` satırı hesap dışı kalır
   (``missing-mass``). Sıfır varsayılmaz — "eksik veri sıfır değildir".
3. **Farklı birimler doğrudan toplanmaz.** Toplama yalnızca dönüşüm sonrası
   metre ekseninde yapılır (bkz. Aşama 4.2).
4. **``adet`` desteklenmez.** Kapsam dışıdır, sessizce dönüştürülmez.
5. Bölme sonucu sonlu olmayabilir; ``DIVISION_PRECISION`` hane ile taşınır.
   Yuvarlama **gösterimde** yapılır, ara hesapta değil.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import Enum

from app.domain.models import Unit

#: Ara hesap hassasiyeti (anlamlı hane). Gösterim yuvarlaması bundan ayrıdır.
DIVISION_PRECISION = 28

#: Desteklenen birimler. ``adet`` bilinçli olarak listede yoktur.
SUPPORTED_UNITS: tuple[Unit, ...] = (Unit.M, Unit.KG, Unit.T)

#: Bir tonun kilogram karşılığı.
KG_PER_TONNE = Decimal("1000")


class ConversionStatus(str, Enum):
    OK = "ok"
    #: Birim geçerli ama ``kg/m`` tanımlı değil → metreye inilemez.
    MISSING_MASS = "missing-mass"


@dataclass(frozen=True, slots=True)
class ConversionStep:
    """Dönüşümün tek adımı — raporda gösterilir."""

    label: str
    expression: str
    result: Decimal


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Bir satır miktarının metre eksenine indirgenmesi."""

    status: ConversionStatus
    unit: Unit
    quantity: Decimal
    mass_kg_per_m: Decimal | None
    metres: Decimal | None
    steps: tuple[ConversionStep, ...]
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ConversionStatus.OK

    def require_metres(self) -> Decimal:
        """Dönüşüm başarısızsa sessizce 0 döndürmez; hata verir."""
        if self.metres is None:
            raise ValueError(
                f"Metre değeri yok ({self.status.value}): {self.message or 'neden belirtilmedi'}"
            )
        return self.metres


def _divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DIVISION_PRECISION
        return numerator / denominator


def to_kilograms(quantity: Decimal, unit: Unit) -> Decimal:
    """Miktarı kilograma çevirir. ``m`` için anlamlı değildir."""
    if unit is Unit.KG:
        return quantity
    if unit is Unit.T:
        return quantity * KG_PER_TONNE
    raise ValueError(f"{unit.value!r} birimi kilograma çevrilemez.")


def convert_to_metres(
    quantity: Decimal,
    unit: Unit,
    mass_kg_per_m: Decimal | None,
) -> ConversionResult:
    """Miktarı metre eksenine indirger.

    ``kg/m`` yoksa ``MISSING_MASS`` döner ve ``metres`` ``None`` kalır.
    Çağıran taraf bu satırı **hesap dışı** saymak zorundadır.
    """
    if quantity <= 0:
        raise ValueError(f"Miktar pozitif olmalı: {quantity}")

    if unit is Unit.M:
        return ConversionResult(
            status=ConversionStatus.OK,
            unit=unit,
            quantity=quantity,
            mass_kg_per_m=mass_kg_per_m,
            metres=quantity,
            steps=(
                ConversionStep(
                    label="Zaten metre",
                    expression="miktar (m)",
                    result=quantity,
                ),
            ),
        )

    if unit not in (Unit.KG, Unit.T):  # pragma: no cover - Unit enum'u kapalı
        raise ValueError(f"Bilinmeyen birim: {unit!r}")

    if mass_kg_per_m is None:
        return ConversionResult(
            status=ConversionStatus.MISSING_MASS,
            unit=unit,
            quantity=quantity,
            mass_kg_per_m=None,
            metres=None,
            steps=(),
            message=(
                f"Birim kütle (kg/m) tanımlı olmadığı için {unit.value!r} "
                "miktarı metreye çevrilemez. Satır hesap dışıdır; sıfır kabul edilmez."
            ),
        )

    if mass_kg_per_m <= 0:
        raise ValueError(f"Birim kütle pozitif olmalı: {mass_kg_per_m}")

    steps: list[ConversionStep] = []

    if unit is Unit.T:
        kilograms = quantity * KG_PER_TONNE
        steps.append(
            ConversionStep(
                label="Ton → kilogram",
                expression=f"{quantity} t × 1000",
                result=kilograms,
            )
        )
    else:
        kilograms = quantity

    metres = _divide(kilograms, mass_kg_per_m)
    steps.append(
        ConversionStep(
            label="Kilogram → metre",
            expression=f"{kilograms} kg ÷ {mass_kg_per_m} kg/m",
            result=metres,
        )
    )

    return ConversionResult(
        status=ConversionStatus.OK,
        unit=unit,
        quantity=quantity,
        mass_kg_per_m=mass_kg_per_m,
        metres=metres,
        steps=tuple(steps),
    )


def mass_from_length(length_m: Decimal, mass_kg_per_m: Decimal) -> Decimal:
    """Metre uzunluğun teorik kütlesi (çıplak çelik)."""
    if length_m < 0:
        raise ValueError(f"Uzunluk negatif olamaz: {length_m}")
    if mass_kg_per_m <= 0:
        raise ValueError(f"Birim kütle pozitif olmalı: {mass_kg_per_m}")
    return length_m * mass_kg_per_m
