"""Türkçe BOQ açıklamalarının normalizasyonu.

Amaç: serbest metin açıklamayı **dört malzeme özelliğine** indirgemek
(grup, ölçü, kalite, kaplama). Uydurma yok: tanınmayan ifade ``None`` kalır.

Türkçe büyük/küçük harf tuzağı
-------------------------------
``str.lower()`` Türkçede yanlış sonuç verir: ``"İ".lower()`` iki kod noktası
üretir (``i`` + birleşik nokta). Bu yüzden açık eşleme kullanılır:

* ``İ`` → ``i``, ``I`` → ``i``
* ``ı`` (noktasız) olduğu gibi kalır; takma adlarda hem ``ipe`` hem ``ıpe`` var

``I → i`` seçimi bilinçlidir: teknik açıklamalar çoğunlukla ASCII büyük harfle
yazılır (``IPE``, ``SIYAH``, ``GALVANIZ``). Türkçe metinden gelen gerçek
noktasız ``ı`` korunur, dolayısıyla iki durum da doğru çalışır.

Bulanık eşleştirme yok
----------------------
Ölçü bileşenleri sayısal olarak normalize edilir (``4`` ≡ ``4.0``) ama
``100×100×4`` ile ``100×100×5`` **asla** birbirine yakın sayılmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models import Coating, Grade, MaterialAttributes, MaterialFamily
from app.domain.sizes import (
    FAMILY_SIZE_ARITY,
    SIZE_SEPARATOR,
    canonical_box_size,
    canonical_flat_size,
    canonical_profile_size,
)

# --- Türkçe harf eşlemesi ---------------------------------------------------

_TR_UPPER_TO_LOWER = str.maketrans(
    {
        "İ": "i",
        "I": "i",
        "Ç": "ç",
        "Ğ": "ğ",
        "Ö": "ö",
        "Ş": "ş",
        "Ü": "ü",
    }
)

#: Türkçe + ASCII küçük harf kümesi (kelime sınırı denetiminde kullanılır).
_LETTERS = "a-zçğıöşü"

_TURKISH_DIGITS = str.maketrans({"İ": "i", "I": "i"})


def tr_lower(text: str) -> str:
    """Türkçe kurallarına göre küçük harfe çevirir."""
    return text.translate(_TR_UPPER_TO_LOWER).lower()


# --- Takma adlar ------------------------------------------------------------

_FAMILY_ALIASES: dict[str, MaterialFamily] = {}

_FAMILY_ALIAS_SOURCE: dict[MaterialFamily, tuple[str, ...]] = {
    MaterialFamily.BOX: (
        "kutu profil",
        "kutu",
        "box",
        "kare profil",
        "dikdörtgen profil",
        "dikdortgen profil",
        "shs",
        "rhs",
    ),
    MaterialFamily.IPE: ("ipe", "ıpe", "i-pe", "ipe profil"),
    MaterialFamily.HEA: ("hea", "hea profil"),
    MaterialFamily.UPN: ("upn", "npu", "upn profil"),
    MaterialFamily.FLAT: ("lama", "flat", "silme", "şerit", "serit", "lama demir"),
}

for _family, _aliases in _FAMILY_ALIAS_SOURCE.items():
    for _alias in _aliases:
        _FAMILY_ALIASES[tr_lower(_alias)] = _family

#: Aile belirtmeyen, tek başına anlamı olmayan genel sözcükler.
_GENERIC_FAMILY_WORDS = ("profil", "demir", "çelik", "celik", "malzeme")

_COATING_ALIASES: dict[str, Coating] = {
    "siyah": Coating.BLACK,
    "siyah hadde": Coating.BLACK,
    "boyasız": Coating.BLACK,
    "boyasiz": Coating.BLACK,
    "çıplak": Coating.BLACK,
    "ciplak": Coating.BLACK,
    "ham": Coating.BLACK,
    "galvaniz": Coating.GALVANIZED,
    "galvanizli": Coating.GALVANIZED,
    "galvanized": Coating.GALVANIZED,
    "galvaniz kaplı": Coating.GALVANIZED,
    "galvaniz kapli": Coating.GALVANIZED,
    "hdg": Coating.GALVANIZED,
    "sıcak daldırma": Coating.GALVANIZED,
    "sicak daldirma": Coating.GALVANIZED,
    "sıcak daldırma galvaniz": Coating.GALVANIZED,
    "sicak daldirma galvaniz": Coating.GALVANIZED,
}

#: Kalite ifadeleri. **Yalnızca** katalogdaki iki kalite tanınır.
#: ``ST37``/``ST44``/``ST52`` ve ``S235JR`` bilinçli olarak eşlenmez:
#: bunlar farklı standart/ürün kaliteleridir, sessizce dönüştürmek uydurma olur.
_GRADE_PATTERNS: tuple[tuple[re.Pattern[str], Grade], ...] = (
    (re.compile(r"(?<![a-z0-9])s\s*-?\s*235(?![a-z0-9])"), Grade.S235),
    (re.compile(r"(?<![a-z0-9])s\s*-?\s*355(?![a-z0-9])"), Grade.S355),
)

#: Tanınan ama **eşlenmeyen** kalite ifadeleri — kullanıcıya rapor edilir.
_UNMAPPED_GRADE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![a-z0-9])st\s*-?\s*(?:37|44|52)(?![0-9])"),
    re.compile(r"(?<![a-z0-9])s\s*-?\s*(?:235|275|355)\s*(?:jr|j0|j2|ar|m)(?![a-z])"),
    re.compile(r"(?<![a-z0-9])s\s*-?\s*275(?![0-9])"),
)

# --- Ölçü kalıpları ---------------------------------------------------------

_NUM = r"\d+(?:[.,]\d+)?"
_SEP = r"\s*[x×X*/]\s*"
_THREE_PART = re.compile(rf"({_NUM}){_SEP}({_NUM}){_SEP}({_NUM})")
_TWO_PART = re.compile(rf"({_NUM}){_SEP}({_NUM})")
_SINGLE_NUMBER = re.compile(rf"^{_NUM}$")


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Normalizasyon çıktısı ve iz bilgisi."""

    attributes: MaterialAttributes
    normalized_text: str
    family_token: str | None
    grade_token: str | None
    coating_token: str | None
    size_token: str | None
    warnings: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return self.attributes.is_complete


