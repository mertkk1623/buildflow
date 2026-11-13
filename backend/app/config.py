"""Uygulama yapılandırması.

Tüm ortam değişkenleri tek noktadan okunur. Gerçek anahtarlar yalnızca
`.env` dosyasında tutulur ve asla depoya eklenmez.

CORS
----
Geliştirmede Vite sunucusu (5173) izinlidir. Üretimde izin listesi
``BUILDFLOW_CORS_ORIGINS`` ile **açıkça** verilmelidir; geniş joker (``*``)
kullanılmaz. Liste boşsa tarayıcı istekleri reddedilir — güvenli varsayılan.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Depo kökü: ``backend/app/config.py`` → 2 üst dizin.
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Varsayılan şablon konumu (depo kökünde ``templates/``).
DEFAULT_TEMPLATE_PATH = _REPO_ROOT / "templates" / "metraj_sablonu.xlsx"

#: Yükleme için varsayılan üst sınır: 10 MB.
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

#: AI isteği için varsayılan zaman aşımı (saniye).
DEFAULT_AI_TIMEOUT_SECONDS = 10.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BUILDFLOW_",
        extra="ignore",
    )

    app_name: str = "BuildFlow AI API"
    environment: str = "development"

    #: Frontend geliştirme sunucusu (Vite). Üretimde daraltılmalıdır.
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    #: Yükleme boyutu üst sınırı (bayt).
    max_upload_bytes: int = Field(default=DEFAULT_MAX_UPLOAD_BYTES, gt=0)

    #: Metraj şablonunun sunucudaki yolu. Testlerde geçici dizine yönlendirilir.
    template_path: Path = Field(default=DEFAULT_TEMPLATE_PATH)

    # --- AI eşleştirme (Aşama 4.5) ---
    #: Sağlayıcı adı. Varsayılan ``none``: AI kapalı, hiçbir ağ çağrısı yok.
    ai_provider: str = Field(default="none", max_length=40)
    #: API anahtarı. Yalnızca ortam değişkeninden okunur ve **hiçbir zaman**
    #: yanıt, log veya ``repr`` içinde görünmez.
    ai_api_key: SecretStr | None = Field(default=None)
    #: OpenAI uyumlu uç nokta kökü (ör. ``https://api.openai.com/v1``).
    ai_base_url: str | None = Field(default=None, max_length=400)
    #: Kullanılacak model adı.
    ai_model: str | None = Field(default=None, max_length=120)
    #: İstek zaman aşımı (saniye). Aşımda satır pending kalır.
    ai_timeout_seconds: float = Field(
        default=DEFAULT_AI_TIMEOUT_SECONDS, gt=0, le=120
    )

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, value: list[str]) -> list[str]:
        """Joker origin kabul edilmez: kimlik bilgisi sızdırabilir."""
        cleaned = [origin.strip().rstrip("/") for origin in value if origin.strip()]
        if "*" in cleaned:
            raise ValueError(
                "Joker CORS origin ('*') kullanılamaz; açık origin listesi verin."
            )
        return cleaned

    @field_validator("ai_provider")
    @classmethod
    def _normalise_provider(cls, value: str) -> str:
        return (value or "none").strip().lower()

    @field_validator("ai_base_url")
    @classmethod
    def _normalise_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        return cleaned or None

    @property
    def ai_api_key_value(self) -> str | None:
        """Anahtarın değeri — yalnızca istek başlığı için okunur."""
        if self.ai_api_key is None:
            return None
        return self.ai_api_key.get_secret_value() or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
