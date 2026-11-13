"""Sağlayıcı adaptörü ve yapılandırma testleri.

Gerçek ağ çağrısı yapılmaz: ``urllib.request.urlopen`` monkeypatch ile
değiştirilir. Kapsanan senaryolar:

1.  ``none`` sağlayıcısı hiç çağrı yapmaz
2.  Anahtar eksik/boşsa AI kapalı kalır
3.  Bilinmeyen sağlayıcı adı güvenli varsayılana düşer
4.  HTTP hatası, timeout ve bozuk gövde güvenli hataya dönüşür
5.  API anahtarı ``repr``/``str``/log içinde görünmez
6.  Ağ trafiği yalnızca seçili model ve uç nokta ile yapılır
7.  AI yapılandırması ayarlardan doğru okunur
"""

from __future__ import annotations

import io
import json
import logging
import urllib.error

import pytest

from app.ai.factory import build_provider, provider_from_settings
from app.ai.models import AiErrorKind
from app.ai.providers import (
    AiProviderError,
    NoneProvider,
    OpenAICompatibleProvider,
    _extract_content,
)
from app.config import Settings

SECRET = "sk-test-gizli-anahtar-abcdef123456"


def ok_response(content: str) -> io.BytesIO:
    return io.BytesIO(
        json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
    )


class TestNoneProvider:
    def test_none_provider_never_calls_network(self) -> None:
        provider = NoneProvider()

        assert provider.name == "none"
        with pytest.raises(AiProviderError):
            provider.suggest("s", "u")

    def test_none_provider_error_kind(self) -> None:
        with pytest.raises(AiProviderError) as excinfo:
            NoneProvider().suggest("s", "u")

        assert excinfo.value.kind is AiErrorKind.NOT_CONFIGURED


