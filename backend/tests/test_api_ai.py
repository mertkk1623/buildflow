"""``/api/analyze`` + ``/api/calculate`` AI entegrasyon testleri.

Bu testler **gerçek HTTP** üzerinden gider: router, şema serileştirmesi ve
``/api/calculate`` güvenlik doğrulaması dahil. AI sağlayıcısı sahtedir
(:class:`tests.fixtures.ai.ScriptedProvider`); hiçbir ağ çağrısı yapılmaz.

Kapsanan senaryolar:

1.  AI kapalıyken yanıt 4.4 ile birebir aynı ve ``ai.enabled == false``
2.  Yalnızca ``pending`` satırlar AI değerlendirmesi taşır
3.  Deterministik eşleşen satırlarda AI **çağrılmaz**
4.  Katalog dışı kod reddedilir
5.  Bozuk JSON reddedilir
6.  Timeout / API hatası güvenli ele alınır
7.  Çoklu aday → ``ambiguous``
8.  Eşleşme yok → ``no_match``
9.  AI önerisi ``matched_code`` alanına **yazılmaz** (otomatik onay yok)
10. Öneri olmadan ``/api/calculate`` satırı hesaplamaz
11. Kullanıcı reddi korunur
12. AI yanıtı miktarı, birimi ve hesabı değiştiremez
13. API anahtarı yanıt gövdesinde görünmez
"""

from __future__ import annotations

import io
import json
import logging
import urllib.error
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.models import AiErrorKind
from app.ai.providers import AiProviderError
from app.api.routes import XLSX_MEDIA_TYPE
from app.config import get_settings
from tests.fixtures.ai import (
    AMBIGUOUS,
    NO_MATCH,
    PENDING_ROWS,
    ScriptedProvider,
    suggestion,
)
from tests.fixtures.api import (
    analyze_ok,
    calculate,
    client_rows,
    decide,
    upload,
)
from tests.fixtures.excel_files import build_demo_workbook

#: Demo'daki pending satırlar, AI çağrı sırasına göre (Excel satır sırası).
DEMO_AI_REPLIES = [
    suggestion("IPE-200-S235"),  # BOQ-003
    suggestion("IPE-240-S355"),  # BOQ-004
    suggestion("HEA-200-S235"),  # BOQ-006
    AMBIGUOUS,  # BOQ-009 — iki aday var, AI zorla seçmez
]


