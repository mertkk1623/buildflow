"""AI eşleştirme motoru testleri.

Kapsanan senaryolar (istenen listeden):

1.  Deterministik eşleşmede AI **çağrılmaz**
2.  Pending satır AI'ya gönderilir
3.  Katalog dışı kod reddedilir
4.  Bozuk JSON yanıtı reddedilir
5.  Timeout ve API hatası güvenli ele alınır
6.  Birden fazla aday ``ambiguous`` döner
7.  Güvenilir eşleşme yoksa ``no_match``
8.  AI önerisi otomatik onaylanmaz
9.  Kullanıcı reddi korunur
10. AI kapalıyken sistem çalışır
11. AI yanıtı miktar/birim/hesabı değiştiremez
12. AI'ya hassas alanlar gönderilmez
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ai.engine import MAX_ROWS_PER_REQUEST, build_request, evaluate_rows
from app.ai.models import AiErrorKind, AiRunResult, AiStatus
from app.ai.providers import AiProviderError, NoneProvider
from app.ai.validate import AiValidationError, parse_suggestion
from app.domain.catalog import get_catalog
from app.domain.decisions import Decision, DecisionAction, apply_decisions
from app.domain.matching import match_row
from app.domain.models import MatchStatus
from app.ai.models import AiSuggestion
from tests.fixtures.ai import (
    AMBIGUOUS,
    NO_MATCH,
    PENDING_ROWS,
    ScriptedProvider,
    suggestion,
)

CATALOG = get_catalog()


@pytest.fixture(scope="module")
def pending_rows():
    """Demo'daki gerçek ``pending`` satırlar (deterministik motordan)."""
    specs = [
        ("BOQ-003", "IPE 200", "kg", Decimal("3")),
        ("BOQ-004", "ipe 240", "t", Decimal("3")),
        ("BOQ-009", "lama 40x5", "m", Decimal("5")),
    ]
    rows = []
    for boq_no, description, unit, waste in specs:
        outcome = match_row(description, unit, waste / Decimal("100"), CATALOG)
        assert outcome.status is MatchStatus.PENDING
        rows.append((boq_no, description, outcome))
    return rows


@pytest.fixture()
def rule_rows():
    """Deterministik eşleşen satırlar — AI'ya **gitmemeli**."""
    specs = [
        ("BOQ-001", "BOX 100×100×4 S235 siyah", "m"),
        ("BOQ-005", "HEA 200 S235 siyah", "m"),
    ]
    rows = []
    for boq_no, description, unit in specs:
        outcome = match_row(description, unit, Decimal("0.05"), CATALOG)
        assert outcome.status is MatchStatus.RULE
        rows.append((boq_no, description, outcome))
    return rows


# ---------------------------------------------------------------------------
# 1–2. Hangi satırlar AI'ya gider?
# ---------------------------------------------------------------------------


class TestRowSelection:
    def test_rule_rows_are_not_sent_to_ai(self, rule_rows) -> None:
        provider = ScriptedProvider([suggestion("BOX-100-4-S235-B")])

        result = evaluate_rows(rule_rows, CATALOG, provider)

        assert provider.call_count == 0
        assert result.evaluated_rows == 0
        # AI yapılandırılmış (enabled) ama çağrılacak satır yok.
        assert result.enabled is True

    def test_rule_only_file_reports_ai_enabled_but_unused(self) -> None:
        """AI açık + pending yok → enabled true, sıfır çağrı."""
        outcome = match_row(
            "BOX 100×100×4 S235 siyah", "m", Decimal("0.05"), CATALOG
        )
        provider = ScriptedProvider([NO_MATCH])

        result = evaluate_rows([("BOQ-001", "BOX 100×100×4 S235 siyah", outcome)], CATALOG, provider)

        assert result.enabled is True
        assert provider.call_count == 0
        assert result.evaluated_rows == 0

    def test_pending_rows_are_sent_to_ai(self, pending_rows) -> None:
        provider = ScriptedProvider(
            [
                suggestion("IPE-200-S235"),
                suggestion("IPE-240-S355"),
                NO_MATCH,
            ]
        )

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert provider.call_count == len(pending_rows)
        assert result.evaluated_rows == len(pending_rows)
        assert set(result.evaluations) == {row[0] for row in pending_rows}

    def test_mixed_rows_only_send_pending(self, rule_rows, pending_rows) -> None:
        provider = ScriptedProvider(
            [suggestion("IPE-200-S235"), suggestion("IPE-240-S355"), NO_MATCH]
        )

        result = evaluate_rows(rule_rows + pending_rows, CATALOG, provider)

        assert provider.call_count == len(pending_rows)
        assert "BOQ-001" not in result.evaluations
        assert "BOQ-005" not in result.evaluations

    def test_excluded_rows_are_not_sent(self) -> None:
        outcome = match_row(
            "profil 100×100", "adet", Decimal("0.05"), CATALOG
        )
        assert outcome.status is MatchStatus.EXCLUDED
        provider = ScriptedProvider([NO_MATCH])

        result = evaluate_rows([("BOQ-100", "profil 100×100", outcome)], CATALOG, provider)

        assert provider.call_count == 0
        assert result.evaluations == {}

    def test_invalid_rows_are_not_sent(self) -> None:
        from app.domain.models import MatchOutcome, MaterialAttributes

        outcome = MatchOutcome(
            status=MatchStatus.INVALID,
            attributes=MaterialAttributes(),
            message="Miktar okunamadı.",
        )
        provider = ScriptedProvider([NO_MATCH])

        result = evaluate_rows([("BOQ-100", "bozuk", outcome)], CATALOG, provider)

        assert provider.call_count == 0
        assert result.evaluated_rows == 0