class TestFactory:
    def test_default_is_none(self) -> None:
        provider = build_provider()

        assert isinstance(provider, NoneProvider)

    @pytest.mark.parametrize("name", ["none", "off", "disabled", "", "NONE"])
    def test_disabled_names_map_to_none(self, name: str) -> None:
        provider = build_provider(
            name=name,
            api_key=SECRET,
            base_url="https://example.test/v1",
            model="m",
        )

        assert isinstance(provider, NoneProvider)

    def test_unknown_provider_falls_back_safely(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            provider = build_provider(
                name="bilinmeyen",
                api_key=SECRET,
                base_url="https://example.test/v1",
                model="m",
            )

        assert isinstance(provider, NoneProvider)
        assert "Bilinmeyen AI sağlayıcısı" in caplog.text

    def test_missing_api_key_disables_ai(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            provider = build_provider(
                name="openai-compatible",
                api_key=None,
                base_url="https://example.test/v1",
                model="m",
            )

        assert isinstance(provider, NoneProvider)
        assert "API anahtarı boş" in caplog.text

    def test_empty_api_key_disables_ai(self) -> None:
        provider = build_provider(
            name="openai-compatible",
            api_key="",
            base_url="https://example.test/v1",
            model="m",
        )

        assert isinstance(provider, NoneProvider)

    def test_missing_base_url_disables_ai(self) -> None:
        provider = build_provider(
            name="openai-compatible",
            api_key=SECRET,
            base_url=None,
            model="m",
        )

        assert isinstance(provider, NoneProvider)

    def test_missing_model_disables_ai(self) -> None:
        provider = build_provider(
            name="openai-compatible",
            api_key=SECRET,
            base_url="https://example.test/v1",
            model=None,
        )

        assert isinstance(provider, NoneProvider)

    def test_complete_config_builds_provider(self) -> None:
        provider = build_provider(
            name="openai-compatible",
            api_key=SECRET,
            base_url="https://example.test/v1",
            model="test-model",
        )

        assert isinstance(provider, OpenAICompatibleProvider)

    def test_provider_repr_hides_api_key(self) -> None:
        provider = build_provider(
            name="openai-compatible",
            api_key=SECRET,
            base_url="https://example.test/v1",
            model="test-model",
        )

        assert SECRET not in repr(provider)
        assert SECRET not in str(provider)

    def test_factory_never_logs_api_key(self, caplog) -> None:
        with caplog.at_level(logging.DEBUG):
            build_provider(
                name="bilinmeyen",
                api_key=SECRET,
                base_url="https://example.test/v1",
                model="m",
            )

        assert SECRET not in caplog.text


class TestSettingsIntegration:
    def test_settings_defaults_disable_ai(self) -> None:
        settings = Settings()

        assert settings.ai_provider == "none"
        assert settings.ai_api_key_value is None
        assert isinstance(provider_from_settings(settings), NoneProvider)

    def test_incomplete_config_falls_back_to_none(self) -> None:
        """Eksik yapılandırma istisna fırlatmaz, güvenli varsayılana düşer."""
        assert isinstance(
            provider_from_settings(
                Settings(
                    ai_provider="openai-compatible",
                    ai_api_key=SECRET,
                    ai_base_url="https://example.test/v1",
                )
            ),
            NoneProvider,
        )
        assert isinstance(
            provider_from_settings(
                Settings(
                    ai_provider="openai-compatible",
                    ai_api_key=SECRET,
                    ai_model="m",
                )
            ),
            NoneProvider,
        )

    def test_api_key_is_secret_in_settings_repr(self) -> None:
        settings = Settings(
            ai_provider="openai-compatible",
            ai_api_key=SECRET,
            ai_base_url="https://example.test/v1",
            ai_model="m",
        )

        assert SECRET not in repr(settings)
        assert SECRET not in str(settings)
        assert settings.ai_api_key_value == SECRET

    def test_provider_from_settings(self) -> None:
        settings = Settings(
            ai_provider="openai-compatible",
            ai_api_key=SECRET,
            ai_base_url="https://example.test/v1/",
            ai_model="m",
        )

        provider = provider_from_settings(settings)

        assert isinstance(provider, OpenAICompatibleProvider)

    def test_provider_from_settings_defaults_to_none(self) -> None:
        assert isinstance(provider_from_settings(Settings()), NoneProvider)

    def test_base_url_trailing_slash_is_normalised(self) -> None:
        settings = Settings(
            ai_provider="openai-compatible",
            ai_api_key=SECRET,
            ai_base_url="https://example.test/v1/",
            ai_model="m",
        )

        assert settings.ai_base_url == "https://example.test/v1"

    def test_provider_name_is_normalised(self) -> None:
        settings = Settings(ai_provider="NONE")

        assert settings.ai_provider == "none"

    @pytest.mark.parametrize("timeout", [0, -1, 500])
    def test_invalid_timeout_is_rejected(self, timeout: float) -> None:
        with pytest.raises(ValueError):
            Settings(ai_timeout_seconds=timeout)


class TestHttpProvider:
    def _provider(self, **overrides) -> OpenAICompatibleProvider:
        options = {
            "base_url": "https://example.test/v1",
            "api_key": SECRET,
            "model": "test-model",
            "timeout_seconds": 5,
        }
        options.update(overrides)
        return OpenAICompatibleProvider(**options)

    def test_successful_call_returns_content(self, monkeypatch) -> None:
        captured: dict = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["auth"] = request.get_header("Authorization")
            return ok_response('{"status": "no_match"}')

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        result = self._provider().suggest("sistem", "kullanıcı")

        assert result == '{"status": "no_match"}'
        assert captured["url"] == "https://example.test/v1/chat/completions"
        assert captured["timeout"] == 5
        assert captured["auth"] == f"Bearer {SECRET}"
        assert captured["body"]["model"] == "test-model"
        assert captured["body"]["temperature"] == 0
        assert captured["body"]["messages"][0]["role"] == "system"

    def test_http_error_becomes_provider_error(self, monkeypatch) -> None:
        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"gizli")
            )

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        with pytest.raises(AiProviderError) as excinfo:
            self._provider().suggest("s", "u")

        assert excinfo.value.kind is AiErrorKind.PROVIDER_ERROR
        assert "gizli" not in excinfo.value.detail
        assert SECRET not in str(excinfo.value)

    @pytest.mark.parametrize(
        "exception",
        [
            TimeoutError("zaman aşımı"),
            urllib.error.URLError("bağlantı yok"),
            OSError("soket kapandı"),
        ],
    )
    def test_network_errors_become_unavailable(self, monkeypatch, exception) -> None:
        def fake_urlopen(request, timeout):
            raise exception

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        with pytest.raises(AiProviderError) as excinfo:
            self._provider().suggest("s", "u")

        assert excinfo.value.kind is AiErrorKind.UNAVAILABLE

    def test_non_json_body_is_provider_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda request, timeout: io.BytesIO(b"<html>hata</html>"),
        )

        with pytest.raises(AiProviderError) as excinfo:
            self._provider().suggest("s", "u")

        assert excinfo.value.kind is AiErrorKind.PROVIDER_ERROR

    def test_missing_choices_is_provider_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda request, timeout: io.BytesIO(b'{"choices": []}'),
        )

        with pytest.raises(AiProviderError) as excinfo:
            self._provider().suggest("s", "u")

        assert excinfo.value.kind is AiErrorKind.PROVIDER_ERROR

    def test_missing_content_is_provider_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda request, timeout: io.BytesIO(
                b'{"choices": [{"message": {}}]}'
            ),
        )

        with pytest.raises(AiProviderError) as excinfo:
            self._provider().suggest("s", "u")

        assert excinfo.value.kind is AiErrorKind.PROVIDER_ERROR

    def test_provider_error_repr_hides_detail(self) -> None:
        error = AiProviderError(AiErrorKind.PROVIDER_ERROR, f"gizli {SECRET}")

        assert SECRET not in repr(error)


class TestExtractContent:
    def test_valid_payload(self) -> None:
        raw = b'{"choices": [{"message": {"content": "merhaba"}}]}'

        assert _extract_content(raw) == "merhaba"

    @pytest.mark.parametrize(
        "raw",
        [
            b"",
            b"null",
            b"[]",
            b'{"choices": null}',
            b'{"choices": [{}]}',
            b'{"choices": [{"message": null}]}',
            b'{"choices": [{"message": {"content": null}}]}',
        ],
    )
    def test_invalid_payloads_raise(self, raw: bytes) -> None:
        with pytest.raises(AiProviderError):
            _extract_content(raw)

    def test_invalid_utf8_raises(self) -> None:
        with pytest.raises(AiProviderError):
            _extract_content(b"\xff\xfe\x00garbage")
