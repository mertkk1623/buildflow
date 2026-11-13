"""Ortak pytest yapılandırması — API testleri.

``client`` fixture'ı gerçek uygulamayı (router + hata yönetimi + CORS) ayağa
kaldırır. Bağlam yöneticisi olarak kullanılır: ``TestClient`` uygulamanın
``startup``/``shutdown`` olaylarını çalıştırır ve bekleyen bağlantıları kapatır.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
