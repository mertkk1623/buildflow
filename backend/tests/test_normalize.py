"""Türkçe açıklama normalizasyonu testleri."""

from __future__ import annotations

import pytest

from app.domain.models import Coating, Grade, MaterialFamily
from app.domain.normalize import normalize_description, tr_lower


class TestTurkishLower:
    def test_dotted_capital_i(self) -> None:
        assert tr_lower("İPE") == "ipe"

    def test_dotless_capital_i(self) -> None:
        assert tr_lower("SIYAH") == "siyah"

    def test_lowercase_dotless_i_is_preserved(self) -> None:
        assert tr_lower("ıpe") == "ıpe"

    def test_all_turkish_specials(self) -> None:
        assert tr_lower("ÇĞİÖŞÜ") == "çğiöşü"

    def test_ascii_uppercase(self) -> None:
        assert tr_lower("GALVANIZ") == "galvaniz"


class TestFamilyDetection:
    def test_box_from_alias(self) -> None:
        result = normalize_description("kutu profil 100×100×4 S235 siyah")
        assert result.attributes.family is MaterialFamily.BOX

    def test_box_from_box_token(self) -> None:
        result = normalize_description("BOX 100×100×4 S235 siyah")
        assert result.attributes.family is MaterialFamily.BOX

    def test_ipe(self) -> None:
        assert normalize_description("IPE 200").attributes.family is MaterialFamily.IPE

    def test_ipe_turkish_small(self) -> None:
        assert normalize_description("ıpe 240").attributes.family is MaterialFamily.IPE

    def test_hea(self) -> None:
        assert normalize_description("hea 200").attributes.family is MaterialFamily.HEA

    def test_upn(self) -> None:
        assert normalize_description("UPN 160").attributes.family is MaterialFamily.UPN

    def test_flat_lama(self) -> None:
        assert normalize_description("lama 40×5").attributes.family is MaterialFamily.FLAT

    def test_generic_profil_does_not_decide_family(self) -> None:
        """``profil`` tek başına aile belirlemez (BOQ-014 senaryosu)."""
        result = normalize_description("profil 100×100")
        assert result.attributes.family is None
        assert any("family" not in w for w in result.warnings)

    def test_unknown_material_has_no_family(self) -> None:
        result = normalize_description("muhtelif bağlantı elemanı")
        assert result.attributes.family is None


class TestSizeParsing:
    def test_box_three_components(self) -> None:
        result = normalize_description("BOX 100×100×4 S235 siyah")
        assert result.attributes.size == "100×100×4"

    def test_box_slash_separators(self) -> None:
        result = normalize_description("kutu profil 100/100/4 S235 galvaniz")
        assert result.attributes.size == "100×100×4"

    def test_box_x_separators(self) -> None:
        result = normalize_description("kutu profil 100x100x4 S235 siyah")
        assert result.attributes.size == "100×100×4"

    def test_box_edges_are_order_independent(self) -> None:
        """100×150×5 ve 150×100×5 aynı fiziksel kesittir."""
        a = normalize_description("kutu profil 150×100×5 S235 siyah")
        b = normalize_description("kutu profil 100×150×5 S235 siyah")
        assert a.attributes.size == b.attributes.size == "150×100×5"

    def test_numeric_normalization_4_equals_4_0(self) -> None:
        a = normalize_description("BOX 100×100×4 S235 siyah")
        b = normalize_description("BOX 100x100x4.0 S235 siyah")
        assert a.attributes.size == b.attributes.size

    def test_thickness_is_never_fuzzy(self) -> None:
        """100×100×4 ile 100×100×5 ASLA yakın kabul edilmez."""
        a = normalize_description("BOX 100×100×4 S235 siyah")
        b = normalize_description("BOX 100×100×5 S235 siyah")
        assert a.attributes.size == "100×100×4"
        assert b.attributes.size == "100×100×5"
        assert a.attributes.size != b.attributes.size

    def test_flat_keeps_order(self) -> None:
        """Lama 40×5 (genişlik × kalınlık) sırası korunur."""
        result = normalize_description("lama 40×5 S235 siyah")
        assert result.attributes.size == "40×5"

    def test_flat_order_is_significant(self) -> None:
        a = normalize_description("lama 40×5")
        b = normalize_description("lama 5×40")
        assert a.attributes.size == "40×5"
        assert b.attributes.size == "5×40"

    def test_profile_height(self) -> None:
        result = normalize_description("IPE 240 S355 siyah")
        assert result.attributes.size == "240"

    def test_ipe_glued_number(self) -> None:
        result = normalize_description("ipe240 s355")
        assert result.attributes.family is MaterialFamily.IPE
        assert result.attributes.size == "240"

    def test_two_component_without_family_is_ambiguous(self) -> None:
        """``100×100`` BOX mı lama mı belli değil → ölçü kullanılmaz."""
        result = normalize_description("profil 100×100")
        assert result.attributes.size is None
        assert any("belirsiz" in w.lower() for w in result.warnings)

    def test_single_number_without_family_is_ambiguous(self) -> None:
        result = normalize_description("200 S235")
        assert result.attributes.size is None
        assert any("aile" in w.lower() for w in result.warnings)


