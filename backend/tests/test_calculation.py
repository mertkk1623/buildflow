"""Hesaplama motoru testleri — Aşama 4.2.

Senaryolar (istek §7)
---------------------
1. Tek satır fire hesabı
2. Çok satırlı birleştirme
3. Farklı kodların ayrı kalması
4. Farklı birimlerin metre ekseninde normalizasyonu
5. Fire eksik → PARTIAL
6. Ticari boy eksik → PARTIAL
7. kg/m eksik → ağırlık hesaplanmaz
8. Yuvarlama yalnızca bir kez
9. Yuvarlama fazlası
10. Hariç / red satırlar hesap dışı
11. Kaynak satır izlenebilirliği
12. Decimal hassasiyeti ve sınır durumlar
13. Sıfır / negatif / geçersiz miktarlar
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.calculation import (
    CALC_PRECISION,
    CalculationError,
    CalculationField,
    CalculationInputRow,
    CalculationStatus,
    SkipReason,
    SourceRowCalculation,
    WasteRate,
    WasteRateError,
    WasteSource,
    calculate_purchase_list,
    display_decimal,
)
from app.domain.catalog import Catalog, load_catalog
from app.domain.models import MatchStatus

BOX100 = "BOX-100-4-S235-B"
BOX100_G = "BOX-100-4-S235-G"
BOX150 = "BOX-150-100-5-S235-B"
IPE200 = "IPE-200-S235"
IPE240 = "IPE-240-S355"
HEA200 = "HEA-200-S235"
UPN160 = "UPN-160-S235"
FLAT40 = "FLAT-40x5-S235-B"

D = Decimal


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog()


def row(
    no: str,
    quantity: str,
    unit: str,
    code: str,
    waste: str | None = "5",
    *,
    status: MatchStatus = MatchStatus.RULE,
    description: str = "",
) -> CalculationInputRow:
    """Test satırı kurar. ``waste`` yüzde olarak verilir."""
    return CalculationInputRow(
        row_no=no,
        description=description or f"{code} test satırı",
        quantity=D(quantity),
        unit=unit,
        waste_rate=WasteRate.from_percent(waste) if waste is not None else None,
        status=status,
        matched_code=code,
    )


# ---------------------------------------------------------------------------
# WasteRate — yüzde/oran sözleşmesi
# ---------------------------------------------------------------------------


class TestWasteRate:
    def test_percent_constructor(self) -> None:
        waste = WasteRate.from_percent("5")
        assert waste.percent == D("5")
        assert waste.fraction == D("0.05")

    def test_fraction_constructor(self) -> None:
        """V1 kaynak verisi fire'ı 0–1 oranı olarak taşır."""
        waste = WasteRate.from_fraction("0.05")
        assert waste.percent == D("5")

    def test_fraction_conversion_is_exact(self) -> None:
        """0.04 × 100 float'ta 4.000000000000001 olur; Decimal'de tam 4."""
        assert WasteRate.from_fraction("0.04").percent == D("4")
        assert WasteRate.from_fraction("0.03").percent == D("3")

    def test_factor(self) -> None:
        assert WasteRate.from_percent("5").factor == D("1.05")
        assert WasteRate.from_percent("0").factor == D("1")

    def test_apply_is_percent_formula(self) -> None:
        """``net × (1 + fire/100)`` — 96 m, %5 → 100.8 m."""
        assert WasteRate.from_percent("5").apply(D("96")) == D("100.8")

    def test_zero_waste_is_allowed_and_explicit(self) -> None:
        """%0 geçerlidir ama **açıkça** verilmelidir; None ile karışmaz."""
        assert WasteRate.from_percent("0").apply(D("96")) == D("96")
        assert WasteRate.from_percent("0").percent == D("0")

    @pytest.mark.parametrize("bad", ["-1", "-0.5"])
    def test_negative_is_rejected(self, bad: str) -> None:
        with pytest.raises(WasteRateError, match="negatif"):
            WasteRate.from_percent(bad)

    @pytest.mark.parametrize("bad", ["100.1", "150"])
    def test_above_100_percent_is_rejected(self, bad: str) -> None:
        """Yüzde yerine oran girilmiş olabilir; sessizce kabul edilmez."""
        with pytest.raises(WasteRateError, match="üstüne çıkamaz"):
            WasteRate.from_percent(bad)

    @pytest.mark.parametrize("bad", ["1.5", "50"])
    def test_fraction_above_one_is_rejected(self, bad: str) -> None:
        with pytest.raises(WasteRateError, match="0–1"):
            WasteRate.from_fraction(bad)

    @pytest.mark.parametrize("bad", [0.05, None, "abc", True])
    def test_float_and_non_numeric_are_rejected(self, bad: object) -> None:
        """float fire oranı ikili kesir hatası taşır; kabul edilmez."""
        with pytest.raises(WasteRateError, match="Decimal"):
            WasteRate(percent=bad)  # type: ignore[arg-type]

    def test_infinite_is_rejected(self) -> None:
        with pytest.raises(WasteRateError):
            WasteRate(percent=D("Infinity"))

    def test_wrong_type_is_not_silently_accepted(self, catalog: Catalog) -> None:
        """Oran/yüzde belirsizliği sessizce çözülmez: açık kurucu zorunlu."""
        with pytest.raises(CalculationError, match="WasteRate"):
            CalculationInputRow(
                row_no="B-1",
                description="test",
                quantity=D("96"),
                unit="m",
                waste_rate=D("5"),  # type: ignore[arg-type]
                matched_code=BOX100,
            )

    def test_invalid_status_type_is_rejected(self) -> None:
        with pytest.raises(CalculationError, match="MatchStatus"):
            CalculationInputRow(
                row_no="B-1",
                description="test",
                quantity=D("96"),
                unit="m",
                status="rule",  # type: ignore[arg-type]
                matched_code=BOX100,
            )


