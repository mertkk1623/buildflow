"""18 satırlık demo metrajın Python golden fixture'ı.

Bu fixture, kilitli demo veri kümesinin **tek kaynağıdır**. Aşama 4.7'de
frontend'deki prototip veri katmanı (`src/data/`) kaldırıldı; demo satırları
artık yalnızca burada tanımlıdır ve API testleri bunları gerçek `.xlsx`
dosyasına dönüştürerek kullanır.

Önemli modelleme kararı
-----------------------
Demo verisindeki 3 ``ai-approved`` satır (BOQ-003, BOQ-004, BOQ-006) gerçek
AI çıktısı **değildir**. AI varsayılan olarak ``none`` olduğu için bunlar
``PREDEFINED_DECISIONS`` içinde önceden tanımlanmış kullanıcı kararları
olarak modellenir. Gerçek kullanıcı dosyalarında bu kararlar kendiliğinden
oluşmaz.

Aynı şekilde BOQ-018'in ``rejected`` durumu da bir AI önerisinin reddidir;
deterministik eşleştirme bu satırda katalog dışı sonucu verir. Bu yüzden o
satırın reddi de önceden tanımlı bir karardır.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.decisions import Decision, DecisionAction, DecisionSource


@dataclass(frozen=True, slots=True)
class DemoRow:
    """Demo metraj satırı — yalnızca kaynak veri, hesap yok."""

    no: str
    description: str
    quantity: Decimal
    unit: str
    waste_rate: Decimal | None


#: 18 satır — kilitli demo veri kümesi (tek kaynak: bu dosya).
DEMO_ROWS: tuple[DemoRow, ...] = (
    DemoRow("BOQ-001", "BOX 100×100×4 S235 siyah", Decimal("96"), "m", Decimal("0.05")),
    DemoRow("BOQ-002", "kutu profil 100/100/4 S235 galvaniz", Decimal("48"), "m", Decimal("0.05")),
    DemoRow("BOQ-003", "IPE 200", Decimal("1240"), "kg", Decimal("0.03")),
    DemoRow("BOQ-004", "ipe240 s355", Decimal("0.84"), "t", Decimal("0.03")),
    DemoRow("BOQ-005", "HEA 200 S235 siyah", Decimal("132"), "m", Decimal("0.04")),
    DemoRow("BOQ-006", "hea 200", Decimal("3.2"), "t", Decimal("0.04")),
    DemoRow("BOQ-007", "UPN 160 S235 siyah", Decimal("54"), "m", Decimal("0.04")),
    DemoRow("BOQ-008", "lama 40×5 S235 siyah", Decimal("210"), "kg", Decimal("0.05")),
    DemoRow("BOQ-009", "lama 40×5", Decimal("180"), "kg", Decimal("0.05")),
    DemoRow("BOQ-010", "UPN 160 S235 siyah", Decimal("0.32"), "t", Decimal("0.04")),
    DemoRow("BOQ-011", "kutu profil 150×100×5 S235 siyah", Decimal("60"), "m", Decimal("0.05")),
    DemoRow("BOQ-012", "BOX 100×100×4 S235 siyah", Decimal("60"), "m", None),
    DemoRow("BOQ-013", "BOX 100×100×4 S235 siyah", Decimal("84"), "m", Decimal("0.05")),
    DemoRow("BOQ-014", "profil 100×100", Decimal("12"), "adet", Decimal("0.05")),
    DemoRow("BOQ-015", "muhtelif bağlantı elemanı", Decimal("40"), "kg", None),
    DemoRow("BOQ-016", "lama 40×5 S235 siyah", Decimal("150"), "kg", Decimal("0.05")),
    DemoRow("BOQ-017", "IPE 240 S355 siyah", Decimal("0.45"), "t", Decimal("0.03")),
    DemoRow("BOQ-018", "IPE 200 S355", Decimal("620"), "kg", Decimal("0.03")),
)

#: Demo için önceden tanımlanmış kararlar. AI çıktısı DEĞİLDİR.
PREDEFINED_DECISIONS: tuple[Decision, ...] = (
    Decision(
        row_no="BOQ-003",
        action=DecisionAction.APPROVE,
        code="IPE-200-S235",
        reason="Kalite ve kaplama açıklamada yok; demo kararı S235 siyah.",
        source=DecisionSource.DEMO_PREDEFINED,
    ),
    Decision(
        row_no="BOQ-004",
        action=DecisionAction.APPROVE,
        code="IPE-240-S355",
        reason="Kaplama belirtilmemiş; demo kararı siyah.",
        source=DecisionSource.DEMO_PREDEFINED,
    ),
    Decision(
        row_no="BOQ-006",
        action=DecisionAction.APPROVE,
        code="HEA-200-S235",
        reason="Kalite ve kaplama eksik; demo kararı S235 siyah.",
        source=DecisionSource.DEMO_PREDEFINED,
    ),
    Decision(
        row_no="BOQ-018",
        action=DecisionAction.REJECT,
        code=None,
        reason=(
            "Kalite çelişkisi: açıklamada S355, katalogda IPE 200 yalnızca S235. "
            "Kalite düşürülmez."
        ),
        source=DecisionSource.DEMO_PREDEFINED,
    ),
)

#: Kilitli dağılım: 18 = 10 rule + 3 ai-approved + 1 pending + 1 rejected + 3 excluded.
EXPECTED_COUNTS: dict[str, int] = {
    "rule": 10,
    "ai-approved": 3,
    "pending": 1,
    "rejected": 1,
    "excluded": 3,
    "invalid": 0,
}

#: Deterministik eşleştirmenin (kararlar öncesi) beklenen durumu.
EXPECTED_DETERMINISTIC: dict[str, tuple[str, str | None]] = {
    "BOQ-001": ("rule", "BOX-100-4-S235-B"),
    "BOQ-002": ("rule", "BOX-100-4-S235-G"),
    "BOQ-003": ("pending", None),
    "BOQ-004": ("pending", None),
    "BOQ-005": ("rule", "HEA-200-S235"),
    "BOQ-006": ("pending", None),
    "BOQ-007": ("rule", "UPN-160-S235"),
    "BOQ-008": ("rule", "FLAT-40x5-S235-B"),
    "BOQ-009": ("pending", None),
    "BOQ-010": ("rule", "UPN-160-S235"),
    "BOQ-011": ("rule", "BOX-150-100-5-S235-B"),
    "BOQ-012": ("excluded", None),
    "BOQ-013": ("rule", "BOX-100-4-S235-B"),
    "BOQ-014": ("excluded", None),
    "BOQ-015": ("excluded", None),
    "BOQ-016": ("rule", "FLAT-40x5-S235-B"),
    "BOQ-017": ("rule", "IPE-240-S355"),
    "BOQ-018": ("excluded", None),
}
