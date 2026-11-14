"""Sağlayıcı fabrikası — yapılandırmadan adaptör üretimi.

Kural: API anahtarı eksikse veya sağlayıcı adı tanınmıyorsa **sessizce**
``NoneProvider`` döner ve sistem deterministik eşleştirmeyle çalışır. Böylece
yanlış yapılandırma uygulamayı durdurmaz; ancak anahtar hiçbir yere yazılmaz.
"""

from __future__ import annotations

import logging

from app.ai.providers import (
    DEFAULT_TIMEOUT_SECONDS,
    AiProvider,
    NoneProvider,
    OpenAICompatibleProvider,
)

logger = logging.getLogger(__name__)

#: Tanınan sağlayıcı adları. Yeni sağlayıcı eklemek buraya bir satır ekler.
SUPPORTED_PROVIDERS: tuple[str, ...] = ("none", "openai-compatible")


def build_provider(
    *,
    name: str = "none",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    reasoning_effort: str | None = "none",
    json_mode: bool = False,
) -> AiProvider:
    """Yapılandırmadan sağlayıcı üretir.

    Eksik/geçersiz yapılandırma istisna **fırlatmaz**: güvenli varsayılana
    (``NoneProvider``) düşer ve sunucu logunda uyarır. API anahtarı loglanmaz.

    ``reasoning_effort`` ve ``json_mode`` varsayılanları Deploy.com
    dokümanına göredir: düşünme kapalı (``none``), JSON modu **istenmez**
    (alan dokümante edilmemiş; biçim istem + doğrulama ile güvence altında).
    """
    normalized = (name or "none").strip().lower()

    if normalized in {"", "none", "off", "disabled"}:
        return NoneProvider()

    if normalized not in SUPPORTED_PROVIDERS:
        logger.warning(
            "Bilinmeyen AI sağlayıcısı %r; AI devre dışı bırakıldı. "
            "Desteklenenler: %s",
            normalized,
            ", ".join(SUPPORTED_PROVIDERS),
        )
        return NoneProvider()

    if not api_key:
        logger.warning(
            "AI sağlayıcısı %r seçildi ancak API anahtarı boş; "
            "AI devre dışı bırakıldı.",
            normalized,
        )
        return NoneProvider()

    if not base_url or not model:
        logger.warning(
            "AI sağlayıcısı %r için base_url/model eksik; AI devre dışı bırakıldı.",
            normalized,
        )
        return NoneProvider()

    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        reasoning_effort=reasoning_effort,
        json_mode=json_mode,
    )


def provider_from_settings(settings) -> AiProvider:
    """``Settings`` nesnesinden sağlayıcı üretir (uygulama için tek giriş)."""
    return build_provider(
        name=settings.ai_provider,
        api_key=settings.ai_api_key_value,
        base_url=settings.ai_base_url,
        model=settings.ai_model,
        timeout_seconds=float(settings.ai_timeout_seconds),
    )