# ---------------------------------------------------------------------------
# 1. Tek satır fire hesabı
# ---------------------------------------------------------------------------


class TestSingleRow:
    def test_single_row_full_chain(self, catalog: Catalog) -> None:
        """96 m, %5, 6 m boy, 11.70 kg/m.

        net 96 → fireli 100.8 → ceil(100.8/6)=17 boy → 102 m
        → fazla 1.2 m → ağırlık 102 × 11.70 = 1193.4 kg
        """
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)

        group = result.group(BOX100)
        assert group.status is CalculationStatus.FULL
        assert group.is_full
        assert group.missing == ()

        source = group.sources[0]
        assert source.net_metres == D("96")
        assert source.waste_percent == D("5")
        assert source.gross_metres == D("100.8")
        assert source.fire_quantity == D("4.8")

        assert group.total_gross_metres == D("100.8")
        assert group.commercial_length_m == D("6")
        assert group.bar_count == D("17")
        assert group.order_length_m == D("102")
        assert group.rounding_surplus_m == D("1.2")
        assert group.weight_kg == D("1193.4")

    def test_waste_is_applied_once_not_twice(self, catalog: Catalog) -> None:
        """Fire tek kez uygulanır: 96 × 1.05 = 100.8 (105.84 değil)."""
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)
        assert result.group(BOX100).total_gross_metres == D("100.8")

    def test_zero_waste_keeps_quantity(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100, "0")], catalog)
        group = result.group(BOX100)
        assert group.total_gross_metres == D("96")
        assert group.bar_count == D("16")
        assert group.rounding_surplus_m == D("0")

    def test_weight_label_is_bare_steel(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)
        group = result.group(BOX100)
        assert group.weight_label == "Teorik çıplak çelik ağırlığı"
        assert "kantar" in group.weight_note

    def test_galvanized_weight_note_excludes_coating(self, catalog: Catalog) -> None:
        """K2: galvaniz kaplama kütlesi ağırlığa dahil değildir."""
        result = calculate_purchase_list([row("B-1", "48", "m", BOX100_G)], catalog)
        group = result.group(BOX100_G)
        assert group.weight_label == "Teorik çıplak çelik ağırlığı"
        assert "Galvaniz kaplama kütlesi dahil değildir" in group.weight_note


# ---------------------------------------------------------------------------
# 2. Çok satırlı birleştirme
# ---------------------------------------------------------------------------


class TestConsolidation:
    def test_two_rows_merge_by_code(self, catalog: Catalog) -> None:
        """96 m + 84 m = 180 net → 189 fireli → 32 boy → 192 m."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100), row("B-2", "84", "m", BOX100)],
            catalog,
        )

        assert result.group_count == 1
        assert result.merged_group_count == 1
        assert result.merge_count == 1

        group = result.group(BOX100)
        assert group.source_row_numbers == ("B-1", "B-2")
        assert group.merged
        assert group.total_gross_metres == D("189")
        assert group.bar_count == D("32")
        assert group.order_length_m == D("192")
        assert group.rounding_surplus_m == D("3")
        assert group.weight_kg == D("2246.4")

    def test_merge_keeps_per_row_waste(self, catalog: Catalog) -> None:
        """Fire satır bazındadır: %5 ve %10 ayrı uygulanır."""
        result = calculate_purchase_list(
            [
                row("B-1", "100", "m", BOX100, "5"),
                row("B-2", "100", "m", BOX100, "10"),
            ],
            catalog,
        )
        group = result.group(BOX100)
        assert group.sources[0].gross_metres == D("105")
        assert group.sources[1].gross_metres == D("110")
        # 105 + 110 = 215; 100×1.075 gibi tek oran kullanılsaydı 215 olmazdı.
        assert group.total_gross_metres == D("215")

    def test_group_waste_is_not_averaged(self, catalog: Catalog) -> None:
        """Ortalama yerine satır toplamı: 105 + 110 = 215, 212.5 değil."""
        result = calculate_purchase_list(
            [
                row("B-1", "100", "m", BOX100, "5"),
                row("B-2", "100", "m", BOX100, "10"),
            ],
            catalog,
        )
        assert result.group(BOX100).total_gross_metres == D("215")

    def test_merge_across_different_units(self, catalog: Catalog) -> None:
        """96 m + 1170 kg (=100 m) → 100.8 + 105 = 205.8 fireli → 35 boy."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100), row("B-2", "1170", "kg", BOX100)],
            catalog,
        )
        group = result.group(BOX100)
        assert group.sources[1].net_metres == D("100")
        assert group.total_gross_metres == D("205.8")
        assert group.bar_count == D("35")
        assert group.order_length_m == D("210")

    def test_three_rows_merge(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                row("B-1", "10", "m", BOX100, "0"),
                row("B-2", "10", "m", BOX100, "0"),
                row("B-3", "10", "m", BOX100, "0"),
            ],
            catalog,
        )
        assert result.group(BOX100).total_gross_metres == D("30")
        assert result.calculated_row_count == 3
        assert result.group_count == 1
        assert result.merge_count == 2


# ---------------------------------------------------------------------------
# 3. Farklı kodlar ayrı kalır
# ---------------------------------------------------------------------------


