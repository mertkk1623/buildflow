"""AI destekli malzeme eşleştirme — veri modelleri.

Tasarım sınırları
-----------------
Bu paket **yalnızca eşleştirme önerisi** üretir. Miktar, birim, fire, ağırlık
veya maliyet hesaplamaz; hesap motoruna hiçbir değer sızdırmaz. AI çıktısı
``described`` bir öneridir, karar değildir: hiçbir zaman otomatik onaylanmaz.

Buradaki modeller HTTP'den ve FastAPI'den bağımsızdır; :mod:`app.api` bunları
kendi yanıt modellerine çevirir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from app.domain.models import MaterialAttributes


class AiSkipReason(str, Enum):
    """AI açıkken hiçbir satırın değerlendirilmemesinin nedeni.

    Bu kod **hata değildir**: yapılandırma doğru, çağrılacak satır yok.
    İstemci bunu "AI bozuk" ile karıştırmamalıdır.
    """

    #: Dosyada ``pending`` satır yok; tüm satırlar deterministik olarak
    #: çözülmüş (``rule``) veya kapsam dışı/fire eksik diye elenmiş.
    NO_PENDING_ROWS = "no-pending-rows"
    #: Pending satır vardı ama BOQ No/açıklama taşımadığı için gönderilemedi.
    MISSING_ROW_IDENTITY = "missing-row-identity"


class AiStatus(str, Enum):
    """AI'nın bildirebileceği **üç** durum. Başka değer kabul edilmez."""

    #: Tek bir aday güçlü biçimde öneriliyor.
    SUGGESTED = "suggested"
    #: Birden fazla aday aynı derecede olası; AI zorla seçim yapmaz.
    AMBIGUOUS = "ambiguous"
    #: Güvenilir eşleşme bulunamadı.
    NO_MATCH = "no_match"


class AiErrorKind(str, Enum):
    """Önerinin neden kullanılmadığı — kullanıcıya gösterilebilir kod.

    Bunlar AI'nın *durumu* değildir; sunucunun kendi değerlendirme sonucudur.
    """

    #: Sağlayıcı hiç yapılandırılmadı (varsayılan ``none``).
    NOT_CONFIGURED = "not-configured"
    #: Yanıt gövdesi JSON nesnesi değil veya şema dışı alanlar taşıyor.
    INVALID_PAYLOAD = "invalid-payload"
    #: Bildirilen durum üç değerden biri değil.
    UNKNOWN_STATUS = "unknown-status"
    #: ``confidence`` sayı değil ya da 0–1 aralığı dışında.
    BAD_CONFIDENCE = "bad-confidence"
    #: Önerilen kod aday listesinde (dolayısıyla katalogda) yok.
    INVALID_CODE = "invalid-code"
    #: Alanlar birbiriyle tutarsız (ör. ``ambiguous`` ama tek aday).
    INCONSISTENT = "inconsistent-response"
    #: Sağlayıcıya ulaşılamadı veya zaman aşımı.
    UNAVAILABLE = "provider-unavailable"
    #: Sağlayıcı beklenmeyen bir hata döndürdü.
    PROVIDER_ERROR = "provider-error"


#: Kullanıcıya gösterilecek kısa açıklamalar. Sunucu ayrıntısı içermez.
ERROR_MESSAGES: dict[AiErrorKind, str] = {
    AiErrorKind.NOT_CONFIGURED: "AI sağlayıcısı devre dışı.",
    AiErrorKind.INVALID_PAYLOAD: "AI yanıtı beklenen JSON biçiminde değil.",
    AiErrorKind.UNKNOWN_STATUS: "AI yanıtı tanımsız bir durum bildirdi.",
    AiErrorKind.BAD_CONFIDENCE: "AI güven değeri 0–1 aralığında değil.",
    AiErrorKind.INVALID_CODE: "AI önerisi aday listesindeki bir kod değil.",
    AiErrorKind.INCONSISTENT: "AI yanıtı kendi içinde tutarsız.",
    AiErrorKind.UNAVAILABLE: "AI servisine ulaşılamadı.",
    AiErrorKind.PROVIDER_ERROR: "AI servisi beklenmeyen bir yanıt döndürdü.",
}


