"""18 satırlık demo fixture'ın birebir doğrulaması.

Bu test dosyası, kilitli demo veri kümesinin (``tests/fixtures/demo_boq.py``)
deterministik eşleştirme ve önceden tanımlı kararlarla ürettiği sonucu
kilitler. Dağılım:

18 = 10 rule + 3 ai-approved + 1 pending + 1 rejected + 3 excluded
"""

from __future__ import annotations

import pytest

from app.domain.catalog import load_catalog
from app.domain.decisions import (
    Decision,
    DecisionAction,
    DecisionError,
    DecisionSource,
    apply_decisions,
    conflicting_features,
)
from app.domain.matching import match_row
from app.domain.models import ExclusionReason, MatchStatus
from tests.fixtures.demo_boq import (
    DEMO_ROWS,
    EXPECTED_COUNTS,
    EXPECTED_DETERMINISTIC,
    PREDEFINED_DECISIONS,
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def deterministic(catalog):
    """Kararlar uygulanmadan önceki deterministik sonuçlar."""
    return {
        row.no: match_row(row.description, row.unit, row.waste_rate, catalog)
        for row in DEMO_ROWS
    }


@pytest.fixture(scope="module")
def finalised(deterministic, catalog):
    """Önceden tanımlı demo kararları uygulanmış sonuçlar."""
    return apply_decisions(deterministic, list(PREDEFINED_DECISIONS), catalog)


def test_fixture_has_18_rows() -> None:
    assert len(DEMO_ROWS) == 18


def test_row_numbers_are_unique() -> None:
    numbers = [row.no for row in DEMO_ROWS]
    assert len(numbers) == len(set(numbers))


def test_deterministic_status_matches_expected(deterministic) -> None:
    assert set(deterministic) == set(EXPECTED_DETERMINISTIC)
    for row_no, (expected_status, expected_code) in EXPECTED_DETERMINISTIC.items():
        outcome = deterministic[row_no]
        assert outcome.status.value == expected_status, row_no
        assert outcome.matched_code == expected_code, row_no


def test_deterministic_counts(deterministic) -> None:
    """Kararlar öncesi: 10 rule + 4 pending + 4 excluded = 18.

    BOQ-003/004/006 henüz onaylanmadığı için pending; BOQ-018 ise kalite
    çelişkisi nedeniyle deterministik olarak katalog dışı.
    """
    counts: dict[str, int] = {}
    for outcome in deterministic.values():
        counts[outcome.status.value] = counts.get(outcome.status.value, 0) + 1

    assert counts.get("rule") == 10
    assert counts.get("pending") == 4
    assert counts.get("excluded") == 4
    assert "ai-approved" not in counts
    assert "rejected" not in counts


def test_final_statuses_match_locked_distribution(finalised) -> None:
    counts = {
        "rule": 0,
        "ai-approved": 0,
        "pending": 0,
        "rejected": 0,
        "excluded": 0,
        "invalid": 0,
    }
    for outcome in finalised.values():
        counts[outcome.status.value] += 1

    assert counts == EXPECTED_COUNTS


def test_final_rule_rows_are_ten(finalised) -> None:
    rules = [row_no for row_no, out in finalised.items() if out.status is MatchStatus.RULE]
    assert len(rules) == 10
    assert sorted(rules) == [
        "BOQ-001",
        "BOQ-002",
        "BOQ-005",
        "BOQ-007",
        "BOQ-008",
        "BOQ-010",
        "BOQ-011",
        "BOQ-013",
        "BOQ-016",
        "BOQ-017",
    ]


def test_ai_approved_rows_are_the_predefined_three(finalised) -> None:
    approved = [
        row_no
        for row_no, out in finalised.items()
        if out.status is MatchStatus.AI_APPROVED
    ]
    assert sorted(approved) == ["BOQ-003", "BOQ-004", "BOQ-006"]


def test_predefined_decisions_are_not_marked_as_user(finalised) -> None:
    """Demo onayları gerçek AI/kullanıcı kararı gibi sunulmamalı."""
    for decision in PREDEFINED_DECISIONS:
        assert decision.source is DecisionSource.DEMO_PREDEFINED


def test_pending_row_is_boq009(finalised) -> None:
    pending = [no for no, out in finalised.items() if out.status is MatchStatus.PENDING]
    assert pending == ["BOQ-009"]


def test_rejected_row_is_boq018(finalised) -> None:
    rejected = [no for no, out in finalised.items() if out.status is MatchStatus.REJECTED]
    assert rejected == ["BOQ-018"]


def test_excluded_rows_have_reasons(finalised) -> None:
    excluded = {no: out for no, out in finalised.items() if out.status is MatchStatus.EXCLUDED}
    assert set(excluded) == {"BOQ-012", "BOQ-014", "BOQ-015"}

    assert excluded["BOQ-012"].exclusion_reason is ExclusionReason.WASTE
    assert excluded["BOQ-014"].exclusion_reason is ExclusionReason.UNIT
    assert excluded["BOQ-015"].exclusion_reason is ExclusionReason.CATALOG


def test_calculable_rows_are_thirteen(finalised) -> None:
    calculable = [
        no
        for no, out in finalised.items()
        if out.status in (MatchStatus.RULE, MatchStatus.AI_APPROVED) and out.matched_code
    ]
    assert len(calculable) == 13


def test_thirteen_calculable_rows_map_to_eight_codes(finalised) -> None:
    codes = {
        out.matched_code
        for out in finalised.values()
        if out.status in (MatchStatus.RULE, MatchStatus.AI_APPROVED) and out.matched_code
    }
    assert len(codes) == 8
    assert codes == {
        "BOX-100-4-S235-B",
        "BOX-100-4-S235-G",
        "BOX-150-100-5-S235-B",
        "IPE-200-S235",
        "IPE-240-S355",
        "HEA-200-S235",
        "UPN-160-S235",
        "FLAT-40x5-S235-B",
    }


def test_merges_are_five(finalised) -> None:
    """8 grup, 13 kaynak satır → 5 birleşme."""
    from collections import Counter

    codes = Counter(
        out.matched_code
        for out in finalised.values()
        if out.status in (MatchStatus.RULE, MatchStatus.AI_APPROVED) and out.matched_code
    )
    merged = sum(1 for count in codes.values() if count > 1)
    assert merged == 5


def test_boq001_and_boq013_share_group(finalised) -> None:
    assert finalised["BOQ-001"].matched_code == finalised["BOQ-013"].matched_code


def test_pending_row_is_not_auto_approved(finalised) -> None:
    """Karar verilmemiş pending satır pending kalır."""
    assert finalised["BOQ-009"].status is MatchStatus.PENDING
    assert finalised["BOQ-009"].matched_code is None


class TestDecisionValidation:
    def test_approving_unknown_code_fails(self, deterministic, catalog) -> None:
        bad = Decision(
            row_no="BOQ-009",
            action=DecisionAction.APPROVE,
            code="FLAT-40x5-S999-B",
        )
        with pytest.raises(DecisionError, match="katalogda bulunmuyor"):
            apply_decisions(deterministic, [bad], catalog)

    def test_approving_conflicting_quality_fails(self, deterministic, catalog) -> None:
        """BOQ-018'de S355 yazıyor; S235 onaylanamaz."""
        bad = Decision(
            row_no="BOQ-018",
            action=DecisionAction.APPROVE,
            code="IPE-200-S235",
        )
        with pytest.raises(DecisionError, match="çelişiyor"):
            apply_decisions(deterministic, [bad], catalog)

    def test_conflict_details_name_the_feature(self, deterministic, catalog) -> None:
        conflicts = conflicting_features(
            deterministic["BOQ-018"].attributes, "IPE-200-S235", catalog
        )
        assert any("kalite" in conflict for conflict in conflicts)

    def test_approving_valid_candidate_works(self, deterministic, catalog) -> None:
        good = Decision(
            row_no="BOQ-009",
            action=DecisionAction.APPROVE,
            code="FLAT-40x5-S235-G",
        )
        result = apply_decisions(deterministic, [good], catalog)
        assert result["BOQ-009"].status is MatchStatus.AI_APPROVED
        assert result["BOQ-009"].matched_code == "FLAT-40x5-S235-G"

    def test_decisions_are_idempotent(self, deterministic, catalog) -> None:
        first = apply_decisions(deterministic, list(PREDEFINED_DECISIONS), catalog)
        second = apply_decisions(deterministic, list(PREDEFINED_DECISIONS), catalog)
        assert {k: v.status for k, v in first.items()} == {
            k: v.status for k, v in second.items()
        }

    def test_unknown_row_number_fails(self, deterministic, catalog) -> None:
        bad = Decision(row_no="BOQ-999", action=DecisionAction.REJECT)
        with pytest.raises(DecisionError, match="bilinmeyen"):
            apply_decisions(deterministic, [bad], catalog)

    def test_duplicate_decision_fails(self, deterministic, catalog) -> None:
        decisions = [
            Decision(row_no="BOQ-009", action=DecisionAction.REJECT),
            Decision(row_no="BOQ-009", action=DecisionAction.REJECT),
        ]
        with pytest.raises(DecisionError, match="iki karar"):
            apply_decisions(deterministic, decisions, catalog)

    def test_rejecting_a_rule_row_is_allowed(self, deterministic, catalog) -> None:
        reject = Decision(row_no="BOQ-001", action=DecisionAction.REJECT)
        result = apply_decisions(deterministic, [reject], catalog)
        assert result["BOQ-001"].status is MatchStatus.REJECTED

    def test_approve_without_code_fails(self, deterministic, catalog) -> None:
        bad = Decision(row_no="BOQ-009", action=DecisionAction.APPROVE)
        with pytest.raises(DecisionError, match="katalog kodu"):
            apply_decisions(deterministic, [bad], catalog)