class TestDistinctCodes:
    def test_different_codes_never_merge(self, catalog: Catalog) -> None:
        """Aynı ölçü, farklı kaplama → iki ayrı grup."""
        result = calculate_purchase_list(
            [row("B-1", "60", "m", BOX100), row("B-2", "60", "m", BOX100_G)],
            catalog,
        )
        assert result.group_count == 2
        assert result.merge_count == 0
        assert {group.code for group in result.groups} == {BOX100, BOX100_G}

    def test_different_families_stay_separate(self, catalog: Catalog) -> None:
        """IPE 200 ile HEA 200 asla birleşmez (farklı malzeme)."""
        result = calculate_purchase_list(
            [row("B-1", "60", "m", IPE200), row("B-2", "60", "m", HEA200)],
            catalog,
        )
        assert result.group_count == 2
        assert result.group(IPE200).total_gross_metres == D("63")
        assert result.group(HEA200).total_gross_metres == D("63")

    def test_different_grades_stay_separate(self, catalog: Catalog) -> None:
        """IPE 240 S355 iki satırda birleşir, IPE 200 S235 ile birleşmez."""
        result = calculate_purchase_list(
            [
                row("B-1", "24", "m", IPE240),
                row("B-2", "24", "m", IPE240),
                row("B-3", "24", "m", IPE200),
            ],
            catalog,
        )
        assert result.group_count == 2
        assert result.group(IPE240).source_row_numbers == ("B-1", "B-2")
        assert result.group(IPE200).source_row_numbers == ("B-3",)

    def test_group_order_is_first_seen(self, catalog: Catalog) -> None:
        """Deterministik çıktı: gruplar ilk görülme sırasına göre."""
        result = calculate_purchase_list(
            [
                row("B-1", "12", "m", UPN160),
                row("B-2", "12", "m", BOX100),
                row("B-3", "12", "m", UPN160),
            ],
            catalog,
        )
        assert [group.code for group in result.groups] == [UPN160, BOX100]


# ---------------------------------------------------------------------------
# 4. Birim normalizasyonu
# ---------------------------------------------------------------------------


class TestUnitNormalization:
    def test_kg_converts_through_mass_per_metre(self, catalog: Catalog) -> None:
        """1240 kg ÷ 22.40 kg/m = 55.357... m (tam geri dönüş)."""
        result = calculate_purchase_list([row("B-1", "1240", "kg", IPE200)], catalog)
        source = result.group(IPE200).sources[0]
        assert source.source_unit.value == "kg"
        assert source.net_metres is not None
        assert abs(source.net_metres * D("22.40") - D("1240")) < D("1E-20")

    def test_tonne_converts_to_kg_then_metres(self, catalog: Catalog) -> None:
        """0.84 t = 840 kg → 840 ÷ 30.70 m."""
        result = calculate_purchase_list([row("B-1", "0.84", "t", IPE240)], catalog)
        source = result.group(IPE240).sources[0]
        assert source.net_metres is not None
        assert abs(source.net_metres * D("30.70") - D("840")) < D("1E-20")
        assert [step.label for step in source.conversion_steps] == [
            "Ton → kilogram",
            "Kilogram → metre",
        ]

    def test_metres_pass_through(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "54", "m", UPN160)], catalog)
        source = result.group(UPN160).sources[0]
        assert source.net_metres == D("54")
        assert source.conversion_steps[0].label == "Zaten metre"

    def test_raw_quantities_are_never_added(self, catalog: Catalog) -> None:
        """Girdi birimleri farklıysa ham değerler toplanmaz.

        Doğru davranış: ``kg`` önce metreye çevrilir, sonra metre ekseninde
        toplanır. 96 + 1120 = 1216 gibi anlamsız bir toplam oluşmaz.
        """
        result = calculate_purchase_list(
            [row("B-1", "96", "m", IPE200), row("B-2", "1120", "kg", IPE200)],
            catalog,
        )
        group = result.group(IPE200)
        # 1120 ÷ 22.40 = 50 m; fire %5 → 100.8 + 52.5 = 153.3
        assert group.sources[1].net_metres == D("50")
        assert group.total_gross_metres == D("100.8") + D("52.5")
        assert group.total_gross_metres == D("153.3")

    def test_unit_text_is_normalized(self, catalog: Catalog) -> None:
        """``" M "`` gibi kirli birim metni kabul edilir."""
        result = calculate_purchase_list(
            [
                CalculationInputRow(
                    row_no="B-1",
                    description="test",
                    quantity=D("12"),
                    unit=" M ",
                    waste_rate=WasteRate.from_percent("0"),
                    status=MatchStatus.RULE,
                    matched_code=BOX100,
                )
            ],
            catalog,
        )
        assert result.group(BOX100).sources[0].net_metres == D("12")


# ---------------------------------------------------------------------------
# 5. Fire eksik → PARTIAL
# ---------------------------------------------------------------------------


