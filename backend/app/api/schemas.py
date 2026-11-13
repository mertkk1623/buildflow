"""API request/response modelleri — Aşama 4.4.

Tasarım kuralları
-----------------
1. **Decimal JSON'da string.** ``0.1`` float olarak taşınırsa tarayıcıda
   ikili kesir hatası oluşur ve miktar değişir. Tüm ``Decimal`` alanları
   ``str`` olarak serileşir.
2. **Eksik değer ``null``.** Fire tanımsızsa ``null``; sıfır yazılmaz.
3. **FULL/PARTIAL açık.** Her grupta ``status`` alanı ve eksik alan listesi.
4. **Kaynak iz korunur.** ``source_row`` (Excel satırı) ve ``boq_no`` her
   satırda birlikte taşınır.
5. **Domain modeli değiştirilmez.** Bu modeller yalnızca taşıma kabıdır;
   dönüşüm :mod:`app.api.mapping` içinde açıkça yapılır.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator


def _decimal_to_str(value: Decimal | None) -> str | None:
    """``Decimal``'ı kayıpsız metne çevirir; ``None`` korunur."""
    if value is None:
        return None
    return format(value, "f")


#: JSON'da string olarak taşınan ``Decimal``.
#:
#: ``format(value, "f")`` bilimsel gösterim üretmez (``1E+2`` değil ``100``),
#: böylece tarayıcıda ``Number(...)`` dönüşümü kayıpsız olur.
DecimalStr = Annotated[
    Decimal,
    PlainSerializer(_decimal_to_str, return_type=str, when_used="json"),
]

OptionalDecimalStr = Annotated[
    Decimal | None,
    PlainSerializer(_decimal_to_str, return_type=str | None, when_used="json"),
]


# ---------------------------------------------------------------------------
# Ortak
# ---------------------------------------------------------------------------


