"""Domain modelleri — Aşama 4.1.

Bu modül HTTP'den ve FastAPI'den **tamamen bağımsızdır**. Hesap motoru ve
eşleştirme mantığı tarayıcı açmadan test edilebilmelidir (ROADMAP §9).

Sayısal kesinlik kuralı: kütle, uzunluk ve oranlar ``Decimal`` ile taşınır.
``float`` kullanılmaz; kayan nokta yuvarlaması sipariş miktarını değiştirir.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.sizes import (
    canonical_box_size,
    canonical_flat_size,
    canonical_profile_size,
    size_issues,
    split_size,
)

#: Katalog dosyasının şema sürümü. Alan kaldırmak sürüm kırar.
CATALOG_SCHEMA_VERSION = "1.0"


class MaterialFamily(str, Enum):
    """Desteklenen malzeme aileleri (ROADMAP §7)."""

    BOX = "BOX"
    IPE = "IPE"
    HEA = "HEA"
    UPN = "UPN"
    FLAT = "FLAT"


class Grade(str, Enum):
    """Katalogda tanımlı çelik kaliteleri.

    Bu liste **kapalıdır**. ``ST37``, ``S275``, ``S235JR`` gibi ifadeler
    burada yoktur ve otomatik olarak bir kaliteye çevrilmez.
    """

    S235 = "S235"
    S355 = "S355"


class Coating(str, Enum):
    BLACK = "siyah"
    GALVANIZED = "galvaniz"


class Manufacturing(str, Enum):
    """Üretim yolu.

    ``EN 10219`` (soğuk şekillendirilmiş) ile ``EN 10210`` (sıcak işlem
    görmüş) ürünler farklı kütlelere sahiptir ve **karıştırılmamalıdır**.
    """

    COLD_FORMED = "cold-formed"
    HOT_FINISHED = "hot-finished"
    HOT_ROLLED = "hot-rolled"


class Unit(str, Enum):
    """Hesaba giren birimler. ``adet`` bilinçli olarak yoktur."""

    M = "m"
    KG = "kg"
    T = "t"


class MatchStatus(str, Enum):
    """Satırın iş akışındaki durumu.

    Durumlar birbirine karıştırılmamalıdır:

    * ``rule`` / ``ai-approved`` → hesaba girer.
    * ``pending`` → kullanıcı eşleştirme kararı bekliyor.
    * ``rejected`` → kullanıcı eşleştirmeyi reddetti.
    * ``excluded`` → veri **geçerli** ama hesap kapsamı dışında
      (desteklenmeyen birim, eksik fire, katalog dışı malzeme).
    * ``invalid`` → veri **hatalı veya okunamadı** (boş/negatif miktar,
      sayısal olmayan değer, önbelleksiz formül, yinelenen BOQ No).
    """

    RULE = "rule"
    AI_APPROVED = "ai-approved"
    PENDING = "pending"
    REJECTED = "rejected"
    EXCLUDED = "excluded"
    INVALID = "invalid"


class ExclusionReason(str, Enum):
    """``excluded`` durumunun nedeni: veri geçerli, hesap kapsamı dışında."""

    WASTE = "waste"
    UNIT = "unit"
    CATALOG = "catalog"
    MISSING_MASS = "missing-mass"


class InvalidReason(str, Enum):
    """``invalid`` durumunun nedeni: veri hatalı veya okunamadı.

    ``excluded`` ile karıştırılmamalıdır: burada satırın kendisi kullanılabilir
    değildir (boş, sayısal olmayan, negatif, yinelenen veya önbelleksiz formül).
    """

    MISSING_BOQ_NO = "missing-boq-no"
    MISSING_DESCRIPTION = "missing-description"
    MISSING_QUANTITY = "missing-quantity"
    INVALID_QUANTITY = "invalid-quantity"
    AMBIGUOUS_NUMBER = "ambiguous-number"
    NON_POSITIVE_QUANTITY = "non-positive-quantity"
    MISSING_UNIT = "missing-unit"
    INVALID_WASTE = "invalid-waste"
    NEGATIVE_WASTE = "negative-waste"
    WASTE_OVER_100 = "waste-over-100"
    DUPLICATE_BOQ_NO = "duplicate-boq-no"
    FORMULA_WITHOUT_CACHE = "formula-without-cache"
    UNREADABLE_VALUE = "unreadable-value"


class MassSource(BaseModel):
    """Birim kütlenin nereden geldiği. Kaynaksız değer kataloğa giremez."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    standard: str = Field(min_length=1, max_length=80)
    reference: str = Field(min_length=1, max_length=160)
    method: Literal["table", "formula"]
    note: str | None = Field(default=None, max_length=400)