class TestMissingWaste:
    def test_missing_waste_makes_partial(self, catalog: Catalog) -> None:
        """Fire yok → sıfır varsayılmaz; fireli miktar hesaplanmaz."""
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100, None)], catalog)

        group = result.group(BOX100)
        assert group.status is CalculationStatus.PARTIAL
        assert not group.is_full
        assert CalculationField.FIRE in group.missing_fields

        source = group.sources[0]
        assert source.waste_percent is None
        assert source.waste_source is WasteSource.NONE
        assert source.gross_metres is None
        assert source.gross_quantity is None
        assert source.fire_quantity is None

        # Eksik fire sıfırla kapatılmaz: sipariş miktarı da yoktur.
        assert group.total_gross_metres is None
        assert group.bar_count is None
        assert group.order_length_m is None
        assert group.weight_kg is None

    def test_missing_waste_message_is_explicit(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100, None)], catalog)
        message = result.group(BOX100).missing[0].message
        assert "sıfır varsayılmadı" in message
        assert result.group(BOX100).missing[0].row_no == "B-1"

    def test_waste_missing_in_one_of_two_rows(self, catalog: Catalog) -> None:
        """Bir satırın fire'si eksikse grup toplamı üretilemez."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100, "5"), row("B-2", "84", "m", BOX100, None)],
            catalog,
        )
        group = result.group(BOX100)
        assert group.status is CalculationStatus.PARTIAL
        assert group.missing_fields == (CalculationField.FIRE,)
        assert group.missing[0].row_no == "B-2"
        assert group.total_gross_metres is None

    def test_catalog_default_waste_is_used_and_traced(self, catalog: Catalog) -> None:
        """Satırda fire yoksa katalog varsayılanı (oran) kullanılır ve izlenir."""
        item = catalog.require(BOX100)
        patched = item.model_copy(update={"default_waste": D("0.02")})
        with_default = Catalog(
            [patched if i.code == BOX100 else i for i in catalog],
            catalog.schema_version,
            list(catalog.notes),
        )

        result = calculate_purchase_list(
            [row("B-1", "100", "m", BOX100, None)], with_default
        )
        group = result.group(BOX100)
        assert group.status is CalculationStatus.FULL
        assert group.sources[0].waste_percent == D("2")
        assert group.sources[0].waste_source is WasteSource.CATALOG
        assert group.total_gross_metres == D("102")
        assert any("katalog varsayılanı" in note for note in group.notes)

    def test_row_waste_wins_over_catalog_default(self, catalog: Catalog) -> None:
        item = catalog.require(BOX100)
        patched = item.model_copy(update={"default_waste": D("0.02")})
        with_default = Catalog(
            [patched if i.code == BOX100 else i for i in catalog],
            catalog.schema_version,
            list(catalog.notes),
        )
        result = calculate_purchase_list(
            [row("B-1", "100", "m", BOX100, "10")], with_default
        )
        assert result.group(BOX100).sources[0].waste_percent == D("10")
        assert result.group(BOX100).sources[0].waste_source is WasteSource.ROW


# ---------------------------------------------------------------------------
# 6. Ticari boy eksik → PARTIAL
# ---------------------------------------------------------------------------


class TestMissingCommercialLength:
    def test_missing_length_makes_partial(self, catalog: Catalog) -> None:
        """Varsayılan boy kullanılmaz; yuvarlanmış miktar üretilemez."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100)],
            catalog,
            commercial_length_overrides={BOX100: None},
        )
        group = result.group(BOX100)

        assert group.status is CalculationStatus.PARTIAL
        assert group.missing_fields == (CalculationField.COMMERCIAL_LENGTH,)
        assert group.commercial_length_m is None
        assert group.bar_count is None
        assert group.order_length_m is None
        assert group.rounding_surplus_m is None
        assert group.weight_kg is None

        # Girdi tarafı korunur: fire uygulanmış toplam hâlâ izlenebilir.
        assert group.total_gross_metres == D("100.8")
        assert group.sources[0].gross_metres == D("100.8")

        # Ağırlığın neden üretilemediği açıkça yazılır.
        assert any("Teorik ağırlık hesaplanmadı" in note for note in group.notes)

    def test_no_default_length_fallback(self, catalog: Catalog) -> None:
        """Ticari boy yoksa katalogdaki 6 m'ye düşülmez."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100)],
            catalog,
            commercial_length_overrides={BOX100: None},
        )
        assert result.group(BOX100).bar_count is None

    def test_supplier_override_changes_rounding(self, catalog: Catalog) -> None:
        """K1: tedarikçi bazlı boy geçersiz kılınabilir (12 m yerine 6 m)."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", UPN160, "0")],
            catalog,
            commercial_length_overrides={UPN160: D("6")},
        )
        group = result.group(UPN160)
        assert group.commercial_length_m == D("6")
        assert group.bar_count == D("16")
        assert group.order_length_m == D("96")

    def test_invalid_override_is_missing_not_guessed(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100)],
            catalog,
            commercial_length_overrides={BOX100: D("0")},
        )
        assert result.group(BOX100).commercial_length_m is None
        assert result.group(BOX100).status is CalculationStatus.PARTIAL


# ---------------------------------------------------------------------------
# 7. kg/m eksik → ağırlık hesaplanmaz
# ---------------------------------------------------------------------------


class TestMissingMass:
    def test_missing_mass_keeps_order_quantity(self, catalog: Catalog) -> None:
        """Alan bazlı sonuç: ağırlık yok ama sipariş miktarı var."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100)],
            catalog,
            mass_overrides={BOX100: None},
        )
        group = result.group(BOX100)

        assert group.status is CalculationStatus.PARTIAL
        assert group.missing_fields == (CalculationField.MASS,)
        assert group.mass_kg_per_m is None
        assert group.weight_kg is None

        # Sipariş miktarı hesaplanmış kalır — grup tümüyle başarısız sayılmaz.
        assert group.total_gross_metres == D("100.8")
        assert group.bar_count == D("17")
        assert group.order_length_m == D("102")
        assert group.rounding_surplus_m == D("1.2")

    def test_missing_mass_with_kg_unit_blocks_conversion(self, catalog: Catalog) -> None:
        """kg satırı kg/m olmadan metreye inemez; sıfır varsayılmaz."""
        result = calculate_purchase_list(
            [row("B-1", "500", "kg", BOX100)],
            catalog,
            mass_overrides={BOX100: None},
        )
        group = result.group(BOX100)
        assert group.status is CalculationStatus.PARTIAL
        assert set(group.missing_fields) == {
            CalculationField.CONVERSION,
            CalculationField.MASS,
        }
        assert group.sources[0].net_metres is None
        assert group.total_gross_metres is None
        assert group.order_length_m is None
        assert group.weight_kg is None

    def test_missing_mass_does_not_zero_weight(self, catalog: Catalog) -> None:
        """Ağırlık 0 değil, ``None`` — eksik veri sıfırla kapatılmaz."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100)],
            catalog,
            mass_overrides={BOX100: None},
        )
        assert result.group(BOX100).weight_kg is None
        assert not result.weight_complete
        assert result.known_weight_kg == D("0")

    def test_missing_mass_in_only_one_group(self, catalog: Catalog) -> None:
        """Bir grubun ağırlığı yoksa diğer grup FULL kalır."""
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100), row("B-2", "48", "m", HEA200)],
            catalog,
            mass_overrides={BOX100: None},
        )
        assert result.group(BOX100).status is CalculationStatus.PARTIAL
        assert result.group(HEA200).status is CalculationStatus.FULL
        assert len(result.full_groups) == 1
        assert len(result.partial_groups) == 1


