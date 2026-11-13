"""Katalog yükleme ve doğrulama.

Katalog tek bir JSON dosyasından okunur ve **çalışma zamanında** doğrulanır.
Doğrulama başarısız olursa uygulama eksik/hatalı veriyle çalışmaya
başlamaz; sessiz varsayım üretilmez.
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.models import (
    CATALOG_SCHEMA_VERSION,
    CatalogItem,
    MaterialFamily,
)
from app.domain.sizes import SIZE_SEPARATOR

#: Varsayılan katalog dosyası.
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


class CatalogError(Exception):
    """Katalog yüklenemedi veya doğrulanamadı."""


class CatalogPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1, max_length=16)
    notes: list[str] = Field(default_factory=list)
    items: list[CatalogItem] = Field(min_length=1)


class Catalog:
    """Doğrulanmış, değişmez katalog.

    Arama tabloları yükleme sırasında bir kez kurulur; eşleştirme sırasında
    yeni hesaplama yapılmaz.
    """

    def __init__(self, items: list[CatalogItem], schema_version: str, notes: list[str]) -> None:
        self._items = tuple(items)
        self._by_code = {item.code: item for item in items}
        self._schema_version = schema_version
        self._notes = tuple(notes)

    # --- Temel erişim ---
    @property
    def schema_version(self) -> str:
        return self._schema_version

    @property
    def notes(self) -> tuple[str, ...]:
        return self._notes

    @property
    def items(self) -> tuple[CatalogItem, ...]:
        return self._items

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def get(self, code: str) -> CatalogItem | None:
        return self._by_code.get(code)

    def require(self, code: str) -> CatalogItem:
        item = self._by_code.get(code)
        if item is None:
            raise KeyError(f"Katalogda bulunmayan kod: {code!r}")
        return item

    def has_code(self, code: str) -> bool:
        return code in self._by_code

    # --- Sorgular ---
    def by_family(self, family: MaterialFamily) -> tuple[CatalogItem, ...]:
        return tuple(item for item in self._items if item.family is family)

    def by_identity(
        self,
        family: MaterialFamily,
        size: str,
        grade: Any,
        coating: Any,
    ) -> CatalogItem | None:
        """Dört özelliğin tamamı verildiğinde tekil kalemi döndürür."""
        for item in self._items:
            if (
                item.family is family
                and item.size == size
                and item.grade is grade
                and item.coating is coating
            ):
                return item
        return None

    def lengths_in_use(self) -> dict[Decimal, list[str]]:
        """Ticari boy → o boyu kullanan kodlar. Raporlama için."""
        result: dict[Decimal, list[str]] = {}
        for item in self._items:
            result.setdefault(item.commercial_length_m, []).append(item.code)
        return result


def _validate_items(items: list[CatalogItem], *, require_null_waste: bool) -> None:
    codes: set[str] = set()
    identities: dict[tuple[str, str, str, str], str] = {}
    sizes_by_family: dict[str, set[str]] = {}

    for item in items:
        if item.code in codes:
            raise CatalogError(f"Yinelenen katalog kodu: {item.code!r}")
        codes.add(item.code)

        if item.identity in identities:
            other = identities[item.identity]
            raise CatalogError(
                "Aynı dört özelliğe sahip iki kalem var: "
                f"{other!r} ve {item.code!r} "
                "(eşleştirme tekilliği bozulur)"
            )
        identities[item.identity] = item.code

        sizes_by_family.setdefault(item.family.value, set()).add(item.size)

        if SIZE_SEPARATOR not in item.size and item.family in {
            MaterialFamily.BOX,
            MaterialFamily.FLAT,
        }:
            raise CatalogError(
                f"{item.code!r}: {item.family.value} ölçüsü {SIZE_SEPARATOR!r} içermeli."
            )

        if require_null_waste and item.default_waste is not None:
            raise CatalogError(
                f"{item.code!r}: V1 kataloğunda default_waste null olmalıdır "
                f"(bulunan: {item.default_waste}). Dolu değer, fire tanımsız "
                "satırların hesaba girmesine ve demo dağılımının bozulmasına yol açar."
            )


def parse_catalog(payload: dict[str, Any]) -> Catalog:
    """Ham JSON sözlüğünü doğrulanmış kataloğa çevirir."""
    try:
        parsed = CatalogPayload.model_validate(payload)
    except ValidationError as exc:
        raise CatalogError(f"Katalog şeması geçersiz:\n{exc}") from exc

    if parsed.schema_version != CATALOG_SCHEMA_VERSION:
        raise CatalogError(
            f"Desteklenmeyen katalog şema sürümü: {parsed.schema_version!r} "
            f"(beklenen: {CATALOG_SCHEMA_VERSION!r})"
        )

    _validate_items(parsed.items, require_null_waste=True)
    return Catalog(parsed.items, parsed.schema_version, parsed.notes)


def load_catalog(path: Path | str | None = None) -> Catalog:
    """Katalog dosyasını okur ve doğrular."""
    resolved = Path(path) if path is not None else DEFAULT_CATALOG_PATH

    if not resolved.exists():
        raise CatalogError(f"Katalog dosyası bulunamadı: {resolved}")

    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogError(f"Katalog JSON geçersiz ({resolved}): {exc}") from exc

    if not isinstance(raw, dict):
        raise CatalogError("Katalog kökü bir JSON nesnesi olmalıdır.")

    return parse_catalog(raw)


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Süreç içinde tek katalog örneği."""
    return load_catalog()