class TestGradeParsing:
    def test_s235(self) -> None:
        assert normalize_description("BOX 100×100×4 S235 siyah").attributes.grade is Grade.S235

    def test_s355(self) -> None:
        assert normalize_description("IPE 240 S355 siyah").attributes.grade is Grade.S355

    def test_grade_with_space(self) -> None:
        assert normalize_description("IPE 200 s 235").attributes.grade is Grade.S235

    @pytest.mark.parametrize("token", ["ST37", "st37", "St37", "ST-37"])
    def test_st37_is_not_mapped(self, token: str) -> None:
        """ST37 tanınır ama eşlenmez — uydurma yapılmaz."""
        result = normalize_description(f"lama 40×5 {token}")
        assert result.attributes.grade is None
        assert any("eşlenmedi" in w for w in result.warnings)

    @pytest.mark.parametrize("token", ["S235JR", "S355J2", "S275"])
    def test_other_quality_designations_are_not_mapped(self, token: str) -> None:
        result = normalize_description(f"IPE 200 {token}")
        assert result.attributes.grade is None
        assert any("eşlenmedi" in w for w in result.warnings)

    def test_s355_with_suffix_is_not_confused_with_s235(self) -> None:
        result = normalize_description("IPE 200 S355JR")
        assert result.attributes.grade is None


class TestCoatingParsing:
    def test_black(self) -> None:
        assert normalize_description("BOX 100×100×4 siyah").attributes.coating is Coating.BLACK

    def test_galvanized(self) -> None:
        assert (
            normalize_description("kutu profil 100×100×4 galvaniz").attributes.coating
            is Coating.GALVANIZED
        )

    def test_galvanized_suffix(self) -> None:
        assert (
            normalize_description("kutu profil 100×100×4 galvanizli").attributes.coating
            is Coating.GALVANIZED
        )

    def test_hot_dip_galvanized(self) -> None:
        assert (
            normalize_description("kutu profil 100×100×4 sıcak daldırma").attributes.coating
            is Coating.GALVANIZED
        )

    def test_hdg(self) -> None:
        assert normalize_description("BOX 100×100×4 HDG").attributes.coating is Coating.GALVANIZED

    def test_painted_is_black(self) -> None:
        assert normalize_description("BOX 100×100×4 boyasız").attributes.coating is Coating.BLACK

    def test_absent_coating_is_none(self) -> None:
        assert normalize_description("IPE 200").attributes.coating is None

    def test_conflicting_coatings_are_ambiguous(self) -> None:
        result = normalize_description("BOX 100×100×4 siyah galvaniz")
        assert result.attributes.coating is None
        assert any("kaplama" in w.lower() for w in result.warnings)


class TestCompleteness:
    def test_full_description_is_complete(self) -> None:
        result = normalize_description("BOX 100×100×4 S235 siyah")
        assert result.is_complete
        assert result.attributes.missing_features == ()

    def test_missing_quality_and_coating_is_incomplete(self) -> None:
        result = normalize_description("IPE 200")
        assert not result.is_complete
        assert set(result.attributes.missing_features) == {"grade", "coating"}

    def test_missing_coating_only(self) -> None:
        result = normalize_description("IPE 240 S355")
        assert result.attributes.missing_features == ("coating",)

    def test_unknown_material_is_incomplete(self) -> None:
        result = normalize_description("muhtelif bağlantı elemanı")
        assert not result.is_complete
        assert len(result.attributes.missing_features) == 4


class TestDemoDescriptions:
    """Demo fixture'daki gerçek açıklamalar normalize edilebilmeli."""

    def test_boq001(self) -> None:
        a = normalize_description("BOX 100×100×4 S235 siyah").attributes
        assert (a.family, a.size, a.grade, a.coating) == (
            MaterialFamily.BOX,
            "100×100×4",
            Grade.S235,
            Coating.BLACK,
        )

    def test_boq002(self) -> None:
        a = normalize_description("kutu profil 100/100/4 S235 galvaniz").attributes
        assert (a.family, a.size, a.grade, a.coating) == (
            MaterialFamily.BOX,
            "100×100×4",
            Grade.S235,
            Coating.GALVANIZED,
        )

    def test_boq003_is_incomplete(self) -> None:
        a = normalize_description("IPE 200").attributes
        assert a.family is MaterialFamily.IPE
        assert a.size == "200"
        assert a.grade is None
        assert a.coating is None

    def test_boq004(self) -> None:
        a = normalize_description("ipe240 s355").attributes
        assert (a.family, a.size, a.grade) == (MaterialFamily.IPE, "240", Grade.S355)
        assert a.coating is None

    def test_boq011(self) -> None:
        a = normalize_description("kutu profil 150×100×5 S235 siyah").attributes
        assert (a.family, a.size, a.grade, a.coating) == (
            MaterialFamily.BOX,
            "150×100×5",
            Grade.S235,
            Coating.BLACK,
        )

    def test_boq018_quality_is_s355(self) -> None:
        """BOQ-018: IPE 200 S355 — kalite S355 okunmalı, S235'e düşürülmemeli."""
        a = normalize_description("IPE 200 S355").attributes
        assert a.grade is Grade.S355
        assert a.size == "200"