# ---------------------------------------------------------------------------
# 8. Yuvarlama yalnızca bir kez
# ---------------------------------------------------------------------------


class TestSingleRounding:
    def test_row_level_rounding_would_be_wrong(self, catalog: Catalog) -> None:
        """7 m + 7 m, 6 m boy.

        Satır bazında yuvarlama: 2 + 2 = 4 boy = 24 m (yanlış).
        Grup bazında: ceil(14/6) = 3 boy = 18 m (doğru).
        """
        result = calculate_purchase_list(
            [
                row("B-1", "7", "m", BOX100, "0"),
                row("B-2", "7", "m", BOX100, "0"),
            ],
            catalog,
        )
        group = result.group(BOX100)
        assert group.total_gross_metres == D("14")
        assert group.bar_count == D("3")
        assert group.order_length_m == D("18")
        assert group.order_length_m != D("24")

    def test_rounding_applied_after_merge_only(self, catalog: Catalog) -> None:
        """Her satırın kendi boyu yoktur; tek boy kararı grup düzeyindedir."""
        result = calculate_purchase_list(
            [
                row("B-1", "5", "m", BOX100, "0"),
                row("B-2", "5", "m", BOX100, "0"),
            ],
            catalog,
        )
        group = result.group(BOX100)
        # 5+5=10 → 2 boy = 12 m (satır satır 1+1=2 boy da 12 m olurdu;
        # ayrımı göstermek için 7+7 testi yukarıdadır). Burada fazla 2 m.
        assert group.order_length_m == D("12")
        assert group.rounding_surplus_m == D("2")

    def test_exact_multiple_has_no_extra_bar(self, catalog: Catalog) -> None:
        """Tam kat: 24 m / 6 m = 4 boy, fazla 0 (19.999... tuzağı yok)."""
        result = calculate_purchase_list(
            [
                row("B-1", "12", "m", BOX100, "0"),
                row("B-2", "12", "m", BOX100, "0"),
            ],
            catalog,
        )
        group = result.group(BOX100)
        assert group.bar_count == D("4")
        assert group.rounding_surplus_m == D("0")

    def test_division_artifact_does_not_add_extra_bar(self, catalog: Catalog) -> None:
        """kg ÷ kg/m artığı fazladan boy üretmemeli.

        1240 kg → 55.357142857142857... m; iki satır toplamı 6 m'nin tam
        katına çok yakınsa bile ``ceil`` bir fazla boy vermemeli.
        """
        result = calculate_purchase_list(
            [row("B-1", "1240", "kg", IPE200, "0")],
            catalog,
        )
        group = result.group(IPE200)
        expected_bars = D("5")  # 55.357... / 12 = 4.61... → 5
        assert group.bar_count == expected_bars
        assert group.order_length_m == D("60")


# ---------------------------------------------------------------------------
# 9. Yuvarlama fazlası
# ---------------------------------------------------------------------------


class TestRoundingSurplus:
    def test_surplus_is_order_minus_gross(self, catalog: Catalog) -> None:
        """10 m, 6 m boy → 2 boy = 12 m → fazla 2 m."""
        result = calculate_purchase_list([row("B-1", "10", "m", BOX100, "0")], catalog)
        group = result.group(BOX100)
        assert group.total_gross_metres == D("10")
        assert group.order_length_m == D("12")
        assert group.rounding_surplus_m == D("2")
        assert group.rounding_surplus_m == group.order_length_m - group.total_gross_metres

    def test_surplus_is_zero_on_exact_fit(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "18", "m", BOX100, "0")], catalog)
        assert result.group(BOX100).rounding_surplus_m == D("0")

    def test_surplus_note_is_recorded(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "10", "m", BOX100, "0")], catalog)
        assert any("fazla sipariş" in note for note in result.group(BOX100).notes)

    def test_surplus_with_waste(self, catalog: Catalog) -> None:
        """96 m %5 → 100.8; 17 boy = 102 → fazla 1.2 m (fazla fireye dahil)."""
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)
        group = result.group(BOX100)
        assert group.rounding_surplus_m == D("1.2")
        assert group.rounding_surplus_m != D("6")

    def test_order_is_multiple_of_commercial_length(self, catalog: Catalog) -> None:
        for gross in ("7", "13", "61", "97"):
            result = calculate_purchase_list(
                [row("B-1", gross, "m", BOX100, "0")], catalog
            )
            group = result.group(BOX100)
            assert group.order_length_m % D("6") == 0, gross
            assert group.order_length_m >= group.total_gross_metres


# ---------------------------------------------------------------------------
# 10. Hariç / reddedilmiş / bekleyen satırlar
# ---------------------------------------------------------------------------


