"""Katalog yükleme ve doğrulama testleri."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.catalog import (
    CatalogError,
    DEFAULT_CATALOG_PATH,
    load_catalog,
    parse_catalog,
)
from app.domain.models import Coating, Grade, MaterialFamily

EXPECTED_MASS: dict[str, str] = {
    "BOX-60-60-3-S235-B": "5.19",
    "BOX-80-80-3-S235-B": "7.07",
    "BOX-100-4-S235-B": "11.70",
    "BOX-100-4-S235-G": "11.70",
    "BOX-150-100-5-S235-B": "18.30",
    "IPE-200-S235": "22.40",
    "IPE-240-S355": "30.70",
    "HEA-160-S235": "30.40",
    "HEA-200-S235": "42.30",
    "UPN-100-S235": "10.60",
    "UPN-160-S235": "18.80",
    "FLAT-40x5-S235-B": "1.570",
    "FLAT-40x5-S235-G": "1.570",
    "FLAT-50x6-S235-B": "2.355",
}

EXPECTED_LENGTH: dict[str, str] = {
    "BOX-60-60-3-S235-B": "6",
    "BOX-80-80-3-S235-B": "6",
    "BOX-100-4-S235-B": "6",
    "BOX-100-4-S235-G": "6",
    "BOX-150-100-5-S235-B": "6",
    "IPE-200-S235": "12",
    "IPE-240-S355": "12",
    "HEA-160-S235": "12",
    "HEA-200-S235": "12",
    "UPN-100-S235": "12",
    "UPN-160-S235": "12",
    "FLAT-40x5-S235-B": "6",
    "FLAT-40x5-S235-G": "6",
    "FLAT-50x6-S235-B": "6",
}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def _payload() -> dict:
    return json.loads(Path(DEFAULT_CATALOG_PATH).read_text(encoding="utf-8"))


def test_catalog_default_path_exists() -> None:
    assert DEFAULT_CATALOG_PATH.exists()


def test_all_fourteen_items_load(catalog) -> None:
    assert len(catalog) == 14
    assert set(item.code for item in catalog) == set(EXPECTED_MASS)


def test_codes_are_unique(catalog) -> None:
    codes = [item.code for item in catalog]
    assert len(codes) == len(set(codes))


def test_mass_values_are_exact_decimals(catalog) -> None:
    for code, expected in EXPECTED_MASS.items():
        item = catalog.require(code)
        assert item.mass_kg_per_m == Decimal(expected), code
        assert isinstance(item.mass_kg_per_m, Decimal)


def test_mass_precision_is_not_lost(catalog) -> None:
    """Decimal korunmalı: float'a düşerse 1.570 → 1.57 olur ama
    2.355 gibi değerlerde ikili kesir hatası oluşur."""
    assert catalog.require("FLAT-50x6-S235-B").mass_kg_per_m == Decimal("2.355")
    assert catalog.require("FLAT-40x5-S235-B").mass_kg_per_m == Decimal("1.570")
    assert str(catalog.require("FLAT-40x5-S235-B").mass_kg_per_m) == "1.570"


def test_commercial_lengths_match_approved_decisions(catalog) -> None:
    for code, expected in EXPECTED_LENGTH.items():
        assert catalog.require(code).commercial_length_m == Decimal(expected), code


def test_lengths_by_family(catalog) -> None:
    for item in catalog:
        if item.family is MaterialFamily.BOX:
            assert item.commercial_length_m == Decimal("6")
        elif item.family is MaterialFamily.FLAT:
            assert item.commercial_length_m == Decimal("6")
        else:
            assert item.commercial_length_m == Decimal("12")


def test_every_item_has_mass_source(catalog) -> None:
    for item in catalog:
        assert item.mass_source.standard, item.code
        assert item.mass_source.reference, item.code
        assert item.mass_source.method in {"table", "formula"}


def test_every_item_has_length_source(catalog) -> None:
    for item in catalog:
        assert item.length_source.basis, item.code
        assert item.length_source.reference, item.code


def test_all_default_waste_null(catalog) -> None:
    for item in catalog:
        assert item.default_waste is None, item.code


def test_production_standard_matches_manufacturing(catalog) -> None:
    for item in catalog:
        if item.family is MaterialFamily.BOX:
            assert item.production_standard == "EN 10219-2", item.code
            assert item.manufacturing.value == "cold-formed", item.code


def test_box_150_100_5_is_cold_formed_18_30(catalog) -> None:
    """K3 kararı: EN 10219-2 soğuk şekillendirilmiş, 18.30 kg/m.
    Sıcak işlem görmüş EN 10210 değeri (18.6) kullanılmamalı."""
    item = catalog.require("BOX-150-100-5-S235-B")
    assert item.mass_kg_per_m == Decimal("18.30")
    assert item.mass_source.standard.startswith("EN 10219")
    assert item.manufacturing.value == "cold-formed"


def test_galvanized_items_are_bare_steel_mass() -> None:
    """K2 kararı: galvaniz kaplama kütlesi dahil değildir."""
    catalog = load_catalog()
    black = catalog.require("BOX-100-4-S235-B")
    galv = catalog.require("BOX-100-4-S235-G")
    assert galv.mass_kg_per_m == black.mass_kg_per_m
    assert "çıplak" in galv.mass_source.reference.lower() or "ÇIPLAK" in galv.mass_source.note.upper()

    galv_flat = catalog.require("FLAT-40x5-S235-G")
    black_flat = catalog.require("FLAT-40x5-S235-B")
    assert galv_flat.mass_kg_per_m == black_flat.mass_kg_per_m


def test_grade_and_coating_coverage(catalog) -> None:
    grades = {item.grade for item in catalog}
    coatings = {item.coating for item in catalog}
    assert grades == {Grade.S235, Grade.S355}
    assert coatings == {Coating.BLACK, Coating.GALVANIZED}


def test_identical_identity_is_rejected() -> None:
    """Aynı dört özelliğe sahip iki kalem eşleştirmeyi belirsizleştirir."""
    payload = _payload()
    duplicate = dict(payload["items"][0])
    duplicate["code"] = "BOX-60-60-3-S235-B-COPY"
    payload["items"].append(duplicate)

    with pytest.raises(CatalogError, match="Aynı dört özelliğe sahip"):
        parse_catalog(payload)


def test_duplicate_code_is_rejected() -> None:
    payload = _payload()
    payload["items"].append(dict(payload["items"][0]))

    with pytest.raises(CatalogError, match="Yinelenen katalog kodu"):
        parse_catalog(payload)


def test_missing_mass_is_rejected() -> None:
    payload = _payload()
    del payload["items"][0]["mass_kg_per_m"]

    with pytest.raises(CatalogError):
        parse_catalog(payload)


def test_zero_mass_is_rejected() -> None:
    payload = _payload()
    payload["items"][0]["mass_kg_per_m"] = "0"

    with pytest.raises(CatalogError):
        parse_catalog(payload)


def test_non_null_default_waste_is_rejected() -> None:
    payload = _payload()
    payload["items"][0]["default_waste"] = "0.05"

    with pytest.raises(CatalogError, match="default_waste null olmalıdır"):
        parse_catalog(payload)


def test_unsupported_schema_version_is_rejected() -> None:
    payload = _payload()
    payload["schema_version"] = "9.9"

    with pytest.raises(CatalogError, match="şema sürümü"):
        parse_catalog(payload)


def test_missing_size_component_is_rejected() -> None:
    payload = _payload()
    payload["items"][0]["size"] = "60×60"

    with pytest.raises(CatalogError):
        parse_catalog(payload)


def test_en10219_cannot_be_hot_finished() -> None:
    """Üretim standardı ile üretim yolu çelişmemeli."""
    payload = _payload()
    payload["items"][0]["manufacturing"] = "hot-finished"

    with pytest.raises(CatalogError):
        parse_catalog(payload)


def test_unknown_code_raises(catalog) -> None:
    with pytest.raises(KeyError):
        catalog.require("NOPE-1")


def test_has_code(catalog) -> None:
    assert catalog.has_code("IPE-200-S235")
    assert not catalog.has_code("IPE-999-S235")


def test_by_family(catalog) -> None:
    assert len(catalog.by_family(MaterialFamily.BOX)) == 5
    assert len(catalog.by_family(MaterialFamily.IPE)) == 2
    assert len(catalog.by_family(MaterialFamily.HEA)) == 2
    assert len(catalog.by_family(MaterialFamily.UPN)) == 2
    assert len(catalog.by_family(MaterialFamily.FLAT)) == 3


def test_by_identity_is_exact(catalog) -> None:
    item = catalog.by_identity(
        MaterialFamily.BOX, "100×100×4", Grade.S235, Coating.BLACK
    )
    assert item is not None
    assert item.code == "BOX-100-4-S235-B"

    # Ölçü farkı eşleşmemeli
    assert (
        catalog.by_identity(MaterialFamily.BOX, "100×100×5", Grade.S235, Coating.BLACK)
        is None
    )


def test_lengths_in_use_groups_by_length(catalog) -> None:
    grouped = catalog.lengths_in_use()
    assert set(grouped) == {Decimal("6"), Decimal("12")}
    assert len(grouped[Decimal("6")]) == 8  # 5 BOX + 3 FLAT
    assert len(grouped[Decimal("12")]) == 6  # 2 IPE + 2 HEA + 2 UPN
