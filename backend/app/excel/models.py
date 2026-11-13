"""Excel metraj okumasının sonuç modelleri — Aşama 4.3.

Bu modeller **dosya okuma** katmanına aittir; hesap yapmaz, ürün eşleştirmez.
Amaç, her satırın kaynak Excel satır numarasını ve varsa hata nedenlerini
kaybetmeden taşımaktır.

Durum ayrımı
------------
Okuma katmanı yalnızca iki şeyi bilir:

* satır **veri olarak** kullanılabilir mi (``MetrajRow.is_valid``),
* değilse neden kullanılamaz (:class:`InvalidReason`).

Eşleştirme durumu (``rule`` / ``pending`` / ``excluded`` / ``rejected``)
**bu katmanda verilmez**; o karar normalize + matching akışının işidir. Tek
istisna, verisi hatalı satırların doğrudan ``invalid`` olarak işaretlenmesidir:
bu satır için eşleştirme hiç yapılamaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from app.domain.models import ExclusionReason, InvalidReason, MatchStatus, Unit


class MetrajColumn(str, Enum):
    """Şablonun ve okuyucunun üzerinde anlaştığı kolon adları.

    Değerler **birebir** başlık metnidir; şablon yazıcısı da bunları yazar.
    """

    BOQ_NO = "BOQ No"
    DESCRIPTION = "Açıklama"
    QUANTITY = "Miktar"
    UNIT = "Birim"
    WASTE = "Fire (%)"


#: Dosya okunabilmesi için bulunması zorunlu kolonlar.
REQUIRED_COLUMNS: tuple[MetrajColumn, ...] = (
    MetrajColumn.BOQ_NO,
    MetrajColumn.DESCRIPTION,
    MetrajColumn.QUANTITY,
    MetrajColumn.UNIT,
)

#: İsteğe bağlı kolonlar. Yoksa fire "tanımsız" kalır (sıfır sayılmaz).
OPTIONAL_COLUMNS: tuple[MetrajColumn, ...] = (MetrajColumn.WASTE,)

#: Beklenen çalışma sayfası.
TEMPLATE_SHEET_NAME = "Metraj"

#: Kullanım açıklamasının bulunduğu yardımcı sayfa.
GUIDE_SHEET_NAME = "Kullanım"


@dataclass(frozen=True, slots=True)
class CellIssue:
    """Tek bir hücre/satır hatası — kullanıcıya düzeltme önerisiyle sunulur."""

    column: MetrajColumn | None
    reason: InvalidReason
    message: str
    suggestion: str

    @property
    def column_label(self) -> str:
        return self.column.value if self.column is not None else "(satır)"


@dataclass(frozen=True, slots=True)
class ScopeIssue:
    """Veri **okunabildi** ama hesap kapsamı dışında.

    ``invalid`` ile karıştırılmamalıdır: satır bozuk değildir, yalnızca bu
    sürümün kapsamı dışındadır. Örnek: ``adet`` birimi. Satır geçerli kalır;
    eşleştirme katmanı ``excluded: unit`` üretir (Aşama 4.1 sözleşmesi).
    """

    column: MetrajColumn
    reason: ExclusionReason
    message: str
    suggestion: str

    @property
    def column_label(self) -> str:
        return self.column.value


@dataclass(frozen=True, slots=True)
class MetrajRow:
    """Excel'den okunan tek metraj satırı.

    ``source_row`` **1 tabanlı** gerçek Excel satır numarasıdır; boş satırlar
    atlansa bile korunur. Kullanıcı "5. satırda hata var" diyebilsin diye
    yeniden numaralandırma yapılmaz.
    """

    source_row: int
    boq_no: str | None
    description: str | None
    quantity: Decimal | None
    unit: str | None
    unit_value: Unit | None
    waste_percent: Decimal | None
    issues: tuple[CellIssue, ...] = ()
    scope_issues: tuple[ScopeIssue, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Satır veri olarak kullanılabilir mi? (eşleştirme kararı değil)

        Kapsam dışı satır (**``scope_issues``**) hâlâ geçerlidir: verisi
        okunmuştur, yalnızca hesap kapsamı dışındadır.
        """
        return not self.issues

    @property
    def status(self) -> MatchStatus | None:
        """Hatalı satır ``invalid``; geçerli satır için durum **atamadır**.

        Geçerli satırda ``None`` döner: eşleştirme yapılmadan ``rule``/
        ``pending`` denemez, okuyucu kullanıcı onayı vermiş gibi davranamaz.
        """
        return None if self.is_valid else MatchStatus.INVALID

    @property
    def invalid_reasons(self) -> tuple[InvalidReason, ...]:
        return tuple(issue.reason for issue in self.issues)

    @property
    def exclusion_reasons(self) -> tuple[ExclusionReason, ...]:
        """Kapsam dışı nedenleri — satır **geçerli** kalır."""
        return tuple(issue.reason for issue in self.scope_issues)

    @property
    def is_out_of_scope(self) -> bool:
        return bool(self.scope_issues)

    @property
    def has_waste(self) -> bool:
        """Fire **açıkça** girilmiş mi? Boş fire sıfır değildir."""
        return self.waste_percent is not None


@dataclass(frozen=True, slots=True)
class MetrajReadResult:
    """Bir dosyanın okuma sonucu: dosya düzeyi bilgi + satırlar."""

    path: str
    sheet_name: str
    column_index: dict[MetrajColumn, int]
    rows: tuple[MetrajRow, ...]
    ignored_columns: tuple[str, ...] = ()
    blank_rows_skipped: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def valid_rows(self) -> tuple[MetrajRow, ...]:
        return tuple(row for row in self.rows if row.is_valid)

    @property
    def invalid_rows(self) -> tuple[MetrajRow, ...]:
        return tuple(row for row in self.rows if not row.is_valid)

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_rows)

    def row_for(self, boq_no: str) -> MetrajRow | None:
        for row in self.rows:
            if row.boq_no == boq_no:
                return row
        return None