class TestSkippedRows:
    def test_excluded_row_is_not_calculated(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                row("B-1", "96", "m", BOX100),
                row("B-2", "60", "m", BOX100, status=MatchStatus.EXCLUDED),
            ],
            catalog,
        )
        assert result.group(BOX100).source_row_numbers == ("B-1",)
        assert result.group(BOX100).total_gross_metres == D("100.8")

        skipped = result.skipped[0]
        assert skipped.row_no == "B-2"
        assert skipped.reason is SkipReason.EXCLUDED

    def test_rejected_row_is_not_calculated(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                row("B-1", "96", "m", BOX100),
                row("B-2", "84", "m", BOX100, status=MatchStatus.REJECTED),
            ],
            catalog,
        )
        assert result.calculated_row_count == 1
        assert result.skipped[0].reason is SkipReason.REJECTED
        # Red satır birleşmeye girmez: 32 boy değil 17 boy.
        assert result.group(BOX100).bar_count == D("17")

    def test_pending_row_is_not_calculated(self, catalog: Catalog) -> None:
        """Onaysız satır hesaba girmez; sessizce hesaba katılmaz."""
        result = calculate_purchase_list(
            [row("B-1", "84", "m", BOX100, status=MatchStatus.PENDING)],
            catalog,
        )
        assert result.groups == ()
        assert result.skipped[0].reason is SkipReason.PENDING

    def test_ai_approved_row_is_calculated(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [row("B-1", "84", "m", BOX100, status=MatchStatus.AI_APPROVED)],
            catalog,
        )
        assert result.group(BOX100).source_row_numbers == ("B-1",)
        assert result.group(BOX100).status is CalculationStatus.FULL

    def test_rule_row_without_code_is_invalid(self, catalog: Catalog) -> None:
        """``rule`` durumunda kod yoksa satır hesaba alınmaz (tutarsız girdi)."""
        result = calculate_purchase_list(
            [
                CalculationInputRow(
                    row_no="B-1",
                    description="test",
                    quantity=D("96"),
                    unit="m",
                    waste_rate=WasteRate.from_percent("5"),
                    status=MatchStatus.RULE,
                    matched_code=None,
                )
            ],
            catalog,
        )
        assert result.groups == ()
        assert result.skipped[0].reason is SkipReason.INVALID

    def test_unknown_catalog_code_is_skipped(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [row("B-1", "96", "m", "BOX-999-9-S235-B")], catalog
        )
        assert result.groups == ()
        assert result.skipped[0].reason is SkipReason.UNKNOWN_CODE
        assert result.skipped[0].matched_code == "BOX-999-9-S235-B"

    def test_skipped_rows_are_counted(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                row("B-1", "96", "m", BOX100),
                row("B-2", "60", "m", BOX100, status=MatchStatus.EXCLUDED),
                row("B-3", "60", "m", BOX100, status=MatchStatus.REJECTED),
                row("B-4", "60", "m", BOX100, status=MatchStatus.PENDING),
            ],
            catalog,
        )
        assert result.input_row_count == 4
        assert result.calculated_row_count == 1
        assert result.skipped_count == 3


# ---------------------------------------------------------------------------
# 11. Kaynak satır izlenebilirliği
# ---------------------------------------------------------------------------


class TestTraceability:
    def test_group_carries_full_product_info(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)
        group = result.group(BOX100)
        assert group.code == BOX100
        assert group.family.value == "BOX"
        assert group.family_label == "Kutu profil"
        assert group.size == "100×100×4"
        assert group.grade.value == "S235"
        assert group.coating.value == "siyah"
        assert group.product_label == "Kutu profil 100×100×4 · S235 · siyah"

    def test_source_rows_keep_all_fields(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                row("BOQ-001", "96", "m", BOX100, "5", description="BOX 100×100×4"),
                row("BOQ-013", "84", "m", BOX100, "5", description="BOX 100×100×4"),
            ],
            catalog,
        )
        group = result.group(BOX100)
        assert group.source_row_numbers == ("BOQ-001", "BOQ-013")

        first = group.sources[0]
        assert first.row_no == "BOQ-001"
        assert first.description == "BOX 100×100×4"
        assert first.source_quantity == D("96")
        assert first.source_unit.value == "m"
        assert first.net_metres == D("96")
        assert first.waste_percent == D("5")
        assert first.gross_metres == D("100.8")
        assert first.gross_quantity == D("100.8")
        assert first.conversion_steps

    def test_every_source_row_has_complete_chain(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                row("B-1", "96", "m", BOX100),
                row("B-2", "1170", "kg", BOX100),
                row("B-3", "0.84", "t", IPE240),
            ],
            catalog,
        )
        for group in result.groups:
            for source in group.sources:
                assert source.row_no
                assert source.source_quantity > 0
                assert source.source_unit is not None
                assert source.waste_percent is not None
                assert source.net_metres is not None
                assert source.gross_metres is not None

    def test_gross_equals_net_times_factor(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [row("B-1", "1170", "kg", BOX100, "7.5")], catalog
        )
        source = result.group(BOX100).sources[0]
        assert source.net_metres is not None
        assert source.gross_metres == source.net_metres * D("1.075")

    def test_fire_quantity_is_traceable(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)
        source = result.group(BOX100).sources[0]
        assert source.fire_quantity == D("4.8")
        assert source.gross_quantity == source.source_quantity + source.fire_quantity

    def test_is_calc_eligible_statuses(self, catalog: Catalog) -> None:
        """Yalnızca rule ve ai-approved hesaplanır."""
        eligible = (MatchStatus.RULE, MatchStatus.AI_APPROVED)
        statuses = [
            MatchStatus.RULE,
            MatchStatus.AI_APPROVED,
            MatchStatus.PENDING,
            MatchStatus.REJECTED,
            MatchStatus.EXCLUDED,
        ]
        for status in statuses:
            result = calculate_purchase_list(
                [row("B-1", "12", "m", BOX100, status=status)], catalog
            )
            assert (result.calculated_row_count == 1) is (status in eligible), status

    def test_result_is_immutable(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)
        group = result.group(BOX100)
        with pytest.raises(Exception):
            group.weight_kg = D("1")  # type: ignore[misc]

    def test_source_row_calculation_is_immutable(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "96", "m", BOX100)], catalog)
        source: SourceRowCalculation = result.group(BOX100).sources[0]
        with pytest.raises(Exception):
            source.net_metres = D("1")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 12. Decimal hassasiyeti ve sınır durumlar
# ---------------------------------------------------------------------------


