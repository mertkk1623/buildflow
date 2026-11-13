"""API güvenlik testleri.

Odak: istemcinin sunucuya sızdırabileceği veya sunucudan sızdırılabilecek
bilgiler, CORS sınırları ve hata zarfının tutarlılığı.

1.  Hata zarfı her hata türünde aynı biçimde
2.  Sunucu iç yolları ve istemci dosya adı hata mesajına sızmaz
3.  Yüklenen dosya içeriği yanıtta geri yansıtılmaz
4.  CORS: izinli/izinsiz origin, izinli metotlar, joker reddi
5.  İstemci sahte alanları reddedilir (şema allowlist)
6.  Bilinmeyen yol/metot tutarlı hata döndürür
7.  Şablon indirmede dosya adı başlığı sabittir
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.uploads import DEFAULT_MAX_UPLOAD_BYTES, UploadWorkspace
from app.config import Settings, get_settings
from tests.fixtures.api import (
    analyze_ok,
    calculate,
    client_rows,
    decide,
    error_of,
    upload,
    upload_bytes,
)
from tests.fixtures.excel_files import build_demo_workbook, write_workbook

VALID_ROW = ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]


# ---------------------------------------------------------------------------
# 1. Hata zarfı
# ---------------------------------------------------------------------------


class TestErrorEnvelope:
    def test_415_uses_envelope(self, client: TestClient, tmp_path: Path) -> None:
        workbook = write_workbook(tmp_path / "x.xlsx", [VALID_ROW])
        body = error_of(upload(client, workbook, filename="x.csv"))

        assert body["code"] == "unsupported-format"
        assert isinstance(body["issues"], list)

    def test_422_uses_envelope(self, client: TestClient) -> None:
        body = error_of(upload_bytes(client, b"PK\x03\x04bozuk"))

        assert body["code"] == "corrupt-file"

    def test_404_uses_envelope(self, client: TestClient) -> None:
        response = client.get("/api/bilinmeyen")

        assert response.status_code == 404
        assert error_of(response)["code"] == "http-error"

    def test_405_uses_envelope(self, client: TestClient) -> None:
        response = client.get("/api/analyze")

        assert response.status_code == 405
        assert error_of(response)["code"] == "http-error"

    def test_validation_error_lists_fields(self, client: TestClient) -> None:
        response = client.post("/api/calculate", json={"rows": "bozuk"})

        assert response.status_code == 422
        body = error_of(response)
        assert body["code"] == "validation-error"
        assert body["issues"]
        assert body["issues"][0]["message"]

    def test_error_body_never_contains_traceback(self, client: TestClient) -> None:
        response = client.post("/api/calculate", json={"rows": "bozuk"})
        text = response.text

        assert "Traceback" not in text
        assert "pydantic" not in text.lower()
        assert ".py" not in text


# ---------------------------------------------------------------------------
# 2. Yol sızıntısı
# ---------------------------------------------------------------------------


class TestPathLeaks:
    def test_strip_paths_removes_windows_and_posix_paths(self) -> None:
        from app.api.errors import _strip_paths

        for text in (
            r"Dosya bulunamadı: C:\Users\mmert\Temp\metraj.xlsx",
            "Dosya bulunamadı: C:/Users/mmert/Temp/metraj.xlsx",
            "Dosya bulunamadı: /tmp/buildflow-metraj-abc/metraj.xlsx",
            "Dosya bulunamadı: /home/user/metraj.xlsx",
        ):
            cleaned = _strip_paths(text)
            assert "mmert" not in cleaned
            assert "buildflow" not in cleaned
            assert "user" not in cleaned
            assert "(dosya)" in cleaned

    def test_strip_paths_keeps_plain_messages(self) -> None:
        from app.api.errors import _strip_paths

        text = "Zorunlu kolon(lar) eksik: Birim"

        assert _strip_paths(text) == text

    def test_missing_column_error_hides_server_paths(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(tmp_path / "sade.xlsx", [VALID_ROW], headers=("BOQ No",))
        response = upload(client, path)

        assert response.status_code == 422
        text = response.text
        assert str(tmp_path) not in text
        assert str(tmp_path).replace("\\", "/") not in text
        assert tempfile.gettempdir() not in text

    def test_corrupt_error_hides_temp_directory(self, client: TestClient) -> None:
        response = upload_bytes(client, b"PK\x03\x04" + b"\x00" * 64)

        text = response.text
        assert "buildflow-metraj-" not in text
        assert tempfile.gettempdir() not in text
        assert "metraj.xlsx" not in text or response.json()["error"]["code"] == "corrupt-file"

    def test_decision_error_contains_no_paths(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        workbook = build_demo_workbook(tmp_path / "demo.xlsx")
        rows = client_rows(analyze_ok(client, workbook))

        response = calculate(client, rows, [decide("BOQ-003", "approve", "YOK-999")])

        assert response.status_code == 409
        assert str(tmp_path) not in response.text

    def test_template_error_hides_path(self, client: TestClient, tmp_path: Path) -> None:
        settings = get_settings()
        original = settings.template_path
        settings.template_path = tmp_path / "gizli" / "sablon.xlsx"
        try:
            response = client.get("/api/template")
        finally:
            settings.template_path = original

        assert response.status_code == 404
        assert str(tmp_path) not in response.text


# ---------------------------------------------------------------------------
# 3. İçerik yansıtılmaz
# ---------------------------------------------------------------------------


class TestUploadEcho:
    def test_client_filename_is_not_echoed(self, client: TestClient, tmp_path: Path) -> None:
        workbook = write_workbook(tmp_path / "x.xlsx", [VALID_ROW])
        response = upload(client, workbook, filename="gizli-musteri-adi.xlsx")

        assert response.status_code == 200
        assert "gizli-musteri-adi" not in response.text

    def test_uploaded_cell_content_is_not_echoed_in_errors(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """Hücre içeriği hata mesajına kopyalanmaz (formül/enjeksiyon riski)."""
        marker = "<script>alert(1)</script>"
        path = write_workbook(
            tmp_path / "enjeksiyon.xlsx",
            [["BOQ-001", marker, 96, "m", 5]],
        )
        response = upload(client, path)

        assert response.status_code == 200
        # Açıklama yanıtta veri olarak döner, hata metni olarak değil.
        body = response.json()
        assert body["rows"][0]["description"] == marker

    def test_error_detail_does_not_include_file_bytes(self, client: TestClient) -> None:
        payload = b"PK\x03\x04" + b"GIZLI_ICERIK" * 8
        response = upload_bytes(client, payload)

        assert "GIZLI_ICERIK" not in response.text


# ---------------------------------------------------------------------------
# 4. CORS
# ---------------------------------------------------------------------------


class TestCors:
    def test_dev_origin_is_allowed(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})

        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_127_origin_is_allowed(self, client: TestClient) -> None:
        response = client.get(
            "/api/health", headers={"Origin": "http://127.0.0.1:5173"}
        )

        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

    def test_unlisted_origin_gets_no_allow_header(self, client: TestClient) -> None:
        response = client.get(
            "/api/health", headers={"Origin": "https://kotu-site.example"}
        )

        assert "access-control-allow-origin" not in response.headers

    @pytest.mark.parametrize("method", ["GET", "POST"])
    def test_required_methods_are_allowed_in_preflight(
        self, client: TestClient, method: str
    ) -> None:
        response = client.options(
            "/api/calculate",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": method,
            },
        )

        assert response.status_code == 200
        allowed = response.headers["access-control-allow-methods"]
        assert method in allowed

    def test_delete_is_not_allowed_in_preflight(self, client: TestClient) -> None:
        response = client.options(
            "/api/calculate",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "DELETE",
            },
        )

        allowed = response.headers.get("access-control-allow-methods", "")
        assert "DELETE" not in allowed

    def test_unlisted_origin_preflight_is_rejected(self, client: TestClient) -> None:
        response = client.options(
            "/api/calculate",
            headers={
                "Origin": "https://kotu-site.example",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert "access-control-allow-origin" not in response.headers

    def test_credentials_are_not_allowed(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})

        assert "access-control-allow-credentials" not in response.headers

    def test_wildcard_origin_configuration_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Joker"):
            Settings(cors_origins=["*"])


class TestUnhandledErrorCors:
    """Sunucu hatası da tarayıcıda okunabilir kalmalı (CORS başlığı)."""

    @staticmethod
    def _app() -> "object":
        from fastapi import FastAPI

        from app.api.errors import install_error_handlers

        test_app = FastAPI()
        install_error_handlers(test_app)

        @test_app.get("/boom")
        def boom() -> None:
            raise RuntimeError("gizli ayrinti C:\\sunucu\\yol")

        return test_app

    def test_500_keeps_cors_header_for_allowed_origin(self) -> None:
        from fastapi.testclient import TestClient

        with TestClient(self._app(), raise_server_exceptions=False) as test_client:
            response = test_client.get(
                "/boom", headers={"Origin": "http://localhost:5173"}
            )

        assert response.status_code == 500
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.headers["vary"] == "Origin"

    def test_500_has_no_cors_header_for_unknown_origin(self) -> None:
        from fastapi.testclient import TestClient

        with TestClient(self._app(), raise_server_exceptions=False) as test_client:
            response = test_client.get(
                "/boom", headers={"Origin": "https://kotu-site.example"}
            )

        assert response.status_code == 500
        assert "access-control-allow-origin" not in response.headers

    def test_500_body_hides_exception_details(self) -> None:
        from fastapi.testclient import TestClient

        with TestClient(self._app(), raise_server_exceptions=False) as test_client:
            response = test_client.get("/boom")

        body = error_of(response)
        assert body["code"] == "internal-error"
        assert "gizli" not in response.text
        assert "C:\\" not in response.text
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text

    def test_empty_origin_list_is_allowed_by_settings(self) -> None:
        """Boş liste güvenli varsayılandır: hiçbir tarayıcı origin'i izinli olmaz."""
        settings = Settings(cors_origins=[])

        assert settings.cors_origins == []

    def test_origin_trailing_slash_is_normalised(self) -> None:
        settings = Settings(cors_origins=["http://localhost:5173/"])

        assert settings.cors_origins == ["http://localhost:5173"]


