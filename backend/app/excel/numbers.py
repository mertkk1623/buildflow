"""Excel hücrelerinden güvenli ``Decimal`` okuma.

Neden ayrı bir modül?
---------------------
Excel sayısal hücreleri IEEE-754 ``double`` saklar. ``Decimal(hücre)`` yazmak
``0.1`` gibi değerlerde ikili kesir hatasını içeri taşır ve sipariş miktarını
değiştirir (Aşama 4.2 kuralı: float üzerinden Decimal kurulmaz).

Kurallar
--------
1. **Sayısal hücre** doğrudan okunur. ``float`` için kayan noktanın *en kısa
   tur-güvenli* gösterimi (``repr``) kullanılır; böylece ``Decimal(0.1)``
   hatası oluşmaz, kullanıcının yazdığı ondalık korunur.
2. **Metin hücreler** Türkçe yazım kurallarıyla ayrıştırılır:
   ``1.240`` = 1240, ``1,24`` = 1,24, ``1.240,50`` = 1240,50.
3. **Belirsiz gösterim tahmin edilmez.** ``1,240`` hem 1240 hem 1,24
   olabilir; ``1,2,3`` hiçbir kurala uymaz. Bu durumlarda
   :class:`NumberParseError` ``ambiguous=True`` ile yükselir ve satır
   ``invalid`` işaretlenir.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal

#: Görünmez/boşluk benzeri karakterler. Excel yapıştırmalarında sık görülür;
#: binlik ayırıcı olarak kullanılan dar boşluklar normal boşluğa çevrilir.
_SPACE_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",  # NBSP
        "\u2007": " ",  # figure space
        "\u2009": " ",  # thin space
        "\u202f": " ",  # narrow NBSP
        "\u200b": "",   # zero width space
    }
)

#: Unicode eksi işareti (Excel'den yapıştırınca görülebilir).
_MINUS_SIGNS = ("-", "\u2212")

_DIGITS = re.compile(r"^[0-9]+$")

#: Excel'in "genel" biçimde saklayabildiği en büyük tam sayı sınırı.
_EXACT_FLOAT_INT_LIMIT = 2**53


class NumberParseError(ValueError):
    """Hücre değeri sayıya çevrilemedi.

    ``ambiguous`` ``True`` ise değer iki farklı okumaya açıktır (binlik/ondalık
    karışıklığı); ``False`` ise değer hiç sayı değildir.
    """

    def __init__(self, message: str, *, ambiguous: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.ambiguous = ambiguous


def looks_empty(value: object) -> bool:
    """Hücre boş sayılmalı mı? (``None``, boş metin, yalnızca boşluk)"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _clean_text(text: str) -> str:
    return text.translate(_SPACE_TRANSLATION).strip()


def _valid_grouping(text: str, separator: str) -> bool:
    """``1.240`` / ``1 240`` / ``1.240.500`` binlik gruplaması geçerli mi?"""
    parts = text.split(separator)
    if len(parts) < 2:
        return False
    if not _DIGITS.match(parts[0]) or not 1 <= len(parts[0]) <= 3:
        return False
    return all(_DIGITS.match(part) and len(part) == 3 for part in parts[1:])


def parse_decimal_text(text: str) -> Decimal:
    """Metin hücresini ``Decimal``'a çevirir.

    Raises
    ------
    NumberParseError
        Değer sayı değilse (``ambiguous=False``) veya binlik/ondalık
        karışıklığı varsa (``ambiguous=True``).
    """
    cleaned = _clean_text(text)
    if not cleaned:
        raise NumberParseError("Hücre boş.")

    sign = ""
    body = cleaned
    if body[0] in _MINUS_SIGNS:
        sign = "-"
        body = body[1:].strip()
    elif body[0] == "+":
        body = body[1:].strip()
    if not body:
        raise NumberParseError("Değer yalnızca işaret içeriyor.")

    if not any(character.isdigit() for character in body):
        raise NumberParseError(f"Sayısal değer değil: {text!r}")

    int_part, frac_part = _split_number(body, original=text)

    if " " in int_part:
        if frac_part or not _valid_grouping(int_part, " "):
            raise NumberParseError(
                f"Boşlukla ayrılmış sayı belirsiz: {text!r}", ambiguous=True
            )
        int_part = int_part.replace(" ", "")

    if int_part and not _DIGITS.match(int_part):
        raise NumberParseError(f"Sayısal olmayan karakter içeriyor: {text!r}")
    if frac_part and not _DIGITS.match(frac_part):
        raise NumberParseError(
            f"Ondalık kısım geçersiz: {text!r}", ambiguous=True
        )
    if not int_part and not frac_part:
        raise NumberParseError(f"Sayısal değer değil: {text!r}")

    literal = f"{sign}{int_part or '0'}"
    if frac_part:
        literal = f"{literal}.{frac_part}"

    try:
        value = Decimal(literal)
    except ArithmeticError as exc:  # pragma: no cover - literal yukarıda doğrulandı
        raise NumberParseError(f"Sayı okunamadı: {text!r}") from exc

    if not value.is_finite():  # pragma: no cover - literal sınırlı
        raise NumberParseError(f"Sonlu olmayan sayı: {text!r}")
    return value