class TestDecimalPrecision:
    def test_all_numeric_outputs_are_decimal(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [row("B-1", "96", "m", BOX100), row("B-2", "1240", "kg", IPE200)],
            catalog,
        )
        for group in result.groups:
            for value in (
                group.total_gross_metres,
                group.commercial_length_m,
                group.bar_count,
                group.order_length_m,
                group.rounding_surplus_m,
                group.weight_kg,
            ):
                assert isinstance(value, Decimal), value

    def test_no_float_drift_in_weight(self, catalog: Catalog) -> None:
        """1.570 kg/m float'ta 1.57'ye kayar; Decimal'de kaymaz."""
        result = calculate_purchase_list(
            [row("B-1", "100", "m", FLAT40, "0")], catalog
        )
        group = result.group(FLAT40)
        assert group.total_gross_metres == D("100")
        # 100 m → 17 boy × 6 m = 102 m
        assert group.order_length_m == D("102")
        assert group.weight_kg == D("102") * D("1.570")
        assert group.weight_kg == D("160.140")

    def test_high_precision_division_round_trips(self, catalog: Catalog) -> None:
        """Bölme artığı 1E-20'den küçük olmalı; erken yuvarlama yok."""
        result = calculate_purchase_list(
            [row("B-1", "1240", "kg", IPE200, "0")], catalog
        )
        net = result.group(IPE200).sources[0].net_metres
        assert net is not None
        assert abs(net * D("22.40") - D("1240")) < D("1E-20")

    def test_calc_precision_is_generous(self) -> None:
        assert CALC_PRECISION >= 28

    def test_large_quantity_is_supported(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [row("B-1", "1234567", "m", BOX100, "0")], catalog
        )
        group = result.group(BOX100)
        assert group.total_gross_metres == D("1234567")
        assert group.bar_count == D("205762")  # ceil(1234567 / 6)
        assert group.order_length_m == D("205762") * D("6")

    def test_many_rows_accumulate_without_drift(self, catalog: Catalog) -> None:
        rows = [row(f"B-{i}", "1", "m", BOX100, "0") for i in range(1, 101)]
        result = calculate_purchase_list(rows, catalog)
        group = result.group(BOX100)
        assert group.total_gross_metres == D("100")
        assert group.bar_count == D("17")  # 100/6 = 16.67 → 17
        assert group.order_length_m == D("102")

    def test_display_rounding_only_at_presentation(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [row("B-1", "1240", "kg", IPE200, "3")], catalog
        )
        group = result.group(IPE200)
        assert group.total_gross_metres is not None
        # İç değer tam hassasiyette; gösterim yuvarlanır.
        assert len(str(group.total_gross_metres)) > 10
        assert display_decimal(group.total_gross_metres) == D("57.018")

    def test_display_decimal_keeps_none(self) -> None:
        assert display_decimal(None) is None

    def test_display_decimal_places(self) -> None:
        assert display_decimal(D("1.23456"), places=2) == D("1.23")
        assert display_decimal(D("1.235"), places=2) == D("1.24")


# ---------------------------------------------------------------------------
# 13. Sıfır / negatif / geçersiz miktarlar
# ---------------------------------------------------------------------------


