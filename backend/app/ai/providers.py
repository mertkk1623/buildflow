"""AI sağlayıcı adaptörleri.

Sözleşme
--------
Sağlayıcı yalnızca **metin üretir**. Doğrulama, katalog denetimi ve iş kuralları
:mod:`app.ai.validate` ve :mod:`app.ai.engine` içindedir; böylece yeni bir
sağlayıcı eklemek güvenlik kurallarını değiştirmez.

Güvenlik
--------
* API anahtarı yalnızca yapılandırmadan okunur, yalnızca istek başlığında
  kullanılır. ``repr``/``str`` çıktısında, log mesajlarında ve hata
  ayrıntılarında **görünmez**.
* Sağlayıcı hataları istemciye ham metin olarak taşınmaz; yalnızca
  :class:`AiErrorKind` kodu döner.
* Sağlayıcı yoksa/erişilemezse sistem deterministik eşleştirmeyle çalışmaya
  devam eder (bkz. :class:`NoneProvider`).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

from app.ai.models import AiErrorKind

#: Varsayılan istek zaman aşımı (saniye). Üzeri yapılandırmadan verilebilir.
DEFAULT_TIMEOUT_SECONDS = 10.0


class AiProviderError(Exception):
    """Sağlayıcı çağrısı başarısız. ``detail`` yalnızca sunucu logları içindir."""

    def __init__(self, kind: AiErrorKind, detail: str = "") -> None:
        super().__init__(detail or kind.value)
        self.kind = kind
        self.detail = detail

    #: API anahtarı veya yanıt gövdesi hata metnine karışmasın diye
    #: ``repr`` sadeleştirilir.
    def __repr__(self) -> str:  # pragma: no cover - hata ayıklama kolaylığı
        return f"AiProviderError({self.kind.value!r})"


@runtime_checkable
class AiProvider(Protocol):
    """Tek yöntemli adaptör: istem → ham yanıt metni."""

    #: Yapılandırmada kullanılan ad (``none``, ``openai-compatible``, ...).
    name: str

    def suggest(self, system_prompt: str, user_prompt: str) -> str:
        """Ham yanıt metnini döndürür.

        Raises
        ------
        AiProviderError
            Zaman aşımı, bağlantı hatası, HTTP hatası veya beklenmeyen gövde.
        """
        ...


class NoneProvider:
    """AI devre dışı — varsayılan sağlayıcı.

    Hiçbir ağ çağrısı yapmaz. Motor bu sağlayıcıyı gördüğünde pending satırlar
    için AI değerlendirmesi **üretmez**; sistem deterministik eşleştirmeyle
    aynen çalışır.
    """

    name = "none"

    def suggest(self, system_prompt: str, user_prompt: str) -> str:
        raise AiProviderError(
            AiErrorKind.NOT_CONFIGURED, "AI sağlayıcısı yapılandırılmadı."
        )


class OpenAICompatibleProvider:
    """OpenAI uyumlu ``/chat/completions`` uç noktası.

    Herhangi bir sağlayıcı (OpenAI, Azure OpenAI uyumlu geçit, yerel model
    sunucusu) aynı sözleşmeyle kullanılabilir. Yeni bağımlılık eklenmez;
    standart kütüphane ``urllib`` kullanılır.
    """

    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    def __repr__(self) -> str:  # pragma: no cover - anahtar sızmasın
        return (
            f"OpenAICompatibleProvider(base_url={self._base_url!r}, "
            f"model={self._model!r})"
        )

    def suggest(self, system_prompt: str, user_prompt: str) -> str:
        body = json.dumps(
            {
                "model": self._model,
                # Yaratıcılık istenmez: aynı girdi aynı öneriyi üretmeli.
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url=f"{self._base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            # Gövde okunmaz: sağlayıcı yanıtı istemciye taşınmaz.
            raise AiProviderError(
                AiErrorKind.PROVIDER_ERROR, f"HTTP {exc.code}"
            ) from exc
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            # Zaman aşımı ve bağlantı hataları aynı güvenli sonuca düşer.
            raise AiProviderError(
                AiErrorKind.UNAVAILABLE, type(exc).__name__
            ) from exc

        return _extract_content(raw)


def _extract_content(raw: bytes) -> str:
    """OpenAI uyumlu gövdeden asistan metnini çıkarır."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AiProviderError(
            AiErrorKind.PROVIDER_ERROR, "Sağlayıcı gövdesi JSON değil."
        ) from exc

    if not isinstance(payload, dict):
        raise AiProviderError(AiErrorKind.PROVIDER_ERROR, "Gövde nesne değil.")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AiProviderError(AiErrorKind.PROVIDER_ERROR, "choices boş.")

    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise AiProviderError(AiErrorKind.PROVIDER_ERROR, "message.content yok.")

    return content
