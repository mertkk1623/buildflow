"""``POST /api/report/excel`` ve ``POST /api/report/pdf`` testleri.

Kapsam
------
1.  İki endpoint de 200 döner ve doğru medya tipini/dosya adını verir.
2.  Gövde gerçek bir ``.xlsx`` / PDF'tir ve içeriği hesapla tutarlıdır.
3.  Boş istek (onaylanmış satır yok) → 422, boş dosya üretilmez.
4.  Geçersiz karar → 409 (``/api/calculate`` ile aynı gövde).
5.  İstemciden sahte hesaplama alanı → 422.
6.  Rapor içeriği ``/api/calculate`` yanıtıyla birebir aynıdır.
7.  İndirme başlıkları güvenli: dosya adı sunucudan, ``nosniff`` var.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pypdf import PdfReader

from app.reports.service import EXCEL_MEDIA_TYPE, PDF_MEDIA_TYPE
from tests.fixtures.api import analyze_ok, calculate, client_rows, decide, error_of
from tests.fixtures.demo_boq import EXPECTED_COUNTS, PREDEFINED_DECISIONS
from tests.fixtures.excel_files import build_demo_workbook

EXCEL_URL = "/api/report/excel"
PDF_URL = "/api/report/pdf"


def demo_decisions() -> list[dict[str, Any]]:
    return [
        decide(
            decision.row_no,
            decision.action.value,
            decision.code,
            decision.reason,
        )
        for decision in PREDEFINED_DECISIONS
    ]


@pytest.fixture(scope="module")
def demo_analysis(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    from app.main import app

    directory = tmp_path_factory.mktemp("api-report")
    workbook = build_demo_workbook(directory / "demo.xlsx")
    with TestClient(app) as test_client:
        return analyze_ok(test_client, workbook)


@pytest.fixture(scope="module")
def demo_rows(demo_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    return client_rows(demo_analysis)


@pytest.fixture()
def excel_response(client: TestClient, demo_rows: list[dict[str, Any]]):
    return client.post(
        EXCEL_URL, json={"rows": demo_rows, "decisions": demo_decisions()}
    )


@pytest.fixture()
def pdf_response(client: TestClient, demo_rows: list[dict[str, Any]]):
    return client.post(
        PDF_URL, json={"rows": demo_rows, "decisions": demo_decisions()}
    )


# ---------------------------------------------------------------------------
# 1. Başarılı indirme
# ---------------------------------------------------------------------------


class TestExcelEndpoint:
    def test_returns_xlsx(self, excel_response) -> None:
        assert excel_response.status_code == 200, excel_response.text
        assert excel_response.headers["content-type"] == EXCEL_MEDIA_TYPE
        assert excel_response.content[:2] == b"PK"

    def test_headers_are_safe(self, excel_response) -> None:
        disposition = excel_response.headers["content-disposition"]
        assert disposition.startswith("attachment;")
        assert disposition.endswith('.xlsx"')
        assert excel_response.headers["x-content-type-options"] == "nosniff"
        assert int(excel_response.headers["content-length"]) == len(
            excel_response.content
        )

    def test_filename_is_server_generated(self, excel_response) -> None:
        disposition = excel_response.headers["content-disposition"]
        # Tarih damgası sunucu saatinden gelir; istemci girdisi yoktur.
        assert "buildflow-satin-alma-" in disposition

    def test_content_matches_calculation(
        self, excel_response, demo_rows: list[dict[str, Any]]
    ) -> None:
        book = load_workbook(BytesIO(excel_response.content))
        sheet = book["Özet"]
        values = {
            row[0]: row[1]
            for row in sheet.iter_rows(values_only=True)
            if row[0]
        }
        assert values["Satın alma kalemi (grup)"] == 8
        assert values["FULL grup"] == 8
        assert values["PARTIAL grup"] == 0
        assert values["Toplam sipariş uzunluğu (m)"] == float(Decimal("966"))

        purchase = book["Satın Alma Listesi"]
        codes = [
            row[0]
            for row in purchase.iter_rows(values_only=True)
            if row[0] and str(row[0])[:1].isupper() and "-" in str(row[0])
        ]
        assert len(codes) == 8


class TestPdfEndpoint:
    def test_returns_pdf(self, pdf_response) -> None:
        assert pdf_response.status_code == 200, pdf_response.text
        assert pdf_response.headers["content-type"] == PDF_MEDIA_TYPE
        assert pdf_response.content.startswith(b"%PDF-")

    def test_headers_are_safe(self, pdf_response) -> None:
        disposition = pdf_response.headers["content-disposition"]
        assert disposition.startswith("attachment;")
        assert disposition.endswith('.pdf"')
        assert pdf_response.headers["x-content-type-options"] == "nosniff"

    def test_content_matches_calculation(self, pdf_response) -> None:
        reader = PdfReader(BytesIO(pdf_response.content))
        text = "\n".join(page.extract_text() for page in reader.pages)
        assert "Satın Alma Raporu" in text
        assert "966,000 m" in text
        assert "18.005,820 kg" in text
        assert "Sayfa 1 /" in text

    def test_all_groups_present(self, pdf_response) -> None:
        text = "\n".join(
            page.extract_text() for page in PdfReader(
                BytesIO(pdf_response.content)
            ).pages
        )
        for code in (
            "BOX-100-4-S235-B",
            "BOX-100-4-S235-G",
            "IPE-200-S235",
            "IPE-240-S355",
            "HEA-200-S235",
            "UPN-160-S235",
            "FLAT-40x5-S235-B",
            "BOX-150-100-5-S235-B",
        ):
            assert code in text


# ---------------------------------------------------------------------------
# 2. Rapor = /api/calculate
# ---------------------------------------------------------------------------


class TestConsistencyWithCalculateEndpoint:
    def test_excel_summary_matches_calculate_summary(
        self, client: TestClient, excel_response, demo_rows: list[dict[str, Any]]
    ) -> None:
        calculated = calculate(client, demo_rows, demo_decisions()).json()
        book = load_workbook(BytesIO(excel_response.content))
        values = {
            row[0]: row[1]
            for row in book["Özet"].iter_rows(values_only=True)
            if row[0]
        }
        summary = calculated["summary"]

        assert values["Girdi satırı"] == summary["input_rows"]
        assert values["Hesaplanan satır"] == summary["calculated_rows"]
        assert values["Hesaba alınmayan satır"] == summary["skipped_rows"]
        assert values["Satın alma kalemi (grup)"] == summary["groups"]
        assert values["Birleşme sayısı"] == summary["merges"]

    def test_pdf_totals_match_calculate_summary(
        self, client: TestClient, pdf_response, demo_rows: list[dict[str, Any]]
    ) -> None:
        summary = calculate(client, demo_rows, demo_decisions()).json()["summary"]
        text = "\n".join(
            page.extract_text() for page in PdfReader(
                BytesIO(pdf_response.content)
            ).pages
        )
        assert "Bilinen teorik ağırlık" in text
        # "18.005,820 kg" -> summary["known_weight_kg"] = "18005.820"
        expected = f"{Decimal(summary['known_weight_kg']):,.3f}"
        expected = expected.replace(",", "\x00").replace(".", ",").replace(
            "\x00", "."
        )
        assert expected in text

    def test_skipped_rows_match(self, client: TestClient, excel_response, demo_rows) -> None:
        calculated = calculate(client, demo_rows, demo_decisions()).json()
        book = load_workbook(BytesIO(excel_response.content))
        sheet = book["Hesaba Alınmayanlar"]
        boq_nos = {
            row[0]
            for row in sheet.iter_rows(values_only=True)
            if row[0] and str(row[0]).startswith("BOQ-")
        }

        assert boq_nos == {row["boq_no"] for row in calculated["skipped"]}
        assert len(boq_nos) == EXPECTED_COUNTS["pending"] + 1 + 3


# ---------------------------------------------------------------------------
# 3. Hata durumları
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_no_approved_rows_returns_422(self, client: TestClient) -> None:
        # Yalnızca onay bekleyen satır: hiç grup oluşmaz.
        rows = [
            {
                "source_row": 10,
                "boq_no": "BOQ-009",
                "description": "lama 40×5",
                "quantity": "180",
                "unit": "kg",
                "waste_percent": "5",
            }
        ]
        for url in (EXCEL_URL, PDF_URL):
            response = client.post(url, json={"rows": rows, "decisions": []})
            assert response.status_code == 422, url
            body = error_of(response)
            assert body["code"] == "report-empty"
            assert "onaylanmış" in body["message"].lower()
            assert body["suggestion"]

    def test_invalid_decision_returns_409(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        decisions = demo_decisions() + [
            decide("BOQ-001", "approve", "IPE-999-YOK")
        ]
        for url in (EXCEL_URL, PDF_URL):
            response = client.post(
                EXCEL_URL if url == EXCEL_URL else url,
                json={"rows": demo_rows, "decisions": decisions},
            )
            assert response.status_code == 409, url
            body = error_of(response)
            assert body["code"] == "invalid-decision"

    def test_decision_for_unknown_row_returns_409(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        decisions = [decide("BOQ-999", "reject")]
        response = client.post(
            PDF_URL, json={"rows": demo_rows, "decisions": decisions}
        )
        assert response.status_code == 409
        assert error_of(response)["code"] == "unknown-row"

    def test_client_cannot_send_computed_fields(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        tampered = [dict(row) for row in demo_rows]
        tampered[0]["weight_kg"] = "1"
        response = client.post(
            EXCEL_URL,
            json={"rows": tampered, "decisions": demo_decisions()},
        )
        assert response.status_code == 422
        assert error_of(response)["code"] == "validation-error"

    def test_empty_row_list_is_rejected_by_schema(self, client: TestClient) -> None:
        """``rows`` en az bir satır ister; boş liste şema düzeyinde reddedilir."""
        response = client.post(EXCEL_URL, json={"rows": [], "decisions": []})
        assert response.status_code == 422
        assert error_of(response)["code"] == "validation-error"


# ---------------------------------------------------------------------------
# 4. Bağımsızlık
# ---------------------------------------------------------------------------


class TestIndependence:
    def test_two_requests_do_not_share_state(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        first = client.post(
            EXCEL_URL, json={"rows": demo_rows, "decisions": demo_decisions()}
        )
        second = client.post(
            EXCEL_URL, json={"rows": demo_rows, "decisions": demo_decisions()}
        )
        assert first.status_code == second.status_code == 200

        def sheet_values(payload: bytes) -> list[tuple[Any, ...]]:
            return list(
                load_workbook(BytesIO(payload))["Satın Alma Listesi"]
                .iter_rows(values_only=True)
            )

        assert sheet_values(first.content) == sheet_values(second.content)

    def test_report_does_not_mutate_request(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        snapshot = [dict(row) for row in demo_rows]
        client.post(
            EXCEL_URL, json={"rows": demo_rows, "decisions": demo_decisions()}
        )
        assert demo_rows == snapshot
