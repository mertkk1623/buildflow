"""AI yanıt doğrulama testleri.

Kapsanan senaryolar:

1.  Geçerli öneri kabul edilir
2.  Katalog dışı kod reddedilir
3.  Bozuk JSON reddedilir
4.  Eksik / fazla alan reddedilir
5.  Bilinmeyen ``status`` reddedilir
6.  Güven değeri aralık dışı / bool / metin reddedilir
7.  ``ambiguous`` tek adayla tutarsızdır
8.  ``ambiguous``/``no_match`` kod taşıyamaz
9.  Markdown çiti soyulur
10. Ham sağlayıcı metni hata ayrıntısına sızmaz
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.ai.models import AiErrorKind, AiStatus
from app.ai.validate import AiValidationError, parse_suggestion

CANDIDATES = ("IPE-200-S235", "IPE-240-S355")


def payload(**overrides: object) -> str:
    body: dict[str, object] = {
        "status": "suggested",
        "suggested_code": "IPE-200-S235",
        "confidence": 0.9,
        "reason": "Ölçü ve kalite uyuşuyor.",
    }
    body.update(overrides)
    return json.dumps(body, ensure_ascii=False)


class TestAcceptedResponses:
    def test_valid_suggestion_is_accepted(self) -> None:
        result = parse_suggestion(payload(), candidates=CANDIDATES)

        assert result.status is AiStatus.SUGGESTED
        assert result.suggested_code == "IPE-200-S235"
        assert result.confidence == Decimal("0.9")
        assert result.reason == "Ölçü ve kalite uyuşuyor."
        assert result.is_suggestion is True

    def test_candidate_codes_are_preserved(self) -> None:
        result = parse_suggestion(payload(), candidates=CANDIDATES)

        assert result.candidate_codes == CANDIDATES

    def test_ambiguous_is_accepted_with_two_candidates(self) -> None:
        result = parse_suggestion(
            payload(status="ambiguous", suggested_code=None, confidence=None),
            candidates=CANDIDATES,
        )

        assert result.status is AiStatus.AMBIGUOUS
        assert result.suggested_code is None
        assert result.is_suggestion is False

    def test_no_match_is_accepted(self) -> None:
        result = parse_suggestion(
            payload(status="no_match", suggested_code=None, confidence=None),
            candidates=CANDIDATES,
        )

        assert result.status is AiStatus.NO_MATCH
        assert result.suggested_code is None

    @pytest.mark.parametrize("confidence", [0, 0.0, 1, 1.0, "0.5"])
    def test_confidence_bounds_are_inclusive(self, confidence: object) -> None:
        result = parse_suggestion(
            payload(confidence=confidence), candidates=CANDIDATES
        )

        assert result.confidence is not None
        assert Decimal("0") <= result.confidence <= Decimal("1")

    def test_status_is_case_insensitive(self) -> None:
        result = parse_suggestion(payload(status="SUGGESTED"), candidates=CANDIDATES)

        assert result.status is AiStatus.SUGGESTED

    def test_markdown_fence_is_stripped(self) -> None:
        fenced = "```json\n" + payload() + "\n```"

        result = parse_suggestion(fenced, candidates=CANDIDATES)

        assert result.suggested_code == "IPE-200-S235"

    def test_surrounding_whitespace_is_tolerated(self) -> None:
        result = parse_suggestion("\n  " + payload() + "  \n", candidates=CANDIDATES)

        assert result.suggested_code == "IPE-200-S235"

    def test_reason_is_truncated(self) -> None:
        result = parse_suggestion(
            payload(reason="x" * 5000), candidates=CANDIDATES
        )

        assert len(result.reason) == 500


class TestRejectedCodes:
    def test_code_outside_candidates_is_rejected(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(
                payload(suggested_code="IPE-999-S235"), candidates=CANDIDATES
            )

        assert excinfo.value.kind is AiErrorKind.INVALID_CODE

    def test_code_outside_single_candidate_list_is_rejected(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(
                payload(suggested_code="HEA-200-S235"),
                candidates=("IPE-200-S235",),
            )

        assert excinfo.value.kind is AiErrorKind.INVALID_CODE

    def test_suggested_without_code_is_inconsistent(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(payload(suggested_code=None), candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.INCONSISTENT

    def test_code_with_non_string_type_is_rejected(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(payload(suggested_code=123), candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.INVALID_CODE

    def test_blank_code_is_treated_as_missing(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(payload(suggested_code="   "), candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.INCONSISTENT


class TestBrokenPayloads:
    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "bu bir json degil",
            "{status: suggested}",
            "{\"status\": \"suggested\",",
            "[]",
            "[{\"status\": \"suggested\"}]",
            "\"suggested\"",
            "null",
        ],
    )
    def test_non_object_or_invalid_json_is_rejected(self, raw: str) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(raw, candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.INVALID_PAYLOAD

    def test_missing_field_is_rejected(self) -> None:
        body = json.dumps({"status": "suggested", "suggested_code": "IPE-200-S235"})

        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(body, candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.INVALID_PAYLOAD
        assert "confidence" in excinfo.value.detail

    def test_extra_field_is_rejected(self) -> None:
        body = json.dumps(
            {
                "status": "suggested",
                "suggested_code": "IPE-200-S235",
                "confidence": 0.9,
                "reason": "ok",
                "quantity": 100,
            }
        )

        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(body, candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.INVALID_PAYLOAD
        assert "quantity" in excinfo.value.detail

    def test_snake_case_injection_is_rejected(self) -> None:
        """AI'nın hesaplama alanı eklemesi şema tarafından engellenir."""
        body = json.dumps(
            {
                "status": "suggested",
                "suggested_code": "IPE-200-S235",
                "confidence": 0.9,
                "reason": "ok",
                "matched_code": "IPE-200-S235",
                "weight_kg": "1",
            }
        )

        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(body, candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.INVALID_PAYLOAD


class TestStatusAndConfidence:
    @pytest.mark.parametrize(
        "status", ["approved", "matched", "ok", "", "suggest", "PENDING", None, 1]
    )
    def test_unknown_status_is_rejected(self, status: object) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(payload(status=status), candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.UNKNOWN_STATUS

    @pytest.mark.parametrize("confidence", [-0.1, 1.1, 2, 100, "abc", True, False, [], {}])
    def test_invalid_confidence_is_rejected(self, confidence: object) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(payload(confidence=confidence), candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.BAD_CONFIDENCE

    def test_suggested_without_confidence_is_rejected(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(payload(confidence=None), candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.BAD_CONFIDENCE

    def test_non_finite_confidence_is_rejected(self) -> None:
        raw = json.dumps(
            {
                "status": "suggested",
                "suggested_code": "IPE-200-S235",
                "confidence": "NaN",
                "reason": "ok",
            }
        )

        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(raw, candidates=CANDIDATES)

        assert excinfo.value.kind is AiErrorKind.BAD_CONFIDENCE


class TestAmbiguityRules:
    def test_ambiguous_with_single_candidate_is_inconsistent(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(
                payload(status="ambiguous", suggested_code=None, confidence=None),
                candidates=("IPE-200-S235",),
            )

        assert excinfo.value.kind is AiErrorKind.INCONSISTENT
        assert "iki aday" in excinfo.value.detail

    def test_ambiguous_with_no_candidates_is_inconsistent(self) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(
                payload(status="ambiguous", suggested_code=None, confidence=None),
                candidates=(),
            )

        assert excinfo.value.kind is AiErrorKind.INCONSISTENT

    @pytest.mark.parametrize("status", ["ambiguous", "no_match"])
    def test_non_suggested_status_cannot_carry_code(self, status: str) -> None:
        with pytest.raises(AiValidationError) as excinfo:
            parse_suggestion(
                payload(status=status, suggested_code="IPE-200-S235"),
                candidates=CANDIDATES,
            )

        assert excinfo.value.kind is AiErrorKind.INCONSISTENT

    def test_no_match_is_allowed_with_single_candidate(self) -> None:
        result = parse_suggestion(
            payload(status="no_match", suggested_code=None, confidence=None),
            candidates=("IPE-200-S235",),
        )

        assert result.status is AiStatus.NO_MATCH
