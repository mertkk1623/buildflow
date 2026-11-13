"""Ölçü (kesit) metinlerinin kanonik biçimi.

Bu modül bilinçli olarak **bağımlılıksızdır**: ne pydantic ne de başka bir
domain modülü import eder. Böylece hem katalog doğrulayıcı hem de açıklama
normalizasyonu aynı kuralları tek kaynaktan kullanır.

Tasarım kararı — bulanık eşleştirme yok:

* Ölçüler sayısal olarak normalize edilir (``4`` ile ``4.0`` aynıdır).
* ``100×100×4`` ile ``100×100×5`` **asla** yakın kabul edilmez.
* BOX kesitlerde ilk iki kenar sıra bağımsızdır (``100×150×5`` ≡ ``150×100×5``),
  çünkü bunlar aynı fiziksel kesittir.
* FLAT (lama) kesitte sıra **korunur**: ``40×5`` (genişlik × kalınlık) ile
  ``5×40`` farklı kesitlerdir.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

#: Ölçü bileşenleri arasındaki tek kanonik ayırıcı.
SIZE_SEPARATOR = "×"

#: Katalog ailelerinin ölçü bileşeni sayısı.
FAMILY_SIZE_ARITY: dict[str, int] = {
    "BOX": 3,  # genişlik × yükseklik × et kalınlığı
    "FLAT": 2,  # genişlik × kalınlık
    "IPE": 1,  # yükseklik
    "HEA": 1,
    "UPN": 1,
}


def canonical_number(text: str) -> str:
    """Sayısal metni kanonik biçime çevirir.

    ``"4"``, ``"4.0"``, ``"4,0"`` → ``"4"``. Ondalık ayırıcı olarak hem nokta
    hem virgül kabul edilir; burada virgül **ondalık** anlamındadır (ölçü
    bağlamında binlik ayırıcı beklenmez).
    """
    cleaned = text.strip().replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:  # pragma: no cover - çağıran doğrular
        raise ValueError(f"Sayısal olmayan ölçü bileşeni: {text!r}") from exc

    if not value.is_finite() or value <= 0:
        raise ValueError(f"Ölçü bileşeni pozitif olmalı: {text!r}")

    if value == value.to_integral_value():
        return str(int(value))

    return format(value.normalize(), "f")


def split_size(size: str) -> list[str]:
    """Kanonik ölçü metnini bileşenlerine ayırır."""
    return [part.strip() for part in size.split(SIZE_SEPARATOR)]


def canonical_box_size(first: str, second: str, thickness: str) -> str:
    """BOX ölçüsünü kanonik biçime getirir (kenarlar büyükten küçüğe)."""
    a = Decimal(canonical_number(first))
    b = Decimal(canonical_number(second))
    high, low = (a, b) if a >= b else (b, a)
    return SIZE_SEPARATOR.join(
        [format(high, "f"), format(low, "f"), canonical_number(thickness)]
    )


def canonical_flat_size(width: str, thickness: str) -> str:
    """FLAT ölçüsünü kanonik biçime getirir (sıra korunur)."""
    return SIZE_SEPARATOR.join(
        [canonical_number(width), canonical_number(thickness)]
    )


def canonical_profile_size(height: str) -> str:
    """IPE/HEA/UPN ölçüsünü kanonik biçime getirir (tek yükseklik)."""
    return canonical_number(height)


def size_issues(family: str, size: str) -> list[str]:
    """Ölçünün aileye göre yapısal geçerliliğini denetler.

    Dönen liste boşsa ölçü geçerlidir. Hata metinleri kullanıcıya değil,
    katalog doğrulama raporuna yöneliktir.
    """
    issues: list[str] = []
    expected = FAMILY_SIZE_ARITY.get(family)
    if expected is None:
        return [f"Bilinmeyen malzeme ailesi: {family}"]

    parts = split_size(size)
    if len(parts) != expected:
        issues.append(
            f"{family} ölçüsü {expected} bileşen bekler, {len(parts)} bulundu: {size!r}"
        )
        return issues

    values: list[Decimal] = []
    for part in parts:
        try:
            values.append(Decimal(canonical_number(part)))
        except ValueError as exc:
            issues.append(f"{family} ölçüsünde geçersiz bileşen: {exc}")

    if issues:
        return issues

    if family == "BOX" and values[0] < values[1]:
        issues.append(
            f"BOX ölçüsü kanonik değil (büyük kenar önce gelmeli): {size!r}"
        )

    return issues
