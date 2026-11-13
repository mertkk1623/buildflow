"""Rapor veri modeli — hesaplama çıktısının **salt okunur** görünümü.

Temel kural
-----------
Bu modül hesap **yapmaz**. Tek veri kaynağı
:class:`app.domain.calculation.CalculationResult` nesnesidir ve buradaki
dönüşüm yalnızca:

* var olan alanları seçer,
* bir grubun kaynak satırlarındaki **zaten hesaplanmış** metre değerlerini
  toplar (grup düzeyinde net/fire sütunları için),
* ``None`` değerleri ``None`` olarak korur.

Fire oranı, ticari boy, yuvarlama, ağırlık veya birim dönüşümü burada
**yeniden hesaplanmaz**; hepsi domain'den geldiği gibi taşınır.

Bilinmeyen değer kuralı
-----------------------
Bir grup içindeki satırlardan biri bile eksikse, toplam **bilinmeyen** kalır
(``None``). Eksik veri asla sıfıra çevrilmez; bu, PARTIAL sonuçların dürüst
gösterilmesinin tek yoludur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.calculation import (
    CalculationResult,
    GroupCalculation,
    SkipReason,
)

#: Rapor metinlerinde kullanılan sabit açıklamalar. Testler bunlara bağlıdır.
WEIGHT_DISCLAIMER = (
    "Ağırlık, katalogdaki teorik çıplak çelik kg/m değerine dayalıdır; "
    "kantar veya sevkiyat ağırlığı değildir."
)
CUTTING_DISCLAIMER = (
    "BuildFlow bu aşamada kesim optimizasyonu veya nesting yapmaz; "
    "sipariş miktarları ticari boya yuvarlanmış teorik ihtiyaçtır."
)
PARTIAL_DISCLAIMER = (
    "PARTIAL gruplarda eksik alanlar boş bırakılmıştır; bilinmeyen değerler "
    "sıfır olarak varsayılmamıştır."
)

#: Raporda gösterilen tüm açıklamalar (sıra korunur).
REPORT_DISCLAIMERS: tuple[str, ...] = (
    WEIGHT_DISCLAIMER,
    CUTTING_DISCLAIMER,
    PARTIAL_DISCLAIMER,
)

#: Atlanan satır nedenlerinin okunabilir etiketleri.
SKIP_REASON_LABELS: dict[SkipReason, str] = {
    SkipReason.PENDING: "Onay bekliyor",
    SkipReason.REJECTED: "Reddedildi",
    SkipReason.EXCLUDED: "Kapsam dışı",
    SkipReason.INVALID: "Geçersiz veri",
    SkipReason.UNKNOWN_CODE: "Katalogda yok",
}


def _sum_or_none(values: tuple[Decimal | None, ...]) -> Decimal | None:
    """Zaten hesaplanmış değerleri toplar; biri bile eksikse ``None``.

    Bu bir hesap kuralı değil, **eksik veriyi koruma** kuralıdır: domain de
    aynı yaklaşımı kullanır (bkz. ``GroupCalculation.total_gross_metres``).
    """
    if not values:
        return None
    total = Decimal(0)
    for value in values:
        if value is None:
            return None
        total += value
    return total


@dataclass(frozen=True, slots=True)
class ReportSourceRow:
    """Rapordaki tek kaynak BOQ satırı izi (izlenebilirlik)."""

    boq_no: str
    description: str
    source_quantity: Decimal
    source_unit: str
    net_metres: Decimal | None
    waste_percent: Decimal | None
    gross_metres: Decimal | None


@dataclass(frozen=True, slots=True)
class ReportGroup:
    """Satın alma tablosunun tek satırı — tüm değerler domain'den."""

    code: str
    product_label: str
    family_label: str
    size: str
    grade: str
    coating: str

    #: Kaynak BOQ satır numaraları (kullanıcıya gösterilen sıra korunur).
    source_boq_nos: tuple[str, ...]
    source_rows: tuple[ReportSourceRow, ...]
    merged: bool

    #: Metre ekseninde toplamlar. Eksik bileşen varsa ``None``.
    net_metres: Decimal | None
    fire_metres: Decimal | None
    gross_metres: Decimal | None

    #: Domain'in ürettiği, **değiştirilmeden** taşınan değerler.
    mass_kg_per_m: Decimal | None
    commercial_length_m: Decimal | None
    bar_count: Decimal | None
    order_length_m: Decimal | None
    rounding_surplus_m: Decimal | None
    weight_kg: Decimal | None

    status: str
    missing_messages: tuple[str, ...]
    notes: tuple[str, ...]

    @property
    def is_full(self) -> bool:
        return self.status == "FULL"

    @property
    def status_label(self) -> str:
        return "FULL" if self.is_full else "PARTIAL"

    @property
    def boq_trace(self) -> str:
        """Excel/PDF'te tek hücrede gösterilen kaynak satır listesi."""
        return ", ".join(self.source_boq_nos)


@dataclass(frozen=True, slots=True)
class ReportSkippedRow:
    """Hesaba girmeyen satır — raporda ayrı bölümde gösterilir."""

    boq_no: str
    description: str
    reason: str
    reason_label: str
    message: str


