"""``GET /api/health`` testleri — mevcut davranış korunur."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == get_settings().environment


def test_health_shape_is_exact(client: TestClient) -> None:
    """Yanıt sözleşmesi dardır: fazladan alan eklenirse frontend kırılmasın."""
    body = client.get("/api/health").json()

    assert set(body) == {"status", "environment"}


def test_health_allows_cors_from_dev_origin(client: TestClient) -> None:
    """Vite geliştirme origin'i izinli olmalı."""
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_health_rejects_unknown_cors_origin(client: TestClient) -> None:
    """Listede olmayan origin'e izin başlığı verilmez."""
    response = client.get(
        "/api/health",
        headers={"Origin": "http://evil.example.com"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") != "http://evil.example.com"
    assert response.headers.get("access-control-allow-origin") != "*"