@dataclass(frozen=True, slots=True)
class AiCandidate:
    """AI'ya gösterilen **tek** aday kalem.

    Kütle, ticari boy ve fire bilinçli olarak yoktur: bunlar ticari/hesap
    verisidir ve AI'ya gönderilmez.
    """

    code: str
    family: str
    family_label: str
    size: str
    grade: str
    coating: str
    production_standard: str
    manufacturing: str

    def to_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "family": self.family,
            "family_label": self.family_label,
            "size": self.size,
            "grade": self.grade,
            "coating": self.coating,
            "production_standard": self.production_standard,
            "manufacturing": self.manufacturing,
        }


@dataclass(frozen=True, slots=True)
class AiMatchRequest:
    """Tek bir bekleyen satır için AI'ya gönderilecek **tam** istek.

    ``boq_no`` kasıtlı olarak yük taşımaz; yalnızca sunucu tarafında eşleme
    anahtarıdır. Gönderilen gövde :meth:`payload` ile üretilir ve yalnızca
    açıklama + bilinen özellikler + adaylar içerir.
    """

    boq_no: str
    description: str
    attributes: MaterialAttributes
    candidates: tuple[AiCandidate, ...]

    @property
    def candidate_codes(self) -> tuple[str, ...]:
        return tuple(candidate.code for candidate in self.candidates)

    def payload(self) -> dict[str, object]:
        """AI'ya giden sözlük. Miktar/birim/fire/ağırlık/maliyet **yoktur**."""
        return {
            "boq_description": self.description,
            "known_features": {
                "family": (
                    self.attributes.family.value
                    if self.attributes.family is not None
                    else None
                ),
                "size": self.attributes.size,
                "grade": (
                    self.attributes.grade.value
                    if self.attributes.grade is not None
                    else None
                ),
                "coating": (
                    self.attributes.coating.value
                    if self.attributes.coating is not None
                    else None
                ),
            },
            "candidates": [candidate.to_payload() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class AiSuggestion:
    """Doğrulanmış AI önerisi — karar değil, yalnızca öneri."""

    status: AiStatus
    suggested_code: str | None
    confidence: Decimal | None
    reason: str
    candidate_codes: tuple[str, ...]

    @property
    def is_suggestion(self) -> bool:
        return self.status is AiStatus.SUGGESTED


@dataclass(frozen=True, slots=True)
class AiEvaluation:
    """Tek satırın AI değerlendirmesi: ya geçerli öneri ya da hata."""

    boq_no: str
    suggestion: AiSuggestion | None = None
    error: AiErrorKind | None = None
    error_detail: str = ""

    @property
    def ok(self) -> bool:
        return self.suggestion is not None

    @property
    def error_message(self) -> str:
        if self.error is None:
            return ""
        return ERROR_MESSAGES.get(self.error, "AI değerlendirmesi kullanılamadı.")


@dataclass(frozen=True, slots=True)
class AiRunResult:
    """Bir analiz isteğinin toplu AI sonucu."""

    enabled: bool
    provider: str
    evaluations: dict[str, AiEvaluation] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    #: AI açıkken hiçbir satır değerlendirilmediyse **neden**. Kapalıyken
    #: veya iş yapıldıysa ``None``. ``AiSkipReason`` değerlerinden biridir.
    skipped_reason: str | None = None

    def suggestion(self, boq_no: str | None) -> AiSuggestion | None:
        if boq_no is None:
            return None
        evaluation = self.evaluations.get(boq_no)
        return evaluation.suggestion if evaluation is not None else None

    def _count(self, status: AiStatus) -> int:
        return sum(
            1
            for evaluation in self.evaluations.values()
            if evaluation.suggestion is not None
            and evaluation.suggestion.status is status
        )

    @property
    def suggested(self) -> int:
        return self._count(AiStatus.SUGGESTED)

    @property
    def ambiguous(self) -> int:
        return self._count(AiStatus.AMBIGUOUS)

    @property
    def no_match(self) -> int:
        return self._count(AiStatus.NO_MATCH)

    @property
    def errors(self) -> int:
        return sum(1 for evaluation in self.evaluations.values() if not evaluation.ok)

    @property
    def evaluated_rows(self) -> int:
        return len(self.evaluations)


DISABLED_RESULT = AiRunResult(enabled=False, provider="none")
"""AI kapalıyken kullanılan sabit sonuç (değiştirilemez)."""
