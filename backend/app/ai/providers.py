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

#: Yanıtın üst sınırı. JSON yanıtı kısa olduğu için cömert bir değer yeterlidir;
#: sınır verilmezse sağlayıcı varsayılanı (bazı modellerde 64K) kullanılır ve
#: yanıt gereksiz yere uzayabilir.
#:
#: Not: Deploy.com bu alanı ``max_completion_tokens`` adıyla bekler; eski
#: ``max_tokens`` adı dokümante edilmemiştir (bkz. :data:`_TOKEN_LIMIT_FIELD`).
DEFAULT_MAX_TOKENS = 512

#: Deploy.com'un token sınırı için beklediği alan adı.
#:
#: Doküman (``deepseek-v4-1-flash-1017``) yalnızca ``max_completion_tokens``
#: listeler. Sınır gönderilmezse model düşünme (`reasoning`) token'larıyla
#: birlikte uzun üretebilir; bu yüzden açıkça gönderilir.
_TOKEN_LIMIT_FIELD = "max_completion_tokens"

#: HTTP durum kodlarının güvenli hata türlerine eşlemesi.
#:
#: Neden ayrı türler: tek bir ``provider-error`` altında toplandığında
#: "anahtar mı geçersiz, bakiye mi bitti, model adı mı hatalı" ayırt edilemiyordu.
#: Eşleme yalnızca **durum koduna** dayanır; yanıt gövdesi hiç okunmaz, böylece
#: sağlayıcı metni (potansiyel olarak PII/anahtar izi) hiçbir yere taşınmaz.
#:
#: 405 istisnadır ve doküman gereği **bakiye** anlamına gelir: Deploy.com
#: bakiyesi olmayan kuruluşlara ``405`` + "Your Organization is currently
#: paused" döndürür. Bu, ``402`` ile aynı güvenli türe eşlenir.
_HTTP_STATUS_KINDS: dict[int, AiErrorKind] = {
    400: AiErrorKind.INVALID_REQUEST,
    401: AiErrorKind.AUTH_FAILED,
    402: AiErrorKind.INSUFFICIENT_BALANCE,
    403: AiErrorKind.AUTH_FAILED,
    404: AiErrorKind.INVALID_REQUEST,
    405: AiErrorKind.INSUFFICIENT_BALANCE,
    408: AiErrorKind.UNAVAILABLE,
    413: AiErrorKind.INVALID_REQUEST,
    422: AiErrorKind.INVALID_REQUEST,
    429: AiErrorKind.RATE_LIMITED,
}


def _kind_for_status(status: int) -> AiErrorKind:
    """HTTP durum kodunu güvenli hata türüne çevirir.

    Eşlenmemiş her kod — ``5xx`` sunucu arızaları ve beklenmeyen kodlar dahil —
    ``PROVIDER_ERROR`` olarak kalır.
    """
    return _HTTP_STATUS_KINDS.get(status, AiErrorKind.PROVIDER_ERROR)


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
        max_completion_tokens: int = DEFAULT_MAX_TOKENS,
        reasoning_effort: str | None = "none",
        json_mode: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._max_completion_tokens = max_completion_tokens
        self._reasoning_effort = reasoning_effort
        self._json_mode = json_mode

    def __repr__(self) -> str:  # pragma: no cover - anahtar sızmasın
        return (
            f"OpenAICompatibleProvider(base_url={self._base_url!r}, "
            f"model={self._model!r})"
        )

    def suggest(self, system_prompt: str, user_prompt: str) -> str:
        body: dict[str, object] = {
            "model": self._model,
            # Yaratıcılık istenmez: aynı girdi aynı öneriyi üretmeli.
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # Deploy.com token sınırı alanı: ``max_completion_tokens``.
            # Eski ``max_tokens`` adı dokümante edilmemiştir.
            _TOKEN_LIMIT_FIELD: self._max_completion_tokens,
        }

        if self._reasoning_effort is not None:
            # Deploy.com: ``reasoning_effort`` ∈ {none, low, high, max},
            # varsayılan ``high``. ``none`` düşünmeyi kapatır ve modeli normal
            # sohbet modeli gibi davrandırır. Bu görev yalnızca sınıflandırma
            # olduğu için varsayılan ``none``: gecikme ve düşünme token'ı
            # maliyeti düşer, ``temperature`` anlamlı kalır.
            body["reasoning_effort"] = self._reasoning_effort

        if self._json_mode:
            # Yalnızca isteğe bağlı. Deploy.com dokümanı ``response_format``
            # alanını **listelemez**; gönderilmesi 400'e yol açabilir. Bu yüzden
            # varsayılan kapalıdır ve JSON biçimi istem + katı doğrulama ile
            # güvence altına alınır (bkz. :mod:`app.ai.validate`).
            body["response_format"] = {"type": "json_object"}

        payload = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            url=f"{self._base_url}/chat/completions",
            data=payload,
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
            # Gövde **okunmaz**: sağlayıcı yanıtı istemciye taşınmaz ve
            # içinde anahtar/PII izi olabilir. Yalnızca durum kodu sınıflanır.
            raise AiProviderError(_kind_for_status(exc.code), f"HTTP {exc.code}") from exc
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
