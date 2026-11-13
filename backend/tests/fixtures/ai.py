"""AI testleri için sahte sağlayıcılar.

Gerçek ağ çağrısı **yapılmaz**. Sağlayıcılar sırayla önceden yazılmış yanıtları
döndürür ve gelen istemleri kaydeder; böylece "AI'ya ne gitti" ve "AI'dan ne
kabul edildi" ayrı ayrı doğrulanabilir.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from app.ai.models import AiErrorKind
from app.ai.providers import AiProviderError


class ScriptedProvider:
    """Sırayla yanıt döndüren sahte sağlayıcı.

    Parameters
    ----------
    replies:
        Her çağrı için ham metin **veya** ``AiProviderError`` örneği.
        Liste tükenirse son öğe tekrar kullanılır.
    name:
        Yapılandırma adı; testlerde ``"scripted"``.
    """

    def __init__(self, replies: Iterable[str | AiProviderError], *, name: str = "scripted") -> None:
        self._replies = list(replies)
        self.name = name
        self.calls: list[tuple[str, str]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def suggest(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))

        if not self._replies:
            raise AiProviderError(AiErrorKind.PROVIDER_ERROR, "Yanıt tanımlı değil.")

        reply = self._replies[0] if len(self._replies) == 1 else self._replies.pop(0)
        if isinstance(reply, AiProviderError):
            raise reply
        return reply

    # --- Test yardımcıları -------------------------------------------------

    def last_payload(self) -> dict:
        """Son çağrının kullanıcı istemini sözlük olarak döndürür."""
        return json.loads(self.calls[-1][1])

    def payloads(self) -> list[dict]:
        return [json.loads(user_prompt) for _, user_prompt in self.calls]


def suggestion(
    code: str | None,
    *,
    status: str = "suggested",
    confidence: float | None = 0.9,
    reason: str = "Aday, açıklamadaki özelliklerle uyuşuyor.",
) -> str:
    """Geçerli biçimde JSON öneri metni üretir."""
    return json.dumps(
        {
            "status": status,
            "suggested_code": code,
            "confidence": confidence,
            "reason": reason,
        },
        ensure_ascii=False,
    )


AMBIGUOUS = suggestion(
    None,
    status="ambiguous",
    confidence=None,
    reason="Açıklamada kaplama belirtilmemiş; iki aday da olası.",
)
NO_MATCH = suggestion(
    None,
    status="no_match",
    confidence=None,
    reason="Açıklama adaylardan hiçbiriyle güvenilir biçimde eşleşmiyor.",
)

#: Demo dosyasında pending olan satırlar ve aday kodları.
PENDING_ROWS: dict[str, str] = {
    "BOQ-003": "IPE-200-S235",
    "BOQ-004": "IPE-240-S355",
    "BOQ-006": "HEA-200-S235",
    "BOQ-009": "FLAT-40x5-S235-B",
}


def replies_for_demo(codes: dict[str, str] | None = None) -> dict[str, str]:
    """Pending satır sırasına göre yanıt listesi üretir.

    ``codes`` verilirse o satır için kod, verilmezse ``PENDING_ROWS`` kullanılır.
    """
    mapping = codes or PENDING_ROWS
    return {boq_no: suggestion(code) for boq_no, code in mapping.items()}