# ---------------------------------------------------------------------------
# 3–5. Doğrulama ve hata yolları
# ---------------------------------------------------------------------------


class TestValidationPaths:
    def test_outside_catalog_code_is_rejected(self, pending_rows) -> None:
        provider = ScriptedProvider([suggestion("IPE-999-S235")] * 3)

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.suggested == 0
        assert result.errors == 3
        for evaluation in result.evaluations.values():
            assert evaluation.error is AiErrorKind.INVALID_CODE
            assert evaluation.suggestion is None

    def test_code_from_other_rows_candidates_is_rejected(self, pending_rows) -> None:
        """Başka satırın adayı bu satır için önerilemez."""
        provider = ScriptedProvider(
            [
                suggestion("IPE-240-S355"),  # BOQ-003'ün adayı değil
                suggestion("IPE-240-S355"),
                NO_MATCH,
            ]
        )

        result = evaluate_rows(pending_rows, CATALOG, provider)

        first = result.evaluations["BOQ-003"]
        assert first.error is AiErrorKind.INVALID_CODE
        assert first.suggestion is None

    def test_broken_json_is_rejected(self, pending_rows) -> None:
        provider = ScriptedProvider(["bu bir json degil"] * 3)

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.errors == 3
        for evaluation in result.evaluations.values():
            assert evaluation.error is AiErrorKind.INVALID_PAYLOAD

    def test_broken_json_does_not_stop_other_rows(self, pending_rows) -> None:
        provider = ScriptedProvider(
            [
                "bozuk",
                suggestion("IPE-240-S355"),
                NO_MATCH,
            ]
        )

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.evaluations["BOQ-003"].error is AiErrorKind.INVALID_PAYLOAD
        assert result.evaluations["BOQ-004"].suggestion is not None
        assert result.evaluations["BOQ-004"].suggestion.suggested_code == "IPE-240-S355"

    def test_timeout_is_handled_safely(self, pending_rows) -> None:
        error = AiProviderError(AiErrorKind.UNAVAILABLE, "TimeoutError")

        result = evaluate_rows(pending_rows, CATALOG, ScriptedProvider([error] * 3))

        assert result.errors == 3
        assert result.suggested == 0
        for evaluation in result.evaluations.values():
            assert evaluation.error is AiErrorKind.UNAVAILABLE
            assert evaluation.error_message
            assert "TimeoutError" not in evaluation.error_message

    def test_provider_error_is_handled_safely(self, pending_rows) -> None:
        error = AiProviderError(AiErrorKind.PROVIDER_ERROR, "HTTP 500")

        result = evaluate_rows(pending_rows, CATALOG, ScriptedProvider([error] * 3))

        assert result.errors == 3
        for evaluation in result.evaluations.values():
            assert evaluation.error is AiErrorKind.PROVIDER_ERROR
            assert "HTTP 500" not in evaluation.error_message

    def test_provider_failure_produces_one_warning(self, pending_rows) -> None:
        error = AiProviderError(AiErrorKind.UNAVAILABLE, "baglanti yok")

        result = evaluate_rows(pending_rows, CATALOG, ScriptedProvider([error] * 3))

        assert len(result.warnings) == 1
        assert "kullanıcı onayı" in result.warnings[0]

    def test_successful_run_has_no_warnings(self, pending_rows) -> None:
        provider = ScriptedProvider(
            [suggestion("IPE-200-S235"), suggestion("IPE-240-S355"), NO_MATCH]
        )

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.warnings == ()


