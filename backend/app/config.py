"""Uygulama yapılandırması.

Tüm ortam değişkenleri tek noktadan okunur. Gerçek anahtarlar yalnızca
`.env` dosyasında tutulur ve asla depoya eklenmez.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BUILDFLOW_",
        extra="ignore",
    )

    app_name: str = "BuildFlow AI API"
    environment: str = "development"

    # Frontend geliştirme sunucusu (Vite). Üretimde daraltılmalıdır.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