@dataclass(frozen=True, slots=True)
class ReportSummary:
    """Rapor özeti. Tüm sayılar domain'den gelir."""

    input_rows: int
    calculated_rows: int
    skipped_rows: int
    group_count: int
    merged_group_count: int
    merge_count: int
    full_groups: int
    partial_groups: int
    total_order_length_m: Decimal | None
    known_weight_kg: Decimal
    weight_complete: bool
    #: Ağırlığı **bilinen** grup sayısı. ``0`` ise toplam bilinmiyor demektir;
    #: bu durumda ``known_weight_kg`` sıfır olarak gösterilmez.
    weighed_group_count: int = 0

    @property
    def has_known_weight(self) -> bool:
        """En az bir grubun ağırlığı hesaplanmış mı?"""
        return self.weighed_group_count > 0


@dataclass(frozen=True, slots=True)
class Report:
    """Raporun tamamı — Excel ve PDF aynı nesneyi kullanır."""

    generated_at: datetime
    summary: ReportSummary
    groups: tuple[ReportGroup, ...]
    skipped: tuple[ReportSkippedRow, ...]
    warnings: tuple[str, ...]
    disclaimers: tuple[str, ...] = REPORT_DISCLAIMERS

    @property
    def has_partial(self) -> bool:
        return any(not group.is_full for group in self.groups)

    @property
    def group_count(self) -> int:
        return len(self.groups)


def build_report(
    result: CalculationResult,
    *,
    generated_at: datetime,
    warnings: tuple[str, ...] | list[str] = (),
    descriptions: dict[str, str] | None = None,
) -> Report:
    """``CalculationResult``'ı rapora çevirir.

    Parameters
    ----------
    result:
        Hesap motorunun çıktısı. **Değiştirilmez.**
    generated_at:
        Rapor üretim zamanı (test edilebilirlik için dışarıdan verilir).
    warnings:
        ``/api/calculate`` yanıtındaki uyarılar; raporda aynen gösterilir.
    descriptions:
        BOQ No → açıklama eşlemesi. Atlanan satırların açıklaması domain
        sonucunda taşınmadığı için dışarıdan verilir. Yoksa boş kalır.
    """
    description_map = descriptions or {}

    groups = tuple(_build_group(group) for group in result.groups)

    #: ``total_order_length_m`` domain'de tekil bir alan değil; grup
    #: toplamlarının sunumudur. Eksik grup varsa toplam bilinmiyor sayılır.
    order_values = tuple(group.order_length_m for group in result.groups)
    total_order_length = _sum_or_none(order_values) if result.groups else None

    summary = ReportSummary(
        input_rows=result.input_row_count,
        calculated_rows=result.calculated_row_count,
        skipped_rows=result.skipped_count,
        group_count=result.group_count,
        merged_group_count=result.merged_group_count,
        merge_count=result.merge_count,
        full_groups=len(result.full_groups),
        partial_groups=len(result.partial_groups),
        total_order_length_m=total_order_length,
        known_weight_kg=result.known_weight_kg,
        weight_complete=result.weight_complete,
        weighed_group_count=sum(
            1 for group in result.groups if group.weight_kg is not None
        ),
    )

    skipped = tuple(
        ReportSkippedRow(
            boq_no=row.row_no,
            description=description_map.get(row.row_no, ""),
            reason=row.reason.value,
            reason_label=SKIP_REASON_LABELS.get(row.reason, row.reason.value),
            message=row.message,
        )
        for row in result.skipped
    )

    return Report(
        generated_at=generated_at,
        summary=summary,
        groups=groups,
        skipped=skipped,
        warnings=tuple(warnings),
    )


def _build_group(group: GroupCalculation) -> ReportGroup:
    """Tek grubu rapor satırına çevirir. Hesap yapmaz, yalnızca toplar."""
    sources = tuple(
        ReportSourceRow(
            boq_no=source.row_no,
            description=source.description,
            source_quantity=source.source_quantity,
            source_unit=(
                source.source_unit.value
                if source.source_unit is not None
                else ""
            ),
            net_metres=source.net_metres,
            waste_percent=source.waste_percent,
            gross_metres=source.gross_metres,
        )
        for source in group.sources
    )

    net = _sum_or_none(tuple(source.net_metres for source in group.sources))
    gross = _sum_or_none(tuple(source.gross_metres for source in group.sources))
    fire = None if net is None or gross is None else gross - net

    return ReportGroup(
        code=group.code,
        product_label=group.product_label,
        family_label=group.family_label,
        size=group.size,
        grade=group.grade.value,
        coating=group.coating.value,
        source_boq_nos=group.source_row_numbers,
        source_rows=sources,
        merged=group.merged,
        net_metres=net,
        fire_metres=fire,
        gross_metres=gross,
        mass_kg_per_m=group.mass_kg_per_m,
        commercial_length_m=group.commercial_length_m,
        bar_count=group.bar_count,
        order_length_m=group.order_length_m,
        rounding_surplus_m=group.rounding_surplus_m,
        weight_kg=group.weight_kg,
        status=group.status.value,
        missing_messages=tuple(item.message for item in group.missing),
        notes=tuple(group.notes),
    )