class LengthSource(BaseModel):
    """Ticari boyun dayanağı.

    Bu bir *stok garantisi* değildir: V1 varsayılanıdır ve tedarikçi bazında
    geçersiz kılınabilir.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    basis: str = Field(min_length=1, max_length=120)
    reference: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=400)


class CatalogItem(BaseModel):
    """Tek bir katalog kalemi: Grup + Ölçü + Kalite + Kaplama."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(pattern=r"^[A-Z0-9x]+(?:-[A-Z0-9x]+)*$", max_length=64)
    family: MaterialFamily
    family_label: str = Field(min_length=1, max_length=40)
    size: str = Field(min_length=1, max_length=40)
    grade: Grade
    coating: Coating

    # --- Kütle (çıplak çelik) ---
    mass_kg_per_m: Decimal = Field(gt=0, max_digits=12, decimal_places=6)
    mass_source: MassSource

    # --- Ticari boy (V1 varsayılanı) ---
    commercial_length_m: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    length_source: LengthSource

    # --- Üretim standardı ayrı tutulur ---
    production_standard: str = Field(min_length=1, max_length=40)
    manufacturing: Manufacturing

    #: V1'de tüm kalemlerde ``None``. Dolu olsaydı fire tanımsız satırlar
    #: hesaba girerdi ve kilitli 18 satırlık demo dağılımı bozulurdu.
    default_waste: Decimal | None = Field(default=None, ge=0, lt=1)

    @model_validator(mode="after")
    def _check_size_and_standard(self) -> "CatalogItem":
        issues = size_issues(self.family.value, self.size)
        if issues:
            raise ValueError("; ".join(issues))

        # Ölçü kanonik biçimde saklanmalı; aksi hâlde eşleştirme sessizce
        # başarısız olur (ör. "100x100x4" ile "100×100×4" farklı anahtar olur).
        if self.family is MaterialFamily.BOX:
            parts = split_size(self.size)
            canonical = canonical_box_size(parts[0], parts[1], parts[2])
        elif self.family is MaterialFamily.FLAT:
            parts = split_size(self.size)
            canonical = canonical_flat_size(parts[0], parts[1])
        else:
            canonical = canonical_profile_size(self.size)

        if canonical != self.size:
            raise ValueError(
                f"{self.code}: ölçü kanonik değil — beklenen {canonical!r}, "
                f"bulunan {self.size!r}"
            )

        standard = self.production_standard.upper().replace(" ", "")
        if standard.startswith("EN10219") and self.manufacturing is not Manufacturing.COLD_FORMED:
            raise ValueError(
                f"{self.code}: EN 10219 soğuk şekillendirilmiş üründür, "
                f"üretim yolu {self.manufacturing.value} olamaz."
            )
        if standard.startswith("EN10210") and self.manufacturing is not Manufacturing.HOT_FINISHED:
            raise ValueError(
                f"{self.code}: EN 10210 sıcak işlem görmüş üründür, "
                f"üretim yolu {self.manufacturing.value} olamaz."
            )
        return self

    @property
    def identity(self) -> tuple[str, str, str, str]:
        """Dört malzeme özelliği — eşleştirmenin tek anahtarı."""
        return (self.family.value, self.size, self.grade.value, self.coating.value)

    @property
    def describe(self) -> str:
        return f"{self.family_label} {self.size} · {self.grade.value} · {self.coating.value}"


class MaterialAttributes(BaseModel):
    """Açıklamadan çıkarılan dört özellik. Her biri eksik olabilir."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family: MaterialFamily | None = None
    size: str | None = None
    grade: Grade | None = None
    coating: Coating | None = None

    #: Kullanıcıya gösterilecek Türkçe özellik adları.
    FEATURE_LABELS: ClassVar[dict[str, str]] = {
        "family": "grup",
        "size": "ölçü",
        "grade": "kalite",
        "coating": "kaplama",
    }

    @property
    def missing_features(self) -> tuple[str, ...]:
        names = ("family", "size", "grade", "coating")
        return tuple(name for name in names if getattr(self, name) is None)

    @property
    def missing_feature_labels(self) -> tuple[str, ...]:
        return tuple(self.FEATURE_LABELS[name] for name in self.missing_features)

    @property
    def is_complete(self) -> bool:
        """Dört özelliğin tamamı biliniyor mu?

        Otomatik ``rule`` durumu **yalnızca** bu koşulda verilebilir.
        """
        return not self.missing_features

    def matches(self, item: CatalogItem) -> bool:
        """Bilinen özellikler kalemle uyuşuyor mu? (eksik özellik filtrelemez)"""
        if self.family is not None and self.family is not item.family:
            return False
        if self.size is not None and self.size != item.size:
            return False
        if self.grade is not None and self.grade is not item.grade:
            return False
        if self.coating is not None and self.coating is not item.coating:
            return False
        return True


class MatchOutcome(BaseModel):
    """Deterministik eşleştirmenin tek satırlık sonucu — izlenebilir."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MatchStatus
    attributes: MaterialAttributes
    matched_code: str | None = None
    candidate_codes: tuple[str, ...] = ()
    exclusion_reason: ExclusionReason | None = None
    message: str = ""