def _split_number(text: str, *, original: str) -> tuple[str, str]:
    """Metni (tam kısım, ondalık kısım) olarak ayırır.

    Tam kısım binlik ayırıcı içerebilir (boşluk dahil); ondalık kısım yalnızca
    rakam olabilir.
    """
    commas = text.count(",")
    dots = text.count(".")

    if commas and dots:
        # Son görülen ayırıcı ondalıktır; diğeri binlik olmak zorundadır.
        # Sayıya değil konuma bakılır: "1.234.567,89" da "1,234.56" da doğru
        # okunmalıdır.
        if text.rfind(",") > text.rfind("."):
            thousands_separator, index = ".", text.rfind(",")
        else:
            thousands_separator, index = ",", text.rfind(".")
        int_part, frac_part = text[:index], text[index + 1 :]
        # Son ayırıcıdan sonra 3 hane varsa bu bir binlik grup da olabilir;
        # iki ayırıcı bir arada kullanıldığında bu belirsizlik kalmaz.
        if not _valid_grouping(int_part, thousands_separator):
            raise NumberParseError(
                f"Binlik ayırıcı gruplaması geçersiz: {original!r}", ambiguous=True
            )
        return int_part.replace(thousands_separator, ""), frac_part

    if commas:
        if commas > 1:
            if not _valid_grouping(text, ","):
                raise NumberParseError(
                    f"Virgüllü sayı belirsiz: {original!r}", ambiguous=True
                )
            return text.replace(",", ""), ""
        head, _, tail = text.partition(",")
        if tail and head and _DIGITS.match(tail) and len(tail) == 3 and head != "0":
            # "1,240" → 1.240 mı 1240 mı? Türkçe ondalık virgül de İngilizce
            # binlik virgül de olabilir; üç haneli kuyruk tek başına karar
            # vermez. Tahmin yürütülmez.
            raise NumberParseError(
                f"Virgülden sonra üç hane var (1,240 mı 1240 mı?): {original!r}",
                ambiguous=True,
            )
        return head, tail

    if dots:
        if dots > 1:
            if not _valid_grouping(text, "."):
                raise NumberParseError(
                    f"Noktalı sayı belirsiz: {original!r}", ambiguous=True
                )
            return text.replace(".", ""), ""
        head, _, tail = text.partition(".")
        if (
            head
            and tail
            and _DIGITS.match(head)
            and _DIGITS.match(tail)
            and len(tail) == 3
            and head != "0"
            and len(head) <= 3
        ):
            # Türkçe yazımda "1.240" bin iki yüz kırk demektir.
            return head + tail, ""
        return head, tail

    return text, ""


def parse_percent_text(text: str) -> Decimal:
    """Yüzde metnini ayrıştırır: ``"%5"`` / ``"5%"`` / ``"5"`` → ``5``.

    Yüzde işareti yalnızca sonda veya başta olabilir; ``"5 % 3"`` gibi
    ifadeler reddedilir.
    """
    cleaned = _clean_text(text)
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()
    elif cleaned.startswith("%"):
        cleaned = cleaned[1:].strip()
    return parse_decimal_text(cleaned)


def decimal_from_number(value: object) -> Decimal:
    """Sayısal hücre değerini ``Decimal``'a çevirir.

    ``float`` için ``Decimal(float)`` **kullanılmaz**: ikili kesir hatası
    ``Decimal(0.1) == 0.1000000000000000055511151231257827`` demektir. Bunun
    yerine kayan noktanın en kısa tur-güvenli gösterimi alınır.
    """
    if isinstance(value, bool):
        raise NumberParseError("Mantıksal değer (DOĞRU/YANLIŞ) miktar olamaz.")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise NumberParseError("Sonlu olmayan sayı (NaN/sonsuz) okunamaz.")
        if value.is_integer() and abs(value) <= _EXACT_FLOAT_INT_LIMIT:
            return Decimal(int(value))
        # repr(0.1) == "0.1" → Decimal("0.1"), float hatası taşınmaz.
        return Decimal(repr(value))
    raise NumberParseError(f"Sayısal olmayan hücre değeri: {type(value).__name__}")


def scale_percent(value: Decimal) -> Decimal:
    """Yüzde biçimli hücrenin sakladığı oranı yüzdeye çevirir.

    Excel'de ``%`` biçimli hücre ``5%`` yazıldığında ``0.05`` saklar. Bu,
    kullanıcının girdiği değerin *kendisidir*; tahmin değildir.
    """
    return value * Decimal(100)
