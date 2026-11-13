"""Deterministik eşleştirme testleri."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.catalog import load_catalog
from app.domain.matching import match_description, match_row, parse_unit
from app.domain.models import ExclusionReason, MatchStatus, Unit


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


class TestParseUnit:
    @pytest.mark.parametrize(
        "raw,expected",
        [("m", Unit.M), ("M", Unit.M), ("kg", Unit.KG), ("KG", Unit.KG), ("t", Unit.T), (" t ", Unit.T)],
    )
    def test_supported(self, raw: str, expected: Unit) -> None:
        assert parse_unit(raw) is expected

    @pytest.mark.parametrize("raw", ["adet", "Adet", "m2", "", "metre"])
    def test_unsupported_returns_none(self, raw: str) -> None:
        assert parse_unit(raw) is None


class TestRuleStatus:
    def test_complete_description_gives_rule(self, catalog) -> None:
        outcome = match_description("BOX 100×100×4 S235 siyah", catalog)
        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "BOX-100-4-S235-B"

    def test_galvanized_variant(self, catalog) -> None:
        outcome = match_description("kutu profil 100/100/4 S235 galvaniz", catalog)
        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "BOX-100-4-S235-G"

    def test_hea(self, catalog) -> None:
        outcome = match_description("HEA 200 S235 siyah", catalog)
        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "HEA-200-S235"

    def test_upn(self, catalog) -> None:
        outcome = match_description("UPN 160 S235 siyah", catalog)
        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "UPN-160-S235"

    def test_flat(self, catalog) -> None:
        outcome = match_description("lama 40×5 S235 siyah", catalog)
        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "FLAT-40x5-S235-B"

    def test_ipe_240_s355(self, catalog) -> None:
        outcome = match_description("IPE 240 S355 siyah", catalog)
        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "IPE-240-S355"


class TestNoFuzzyMatching:
    def test_thickness_5_does_not_match_4(self, catalog) -> None:
        """100×100×5 katalogda yok; 100×100×4'e düşürülmez."""
        outcome = match_description("BOX 100×100×5 S235 siyah", catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.CATALOG
        assert outcome.matched_code is None

    def test_wrong_size_is_not_downgraded(self, catalog) -> None:
        outcome = match_description("IPE 300 S235 siyah", catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.matched_code is None

    def test_quality_is_not_downgraded(self, catalog) -> None:
        """IPE 200 S355 katalogda yok; S235'e düşürülmez (BOQ-018)."""
        outcome = match_description("IPE 200 S355", catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.CATALOG
        assert outcome.matched_code is None

    def test_flat_order_matters_in_matching(self, catalog) -> None:
        outcome = match_description("lama 5×40 S235 siyah", catalog)
        assert outcome.status is MatchStatus.EXCLUDED


class TestPendingStatus:
    def test_missing_quality_and_coating_pends(self, catalog) -> None:
        outcome = match_description("IPE 200", catalog)
        assert outcome.status is MatchStatus.PENDING
        assert outcome.matched_code is None
        assert "IPE-200-S235" in outcome.candidate_codes

    def test_lama_40x5_has_two_candidates(self, catalog) -> None:
        """BOQ-009: kaplama eksik, iki varyant da geçerli."""
        outcome = match_description("lama 40×5", catalog)
        assert outcome.status is MatchStatus.PENDING
        assert set(outcome.candidate_codes) == {
            "FLAT-40x5-S235-B",
            "FLAT-40x5-S235-G",
        }
        assert len(outcome.candidate_codes) == 2

    def test_single_candidate_still_pends(self, catalog) -> None:
        """Tek aday bile olsa onay gerekir."""
        outcome = match_description("IPE 240 S355", catalog)
        assert outcome.status is MatchStatus.PENDING
        assert outcome.candidate_codes == ("IPE-240-S355",)

    def test_missing_grade_only_pends(self, catalog) -> None:
        outcome = match_description("HEA 160 siyah", catalog)
        assert outcome.status is MatchStatus.PENDING

    def test_pending_message_names_missing_features(self, catalog) -> None:
        outcome = match_description("lama 40×5", catalog)
        assert "kalite" in outcome.message
        assert "kaplama" in outcome.message


class TestExcludedStatus:
    def test_unknown_material(self, catalog) -> None:
        outcome = match_description("muhtelif bağlantı elemanı", catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.CATALOG

    def test_ambiguous_family_is_catalog_exclusion(self, catalog) -> None:
        """BOQ-014: ``profil 100×100`` — aile belirsiz, katalog dışı."""
        outcome = match_description("profil 100×100", catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.CATALOG

    def test_unsupported_unit_excludes(self, catalog) -> None:
        outcome = match_row("profil 100×100", "adet", Decimal("0.05"), catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.UNIT

    def test_missing_waste_excludes(self, catalog) -> None:
        """Fire yok + katalogda varsayılan yok → hesap dışı (sıfır değil)."""
        outcome = match_row("BOX 100×100×4 S235 siyah", "m", None, catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.WASTE


class TestMatchRowPriority:
    """Belgelenmiş öncelik sırası testleri."""

    def test_unit_check_runs_first(self, catalog) -> None:
        """Birim desteklenmiyorsa açıklama hiç değerlendirilmez."""
        outcome = match_row("muhtelif bağlantı elemanı", "adet", None, catalog)
        assert outcome.exclusion_reason is ExclusionReason.UNIT

    def test_catalog_check_runs_before_waste(self, catalog) -> None:
        outcome = match_row("muhtelif bağlantı elemanı", "kg", None, catalog)
        assert outcome.exclusion_reason is ExclusionReason.CATALOG

    def test_waste_applies_to_matched_row(self, catalog) -> None:
        outcome = match_row("BOX 100×100×4 S235 siyah", "m", Decimal("0.05"), catalog)
        assert outcome.status is MatchStatus.RULE
        assert outcome.matched_code == "BOX-100-4-S235-B"

    def test_waste_applies_to_pending_row(self, catalog) -> None:
        outcome = match_row("lama 40×5", "kg", Decimal("0.05"), catalog)
        assert outcome.status is MatchStatus.PENDING
        assert len(outcome.candidate_codes) == 2

    def test_pending_without_waste_is_waste_exclusion(self, catalog) -> None:
        outcome = match_row("lama 40×5", "kg", None, catalog)
        assert outcome.status is MatchStatus.EXCLUDED
        assert outcome.exclusion_reason is ExclusionReason.WASTE


class TestTraceability:
    def test_rule_outcome_records_attributes(self, catalog) -> None:
        outcome = match_description("BOX 100×100×4 S235 siyah", catalog)
        assert outcome.attributes.family is not None
        assert outcome.attributes.size == "100×100×4"
        assert outcome.attributes.is_complete

    def test_outcome_is_immutable(self, catalog) -> None:
        outcome = match_description("IPE 200", catalog)
        with pytest.raises(Exception):
            outcome.status = MatchStatus.RULE  # type: ignore[misc]

    def test_description_only_never_returns_ai_status(self, catalog) -> None:
        """Aşama 4.1'de AI yok: hiçbir açıklama ai-approved dönmemeli."""
        descriptions = [
            "BOX 100×100×4 S235 siyah",
            "IPE 200",
            "lama 40×5",
            "muhtelif bağlantı elemanı",
            "IPE 200 S355",
            "hea 200",
        ]
        for description in descriptions:
            assert match_description(description, catalog).status is not MatchStatus.AI_APPROVED
