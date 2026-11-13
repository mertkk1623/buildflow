"""Birim dönüşümü testleri — kanonik eksen metre."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.models import Unit
from app.domain.units import (
    ConversionStatus,
    convert_to_metres,
    mass_from_length,
    to_kilograms,
)

MASS_BOX_100 = Decimal("11.70")
MASS_IPE_200 = Decimal("22.40")
MASS_IPE_240 = Decimal("30.70")


def test_96_metres_stays_96_metres() -> None:
    result = convert_to_metres(Decimal("96"), Unit.M, MASS_BOX_100)
    assert result.status is ConversionStatus.OK
    assert result.metres == Decimal("96")
    assert result.require_metres() == Decimal("96")


def test_1240_kg_converts_via_mass_per_metre() -> None:
    """1240 kg ÷ 22.40 kg/m = 55.357142857... m"""
    result = convert_to_metres(Decimal("1240"), Unit.KG, MASS_IPE_200)
    assert result.status is ConversionStatus.OK
    assert result.metres is not None
    # Tam değer tekrar çarpıldığında 1240'a dönmeli (hassasiyet korunur).
    assert abs(result.metres * MASS_IPE_200 - Decimal("1240")) < Decimal("1E-20")


def test_084_tonnes_converts_to_840_kg_then_metres() -> None:
    """0.84 t = 840 kg; 840 ÷ 30.70 = 27.361... m"""
    result = convert_to_metres(Decimal("0.84"), Unit.T, MASS_IPE_240)
    assert result.status is ConversionStatus.OK
    assert result.metres is not None
    assert abs(result.metres * MASS_IPE_240 - Decimal("840")) < Decimal("1E-20")


def test_ton_conversion_records_both_steps() -> None:
    result = convert_to_metres(Decimal("0.84"), Unit.T, MASS_IPE_240)
    labels = [step.label for step in result.steps]
    assert labels == ["Ton → kilogram", "Kilogram → metre"]
    assert result.steps[0].result == Decimal("840.00")


def test_missing_mass_is_not_zero() -> None:
    """kg/m yoksa satır hesap dışıdır; sıfır varsayılmaz."""
    result = convert_to_metres(Decimal("500"), Unit.KG, None)
    assert result.status is ConversionStatus.MISSING_MASS
    assert result.metres is None
    assert not result.ok

    with pytest.raises(ValueError, match="Metre değeri yok"):
        result.require_metres()


def test_missing_mass_message_is_explicit() -> None:
    result = convert_to_metres(Decimal("500"), Unit.KG, None)
    assert "kg/m" in result.message
    assert "hesap dışı" in result.message


def test_unsupported_unit_is_not_in_enum() -> None:
    """``adet`` kapsam dışıdır: enum'da yoktur, sessizce dönüştürülmez."""
    with pytest.raises(ValueError):
        Unit("adet")


def test_supported_units_are_exactly_m_kg_t() -> None:
    from app.domain.units import SUPPORTED_UNITS

    assert SUPPORTED_UNITS == (Unit.M, Unit.KG, Unit.T)


def test_metres_work_without_mass() -> None:
    """``m`` birimi kg/m gerektirmez."""
    result = convert_to_metres(Decimal("54"), Unit.M, None)
    assert result.status is ConversionStatus.OK
    assert result.metres == Decimal("54")


@pytest.mark.parametrize("bad", ["0", "-5"])
def test_non_positive_quantity_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="pozitif"):
        convert_to_metres(Decimal(bad), Unit.M, MASS_BOX_100)


def test_zero_mass_is_rejected_not_silently_used() -> None:
    with pytest.raises(ValueError, match="pozitif"):
        convert_to_metres(Decimal("100"), Unit.KG, Decimal("0"))


def test_to_kilograms() -> None:
    assert to_kilograms(Decimal("5"), Unit.KG) == Decimal("5")
    assert to_kilograms(Decimal("1.5"), Unit.T) == Decimal("1500.0")


def test_mass_from_length() -> None:
    assert mass_from_length(Decimal("96"), MASS_BOX_100) == Decimal("1123.20")


def test_mass_from_length_rejects_negative() -> None:
    with pytest.raises(ValueError, match="negatif"):
        mass_from_length(Decimal("-1"), MASS_BOX_100)


def test_different_units_are_not_added_directly() -> None:
    """Farklı birimlerin ham değerleri toplanamaz; önce metreye inilmelidir.

    Bu test, yanlış bir uygulamanın (ham miktarları toplamanın) neden
    yanlış olduğunu belgeler.
    """
    metres = convert_to_metres(Decimal("96"), Unit.M, MASS_BOX_100)
    kilograms = convert_to_metres(Decimal("1240"), Unit.KG, MASS_IPE_200)

    assert metres.unit != kilograms.unit
    # Ham toplam anlamsızdır:
    assert metres.quantity + kilograms.quantity == Decimal("1336")
    # Doğru olan metre ekseninde toplamaktır (Aşama 4.2).
    assert metres.require_metres() == Decimal("96")


def test_division_precision_survives_round_trip() -> None:
    """Ara hesap yuvarlanmaz; 1 kg'lık geri dönüş hatası oluşmamalı."""
    for quantity, mass in [
        (Decimal("1240"), Decimal("22.40")),
        (Decimal("840"), Decimal("30.70")),
        (Decimal("210"), Decimal("1.570")),
        (Decimal("150"), Decimal("1.570")),
    ]:
        result = convert_to_metres(quantity, Unit.KG, mass)
        assert result.metres is not None
        assert abs(result.metres * mass - quantity) < Decimal("1E-20")