class ApiModel(BaseModel):
    """API modellerinin ortak yapılandırması."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class FieldIssue(ApiModel):
    """Tek bir satır/alan hatası — kullanıcıya düzeltme önerisiyle."""

    source_row: int | None = Field(
        default=None, description="Excel'deki 1 tabanlı satır numarası"
    )
    boq_no: str | None = None
    column: str | None = Field(default=None, description="Hatalı kolon adı")
    code: str = Field(description="Makine tarafından okunabilir hata nedeni")
    message: str
    suggestion: str = ""


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(ApiModel):
    status: str
    environment: str


# ---------------------------------------------------------------------------
# Analyze — satır sonuçları
# ---------------------------------------------------------------------------


class CandidateOut(ApiModel):
    """Kullanıcıya sunulan aday katalog kalemi."""

    code: str
    family: str
    family_label: str
    size: str
    grade: str
    coating: str
    label: str = Field(description="Okunabilir tek satır etiket")
    mass_kg_per_m: OptionalDecimalStr = None
    commercial_length_m: OptionalDecimalStr = None


class MatchOut(ApiModel):
    """Deterministik eşleştirme sonucu — sunucu üretir, istemci karar verir."""

    status: Literal["rule", "pending", "excluded", "invalid"]
    matched_code: str | None = None
    candidate_codes: list[str] = Field(default_factory=list)
    candidates: list[CandidateOut] = Field(default_factory=list)
    exclusion_reason: Literal["waste", "unit", "catalog", "missing-mass"] | None = None
    message: str = ""


class AiSuggestionOut(ApiModel):
    """AI'nın doğrulanmış önerisi — **karar değildir**.

    ``matched_code`` alanıyla karıştırılmamalıdır: bu alan yalnızca kullanıcıya
    sunulan bir öneridir ve hiçbir zaman hesaplamaya girmez. Kullanıcı
    onaylamadan satır ``pending`` kalır.
    """

    status: Literal["suggested", "ambiguous", "no_match"]
    suggested_code: str | None = Field(
        default=None,
        description="Yalnızca 'suggested' durumunda dolu; katalog kodu",
    )
    confidence: OptionalDecimalStr = Field(
        default=None, description="0–1 arası güven; yoksa null"
    )
    reason: str = ""
    candidate_codes: list[str] = Field(
        default_factory=list, description="AI'ya gösterilen adaylar"
    )


class AiErrorOut(ApiModel):
    """AI değerlendirmesinin neden kullanılamadığı — öneri yoktur."""

    code: Literal[
        "not-configured",
        "invalid-payload",
        "unknown-status",
        "bad-confidence",
        "invalid-code",
        "inconsistent-response",
        "provider-unavailable",
        "provider-error",
    ]
    message: str


class AiOut(ApiModel):
    """Bir satırın AI değerlendirmesi: ya öneri ya hata (ikisi birden olmaz).

    Alan ``null`` ise AI o satır için **çalışmadı** (satır ``pending``
    değildi veya AI kapalıydı).
    """

    suggestion: AiSuggestionOut | None = None
    error: AiErrorOut | None = None


class AiSummaryOut(ApiModel):
    """Analizdeki AI kullanımının özeti."""

    enabled: bool
    provider: str
    evaluated_rows: int
    suggested: int
    ambiguous: int
    no_match: int
    errors: int
    #: AI açıkken hiçbir satır değerlendirilmediyse nedeni; aksi hâlde
    #: yanıttan **tamamen çıkarılır** (geriye dönük uyumluluk: eski
    #: istemciler ve mevcut testler sözlüğü birebir karşılaştırır).
    skipped_reason: (
        Literal["no-pending-rows", "missing-row-identity"] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    #: ``skipped_reason`` için kullanıcıya gösterilecek açıklama.
    skipped_message: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class AnalyzeRow(ApiModel):
    """Analiz edilen tek BOQ satırı.

    ``source_row`` Excel satırıdır; ``boq_no`` izlenebilirlik anahtarıdır.
    İkisi de kaybolmaz — kullanıcı "7. satır" veya "BOQ-003" diyebilmelidir.
    """

    source_row: int
    boq_no: str | None
    description: str | None
    quantity: OptionalDecimalStr
    unit: str | None
    waste_percent: OptionalDecimalStr = Field(
        default=None, description="Fire yüzdesi; tanımsızsa null (sıfır değil)"
    )

    status: Literal["rule", "pending", "excluded", "invalid"]
    match: MatchOut

    ai: AiOut | None = Field(
        default=None,
        description="Yalnızca pending satırlarda AI değerlendirmesi; karar değildir",
    )

    issues: list[FieldIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AnalyzeSummary(ApiModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    blank_rows_skipped: int
    rule: int
    pending: int
    excluded: int
    invalid: int


class AnalyzeResponse(ApiModel):
    rows: list[AnalyzeRow]
    summary: AnalyzeSummary
    ai: AiSummaryOut = Field(
        default_factory=lambda: AiSummaryOut(
            enabled=False,
            provider="none",
            evaluated_rows=0,
            suggested=0,
            ambiguous=0,
            no_match=0,
            errors=0,
        )
    )
    warnings: list[str] = Field(default_factory=list)
    ignored_columns: list[str] = Field(default_factory=list)
    sheet_name: str


# ---------------------------------------------------------------------------
# Calculate — istek
# ---------------------------------------------------------------------------


class ClientRow(ApiModel):
    """İstemcinin geri gönderdiği ham BOQ satırı.

    Güvenlik: istemci **yalnızca** bu alanları gönderebilir. ``match_status``,
    ``matched_code``, hesaplanmış miktar/ağırlık gibi alanlar şemada yoktur;
    ``extra="forbid"`` sayesinde gönderilirse 422 ile reddedilir.
    """

    source_row: int = Field(ge=2, description="Excel'deki 1 tabanlı satır numarası")
    boq_no: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    quantity: DecimalStr = Field(gt=0)
    unit: str = Field(min_length=1, max_length=16)
    waste_percent: OptionalDecimalStr = Field(
        default=None,
        ge=0,
        le=100,
        description="Fire yüzdesi; tanımsızsa null (sıfır değil)",
    )

    @field_validator("boq_no", "description", "unit")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Boş olamaz.")
        return value

    @field_validator("quantity", mode="before")
    @classmethod
    def _reject_float(cls, value: object) -> object:
        """JSON ondalık sayı (``float``) kabul edilmez.

        Tarayıcıda ``0.1`` ikili kesir olarak saklanır; ``str`` veya tam sayı
        gönderilmelidir. Aksi hâlde miktar sessizce değişebilir.
        """
        if isinstance(value, float):
            raise ValueError(
                "Ondalık değerler JSON'da string olarak gönderilmelidir "
                '(ör. "12.5"). Kayan nokta değeri kabul edilmez.'
            )
        return value

    @field_validator("quantity")
    @classmethod
    def _finite_quantity(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Sonlu bir sayı olmalı.")
        return value

    @field_validator("waste_percent", mode="before")
    @classmethod
    def _reject_float_waste(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError(
                "Fire oranı JSON'da string olarak gönderilmelidir "
                '(ör. "5"). Kayan nokta değeri kabul edilmez.'
            )
        return value

    @field_validator("waste_percent")
    @classmethod
    def _finite_waste(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Sonlu bir sayı olmalı.")
        return value


class ClientDecision(ApiModel):
    """Kullanıcı kararı: onay (kod ile) veya red.

    ``status`` alanı **yoktur**: onay/red kararı ``action`` ile verilir ve
    sunucu bunu katalogla yeniden doğrular.
    """

    boq_no: str = Field(min_length=1, max_length=120)
    action: Literal["approve", "reject"]
    code: str | None = Field(default=None, max_length=64)
    reason: str = Field(default="", max_length=500)

    @field_validator("boq_no")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Boş olamaz.")
        return value

    @field_validator("code")
    @classmethod
    def _normalise_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CalculateRequest(ApiModel):
    """İkinci aşama isteği: ham satırlar + kullanıcı kararları.

    Sunucu analiz sonucunu saklamaz; bu yüzden satırlar yeniden gönderilir.
    Kararlar BOQ No ile eşlenir; başka satıra ait karar reddedilir.
    """

    rows: list[ClientRow] = Field(min_length=1, max_length=5000)
    decisions: list[ClientDecision] = Field(default_factory=list, max_length=5000)

    @field_validator("rows")
    @classmethod
    def _unique_source_rows(cls, value: list[ClientRow]) -> list[ClientRow]:
        seen: set[int] = set()
        for row in value:
            if row.source_row in seen:
                raise ValueError(
                    f"source_row {row.source_row} birden fazla satırda kullanılmış."
                )
            seen.add(row.source_row)
        return value

    @field_validator("rows")
    @classmethod
    def _unique_boq_numbers(cls, value: list[ClientRow]) -> list[ClientRow]:
        seen: set[str] = set()
        for row in value:
            if row.boq_no in seen:
                raise ValueError(
                    f"BOQ No {row.boq_no!r} birden fazla satırda kullanılmış. "
                    "İzlenebilirlik için tekil olmalıdır."
                )
            seen.add(row.boq_no)
        return value


# ---------------------------------------------------------------------------
# Calculate — yanıt
# ---------------------------------------------------------------------------


class SourceRowOut(ApiModel):
    """Satın alma grubunun içindeki kaynak BOQ satırı izi."""

    source_row: int | None = Field(
        default=None, description="Excel'deki 1 tabanlı satır numarası"
    )
    boq_no: str
    description: str
    source_quantity: DecimalStr
    source_unit: str | None
    net_metres: OptionalDecimalStr = None
    waste_percent: OptionalDecimalStr = None
    gross_metres: OptionalDecimalStr = None
    gross_quantity: OptionalDecimalStr = None
    fire_quantity: OptionalDecimalStr = None
    waste_source: Literal["row", "catalog", "none"]
    conversion_steps: list[str] = Field(default_factory=list)


class MissingFieldOut(ApiModel):
    field: Literal["fire", "conversion", "commercial-length", "mass"]
    message: str
    boq_no: str | None = None
    source_row: int | None = None


class GroupOut(ApiModel):
    """Tek katalog kodunun satın alma hesabı — FULL veya PARTIAL."""

    code: str
    family: str
    family_label: str
    size: str
    grade: str
    coating: str
    product_label: str

    status: Literal["FULL", "PARTIAL"]
    missing_fields: list[str] = Field(default_factory=list)
    missing: list[MissingFieldOut] = Field(default_factory=list)

    mass_kg_per_m: OptionalDecimalStr = None
    commercial_length_m: OptionalDecimalStr = None
    bar_count: OptionalDecimalStr = None
    total_gross_metres: OptionalDecimalStr = None
    order_length_m: OptionalDecimalStr = None
    rounding_surplus_m: OptionalDecimalStr = None
    weight_kg: OptionalDecimalStr = None

    weight_label: str
    weight_note: str

    merged: bool
    source_boq_nos: list[str] = Field(default_factory=list)
    source_rows: list[int] = Field(
        default_factory=list,
        description="Kaynak BOQ satırlarının Excel satır numaraları (paralel liste)",
    )
    sources: list[SourceRowOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SkippedRowOut(ApiModel):
    """Hesaba girmeyen satır ve nedeni — izlenebilirlik için korunur."""

    source_row: int | None = Field(
        default=None, description="Excel'deki 1 tabanlı satır numarası"
    )
    boq_no: str
    status: Literal["pending", "rejected", "excluded", "invalid", "unknown-code"]
    match_status: Literal[
        "rule", "ai-approved", "pending", "rejected", "excluded", "invalid"
    ] | None = None
    matched_code: str | None = None
    message: str
    #: ``status == "excluded"`` iken **hangi** kuralın devreye girdiği.
    #: Geriye dönük uyumlu: alan yalnızca anlamlıyken yanıtta bulunur.
    exclusion_reason: (
        Literal["waste", "unit", "catalog", "missing-mass"] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    #: Dışlama nedeninin kısa etiketi (ör. "Fire tanımsız").
    exclusion_reason_label: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class CalculationSummaryOut(ApiModel):
    input_rows: int
    calculated_rows: int
    skipped_rows: int
    groups: int
    merged_groups: int
    merges: int
    full_groups: int
    partial_groups: int
    total_order_length_m: OptionalDecimalStr = None
    known_weight_kg: OptionalDecimalStr = None
    weight_complete: bool


class CalculateResponse(ApiModel):
    groups: list[GroupOut]
    skipped: list[SkippedRowOut]
    summary: CalculationSummaryOut
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Hata
# ---------------------------------------------------------------------------


class ErrorIssue(ApiModel):
    """Hata zarfındaki tek bir alan/satır sorunu.

    Tüm alanlar her zaman bulunur (``null`` olabilir); frontend tek tip
    işleyebilsin diye şart.
    """

    source_row: int | None = None
    boq_no: str | None = None
    column: str | None = None
    code: str | None = None
    message: str
    suggestion: str = ""


class ErrorBody(ApiModel):
    code: str
    message: str
    detail: str = ""
    suggestion: str = ""
    issues: list[ErrorIssue] = Field(default_factory=list)


class ErrorResponse(ApiModel):
    error: ErrorBody