# ---------------------------------------------------------------------------
# 5. İstemci sahtekârlığı
# ---------------------------------------------------------------------------


def _one_row() -> dict:
    """İstemcinin gönderebileceği en küçük geçerli satır."""
    return {
        "source_row": 2,
        "boq_no": "BOQ-001",
        "description": "BOX 100×100×4 S235 siyah",
        "quantity": "96",
        "unit": "m",
        "waste_percent": "5",
    }


class TestClientForgery:
    @pytest.mark.parametrize(
        "payload",
        [
            {"rows": [{**_one_row(), "match_status": "rule"}]},
            {"rows": [{**_one_row(), "matched_code": "BOX-100-4-S235-B"}]},
            {"rows": [{**_one_row(), "computed_weight": "1"}]},
            {"rows": [{**_one_row(), "order_length_m": "1"}]},
        ],
    )
    def test_forged_fields_are_rejected(self, client: TestClient, payload: dict) -> None:
        response = client.post("/api/calculate", json=payload)

        assert response.status_code == 422
        assert error_of(response)["code"] == "validation-error"

    def test_decision_cannot_change_another_rows_code(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        workbook = build_demo_workbook(tmp_path / "demo.xlsx")
        rows = client_rows(analyze_ok(client, workbook))

        response = calculate(client, rows, [decide("BOQ-005", "approve", "FLAT-40x5-S235-B")])

        assert response.status_code == 409
        assert error_of(response)["code"] == "invalid-decision"

    def test_decision_with_unknown_boq_cannot_smuggle_code(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        workbook = build_demo_workbook(tmp_path / "demo2.xlsx")
        rows = client_rows(analyze_ok(client, workbook))

        response = calculate(client, rows, [decide("BOQ-XXX", "approve", "IPE-200-S235")])

        assert response.status_code == 409
        assert error_of(response)["code"] == "unknown-row"


class TestNumericContract:
    """JSON'da ondalık sayılar string taşınır; ``float`` kabul edilmez."""

    def test_float_quantity_is_rejected(self, client: TestClient) -> None:
        row = {**_one_row(), "quantity": 0.84}

        response = client.post("/api/calculate", json={"rows": [row]})

        assert response.status_code == 422
        assert "string" in response.json()["error"]["issues"][0]["message"]

    def test_float_waste_is_rejected(self, client: TestClient) -> None:
        row = {**_one_row(), "waste_percent": 5.0}

        response = client.post("/api/calculate", json={"rows": [row]})

        assert response.status_code == 422

    def test_integer_quantity_is_accepted(self, client: TestClient) -> None:
        row = {**_one_row(), "quantity": 96, "waste_percent": 5}

        response = client.post("/api/calculate", json={"rows": [row]})

        assert response.status_code == 200, response.text

    def test_string_decimals_are_accepted_verbatim(self, client: TestClient) -> None:
        row = {**_one_row(), "quantity": "0.84", "unit": "t"}

        response = client.post("/api/calculate", json={"rows": [row]})

        assert response.status_code == 200, response.text
        group = response.json()["groups"][0]
        assert group["sources"][0]["source_quantity"] == "0.84"

    def test_nan_and_infinity_are_rejected(self, client: TestClient) -> None:
        for value in ("NaN", "Infinity", "-Infinity"):
            response = client.post(
                "/api/calculate", json={"rows": [{**_one_row(), "quantity": value}]}
            )
            assert response.status_code == 422, value


# ---------------------------------------------------------------------------
# 6. Dosya güvenliği birimleri
# ---------------------------------------------------------------------------


class TestUploadWorkspace:
    def test_workspace_is_removed_on_success(self) -> None:
        with UploadWorkspace() as workspace:
            workspace.path.write_bytes(b"veri")
            directory = workspace.path.parent

        assert not directory.exists()

    def test_workspace_is_removed_on_exception(self) -> None:
        workspace = UploadWorkspace()
        path = workspace.path
        try:
            with workspace:
                path.write_bytes(b"veri")
                raise RuntimeError("hata")
        except RuntimeError:
            pass

        assert not path.parent.exists()

    def test_upload_limit_default_is_reasonable(self) -> None:
        assert DEFAULT_MAX_UPLOAD_BYTES == 10 * 1024 * 1024

    def test_upload_limit_is_configurable(self) -> None:
        settings = Settings(max_upload_bytes=1024)

        assert settings.max_upload_bytes == 1024

    def test_zero_upload_limit_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            Settings(max_upload_bytes=0)