# ---------------------------------------------------------------------------
# 6–7. Durumlar
# ---------------------------------------------------------------------------


class TestStatuses:
    def test_ambiguous_is_reported_without_choice(self) -> None:
        outcome = match_row("lama 40x5", "m", Decimal("0.05"), CATALOG)
        assert outcome.status is MatchStatus.PENDING
        assert len(outcome.candidate_codes) >= 2

        provider = ScriptedProvider([AMBIGUOUS])
        result = evaluate_rows([("BOQ-009", "lama 40x5", outcome)], CATALOG, provider)

        evaluation = result.evaluations["BOQ-009"]
        assert evaluation.ok is True
        assert evaluation.suggestion.status is AiStatus.AMBIGUOUS
        assert evaluation.suggestion.suggested_code is None
        assert result.ambiguous == 1
        assert result.suggested == 0

    def test_no_match_is_reported(self, pending_rows) -> None:
        provider = ScriptedProvider([NO_MATCH] * 3)

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.no_match == 3
        assert result.suggested == 0
        for evaluation in result.evaluations.values():
            assert evaluation.suggestion.suggested_code is None

    def test_single_candidate_ambiguous_is_rejected(self, pending_rows) -> None:
        """Tek adaylı satırda ``ambiguous`` tutarsızdır."""
        provider = ScriptedProvider([AMBIGUOUS, AMBIGUOUS, NO_MATCH])

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.evaluations["BOQ-003"].error is AiErrorKind.INCONSISTENT
        assert result.evaluations["BOQ-004"].error is AiErrorKind.INCONSISTENT
        assert result.evaluations["BOQ-009"].ok is True

    def test_confidence_is_kept_as_decimal(self, pending_rows) -> None:
        provider = ScriptedProvider(
            [suggestion("IPE-200-S235", confidence=0.73), NO_MATCH, NO_MATCH]
        )

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.evaluations["BOQ-003"].suggestion.confidence == Decimal("0.73")


# ---------------------------------------------------------------------------
# 8–9. Otomatik onay yok
# ---------------------------------------------------------------------------


class TestNoAutomaticApproval:
    def test_ai_suggestion_never_sets_matched_code(self, pending_rows) -> None:
        provider = ScriptedProvider(
            [suggestion("IPE-200-S235"), suggestion("IPE-240-S355"), NO_MATCH]
        )

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.suggested == 2
        # Öneri var ama satır sonucu hâlâ pending; matched_code boş.
        for _, _, outcome in pending_rows:
            assert outcome.status is MatchStatus.PENDING
            assert outcome.matched_code is None

    def test_ai_suggestion_does_not_pass_through_apply_decisions(
        self, pending_rows
    ) -> None:
        """AI önerisi karar değildir: ``apply_decisions`` girdisine giremez."""
        outcomes = {boq_no: outcome for boq_no, _, outcome in pending_rows}

        finalised = apply_decisions(outcomes, [], CATALOG)

        for boq_no, outcome in finalised.items():
            assert outcome.status is MatchStatus.PENDING
            assert outcome.matched_code is None

    def test_rejected_row_stays_rejected_regardless_of_ai(self, pending_rows) -> None:
        outcomes = {boq_no: outcome for boq_no, _, outcome in pending_rows}
        decisions = [
            Decision(
                row_no="BOQ-003",
                action=DecisionAction.REJECT,
                reason="Kullanıcı reddetti.",
            )
        ]

        finalised = apply_decisions(outcomes, decisions, CATALOG)

        assert finalised["BOQ-003"].status is MatchStatus.REJECTED
        assert finalised["BOQ-003"].matched_code is None

    def test_user_can_choose_other_candidate_than_ai(
        self, pending_rows
    ) -> None:
        """Kullanıcı AI'nın önerdiğinden başka bir aday seçebilir."""
        outcomes = {boq_no: outcome for boq_no, _, outcome in pending_rows}
        # AI BOQ-009 için ambiguous dedi; kullanıcı galvaniz olanı seçiyor.
        decisions = [
            Decision(
                row_no="BOQ-009",
                action=DecisionAction.APPROVE,
                code="FLAT-40x5-S235-G",
                reason="Galvaniz isteniyor.",
            )
        ]

        finalised = apply_decisions(outcomes, decisions, CATALOG)

        assert finalised["BOQ-009"].status is MatchStatus.AI_APPROVED
        assert finalised["BOQ-009"].matched_code == "FLAT-40x5-S235-G"

    def test_ai_suggestion_cannot_bypass_apply_decisions_validation(self) -> None:
        """AI'nın önerdiği kod açıklamayla çelişirse karar reddedilir."""
        outcome = match_row("IPE 200", "kg", Decimal("0.03"), CATALOG)
        # AI bir şekilde katalogda olan ama çelişen bir kod önerse bile
        # kullanıcı kararı ``apply_decisions`` tarafından denetlenir.
        decisions = [
            Decision(
                row_no="BOQ-003",
                action=DecisionAction.APPROVE,
                code="HEA-200-S235",
                reason="AI önerisi (kötü niyetli varsayım)",
            )
        ]

        from app.domain.decisions import DecisionError

        with pytest.raises(DecisionError, match="çelişiyor"):
            apply_decisions({"BOQ-003": outcome}, decisions, CATALOG)


