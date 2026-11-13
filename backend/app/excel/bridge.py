"""Excel okuma sonucundan domaine köprü — Aşama 4.3.

Amaç: okunan satırları **mevcut** normalize + eşleştirme + hesaplama akışına
aktarmak. Köprü kendi başına:

* ürün eşleştirmesi **yapmaz** (``match_row`` çağrısı çağıranın işidir),
* kullanıcı onayı **vermez** (``status`` üretmez),
* miktar dönüşümü **yapmaz** (o hesap motorunun işidir).

Tek dönüşüm, fire biriminin kaynak sözleşmesine çevrilmesidir: Excel'deki
``Fire (%)`` **yüzde**dir, domain'deki ``waste_rate`` **0–1 oranıdır**
(Aşama 4.2 ve frontend sözleşmesi). Dönüşüm tek yönlü ve açıktır; yüzde/oran
tahmini yapılmaz.

Birim ayrımı
------------
``unit_value`` yalnızca **hesaba girebilen** birimlerde (m, kg, t) doludur.
Okunabilen ama kapsam dışı bir birim (``adet``) ``unit_text`` içinde
korunur ve eşleştirmeye **ham metin** olarak verilir; böylece 4.1'in
``excluded: unit`` kararı aynen üretilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.calculation import CalculationInputRow, WasteRate
from app.domain.catalog import Catalog
from app.domain.matching import match_row
from app.domain.models import InvalidReason, MatchOutcome, MatchStatus, Unit
from app.excel.models import CellIssue, MetrajReadResult, MetrajRow


@dataclass(frozen=True, slots=True)
class MetrajSourceRow:
    """Eşleştirmeye hazır, doğrulanmış kaynak satır.

    Yalnızca :attr:`source_row` ve :attr:`boq_no` birlikte taşınır: kullanıcı
    "Excel 7. satır / BOQ-003" diyerek satırı bulabilmelidir.
    """

    source_row: int
    boq_no: str
    description: str
    quantity: Decimal
    unit_text: str
    unit: Unit | None
    waste_percent: Decimal | None

    @property
    def is_out_of_scope(self) -> bool:
        """Birim hesap kapsamı dışında mı? (satır geçerli, hesap dışı)"""
        return self.unit is None

    @property
    def waste_rate(self) -> WasteRate | None:
        """Yüzde → oran dönüşümü. Fire yoksa ``None`` (sıfır değil)."""
        if self.waste_percent is None:
            return None
        return WasteRate.from_percent(self.waste_percent)

    def to_match_waste(self) -> Decimal | None:
        """``match_row`` imzasının beklediği 0–1 oranı."""
        rate = self.waste_rate
        return None if rate is None else rate.fraction

    def match(self, catalog: Catalog) -> MatchOutcome:
        """Bu satırı mevcut eşleştirme akışına verir (karar üretmez).

        Birim **ham metin** olarak verilir; ``match_row`` desteklenmeyen birimi
        kendisi ``excluded: unit`` olarak sınıflandırır.
        """
        return match_row(
            self.description,
            self.unit_text,
            self.to_match_waste(),
            catalog,
        )

    def to_calculation_row(self, outcome: MatchOutcome) -> CalculationInputRow:
        """Eşleştirme sonucuyla hesap motoru satırı üretir.

        Durum ve kod **her zaman** ``outcome``'dan gelir; okuyucudan veya
        istemciden gelen bir duruma güvenilmez.
        """
        return CalculationInputRow.from_outcome(
            row_no=self.boq_no,
            description=self.description,
            quantity=self.quantity,
            unit=self.unit if self.unit is not None else self.unit_text,
            waste_rate=self.waste_rate,
            outcome=outcome,
        )


@dataclass(frozen=True, slots=True)
class RejectedMetrajRow:
    """Veri hatası nedeniyle eşleştirmeye alınmayan satır."""

    source_row: int
    boq_no: str | None
    reasons: tuple[InvalidReason, ...]
    issues: tuple[CellIssue, ...]

    @property
    def status(self) -> MatchStatus:
        return MatchStatus.INVALID


@dataclass(frozen=True, slots=True)
class MetrajBatch:
    """Okuma sonucunun domaine aktarılabilir hâli."""

    sources: tuple[MetrajSourceRow, ...]
    rejected: tuple[RejectedMetrajRow, ...]

    @property
    def total(self) -> int:
        return len(self.sources) + len(self.rejected)

    @property
    def out_of_scope(self) -> tuple[MetrajSourceRow, ...]:
        return tuple(source for source in self.sources if source.is_out_of_scope)


def to_domain(result: MetrajReadResult) -> MetrajBatch:
    """Okuma sonucunu domaine çevirir.

    Geçerli satırlar eşleştirmeye hazır hale gelir; hatalı satırlar
    ``invalid`` olarak ayrı tutulur. Hiçbir satır sessizce düşürülmez:
    ``len(sources) + len(rejected) == len(result.rows)``.
    """
    sources: list[MetrajSourceRow] = []
    rejected: list[RejectedMetrajRow] = []

    for row in result.rows:
        if not row.is_valid:
            rejected.append(
                RejectedMetrajRow(
                    source_row=row.source_row,
                    boq_no=row.boq_no,
                    reasons=row.invalid_reasons,
                    issues=row.issues,
                )
            )
            continue
        sources.append(_as_source(row))

    return MetrajBatch(sources=tuple(sources), rejected=tuple(rejected))


def _as_source(row: MetrajRow) -> MetrajSourceRow:
    """Geçerli satırı kaynak satıra çevirir.

    ``MetrajRow.is_valid`` doğrulaması bu alanların dolu olduğunu garanti eder;
    yine de tip daraltması sessiz ``None`` taşımamak için burada yapılır.
    """
    if row.boq_no is None or row.description is None or row.quantity is None:
        raise ValueError(
            f"Satır {row.source_row}: geçerli satırda BOQ No/açıklama/miktar yok."
        )
    if row.unit is None:
        raise ValueError(f"Satır {row.source_row}: geçerli satırda birim yok.")

    return MetrajSourceRow(
        source_row=row.source_row,
        boq_no=row.boq_no,
        description=row.description,
        quantity=row.quantity,
        unit_text=row.unit,
        unit=row.unit_value,
        waste_percent=row.waste_percent,
    )
