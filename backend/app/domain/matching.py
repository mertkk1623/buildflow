"""Deterministik malzeme eşleştirme.

Kural (Aşama 3'te kilitlenen ve değişmeyen):
otomatik ``rule`` durumu **yalnızca dört özelliğin tamamı** bilindiğinde ve
katalogda **tek** kalem eşleştiğinde verilir.

Aksi hâlde satır ``pending`` olur ve kullanıcı onayı gerekir. AI bu aşamada
devrede değildir; ``pending`` satırlar aday listesiyle birlikte döner.

Öncelik sırası (belgelenmiş ve test edilmiş):
1. Birim desteklenmiyor → ``excluded: unit``
2. Aile/ölçü/kalite/kaplama katalogla eşleşmiyor → ``excluded: catalog``
3. Eşleşti ama fire tanımsız → ``excluded: waste``
4. Eksik özellik var → ``pending``
5. Dört özellik tam + tek eşleşme → ``rule``

Bu sıra, 18 satırlık demo fixture'ının dağılımıyla birebir uyumludur.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.catalog import Catalog
from app.domain.models import (
    CatalogItem,
    ExclusionReason,
    MatchOutcome,
    MatchStatus,
    MaterialAttributes,
    Unit,
)
from app.domain.normalize import normalize_description


def parse_unit(value: str) -> Unit | None:
    """Birim metnini ayrıştırır. Desteklenmeyen birimde ``None`` döner."""
    cleaned = value.strip().lower()
    try:
        return Unit(cleaned)
    except ValueError:
        return None


def _candidates(attributes: MaterialAttributes, catalog: Catalog) -> tuple[CatalogItem, ...]:
    """Bilinen özelliklerle uyuşan kalemler.

    Eksik özellik filtre uygulamaz; bilinen özellik **tam eşleşme** olmalıdır.
    Ölçüde hiçbir tolerans yoktur: ``100×100×4`` ile ``100×100×5`` eşleşmez.
    """
    return tuple(item for item in catalog if attributes.matches(item))


def match_description(description: str, catalog: Catalog) -> MatchOutcome:
    """Yalnızca açıklamaya bakarak eşleştirir (birim/fire değerlendirmez)."""
    result = normalize_description(description)
    attributes = result.attributes
    candidates = _candidates(attributes, catalog)

    if attributes.is_complete:
        if len(candidates) == 1:
            return MatchOutcome(
                status=MatchStatus.RULE,
                attributes=attributes,
                matched_code=candidates[0].code,
                candidate_codes=(candidates[0].code,),
                message="Dört özellik eksiksiz ve katalogda tek kalem eşleşti.",
            )
        # Kimlik dört özelliği kapsadığı için >1 sonuç katalog hatasıdır;
        # yükleyici bunu zaten engeller.
        return MatchOutcome(
            status=MatchStatus.EXCLUDED,
            attributes=attributes,
            exclusion_reason=ExclusionReason.CATALOG,
            message=(
                "Dört özellik eksiksiz ancak katalogda eşleşen kalem yok. "
                "Benzer ölçü/kaliteye düşürme yapılmaz."
            ),
        )

    missing = ", ".join(attributes.missing_feature_labels)
    if not _candidates_have_family(attributes):
        return MatchOutcome(
            status=MatchStatus.EXCLUDED,
            attributes=attributes,
            exclusion_reason=ExclusionReason.CATALOG,
            message=(
                "Açıklama katalogdaki malzeme ailelerinden hiçbiriyle "
                f"eşleşmiyor. Eksik özellikler: {missing}"
            ),
        )

    if not candidates:
        return MatchOutcome(
            status=MatchStatus.EXCLUDED,
            attributes=attributes,
            exclusion_reason=ExclusionReason.CATALOG,
            message=(
                "Bilinen özelliklerle eşleşen katalog kalemi yok. "
                f"Eksik özellikler: {missing}"
            ),
        )

    note = (
        f"Eksik özellik(ler): {missing}. Otomatik eşleştirme yapılmaz; "
        "kullanıcı onayı gerekir."
    )
    if result.warnings:
        note = f"{note} {' '.join(result.warnings)}"

    return MatchOutcome(
        status=MatchStatus.PENDING,
        attributes=attributes,
        candidate_codes=tuple(item.code for item in candidates),
        message=note,
    )


def _candidates_have_family(attributes: MaterialAttributes) -> bool:
    """Aile belirlenebildiyse aday aramaya değer mi?"""
    return attributes.family is not None


def match_row(
    description: str,
    unit: str,
    waste_rate: Decimal | None,
    catalog: Catalog,
) -> MatchOutcome:
    """Bir BOQ satırını belgelenmiş öncelik sırasıyla değerlendirir.

    Not: Bu fonksiyon **miktar dönüşümü yapmaz**; yalnızca satırın durumunu
    belirler. Dönüşüm ve fire uygulaması Aşama 4.2'nin işidir.
    """
    parsed_unit = parse_unit(unit)

    # 1) Birim kapsam dışı
    if parsed_unit is None:
        return MatchOutcome(
            status=MatchStatus.EXCLUDED,
            attributes=normalize_description(description).attributes,
            exclusion_reason=ExclusionReason.UNIT,
            message=(
                f"Birim {unit.strip()!r} desteklenmiyor. "
                "Desteklenen birimler: m, kg, t."
            ),
        )

    outcome = match_description(description, catalog)

    # 2) Katalogla eşleşmedi
    if outcome.status is MatchStatus.EXCLUDED:
        return outcome

    # 3) Eşleşti ama fire tanımsız → hesaba giremez
    if waste_rate is None:
        detail = (
            f" Eşleşen kalem {outcome.matched_code} olsa da fire tanımsız olduğu "
            "için hesaba girmez."
            if outcome.matched_code
            else ""
        )
        return MatchOutcome(
            status=MatchStatus.EXCLUDED,
            attributes=outcome.attributes,
            # Hariç satır "eşleşmiş" sayılmaz: nihai kod taşımaz, aday olarak izlenir.
            matched_code=None,
            candidate_codes=outcome.candidate_codes,
            exclusion_reason=ExclusionReason.WASTE,
            message=(
                "Satırda fire oranı yok ve katalogda varsayılan fire tanımlı değil. "
                "Eksik fire sıfır kabul edilmez." + detail
            ),
        )

    return outcome