@pytest.fixture(scope="module")
def demo_workbook(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("api-ai-demo")
    return build_demo_workbook(directory / "demo.xlsx")


@pytest.fixture()
def scripted(monkeypatch: pytest.MonkeyPatch) -> Any:
    """``/api/analyze`` için sahte sağlayıcı enjekte eden fabrika.

    Kullanım: ``provider = scripted([...])``. Sağlayıcı router'ın gördüğü
    fabrika fonksiyonuna bağlanır; uygulama kodu değişmez.
    """

    def install(replies: list[Any]) -> ScriptedProvider:
        provider = ScriptedProvider(replies)
        monkeypatch.setattr(
            "app.api.routes.provider_from_settings", lambda settings: provider
        )
        return provider

    return install


def rows_by_no(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["boq_no"]: row for row in body["rows"]}


# ---------------------------------------------------------------------------
# 1. AI kapalı (varsayılan)
# ---------------------------------------------------------------------------


class TestAiDisabledByDefault:
    def test_summary_reports_ai_disabled(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        body = analyze_ok(client, demo_workbook)

        assert body["ai"] == {
            "enabled": False,
            "provider": "none",
            "evaluated_rows": 0,
            "suggested": 0,
            "ambiguous": 0,
            "no_match": 0,
            "errors": 0,
        }

    def test_no_row_carries_ai_payload(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        body = analyze_ok(client, demo_workbook)

        assert body["rows"]
        for row in body["rows"]:
            assert row["ai"] is None

    def test_deterministic_distribution_is_unchanged(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        """AI kapalıyken 4.4 dağılımı birebir korunur."""
        summary = analyze_ok(client, demo_workbook)["summary"]

        assert summary["rule"] == 10
        assert summary["pending"] == 4
        assert summary["excluded"] == 4
        assert summary["invalid"] == 0

    def test_disabled_ai_adds_no_warning(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        body = analyze_ok(client, demo_workbook)

        assert body["warnings"] == []

    def test_none_provider_makes_no_network_call(
        self, client: TestClient, demo_workbook: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def forbidden(*args, **kwargs):  # pragma: no cover - çağrılırsa test düşer
            raise AssertionError("AI kapalıyken ağ çağrısı yapılmamalı")

        monkeypatch.setattr("urllib.request.urlopen", forbidden)

        body = analyze_ok(client, demo_workbook)

        assert body["ai"]["enabled"] is False


# ---------------------------------------------------------------------------
# 2–3. Yalnızca pending satırlar
# ---------------------------------------------------------------------------


class TestOnlyPendingRows:
    def test_pending_rows_receive_suggestions(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        provider = scripted(DEMO_AI_REPLIES)

        body = analyze_ok(client, demo_workbook)
        rows = rows_by_no(body)

        assert provider.call_count == 4
        assert set(PENDING_ROWS) == {
            boq_no for boq_no, row in rows.items() if row["ai"] is not None
        }
        assert rows["BOQ-003"]["ai"]["suggestion"]["suggested_code"] == "IPE-200-S235"
        assert rows["BOQ-006"]["ai"]["suggestion"]["suggested_code"] == "HEA-200-S235"

    def test_rule_and_excluded_rows_have_no_ai(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)

        rows = rows_by_no(analyze_ok(client, demo_workbook))

        for boq_no, row in rows.items():
            if row["status"] == "pending":
                assert row["ai"] is not None, boq_no
            else:
                assert row["ai"] is None, boq_no

    def test_ai_payload_has_no_forbidden_fields(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        provider = scripted(DEMO_AI_REPLIES)

        analyze_ok(client, demo_workbook)

        for payload in provider.payloads():
            assert set(payload) == {"boq_description", "known_features", "candidates"}
            assert "quantity" not in payload
            assert "unit" not in payload
            assert "waste_percent" not in payload
            for candidate in payload["candidates"]:
                assert "mass_kg_per_m" not in candidate
                assert "code" in candidate

    def test_summary_counts_match_statuses(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)

        body = analyze_ok(client, demo_workbook)

        assert body["ai"] == {
            "enabled": True,
            "provider": "scripted",
            "evaluated_rows": 4,
            "suggested": 3,
            "ambiguous": 1,
            "no_match": 0,
            "errors": 0,
        }


# ---------------------------------------------------------------------------
# 4–6. Doğrulama ve hata yolları
# ---------------------------------------------------------------------------


class TestRejectedResponses:
    def test_outside_catalog_code_is_rejected(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted([suggestion("IPE-999-S235")])

        body = analyze_ok(client, demo_workbook)
        ai = rows_by_no(body)["BOQ-003"]["ai"]

        assert ai["suggestion"] is None
        assert ai["error"]["code"] == "invalid-code"
        assert ai["error"]["message"]
        assert body["ai"]["errors"] == 4

    def test_broken_json_is_rejected(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(["```json\n{ bozuk }\n```"])

        body = analyze_ok(client, demo_workbook)
        ai = rows_by_no(body)["BOQ-003"]["ai"]

        assert ai["suggestion"] is None
        assert ai["error"]["code"] == "invalid-payload"

    def test_timeout_is_reported_safely(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted([AiProviderError(AiErrorKind.UNAVAILABLE, "TimeoutError")])

        body = analyze_ok(client, demo_workbook)
        ai = rows_by_no(body)["BOQ-003"]["ai"]

        assert ai["error"]["code"] == "provider-unavailable"
        assert "TimeoutError" not in ai["error"]["message"]
        assert body["ai"]["errors"] == 4
        assert len(body["warnings"]) == 1

    def test_api_error_is_reported_safely(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted([AiProviderError(AiErrorKind.PROVIDER_ERROR, "HTTP 503")])

        body = analyze_ok(client, demo_workbook)
        ai = rows_by_no(body)["BOQ-003"]["ai"]

        assert ai["error"]["code"] == "provider-error"
        assert "HTTP 503" not in ai["error"]["message"]

    def test_provider_failure_does_not_break_analysis(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        """AI erişilemezse deterministik sonuç aynen döner."""
        scripted([AiProviderError(AiErrorKind.UNAVAILABLE, "bağlantı yok")])

        body = analyze_ok(client, demo_workbook)

        assert body["summary"]["rule"] == 10
        assert body["summary"]["pending"] == 4
        assert body["summary"]["excluded"] == 4

    def test_one_bad_row_does_not_block_others(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(["bozuk json"] + DEMO_AI_REPLIES[1:])

        body = analyze_ok(client, demo_workbook)
        rows = rows_by_no(body)

        assert rows["BOQ-003"]["ai"]["error"]["code"] == "invalid-payload"
        assert rows["BOQ-004"]["ai"]["suggestion"]["status"] == "suggested"
        assert body["ai"] == {
            "enabled": True,
            "provider": "scripted",
            "evaluated_rows": 4,
            "suggested": 2,
            "ambiguous": 1,
            "no_match": 0,
            "errors": 1,
        }


# ---------------------------------------------------------------------------
# 7–8. ambiguous / no_match
# ---------------------------------------------------------------------------


class TestStatuses:
    def test_multiple_candidates_yield_ambiguous(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)

        row = rows_by_no(analyze_ok(client, demo_workbook))["BOQ-009"]

        assert row["match"]["candidate_codes"] == [
            "FLAT-40x5-S235-B",
            "FLAT-40x5-S235-G",
        ]
        assert row["ai"]["suggestion"]["status"] == "ambiguous"
        assert row["ai"]["suggestion"]["suggested_code"] is None
        assert row["ai"]["suggestion"]["confidence"] is None
        assert row["status"] == "pending"

    def test_no_match_is_reported_without_code(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted([NO_MATCH] * 4)

        body = analyze_ok(client, demo_workbook)

        assert body["ai"]["no_match"] == 4
        assert body["ai"]["suggested"] == 0
        for row in body["rows"]:
            if row["ai"] is not None:
                assert row["ai"]["suggestion"]["suggested_code"] is None

    def test_ambiguous_with_single_candidate_is_rejected(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted([AMBIGUOUS] * 4)

        body = analyze_ok(client, demo_workbook)
        row = rows_by_no(body)["BOQ-003"]

        assert row["ai"]["suggestion"] is None
        assert row["ai"]["error"]["code"] == "inconsistent-response"
        # BOQ-009'un gerçekten iki adayı var; o satır geçerli.
        assert rows_by_no(body)["BOQ-009"]["ai"]["suggestion"]["status"] == "ambiguous"


# ---------------------------------------------------------------------------
# 9–11. Otomatik onay yok, kullanıcı kararı
# ---------------------------------------------------------------------------


class TestNoAutomaticApproval:
    def test_suggestion_is_not_written_to_matched_code(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)

        rows = rows_by_no(analyze_ok(client, demo_workbook))

        for boq_no in PENDING_ROWS:
            assert rows[boq_no]["status"] == "pending"
            assert rows[boq_no]["match"]["matched_code"] is None

    def test_suggested_code_is_not_an_allowed_calculate_field(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        """İstemci ``suggested_code`` alanını satıra ekleyemez."""
        scripted(DEMO_AI_REPLIES)
        body = analyze_ok(client, demo_workbook)
        rows = client_rows(body)
        rows[0]["suggested_code"] = "IPE-200-S235"

        response = calculate(client, rows)

        assert response.status_code == 422

    def test_pending_row_without_decision_is_skipped(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        """AI önerisi hesaplamaya kendiliğinden girmez."""
        scripted(DEMO_AI_REPLIES)
        body = analyze_ok(client, demo_workbook)

        result = calculate(client, client_rows(body)).json()

        assert result["summary"]["calculated_rows"] == 10
        pending = {row["boq_no"] for row in result["skipped"] if row["status"] == "pending"}
        assert pending == set(PENDING_ROWS)

    def test_user_can_approve_with_suggested_code(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)
        body = analyze_ok(client, demo_workbook)
        decisions = [
            decide("BOQ-003", "approve", "IPE-200-S235", "AI önerisi onaylandı.")
        ]

        result = calculate(client, client_rows(body), decisions).json()

        assert "IPE-200-S235" in {group["code"] for group in result["groups"]}

    def test_user_can_reject_ai_suggestion(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)
        body = analyze_ok(client, demo_workbook)
        decisions = [
            decide("BOQ-003", "reject", reason="AI önerisi reddedildi."),
        ]

        result = calculate(client, client_rows(body), decisions).json()
        skipped = {row["boq_no"]: row for row in result["skipped"]}

        assert skipped["BOQ-003"]["status"] == "rejected"
        assert skipped["BOQ-003"]["matched_code"] is None
        assert "IPE-200-S235" not in {group["code"] for group in result["groups"]}

    def test_user_can_pick_a_candidate_ai_rejected(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        """AI ``ambiguous`` dedi; kullanıcı galvaniz olanı seçebilir."""
        scripted(DEMO_AI_REPLIES)
        body = analyze_ok(client, demo_workbook)
        decisions = [
            decide("BOQ-009", "approve", "FLAT-40x5-S235-G", "Galvaniz isteniyor.")
        ]

        result = calculate(client, client_rows(body), decisions).json()

        assert "FLAT-40x5-S235-G" in {group["code"] for group in result["groups"]}

    def test_ai_suggestion_cannot_bypass_conflict_validation(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        """Kullanıcı AI'nın kodunu açıklamayla çelişecek şekilde kullanamaz."""
        scripted(DEMO_AI_REPLIES)
        body = analyze_ok(client, demo_workbook)
        # BOQ-003 açıklaması IPE 200/S235; HEA kodu çelişir.
        decisions = [decide("BOQ-003", "approve", "HEA-200-S235", "AI dedi")]

        response = calculate(client, client_rows(body), decisions)

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid-decision"

    def test_catalog_outside_code_is_rejected_by_calculate(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)
        body = analyze_ok(client, demo_workbook)
        decisions = [decide("BOQ-003", "approve", "IPE-999-S235", "uydurma")]

        response = calculate(client, client_rows(body), decisions)

        assert response.status_code == 409


# ---------------------------------------------------------------------------
# 12. Hesaplama değişmezliği
# ---------------------------------------------------------------------------


class TestCalculationUnchanged:
    def test_ai_does_not_change_quantity_or_unit(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        baseline = rows_by_no(analyze_ok(client, demo_workbook))
        scripted(DEMO_AI_REPLIES)
        with_ai = rows_by_no(analyze_ok(client, demo_workbook))

        for boq_no, before in baseline.items():
            after = with_ai[boq_no]
            assert after["quantity"] == before["quantity"]
            assert after["unit"] == before["unit"]
            assert after["waste_percent"] == before["waste_percent"]
            assert after["description"] == before["description"]
            assert after["match"] == before["match"]

    def test_total_weight_is_identical_with_ai_enabled(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        baseline_body = analyze_ok(client, demo_workbook)
        baseline = calculate(
            client,
            client_rows(baseline_body),
            [
                decide("BOQ-003", "approve", "IPE-200-S235"),
                decide("BOQ-004", "approve", "IPE-240-S355"),
                decide("BOQ-006", "approve", "HEA-200-S235"),
            ],
        ).json()

        scripted(DEMO_AI_REPLIES)
        with_ai_body = analyze_ok(client, demo_workbook)
        with_ai = calculate(
            client,
            client_rows(with_ai_body),
            [
                decide("BOQ-003", "approve", "IPE-200-S235"),
                decide("BOQ-004", "approve", "IPE-240-S355"),
                decide("BOQ-006", "approve", "HEA-200-S235"),
            ],
        ).json()

        assert with_ai["summary"] == baseline["summary"]
        assert with_ai["groups"] == baseline["groups"]

    def test_malicious_ai_payload_cannot_change_numbers(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        """AI yanıtına hesaplama alanı eklenirse tüm yanıt reddedilir."""
        scripted(
            [
                '{"status": "suggested", "suggested_code": "IPE-200-S235",'
                ' "confidence": 0.9, "reason": "ok", "quantity": "99999", "unit": "t"}'
            ]
            + DEMO_AI_REPLIES[1:]
        )

        body = analyze_ok(client, demo_workbook)
        rows = rows_by_no(body)

        assert rows["BOQ-003"]["ai"]["error"]["code"] == "invalid-payload"
        assert rows["BOQ-003"]["quantity"] == "1240"
        assert rows["BOQ-003"]["unit"] == "kg"


# ---------------------------------------------------------------------------
# 13. Gizli bilgi sızıntısı
# ---------------------------------------------------------------------------


class TestSecretHandling:
    SECRET = "sk-canli-test-anahtari-0123456789abcdef"

    def test_api_key_never_appears_in_response(
        self,
        client: TestClient,
        demo_workbook: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Gerçek yapılandırmadan gelen anahtar yanıta sızmaz.

        Sağlayıcı **gerçek** olandır (``openai-compatible``); yalnızca ağ
        katmanı taklit edilir. Böylece anahtarın başlıkta kullanıldığı ve
        yanıta sızmadığı aynı testte doğrulanır.
        """
        captured: dict[str, str] = {}

        def fake_urlopen(request, timeout):
            captured["auth"] = request.get_header("Authorization") or ""
            content = suggestion("IPE-200-S235")
            return io.BytesIO(
                json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            )

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setenv("BUILDFLOW_AI_PROVIDER", "openai-compatible")
        monkeypatch.setenv("BUILDFLOW_AI_API_KEY", self.SECRET)
        monkeypatch.setenv("BUILDFLOW_AI_BASE_URL", "https://example.test/v1")
        monkeypatch.setenv("BUILDFLOW_AI_MODEL", "test-model")
        get_settings.cache_clear()

        try:
            response = upload(client, demo_workbook)
        finally:
            get_settings.cache_clear()

        assert response.status_code == 200
        # Anahtar istekte kullanıldı ama yanıtta yok.
        assert captured["auth"] == f"Bearer {self.SECRET}"
        raw = response.text
        assert self.SECRET not in raw
        assert "Bearer" not in raw
        assert "Authorization" not in raw
        assert "sk-" not in raw
        assert response.json()["ai"]["enabled"] is True
        assert response.json()["ai"]["provider"] == "openai-compatible"

    def test_api_key_never_appears_in_logs(
        self,
        client: TestClient,
        demo_workbook: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sağlayıcı hatası loglansa bile anahtar log satırına düşmez."""
        def fake_urlopen(request, timeout):
            raise urllib.error.URLError("bağlantı yok")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setenv("BUILDFLOW_AI_PROVIDER", "openai-compatible")
        monkeypatch.setenv("BUILDFLOW_AI_API_KEY", self.SECRET)
        monkeypatch.setenv("BUILDFLOW_AI_BASE_URL", "https://example.test/v1")
        monkeypatch.setenv("BUILDFLOW_AI_MODEL", "test-model")
        get_settings.cache_clear()

        try:
            with caplog.at_level(logging.DEBUG):
                body = analyze_ok(client, demo_workbook)
        finally:
            get_settings.cache_clear()

        assert self.SECRET not in caplog.text
        assert "Bearer" not in caplog.text
        assert "sk-" not in caplog.text
        assert body["ai"]["errors"] == 4

    def test_ai_block_has_only_two_fields(
        self, client: TestClient, demo_workbook: Path, scripted
    ) -> None:
        scripted(DEMO_AI_REPLIES)

        body = analyze_ok(client, demo_workbook)

        for row in body["rows"]:
            if row["ai"] is not None:
                assert set(row["ai"]) == {"suggestion", "error"}


# ---------------------------------------------------------------------------
# Dosya biçimi / kapsam dışı davranış korunur
# ---------------------------------------------------------------------------


def test_ai_does_not_change_error_responses(
    client: TestClient, scripted, tmp_path: Path
) -> None:
    """AI etkin olsa da bozuk dosya aynı 415/422 hatasını verir."""
    scripted([])

    response = upload(
        client,
        _write_bytes(tmp_path / "bozuk.csv", b"a,b,c"),
        filename="bozuk.csv",
        content_type="text/csv",
    )

    assert response.status_code == 415


def test_crashing_engine_does_not_break_analyze(
    client: TestClient, demo_workbook: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI motoru çökse bile analiz deterministik sonuçla döner."""

    def explode(*args, **kwargs):
        raise RuntimeError("motor çöktü")

    monkeypatch.setattr("app.api.service.evaluate_rows", explode)
    monkeypatch.setattr(
        "app.api.routes.provider_from_settings",
        lambda settings: ScriptedProvider([]),
    )

    response = upload(client, demo_workbook)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["rule"] == 10
    assert body["summary"]["pending"] == 4
    assert body["ai"]["enabled"] is True
    assert body["ai"]["evaluated_rows"] == 0
    assert any("AI değerlendirmesi çalıştırılamadı" in w for w in body["warnings"])
    for row in body["rows"]:
        assert row["ai"] is None
        if row["status"] == "pending":
            assert row["match"]["matched_code"] is None


def _write_bytes(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def test_xlsx_media_type_is_unchanged() -> None:
    assert XLSX_MEDIA_TYPE.endswith("spreadsheetml.sheet")


def test_analyze_response_shape_has_ai_block(
    client: TestClient, demo_workbook: Path
) -> None:
    body = analyze_ok(client, demo_workbook)

    assert set(body) == {
        "rows",
        "summary",
        "ai",
        "warnings",
        "ignored_columns",
        "sheet_name",
    }


def test_quantity_strings_are_exact(
    client: TestClient, demo_workbook: Path, scripted
) -> None:
    """AI açıkken de Decimal metin olarak kayıpsız taşınır."""
    scripted(DEMO_AI_REPLIES)

    rows = rows_by_no(analyze_ok(client, demo_workbook))

    assert Decimal(rows["BOQ-004"]["quantity"]) == Decimal("0.84")
    assert rows["BOQ-004"]["unit"] == "t"