# ---------------------------------------------------------------------------
# 10. AI kapalı
# ---------------------------------------------------------------------------


class TestAiDisabled:
    def test_none_provider_makes_no_calls(self, pending_rows) -> None:
        provider = NoneProvider()

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.enabled is False
        assert result.provider == "none"
        assert result.evaluations == {}

    def test_default_provider_is_none(self, pending_rows) -> None:
        result = evaluate_rows(pending_rows, CATALOG)

        assert result.enabled is False
        assert result.evaluations == {}

    def test_none_provider_raises_if_called_directly(self) -> None:
        with pytest.raises(AiProviderError) as excinfo:
            NoneProvider().suggest("s", "u")

        assert excinfo.value.kind is AiErrorKind.NOT_CONFIGURED

    def test_disabled_result_has_expected_shape(self) -> None:
        from app.ai.models import DISABLED_RESULT

        assert DISABLED_RESULT.enabled is False
        assert DISABLED_RESULT.provider == "none"
        assert DISABLED_RESULT.evaluated_rows == 0
        assert DISABLED_RESULT.suggestion("BOQ-001") is None


# ---------------------------------------------------------------------------
# 11–12. AI'ya giden veri sınırı
# ---------------------------------------------------------------------------


class TestPayloadBoundary:
    def test_payload_contains_only_recognition_data(self, pending_rows) -> None:
        provider = ScriptedProvider([NO_MATCH] * 3)

        evaluate_rows(pending_rows, CATALOG, provider)

        for payload in provider.payloads():
            assert set(payload) == {"boq_description", "known_features", "candidates"}
            for candidate in payload["candidates"]:
                assert set(candidate) == {
                    "code",
                    "family",
                    "family_label",
                    "size",
                    "grade",
                    "coating",
                    "production_standard",
                    "manufacturing",
                }

    @pytest.mark.parametrize(
        "forbidden",
        [
            "quantity",
            "unit",
            "waste",
            "waste_percent",
            "mass_kg_per_m",
            "commercial_length_m",
            "weight_kg",
            "order_length_m",
            "price",
            "cost",
            "amount",
        ],
    )
    def test_forbidden_fields_never_reach_ai(self, pending_rows, forbidden: str) -> None:
        provider = ScriptedProvider([NO_MATCH] * 3)

        evaluate_rows(pending_rows, CATALOG, provider)

        for _, user_prompt in provider.calls:
            assert forbidden not in user_prompt

    def test_system_prompt_forbids_calculation(self) -> None:
        from app.ai.prompt import SYSTEM_PROMPT

        lowered = SYSTEM_PROMPT.lower()
        assert "hesaplama yapma" in lowered
        assert "miktar" in lowered
        assert "ağırlık" in lowered

    def test_ai_response_cannot_inject_quantity(self, pending_rows) -> None:
        """Yanıt şemasında hesaplama alanı yok; eklenirse reddedilir."""
        import json

        malicious = json.dumps(
            {
                "status": "suggested",
                "suggested_code": "IPE-200-S235",
                "confidence": 0.99,
                "reason": "ok",
                "quantity": "99999",
                "unit": "t",
            }
        )
        provider = ScriptedProvider([malicious] * 3)

        result = evaluate_rows(pending_rows, CATALOG, provider)

        assert result.suggested == 0
        for evaluation in result.evaluations.values():
            assert evaluation.error is AiErrorKind.INVALID_PAYLOAD

    def test_payload_is_deterministic(self, pending_rows) -> None:
        boq_no, description, outcome = pending_rows[0]
        request = build_request(boq_no, description, outcome, CATALOG)

        from app.ai.prompt import build_user_prompt

        assert build_user_prompt(request) == build_user_prompt(request)

    def test_unknown_candidate_codes_are_dropped_from_payload(self) -> None:
        outcome = match_row("IPE 200", "kg", Decimal("0.03"), CATALOG)

        request = build_request("BOQ-003", "IPE 200", outcome, CATALOG)

        assert all(
            CATALOG.get(code) is not None for code in request.candidate_codes
        )

    def test_unexpected_provider_exception_is_isolated(self, pending_rows) -> None:
        """Beklenmeyen sağlayıcı hatası analizi durdurmaz."""

        class Exploding:
            name = "exploding"

            def suggest(self, system_prompt: str, user_prompt: str) -> str:
                raise RuntimeError("adaptör çöktü")

        result = evaluate_rows(pending_rows, CATALOG, Exploding())

        assert result.errors == len(pending_rows)
        assert result.suggested == 0
        for evaluation in result.evaluations.values():
            assert evaluation.error is AiErrorKind.PROVIDER_ERROR
            assert "RuntimeError" not in evaluation.error_message

    def test_row_limit_is_enforced(self) -> None:
        outcome = match_row("IPE 200", "kg", Decimal("0.03"), CATALOG)
        rows = [(f"BOQ-{index:03d}", "IPE 200", outcome) for index in range(MAX_ROWS_PER_REQUEST + 5)]
        provider = ScriptedProvider([NO_MATCH])

        result = evaluate_rows(rows, CATALOG, provider)

        assert provider.call_count == MAX_ROWS_PER_REQUEST
        assert result.evaluated_rows == MAX_ROWS_PER_REQUEST
        assert any("sınırlandırıldı" in warning for warning in result.warnings)


