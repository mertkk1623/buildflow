"""``GET /api/template`` testleri.

Şablon dosyası sunucuda sabittir; istemci girdisi dosya yoluna girmez.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.routes import TEMPLATE_DOWNLOAD_NAME, XLSX_MEDIA_TYPE
from app.config import get_settings


def test_template_downloads_xlsx(client: TestClient) -> None:
    response = client.get("/api/template")

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_MEDIA_TYPE
    assert len(response.content) > 0


def test_template_is_a_real_workbook(client: TestClient) -> None:
    """İndirilen dosya gerçekten açılabilen bir .xlsx olmalı."""
    content = client.get("/api/template").content

    workbook = load_workbook(io.BytesIO(content))
    try:
        assert workbook.sheetnames
    finally:
        workbook.close()


def test_template_is_attachment_with_fixed_name(client: TestClient) -> None:
    response = client.get("/api/template")

    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert TEMPLATE_DOWNLOAD_NAME in disposition
    # Dosya adı koddan gelir; istemciden hiçbir ad yansıtılmaz.
    assert "buildflow" in TEMPLATE_DOWNLOAD_NAME


def test_template_sets_nosniff(client: TestClient) -> None:
    response = client.get("/api/template")

    assert response.headers["x-content-type-options"] == "nosniff"


def test_template_bytes_match_source_file(client: TestClient) -> None:
    """İndirme, yapılandırmadaki şablonun birebir kopyasıdır."""
    expected = get_settings().template_path.read_bytes()

    assert client.get("/api/template").content == expected


def test_template_missing_returns_clean_error(client: TestClient, tmp_path) -> None:
    """Şablon yoksa 404 döner ve sunucu yolu istemciye sızmaz."""
    from app.config import get_settings as real_get_settings

    settings = real_get_settings()
    original = settings.template_path
    settings.template_path = tmp_path / "yok.xlsx"
    try:
        response = client.get("/api/template")
    finally:
        settings.template_path = original

    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "template-not-found"
    assert str(tmp_path) not in response.text
    assert "yok.xlsx" not in response.text
