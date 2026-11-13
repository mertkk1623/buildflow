"""Raporlarda kullanılan Türkçe sayı ve tarih biçimlendirmesi.

Neden ayrı modül?
-----------------
Excel ve PDF aynı metni göstermelidir. Biçimlendirme tek yerde tutulur ki iki
çıktı birbirinden ayrışmasın.

Kurallar
--------
1. **Yuvarlama yalnızca gösterim içindir.** ``Decimal`` değer korunur; bu
   modül hiçbir hesap yapmaz, yalnızca metne çevirir.
2. **``None`` boş metindir, sıfır değildir.** Bilinmeyen değer raporda
   ``"0"`` olarak görünmez; hücre boş kalır (PARTIAL kuralı).
3. **Türkçe yazım:** binlik ayırıcı ``.``, ondalık ayırıcı ``,``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

#: Rapor sütunlarında kullanılan ondalık basamak sayıları.
METRE_PLACES = 3
WEIGHT_PLACES = 3
MASS_PLACES = 3
PERCENT_PLACES = 2

#: Bilinmeyen değerin Excel hücresindeki karşılığı: **boş hücre**.
#: PDF'te görünür bir yer tutucu kullanılır; bkz. :data:`EMPTY_PLACEHOLDER`.
UNKNOWN_TEXT = ""

#: PDF tablo hücresinde bilinmeyen değerin karşılığı. Excel'de hücre boş
#: bırakılır; PDF'te boş hücre "veri kayboldu" izlenimi vereceği için tire
#: kullanılır. Hiçbir durumda ``0`` yazılmaz.
EMPTY_PLACEHOLDER = "—"


def format_decimal(value: Decimal | None, places: int = METRE_PLACES) -> str:
    """``Decimal``'ı Türkçe yazımla metne çevirir.

    ``None`` → ``""`` (boş). Böylece bilinmeyen değer sıfır gibi okunmaz.

    >>> format_decimal(Decimal("18005.82"), 3)
    '18.005,820'
    >>> format_decimal(None)
    ''
    """
    if value is None:
        return UNKNOWN_TEXT

    quantum = Decimal(1).scaleb(-places)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    text = f"{rounded:,.{places}f}"
    # ``f"{...:,.3f}"`` her zaman ASCII ayırıcı üretir: önce yer tutucuya
    # çevirip sonra yer değiştirmek karışmayı önler.
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_integer(value: Decimal | None) -> str:
    """Tam sayı gösterimi (sipariş adedi gibi)."""
    return format_decimal(value, 0)


def format_percent(value: Decimal | None, places: int = PERCENT_PLACES) -> str:
    """Yüzde gösterimi. ``None`` → boş (sıfır fire varsayılmaz)."""
    if value is None:
        return UNKNOWN_TEXT
    return f"%{format_decimal(value, places)}"


def format_datetime(value: datetime) -> str:
    """Rapor tarihi: ``13.11.2026 14:05``."""
    return value.strftime("%d.%m.%Y %H:%M")


def display_or_placeholder(text: str) -> str:
    """PDF hücresi için: boşsa görünür bir yer tutucu koyar.

    Excel'de boş hücre doğru davranıştır; PDF'te ise tablo hücresinin boş
    kalması "veri kayboldu" izlenimi verebilir. Bu yüzden PDF katmanı
    :data:`EMPTY_PLACEHOLDER` kullanır. **Sayı asla yer tutucuyla
    değiştirilmez**; yer tutucu yalnızca tablo hücresinde gösterilir.
    """
    return text if text else EMPTY_PLACEHOLDER
