"""Kullanıcı kararları ve sunucu tarafı doğrulaması.

Bağlayıcı gereksinim: istemciden gelen ``status``/``matchedCode`` alanlarına
**güvenilmez**. Sunucu kararı katalog ve çelişki kurallarına göre yeniden
doğrular.

Demo verisindeki 3 ``ai-approved`` satır gerçek AI çıktısı değildir; bu
modüldeki ``Decision`` nesneleriyle **önceden tanımlanmış kararlar** olarak
modellenir. Gerçek kullanıcı dosyalarında bu kararlar kendiliğinden oluşmaz.

Not: HTTP hata kodlarına (400/409) eşleme Aşama 4.4'ün işidir. Burada yalnızca
domain düzeyinde doğrulama yapılır.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.catalog import Catalog
from app.domain.models import (
    MatchOutcome,
    MatchStatus,
    MaterialAttributes,
)


class DecisionAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class DecisionSource(str, Enum):
    """Kararın kaynağı — raporda ve denetim izinde gösterilir."""

    #: Kullanıcı arayüzden verdi.
    USER = "user"
    #: Demo verisinde önceden tanımlı. AI sonucu DEĞİLDİR.
    DEMO_PREDEFINED = "demo-predefined"


@dataclass(frozen=True, slots=True)
class Decision:
    row_no: str
    action: DecisionAction
    code: str | None = None
    reason: str = ""
    source: DecisionSource = DecisionSource.USER


class DecisionError(Exception):
    """Karar geçersiz (kod katalogda yok veya açıklamayla çelişiyor)."""

    def __init__(self, row_no: str, code: str, message: str) -> None:
        super().__init__(f"{row_no}: {message}")
        self.row_no = row_no
        self.code = code
        self.message = message


def conflicting_features(
    attributes: MaterialAttributes,
    item_code: str,
    catalog: Catalog,
) -> list[str]:
    """Açıklamada **açıkça** yazan ama kalemle çelişen özellikler.

    Yalnızca bilinen özellikler karşılaştırılır; eksik özellik çelişki saymaz
    (o zaten ``pending`` nedeniydi).
    """
    item = catalog.get(item_code)
    if item is None:
        raise KeyError(item_code)

    conflicts: list[str] = []
    if attributes.family is not None and attributes.family is not item.family:
        conflicts.append(
            f"grup: açıklamada {attributes.family.value}, kalemde {item.family.value}"
        )
    if attributes.size is not None and attributes.size != item.size:
        conflicts.append(f"ölçü: açıklamada {attributes.size}, kalemde {item.size}")
    if attributes.grade is not None and attributes.grade is not item.grade:
        conflicts.append(
            f"kalite: açıklamada {attributes.grade.value}, kalemde {item.grade.value}"
        )
    if attributes.coating is not None and attributes.coating is not item.coating:
        conflicts.append(
            f"kaplama: açıklamada {attributes.coating.value}, kalemde {item.coating.value}"
        )
    return conflicts


def apply_decision(
    outcome: MatchOutcome,
    decision: Decision,
    catalog: Catalog,
) -> MatchOutcome:
    """Tek bir kararı doğrulanmış biçimde uygular.

    * Onaylanan kod katalogda yoksa → ``DecisionError``
    * Onay açıklamayla çelişiyorsa → ``DecisionError``
    * Red kararı her durumda geçerlidir (kullanıcı son kararı verir)
    """
    if decision.row_no != decision.row_no.strip():
        raise DecisionError(decision.row_no, decision.code or "", "Satır no boş olamaz.")

    if decision.action is DecisionAction.REJECT:
        return MatchOutcome(
            status=MatchStatus.REJECTED,
            attributes=outcome.attributes,
            matched_code=None,
            candidate_codes=outcome.candidate_codes,
            message=decision.reason or "Kullanıcı satırı reddetti.",
        )

    code = decision.code
    if not code:
        raise DecisionError(decision.row_no, "", "Onay kararı bir katalog kodu gerektirir.")

    item = catalog.get(code)
    if item is None:
        raise DecisionError(
            decision.row_no,
            code,
            f"Onaylanan kod katalogda bulunmuyor: {code!r}",
        )

    conflicts = conflicting_features(outcome.attributes, code, catalog)
    if conflicts:
        raise DecisionError(
            decision.row_no,
            code,
            "Karar açıklamayla çelişiyor — " + "; ".join(conflicts),
        )

    return MatchOutcome(
        status=MatchStatus.AI_APPROVED,
        attributes=outcome.attributes,
        matched_code=code,
        candidate_codes=(code,),
        message=decision.reason or "Kullanıcı onayladı.",
    )


def apply_decisions(
    outcomes: dict[str, MatchOutcome],
    decisions: list[Decision],
    catalog: Catalog,
) -> dict[str, MatchOutcome]:
    """Kararları satır sonuçlarına uygular.

    Kararsız ``pending`` satırlar ``pending`` kalır — sessizce onaylanmaz.
    Bilinmeyen satır numarası hata verir (yazım hatası sessizce yutulmaz).
    """
    seen: set[str] = set()
    for decision in decisions:
        if decision.row_no in seen:
            raise DecisionError(
                decision.row_no, decision.code or "", "Aynı satır için iki karar verildi."
            )
        seen.add(decision.row_no)
        if decision.row_no not in outcomes:
            raise DecisionError(
                decision.row_no, decision.code or "", "Karar bilinmeyen bir satıra ait."
            )

    result = dict(outcomes)
    by_row = {decision.row_no: decision for decision in decisions}

    for row_no, outcome in outcomes.items():
        decision = by_row.get(row_no)
        if decision is None:
            continue
        result[row_no] = apply_decision(outcome, decision, catalog)

    return result
