"""AI alt sistemi — dışa aktarım yüzeyi.

Bu paket :mod:`app.domain` ve :mod:`app.excel` modüllerini **değiştirmez**;
yalnızca okur. HTTP'den bağımsızdır, böylece sağlayıcı olmadan da test
edilebilir.

Varsayılan davranış: AI **kapalı**. ``AiProviderName.NONE`` sağlayıcısı hiçbir
ağ çağrısı yapmaz ve sistem deterministik eşleştirmeyle birebir aynı sonucu
verir.
"""

from app.ai.engine import MAX_ROWS_PER_REQUEST, build_request, evaluate_rows
from app.ai.factory import build_provider, provider_from_settings
from app.ai.models import (
    AiCandidate,
    AiErrorKind,
    AiEvaluation,
    AiMatchRequest,
    AiRunResult,
    AiStatus,
    AiSuggestion,
    DISABLED_RESULT,
)
from app.ai.providers import (
    AiProvider,
    AiProviderError,
    NoneProvider,
    OpenAICompatibleProvider,
)
from app.ai.validate import AiValidationError, parse_suggestion

__all__ = [
    "DISABLED_RESULT",
    "MAX_ROWS_PER_REQUEST",
    "AiCandidate",
    "AiErrorKind",
    "AiEvaluation",
    "AiMatchRequest",
    "AiProvider",
    "AiProviderError",
    "AiRunResult",
    "AiStatus",
    "AiSuggestion",
    "AiValidationError",
    "NoneProvider",
    "OpenAICompatibleProvider",
    "build_provider",
    "build_request",
    "evaluate_rows",
    "parse_suggestion",
    "provider_from_settings",
]