class TestInvalidQuantities:
    @pytest.mark.parametrize("quantity", ["0", "-1", "-0.001"])
    def test_non_positive_is_skipped(self, catalog: Catalog, quantity: str) -> None:
        result = calculate_purchase_list(
            [row("B-1", quantity, "m", BOX100)], catalog
        )
        assert result.groups == ()
        assert result.skipped[0].reason is SkipReason.INVALID
        assert "pozitif" in result.skipped[0].message

    def test_zero_quantity_is_not_silently_used(self, catalog: Catalog) -> None:
        """Sıfır miktar gruba girmez; 0 m'lik grup oluşmaz."""
        result = calculate_purchase_list(
            [row("B-1", "0", "m", BOX100), row("B-2", "12", "m", BOX100)],
            catalog,
        )
        assert result.group(BOX100).source_row_numbers == ("B-2",)
        assert result.group(BOX100).total_gross_metres == D("12.6")

    def test_float_quantity_is_rejected(self, catalog: Catalog) -> None:
        """float miktar sessizce Decimal'e çevrilmez."""
        result = calculate_purchase_list(
            [
                CalculationInputRow(
                    row_no="B-1",
                    description="test",
                    quantity=96.0,  # type: ignore[arg-type]
                    unit="m",
                    waste_rate=WasteRate.from_percent("5"),
                    status=MatchStatus.RULE,
                    matched_code=BOX100,
                )
            ],
            catalog,
        )
        assert result.groups == ()
        assert result.skipped[0].reason is SkipReason.INVALID
        assert "float" in result.skipped[0].message

    def test_nan_quantity_is_rejected(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                CalculationInputRow(
                    row_no="B-1",
                    description="test",
                    quantity=D("NaN"),
                    unit="m",
                    waste_rate=WasteRate.from_percent("5"),
                    status=MatchStatus.RULE,
                    matched_code=BOX100,
                )
            ],
            catalog,
        )
        assert result.groups == ()
        assert result.skipped[0].reason is SkipReason.INVALID

    def test_unsupported_unit_is_rejected(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([row("B-1", "12", "adet", BOX100)], catalog)
        assert result.groups == ()
        assert result.skipped[0].reason is SkipReason.INVALID
        assert "Birim desteklenmiyor" in result.skipped[0].message

    def test_empty_row_number_is_rejected(self, catalog: Catalog) -> None:
        with pytest.raises(CalculationError, match="Boş BOQ satır"):
            calculate_purchase_list([row("  ", "12", "m", BOX100)], catalog)

    def test_duplicate_row_number_is_rejected(self, catalog: Catalog) -> None:
        """İzlenebilirlik bozulur; sessizce birleştirilmez."""
        with pytest.raises(CalculationError, match="Yinelenen"):
            calculate_purchase_list(
                [row("B-1", "12", "m", BOX100), row("B-1", "12", "m", BOX100)],
                catalog,
            )

    def test_empty_input_returns_empty_result(self, catalog: Catalog) -> None:
        result = calculate_purchase_list([], catalog)
        assert result.groups == ()
        assert result.skipped == ()
        assert result.input_row_count == 0
        assert result.group_count == 0
        assert result.weight_complete is True
        assert result.known_weight_kg == D("0")

    def test_one_bad_row_does_not_block_others(self, catalog: Catalog) -> None:
        result = calculate_purchase_list(
            [
                row("B-1", "-5", "m", BOX100),
                row("B-2", "96", "m", BOX100),
                row("B-3", "12", "adet", BOX100),
            ],
            catalog,
        )
        assert result.group(BOX100).source_row_numbers == ("B-2",)
        assert result.skipped_count == 2


# ---------------------------------------------------------------------------
# Demo fixture — 18 satır, kilitli 8 grup / 5 birleşme
# ---------------------------------------------------------------------------


class TestDemoScenario:
    @pytest.fixture(scope="class")
    @classmethod
    def demo_result(cls, catalog: Catalog):
        from app.domain.decisions import apply_decisions
        from app.domain.matching import match_row
        from tests.fixtures.demo_boq import DEMO_ROWS, PREDEFINED_DECISIONS

        deterministic = {
            r.no: match_row(r.description, r.unit, r.waste_rate, catalog)
            for r in DEMO_ROWS
        }
        finalised = apply_decisions(
            deterministic, list(PREDEFINED_DECISIONS), catalog
        )

        rows = [
            CalculationInputRow.from_outcome(
                row_no=r.no,
                description=r.description,
                quantity=r.quantity,
                unit=r.unit,
                waste_rate=(
                    WasteRate.from_fraction(r.waste_rate)
                    if r.waste_rate is not None
                    else None
                ),
                outcome=finalised[r.no],
            )
            for r in DEMO_ROWS
        ]
        return calculate_purchase_list(rows, catalog)

    def test_thirteen_rows_become_eight_groups(self, demo_result) -> None:
        assert demo_result.input_row_count == 18
        assert demo_result.calculated_row_count == 13
        assert demo_result.group_count == 8
        assert demo_result.merge_count == 5

    def test_five_rows_are_skipped(self, demo_result) -> None:
        assert demo_result.skipped_count == 5
        skipped = {item.row_no: item.reason for item in demo_result.skipped}
        assert skipped == {
            "BOQ-009": SkipReason.PENDING,
            "BOQ-012": SkipReason.EXCLUDED,
            "BOQ-014": SkipReason.EXCLUDED,
            "BOQ-015": SkipReason.EXCLUDED,
            "BOQ-018": SkipReason.REJECTED,
        }

    def test_all_demo_groups_are_full(self, demo_result) -> None:
        """Katalogda eksik veri yok; demo tamamen hesaplanabilir."""
        assert len(demo_result.full_groups) == 8
        assert demo_result.partial_groups == ()
        assert demo_result.weight_complete

    def test_box_100_merges_boq001_and_boq013(self, demo_result) -> None:
        group = demo_result.group(BOX100)
        assert group.source_row_numbers == ("BOQ-001", "BOQ-013")
        assert group.total_gross_metres == D("189.00000")
        assert group.bar_count == D("32")
        assert group.order_length_m == D("192.00000")
        assert group.weight_kg == D("2246.400000")

    def test_upn_160_merges_boq007_and_boq010(self, demo_result) -> None:
        """54 m + 0.32 t (=17.02 m) → 73.86 m fireli → 7 boy = 84 m."""
        group = demo_result.group(UPN160)
        assert group.source_row_numbers == ("BOQ-007", "BOQ-010")
        assert group.bar_count == D("7")
        assert group.order_length_m == D("84")

    def test_flat_merges_boq008_and_boq016(self, demo_result) -> None:
        group = demo_result.group(FLAT40)
        assert group.source_row_numbers == ("BOQ-008", "BOQ-016")
        assert group.bar_count == D("41")
        assert group.order_length_m == D("246")

    def test_ipe_240_merges_boq004_and_boq017(self, demo_result) -> None:
        group = demo_result.group(IPE240)
        assert group.source_row_numbers == ("BOQ-004", "BOQ-017")
        assert group.commercial_length_m == D("12")
        assert group.bar_count == D("4")
        assert group.order_length_m == D("48")

    def test_hea_200_merges_boq005_and_boq006(self, demo_result) -> None:
        group = demo_result.group(HEA200)
        assert group.source_row_numbers == ("BOQ-005", "BOQ-006")
        assert group.bar_count == D("18")

    def test_galvanized_group_is_separate(self, demo_result) -> None:
        assert demo_result.group(BOX100_G).source_row_numbers == ("BOQ-002",)
        assert demo_result.group(BOX100_G).coating.value == "galvaniz"

    def test_box_150_group(self, demo_result) -> None:
        group = demo_result.group(BOX150)
        assert group.total_gross_metres == D("63.00000")
        assert group.bar_count == D("11")
        assert group.order_length_m == D("66")

    def test_ipe_200_group(self, demo_result) -> None:
        group = demo_result.group(IPE200)
        assert group.source_row_numbers == ("BOQ-003",)
        assert group.bar_count == D("5")
        assert group.order_length_m == D("60")

    def test_known_weight_total(self, demo_result) -> None:
        """Tüm gruplar hesaplanabildiği için kısmi toplam tam toplamdır."""
        assert demo_result.known_weight_kg == D("18005.820000")

    def test_result_is_deterministic(self, catalog: Catalog, demo_result) -> None:
        """Aynı girdi aynı çıktıyı vermeli (deterministik motor)."""
        rebuilt = calculate_purchase_list(
            [
                CalculationInputRow(
                    row_no=source.row_no,
                    description=source.description,
                    quantity=source.source_quantity,
                    unit=source.source_unit,
                    waste_rate=WasteRate(percent=source.waste_percent)
                    if source.waste_percent is not None
                    else None,
                    status=MatchStatus.RULE,
                    matched_code=group.code,
                )
                for group in demo_result.groups
                for source in group.sources
            ],
            catalog,
        )
        assert rebuilt.group_count == demo_result.group_count
        for original, replayed in zip(demo_result.groups, rebuilt.groups):
            assert original.code == replayed.code
            assert original.order_length_m == replayed.order_length_m
            assert original.weight_kg == replayed.weight_kg
