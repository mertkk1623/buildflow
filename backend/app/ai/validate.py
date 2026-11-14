"""AI yanıtının doğrulanması — güven sınırının tek kapısı.

Bu modül **savunmacı** çalışır: sağlayıcıdan gelen metin, doğrulanana kadar
hiçbir anlam taşımaz. Reddetme nedenleri kullanıcıya kod olarak döner; ham
sağlayıcı metni istemciye asla gitmez (istek/yanıt içeriği sızdırmaz).

Reddetme kuralı özeti
---------------------
1. Gövde JSON nesnesi olmalı; başka hiçbir şey kabul edilmez.
2. Yalnızca dört anahtar bulunabilir: ``status``, ``suggested_code``,
   ``confidence``, ``reason``. Fazlası → ``invalid-payload``.
3. ``status`` üç değerden biri olmalı.
4. ``suggested`` ise: kod **zorunlu**, aday listesinde olmalı, güven 0–1.
5. ``ambiguous``/``no_match`` ise: kod **null** olmalı (öneri yok).
6. Yalnızca tek aday varken ``ambiguous`` bildirilmesi tutarsızdır.
7. ``confidence`` bool olamaz (``True`` sayı gibi görünür ama değildir).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from app.ai.models import AiErrorKind, AiStatus, AiSuggestion

#: Yanıtta bulunabilecek **tam** anahtar kümesi.
_ALLOWED_KEYS = frozenset({"status", "suggested_code", "confidence", "reason"})

#: Açıklama alanının üst sınırı — model taşması istemciye sızmasın.
_MAX_REASON = 500

#: Tek bir markdown kod bloğunu saran çitler. Model bazen JSON'u böyle sarar.
_FENCE = re.compile(r"^\s*```(?:json|JSON)?\s*\n(?P<body>.*?)\n?\s*```\s*$", re.DOTALL)


class AiValidationError(Exception):
    """AI yanıtı kullanılamaz. ``detail`` yalnızca sunucu logları içindir."""

    def __init__(self, kind: AiErrorKind, detail: str = "") -> None:
        super().__init__(detail or kind.value)
        self.kind = kind
        self.detail = detail


def parse_suggestion(text: str, *, candidates: Iterable[str]) -> AiSuggestion:
    """Ham metni doğrulanmış öneriye çevirir.

    Raises
    ------
    AiValidationError
        Herhangi bir kural ihlalinde; çağıran taraf bunu satır düzeyi hataya
        çevirir ve öneriyi **kullanmaz**.
    """
    payload = _decode(text)
    allowed = set(candidates)

    if not isinstance(payload, dict):
        raise AiValidationError(
            AiErrorKind.INVALID_PAYLOAD, "Yanıt bir JSON nesnesi değil."
        )

    extra = set(payload) - _ALLOWED_KEYS
    if extra:
        raise AiValidationError(
            AiErrorKind.INVALID_PAYLOAD, f"Şema dışı alan(lar): {sorted(extra)}"
        )

    missing = _ALLOWED_KEYS - set(payload)
    if missing:
        raise AiValidationError(
            AiErrorKind.INVALID_PAYLOAD, f"Eksik alan(lar): {sorted(missing)}"
        )

    status = _parse_status(payload["status"])
    suggested_code = _parse_code(payload["suggested_code"])
    confidence = _parse_confidence(payload["confidence"])
    reason = _parse_reason(payload["reason"])

    if status is AiStatus.SUGGESTED:
        if suggested_code is None:
            raise AiValidationError(
                AiErrorKind.INCONSISTENT,
                "'suggested' durumunda kod boş olamaz.",
            )
        if suggested_code not in allowed:
            raise AiValidationError(
                AiErrorKind.INVALID_CODE,
                "Önerilen kod aday listesinde yok.",
            )
        if confidence is None:
            raise AiValidationError(
                AiErrorKind.BAD_CONFIDENCE,
                "'suggested' durumunda güven değeri zorunlu.",
            )
        return AiSuggestion(
            status=status,
            suggested_code=suggested_code,
            confidence=confidence,
            reason=reason,
            candidate_codes=tuple(candidates),
        )

    # ambiguous / no_match → öneri taşımaz.
    if suggested_code is not None:
        raise AiValidationError(
            AiErrorKind.INCONSISTENT,
            f"'{status.value}' durumunda kod null olmalı.",
        )
    if status is AiStatus.AMBIGUOUS and len(allowed) < 2:
        raise AiValidationError(
            AiErrorKind.INCONSISTENT,
            "'ambiguous' için en az iki aday gerekir.",
        )
    return AiSuggestion(
        status=status,
        suggested_code=None,
        confidence=confidence,
        reason=reason,
        candidate_codes=tuple(candidates),
    )


def _decode(text: str) -> object:
    """Metni JSON'a çevirir; markdown çitini ve çevre metnini tolere eder.

    Neden toleranslı: Deploy.com dokümanı ``response_format=json_object``
    alanını **listelemez**. JSON modu istemle istenir ama garanti edilmez;
    model yanıtı bir kod bloğuna sarabilir veya kısa bir giriş cümlesi
    ekleyebilir. Buradaki çözüm **gevşek kabul değildir**: yalnızca tek bir
    JSON nesnesi çıkarılır ve ardından katı şema doğrulaması aynen uygulanır
    (fazla/eksik alan, katalog dışı kod vb. yine reddedilir).
    """
    cleaned = text.strip()
    if not cleaned:
        raise AiValidationError(AiErrorKind.INVALID_PAYLOAD, "Yanıt boş.")

    fenced = _FENCE.match(cleaned)
    if fenced:
        cleaned = fenced.group("body").strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Metnin içine gömülü tek bir JSON nesnesi ara (kod bloğu olmadan).
    embedded = _extract_embedded_object(cleaned)
    if embedded is None:
        raise AiValidationError(
            AiErrorKind.INVALID_PAYLOAD, "JSON çözümlenemedi."
        )

    try:
        return json.loads(embedded)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AiValidationError(
            AiErrorKind.INVALID_PAYLOAD, f"JSON çözümlenemedi: {exc}"
        ) from exc


def _extract_embedded_object(text: str) -> str | None:
    """Metindeki ilk dengeli ``{...}`` bloğunu döndürür.

    Metin içindeki süslü parantezler dize değerlerinde de geçebileceği için
    naif bir sayaç yerine ``json.JSONDecoder.raw_decode`` ile her ``{``
    konumundan itibaren çözümleme denenir. Yalnızca **nesne** kabul edilir.
    """
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(text, index)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            return text[index:end]
    return None


def _parse_status(value: object) -> AiStatus:
    if not isinstance(value, str):
        raise AiValidationError(AiErrorKind.UNKNOWN_STATUS, "status metin değil.")
    try:
        return AiStatus(value.strip().lower())
    except ValueError as exc:
        raise AiValidationError(
            AiErrorKind.UNKNOWN_STATUS, f"Bilinmeyen status: {value!r}"
        ) from exc


def _parse_code(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AiValidationError(
            AiErrorKind.INVALID_CODE, "suggested_code metin değil."
        )
    cleaned = value.strip()
    return cleaned or None


def _parse_confidence(value: object) -> Decimal | None:
    if value is None:
        return None
    # ``bool`` ``int`` alt sınıfıdır; sayı olarak kabul edilmez.
    if isinstance(value, bool):
        raise AiValidationError(
            AiErrorKind.BAD_CONFIDENCE, "confidence mantıksal değer olamaz."
        )
    if not isinstance(value, (int, float, Decimal, str)):
        raise AiValidationError(
            AiErrorKind.BAD_CONFIDENCE, "confidence sayısal değil."
        )
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise AiValidationError(
            AiErrorKind.BAD_CONFIDENCE, "confidence çözümlenemedi."
        ) from exc
    if not number.is_finite() or number < 0 or number > 1:
        raise AiValidationError(
            AiErrorKind.BAD_CONFIDENCE, f"confidence aralık dışı: {number}"
        )
    return number


def _parse_reason(value: object) -> str:
    if not isinstance(value, str):
        raise AiValidationError(AiErrorKind.INVALID_PAYLOAD, "reason metin değil.")
    return value.strip()[:_MAX_REASON]