def _boundary(alias: str) -> re.Pattern[str]:
    """Takma adı kelime sınırlarıyla eşleyen desen."""
    return re.compile(
        rf"(?<![{_LETTERS}]){re.escape(alias)}(?![{_LETTERS}])"
    )


def _strip_phrase(text: str, phrase: str) -> tuple[str, bool]:
    """İfadeyi metinden çıkarır; bulunup bulunmadığını da döndürür."""
    pattern = _boundary(phrase)
    if pattern.search(text):
        return pattern.sub(" ", text), True
    return text, False


def normalize_description(description: str) -> NormalizationResult:
    """Serbest açıklamayı dört özelliğe indirger."""
    warnings: list[str] = []
    text = tr_lower(description.strip())
    text = text.replace(SIZE_SEPARATOR, "x")
    normalized_text = text

    # --- 1. Kaplama (önce çıkar: içinde sayı yok, ölçüyü kirletmez) ---
    found_coatings: list[Coating] = []
    coating_token: str | None = None
    # Uzun ifadeler önce denenir ("sıcak daldırma galvaniz" > "galvaniz").
    for alias in sorted(_COATING_ALIASES, key=len, reverse=True):
        text, found = _strip_phrase(text, tr_lower(alias))
        if found:
            found_coatings.append(_COATING_ALIASES[alias])
            if coating_token is None:
                coating_token = alias

    coating: Coating | None = None
    if len(set(found_coatings)) == 1:
        coating = found_coatings[0]
    elif len(set(found_coatings)) > 1:
        warnings.append(
            "Açıklamada birden fazla kaplama ifadesi var; kaplama belirsiz bırakıldı."
        )

    # --- 2. Kalite ---
    grade: Grade | None = None
    grade_token: str | None = None
    for pattern, candidate in _GRADE_PATTERNS:
        match = pattern.search(text)
        if match:
            grade = candidate
            grade_token = match.group(0)
            text = pattern.sub(" ", text, count=1)
            break

    for pattern in _UNMAPPED_GRADE_PATTERNS:
        match = pattern.search(text)
        if match:
            warnings.append(
                f"Kalite ifadesi {match.group(0)!r} katalog kalitelerine "
                "eşlenmedi; otomatik eşleştirme yapılmayacak."
            )
            text = pattern.sub(" ", text, count=1)

    # --- 3. Aile ---
    family: MaterialFamily | None = None
    family_token: str | None = None
    for alias in sorted(_FAMILY_ALIASES, key=len, reverse=True):
        text, found = _strip_phrase(text, alias)
        if found:
            family = _FAMILY_ALIASES[alias]
            family_token = alias
            break

    for generic in _GENERIC_FAMILY_WORDS:
        text, found = _strip_phrase(text, generic)
        if found and family is None:
            warnings.append(
                f"{generic!r} tek başına malzeme ailesini belirlemez."
            )

    # --- 4. Ölçü ---
    size: str | None = None
    size_token: str | None = None
    text = text.replace("×", "x")

    three = _THREE_PART.search(text)
    two = _TWO_PART.search(text)
    stripped = re.sub(r"\s+", " ", text).strip()

    if three and (family is None or family is MaterialFamily.BOX):
        if family is None:
            family = MaterialFamily.BOX
            family_token = family_token or "(ölçüden çıkarıldı)"
            warnings.append(
                "Üç bileşenli ölçü yalnızca BOX ailesinde bulunur; aile buradan çıkarıldı."
            )
        size = canonical_box_size(three.group(1), three.group(2), three.group(3))
        size_token = three.group(0)
    elif two and (family is None or family is MaterialFamily.FLAT):
        if family is None:
            warnings.append(
                "İki bileşenli ölçü FLAT veya et kalınlığı belirtilmemiş BOX olabilir; "
                "aile belirsiz bırakıldı."
            )
        else:
            size = canonical_flat_size(two.group(1), two.group(2))
            size_token = two.group(0)
    elif family is not None and FAMILY_SIZE_ARITY[family.value] == 1:
        single = re.search(rf"({_NUM})", stripped)
        if single:
            size = canonical_profile_size(single.group(1))
            size_token = single.group(1)
        else:
            warnings.append(
                f"{family.value} için yükseklik ölçüsü bulunamadı."
            )
    elif two is not None:
        warnings.append(
            "Ölçü aileyle uyuşmuyor; ölçü belirsiz bırakıldı."
        )
    else:
        single_only = _SINGLE_NUMBER.match(stripped)
        if single_only:
            warnings.append(
                "Tek sayısal ölçü IPE/HEA/UPN olabilir; aile belirtilmediği için "
                "ölçü kullanılmadı."
            )

    return NormalizationResult(
        attributes=MaterialAttributes(
            family=family,
            size=size,
            grade=grade,
            coating=coating,
        ),
        normalized_text=normalized_text,
        family_token=family_token,
        grade_token=grade_token,
        coating_token=coating_token,
        size_token=size_token,
        warnings=tuple(warnings),
    )