# ---------------------------------------------------------------------------
# Boş aday listesi
# ---------------------------------------------------------------------------


class TestEmptyCandidates:
    def test_no_candidates_yields_no_match_without_calling_ai(self) -> None:
        from app.domain.models import (
            MatchOutcome,
            MatchStatus,
            MaterialAttributes,
        )

        outcome = MatchOutcome(
            status=MatchStatus.PENDING,
            attributes=MaterialAttributes(),
            candidate_codes=(),
            message="Aday yok.",
        )
        provider = ScriptedProvider([NO_MATCH])

        result = evaluate_rows([("BOQ-100", "belirsiz", outcome)], CATALOG, provider)

        assert provider.call_count == 0
        evaluation = result.evaluations["BOQ-100"]
        assert evaluation.suggestion.status is AiStatus.NO_MATCH
        assert evaluation.suggestion.suggested_code is None


# ---------------------------------------------------------------------------
# Sözleşme bekçileri
# ---------------------------------------------------------------------------


def test_suggestion_is_frozen() -> None:
    item = AiSuggestion(
        status=AiStatus.NO_MATCH,
        suggested_code=None,
        confidence=None,
        reason="yok",
        candidate_codes=(),
    )

    with pytest.raises(Exception):
        item.status = AiStatus.SUGGESTED  # type: ignore[misc]


def test_run_result_defaults_are_immutable_tuple() -> None:
    result = AiRunResult(enabled=True, provider="scripted")

    assert result.warnings == ()
    assert isinstance(result.warnings, tuple)


def test_pending_fixture_matches_demo_rows() -> None:
    """Fixture'daki satırlar demo dosyasındaki pending satırlarla aynı."""
    assert set(PENDING_ROWS) == {"BOQ-003", "BOQ-004", "BOQ-006", "BOQ-009"}


def test_validation_error_does_not_leak_provider_text() -> None:
    """Reddedilen ham sağlayıcı metni istemci mesajına taşınmaz."""
    secret = "sk-cok-gizli-anahtar-1234567890"

    with pytest.raises(AiValidationError) as excinfo:
        parse_suggestion(secret, candidates=("IPE-200-S235",))

    from app.ai.models import ERROR_MESSAGES

    message = ERROR_MESSAGES[excinfo.value.kind]
    assert secret not in message
    assert "sk-" not in message
    assert "Traceback" not in message
