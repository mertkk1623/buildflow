"""``POST /api/analyze`` testleri.

Kapsanan senaryolar:

1.  Geçerli Excel yükleme (18 satırlık demo)
2.  Bozuk Excel yükleme (ZIP imzası geçerli, içerik bozuk)
3.  Desteklenmeyen dosya formatı (``.csv``, ``.xls``, uzantısız)
4.  Eksik zorunlu kolon
5.  Invalid satırların ayrı ve doğru dönmesi
6.  Deterministik eşleştirme sonuçları
7.  Kullanıcı kararı gerektiren satırlar ve adaylar
8.  Kaynak Excel satır numarası ve BOQ No korunumu
9.  Geçici dosya temizliği
10. Eşzamanlı isteklerde veri karışmaması
"""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import uploads
from app.api.routes import XLSX_MEDIA_TYPE
from tests.fixtures.api import (
    analyze_ok,
    error_of,
    upload,
    upload_bytes,
)
from tests.fixtures.demo_boq import EXPECTED_DETERMINISTIC
from tests.fixtures.excel_files import build_demo_workbook, write_workbook

VALID_ROW = ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]


@pytest.fixture(scope="module")
def demo_workbook(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("api-demo")
    return build_demo_workbook(directory / "demo.xlsx")


# ---------------------------------------------------------------------------
# 1. Geçerli dosya
# ---------------------------------------------------------------------------


class TestValidUpload:
    def test_demo_file_returns_200(self, client: TestClient, demo_workbook: Path) -> None:
        response = upload(client, demo_workbook)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

    def test_all_18_rows_are_returned(self, client: TestClient, demo_workbook: Path) -> None:
        body = analyze_ok(client, demo_workbook)

        assert len(body["rows"]) == 18
        assert body["summary"]["total_rows"] == 18
        assert body["summary"]["valid_rows"] == 18
        assert body["summary"]["invalid_rows"] == 0

    def test_summary_distribution_matches_domain(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        """Deterministik dağılım: 10 rule + 4 pending + 4 excluded.

        (Aşama 4.3 dağılımı kararlar uygulanmadan önce pending=4, excluded=4
        verir; ``ai-approved``/``rejected`` yalnızca karar sonrası oluşur.)
        """
        summary = analyze_ok(client, demo_workbook)["summary"]

        assert summary["rule"] == 10
        assert summary["pending"] == 4
        assert summary["excluded"] == 4
        assert summary["invalid"] == 0
        assert summary["blank_rows_skipped"] == 0

    def test_sheet_name_is_reported(self, client: TestClient, demo_workbook: Path) -> None:
        body = analyze_ok(client, demo_workbook)

        assert body["sheet_name"]
        assert body["ignored_columns"] == []
        assert isinstance(body["warnings"], list)


# ---------------------------------------------------------------------------
# 2–3. Bozuk / desteklenmeyen dosya
# ---------------------------------------------------------------------------


class TestRejectedUploads:
    def test_corrupt_xlsx_returns_422(self, client: TestClient) -> None:
        # Uzantı ve ZIP imzası doğru, içerik bir Excel paketi değil.
        response = upload_bytes(client, b"PK\x03\x04" + b"\x00" * 128)

        assert response.status_code == 422
        assert error_of(response)["code"] == "corrupt-file"

    def test_non_zip_payload_with_xlsx_extension_returns_422(
        self, client: TestClient
    ) -> None:
        response = upload_bytes(client, b"bu bir excel dosyasi degil")

        assert response.status_code == 422
        assert error_of(response)["code"] == "corrupt-file"

    def test_empty_file_returns_422(self, client: TestClient) -> None:
        response = upload_bytes(client, b"")

        assert response.status_code == 422
        assert error_of(response)["code"] == "empty-file"

    @pytest.mark.parametrize("name", ["metraj.csv", "metraj.xls", "metraj.xlsm", "metraj.txt", "metraj"])
    def test_unsupported_format_returns_415(
        self, client: TestClient, tmp_path: Path, name: str
    ) -> None:
        # İçerik geçerli bir çalışma kitabı olsa bile uzantı reddedilir.
        workbook = write_workbook(tmp_path / "gercek.xlsx", [VALID_ROW])
        response = upload(client, workbook, filename=name)

        assert response.status_code == 415
        body = error_of(response)
        assert body["code"] == "unsupported-format"
        assert ".xlsx" in body["suggestion"]

    def test_path_traversal_in_filename_is_not_trusted(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        """``../../x.xlsx`` gibi ad yalnızca uzantı olarak değerlendirilir."""
        response = upload(client, demo_workbook, filename="../../etc/passwd.xlsx")

        assert response.status_code == 200
        assert len(response.json()["rows"]) == 18

    def test_upload_size_limit_is_enforced(self, client: TestClient) -> None:
        """Sınır aşılırsa 413 döner ve dosya tamamen yazılmaz."""
        payload = b"PK\x03\x04" + b"\x00" * 4096

        from app.config import get_settings

        settings = get_settings()
        previous = settings.max_upload_bytes
        settings.max_upload_bytes = 1024
        try:
            response = upload_bytes(client, payload)
        finally:
            settings.max_upload_bytes = previous

        assert response.status_code == 413
        assert error_of(response)["code"] == "file-too-large"

    def test_upload_size_limit_message_reports_megabytes(
        self, client: TestClient
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        previous = settings.max_upload_bytes
        settings.max_upload_bytes = 2 * 1024 * 1024
        try:
            response = upload_bytes(client, b"PK\x03\x04" + b"\x00" * (3 * 1024 * 1024))
        finally:
            settings.max_upload_bytes = previous

        assert response.status_code == 413
        assert "2 MB" in response.json()["error"]["detail"]


# ---------------------------------------------------------------------------
# 4. Eksik kolon
# ---------------------------------------------------------------------------


class TestMissingColumns:
    def test_missing_unit_column_returns_422(self, client: TestClient, tmp_path: Path) -> None:
        path = write_workbook(
            tmp_path / "eksik.xlsx",
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96]],
            headers=("BOQ No", "Açıklama", "Miktar"),
        )

        response = upload(client, path)

        assert response.status_code == 422
        body = error_of(response)
        assert body["code"] == "missing-column"
        assert "Birim" in body["message"]

    def test_missing_boq_no_column_returns_422(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(
            tmp_path / "eksik2.xlsx",
            [["BOX 100×100×4 S235 siyah", 96, "m", 5]],
            headers=("Açıklama", "Miktar", "Birim", "Fire (%)"),
        )

        response = upload(client, path)

        assert response.status_code == 422
        assert error_of(response)["code"] == "missing-column"

    def test_missing_header_row_returns_422(self, client: TestClient, tmp_path: Path) -> None:
        path = write_workbook(tmp_path / "basliksiz.xlsx", [VALID_ROW], headers=None)

        response = upload(client, path)

        assert response.status_code == 422
        assert error_of(response)["code"] == "no-header-row"

    def test_error_does_not_leak_server_path(self, client: TestClient, tmp_path: Path) -> None:
        path = write_workbook(tmp_path / "eksik3.xlsx", [VALID_ROW], headers=("BOQ No",))
        response = upload(client, path)

        assert response.status_code == 422
        text = response.text
        assert str(tmp_path) not in text
        assert tempfile.gettempdir() not in text
        assert "buildflow-metraj-" not in text


# ---------------------------------------------------------------------------
# 5. Invalid satırlar
# ---------------------------------------------------------------------------


class TestInvalidRows:
    def test_invalid_rows_are_reported_separately(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(
            tmp_path / "karisik.xlsx",
            [
                VALID_ROW,
                ["BOQ-002", "IPE 200 S235 siyah", "abc", "m", 3],
                ["BOQ-003", "HEA 200 S235 siyah", -5, "m", 3],
            ],
        )

        body = analyze_ok(client, path)

        assert body["summary"]["valid_rows"] == 1
        assert body["summary"]["invalid_rows"] == 2
        statuses = {row["boq_no"]: row["status"] for row in body["rows"]}
        assert statuses["BOQ-001"] == "rule"
        assert statuses["BOQ-002"] == "invalid"
        assert statuses["BOQ-003"] == "invalid"

    def test_invalid_row_keeps_reason_and_suggestion(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(
            tmp_path / "hatali.xlsx",
            [["BOQ-001", "BOX 100×100×4 S235 siyah", "abc", "m", 5]],
        )

        body = analyze_ok(client, path)
        row = body["rows"][0]

        assert row["status"] == "invalid"
        assert row["match"]["status"] == "invalid"
        assert row["match"]["matched_code"] is None
        assert row["issues"], "hata nedeni ve açıklaması korunmalı"
        issue = row["issues"][0]
        assert issue["code"] == "invalid-quantity"
        assert issue["column"] == "Miktar"
        assert issue["message"]
        assert issue["suggestion"]
        assert issue["source_row"] == row["source_row"]
        assert issue["boq_no"] == row["boq_no"]

    def test_invalid_row_never_gets_matched_code(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(
            tmp_path / "hatali2.xlsx",
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", None, "m", 5],
                ["BOQ-002", "BOX 100×100×4 S235 siyah", 0, "m", 5],
            ],
        )

        body = analyze_ok(client, path)

        for row in body["rows"]:
            assert row["status"] == "invalid"
            assert row["match"]["matched_code"] is None
            assert row["match"]["candidate_codes"] == []

    def test_duplicate_boq_no_flags_all_valid_rows(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(
            tmp_path / "yinelenen.xlsx",
            [
                VALID_ROW,
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 60, "m", 5],
            ],
        )

        body = analyze_ok(client, path)
        reasons = [
            issue["code"]
            for row in body["rows"]
            for issue in row["issues"]
        ]

        assert reasons.count("duplicate-boq-no") == 2


# ---------------------------------------------------------------------------
# 6. Deterministik eşleştirme
# ---------------------------------------------------------------------------


class TestDeterministicMatching:
    def test_every_row_matches_expected_domain_outcome(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        body = analyze_ok(client, demo_workbook)
        actual = {
            row["boq_no"]: (row["status"], row["match"]["matched_code"])
            for row in body["rows"]
        }

        assert actual == EXPECTED_DETERMINISTIC

    def test_repeated_upload_produces_identical_body(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        """Aynı dosya iki kez aynı sıra ve içerikle sonuçlanır."""
        first = analyze_ok(client, demo_workbook)
        second = analyze_ok(client, demo_workbook)

        assert first == second

    def test_matching_is_independent_of_upload_order(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """Sıra değişse de satırların kendi sonucu değişmez."""
        rows = [
            VALID_ROW,
            ["BOQ-002", "UPN 160 S235 siyah", 54, "m", 4],
            ["BOQ-003", "lama 40×5", 180, "kg", 5],
        ]
        forward = write_workbook(tmp_path / "ileri.xlsx", rows)
        backward = write_workbook(tmp_path / "geri.xlsx", list(reversed(rows)))

        def by_boq(payload: dict) -> dict:
            return {
                row["boq_no"]: (row["status"], row["match"]["matched_code"])
                for row in payload["rows"]
            }

        assert by_boq(analyze_ok(client, forward)) == by_boq(analyze_ok(client, backward))


# ---------------------------------------------------------------------------
# 7. Karar gerektiren satırlar
# ---------------------------------------------------------------------------


class TestPendingRows:
    def test_pending_rows_expose_candidates(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        body = analyze_ok(client, demo_workbook)
        pending = [row for row in body["rows"] if row["status"] == "pending"]

        assert [row["boq_no"] for row in pending] == [
            "BOQ-003",
            "BOQ-004",
            "BOQ-006",
            "BOQ-009",
        ]
        for row in pending:
            match = row["match"]
            assert match["matched_code"] is None
            assert match["candidate_codes"], "aday kodsuz pending satır olamaz"
            assert match["message"]

    def test_candidates_are_enriched_from_catalog(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        body = analyze_ok(client, demo_workbook)
        row = next(row for row in body["rows"] if row["boq_no"] == "BOQ-003")
        candidate = row["match"]["candidates"][0]

        assert candidate["code"] == "IPE-200-S235"
        assert candidate["family"] == "IPE"
        assert candidate["size"] == "200"
        assert candidate["grade"] == "S235"
        assert candidate["coating"] == "siyah"
        assert candidate["label"]
        assert Decimal(candidate["mass_kg_per_m"]) > 0
        assert Decimal(candidate["commercial_length_m"]) > 0

    def test_pending_does_not_claim_a_match(self, client: TestClient, demo_workbook: Path) -> None:
        """Sunucu karar vermeden ``matched_code`` üretmez."""
        body = analyze_ok(client, demo_workbook)

        for row in body["rows"]:
            if row["status"] == "pending":
                assert row["match"]["matched_code"] is None

    def test_excluded_rows_are_not_marked_invalid(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        """Kapsam dışı (excluded) ile hatalı (invalid) ayrı tutulur."""
        body = analyze_ok(client, demo_workbook)
        excluded = {row["boq_no"]: row for row in body["rows"] if row["status"] == "excluded"}

        assert set(excluded) == {"BOQ-012", "BOQ-014", "BOQ-015", "BOQ-018"}
        reasons = {row["match"]["exclusion_reason"] for row in excluded.values()}
        assert reasons == {"waste", "unit", "catalog"}
        for row in excluded.values():
            assert row["match"]["matched_code"] is None
            # Kapsam dışı nedeni her zaman açıklanır: birim/fire/katalog için
            # eşleştirme mesajı, ``adet`` gibi okuma düzeyi durumlarda ``issues``.
            assert row["match"]["message"]
        # ``adet`` birimi okuma katmanında da raporlanır (satır korunur).
        assert excluded["BOQ-014"]["issues"][0]["code"] == "unit"


# ---------------------------------------------------------------------------
# 8. Kaynak izlenebilirliği
# ---------------------------------------------------------------------------


class TestTraceability:
    def test_source_row_is_real_excel_row(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        """Başlık 1. satırda; ilk veri satırı Excel'de 2. satırdır."""
        body = analyze_ok(client, demo_workbook)

        assert [row["source_row"] for row in body["rows"]] == list(range(2, 20))

    def test_source_row_survives_blank_rows(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(
            tmp_path / "bosluklu.xlsx",
            [VALID_ROW, [None, None, None, None, None], ["BOQ-002", "UPN 160 S235 siyah", 54, "m", 4]],
        )

        body = analyze_ok(client, path)

        assert [row["source_row"] for row in body["rows"]] == [2, 4]
        assert body["summary"]["blank_rows_skipped"] == 1

    def test_boq_numbers_are_preserved_verbatim(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        path = write_workbook(
            tmp_path / "ozel.xlsx",
            [["MT-2026/001", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
        )

        body = analyze_ok(client, path)

        assert body["rows"][0]["boq_no"] == "MT-2026/001"

    def test_quantities_are_exact_strings(self, client: TestClient, demo_workbook: Path) -> None:
        """Decimal değerler string taşınır; float yuvarlaması yok."""
        body = analyze_ok(client, demo_workbook)
        row = next(row for row in body["rows"] if row["boq_no"] == "BOQ-004")

        assert isinstance(row["quantity"], str)
        assert row["quantity"] == "0.84"
        assert row["waste_percent"] == "3"


# ---------------------------------------------------------------------------
# 9. Geçici dosya temizliği
# ---------------------------------------------------------------------------


class TestTempFileCleanup:
    def test_successful_analysis_leaves_no_files(
        self,
        client: TestClient,
        demo_workbook: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        created: list[Path] = []
        original = uploads.UploadWorkspace.__init__

        def tracking_init(self) -> None:  # type: ignore[no-untyped-def]
            original(self)
            created.append(self.path)

        temp_root = Path(tempfile.gettempdir())
        before = set(temp_root.glob("buildflow-metraj-*"))

        monkeypatch.setattr(uploads.UploadWorkspace, "__init__", tracking_init)
        upload(client, demo_workbook)

        after = set(temp_root.glob("buildflow-metraj-*"))
        assert after == before, "geçici dizin işlem sonrası silinmeli"
        assert created, "geçici dosya gerçekten oluşturulmuş olmalı"
        for path in created:
            assert not path.exists()
            assert not path.parent.exists()

    def test_failed_analysis_leaves_no_files(self, client: TestClient) -> None:
        before = set(Path(tempfile.gettempdir()).glob("buildflow-metraj-*"))

        upload_bytes(client, b"PK\x03\x04bozuk")

        after = set(Path(tempfile.gettempdir()).glob("buildflow-metraj-*"))
        assert after == before, "hata durumunda da geçici dizin silinmeli"

    def test_no_analysis_result_is_kept_in_memory(
        self, client: TestClient, demo_workbook: Path
    ) -> None:
        """Analiz sonrası süreçte satır saklanmaz; ikinci istek dosya ister."""
        analyze_ok(client, demo_workbook)

        # Aynı içerik yüklenmeden hesaplama çağrısı satırları kendisi taşımalı.
        response = client.post("/api/calculate", json={"rows": [], "decisions": []})

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 10. Eşzamanlılık
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_concurrent_uploads_do_not_mix_data(self, tmp_path: Path) -> None:
        """Farklı dosyalar aynı anda yüklenince veri karışmaz."""
        from app.main import app

        workbook_a = write_workbook(
            tmp_path / "a.xlsx",
            [["BOQ-A1", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
        )
        workbook_b = write_workbook(
            tmp_path / "b.xlsx",
            [["BOQ-B1", "UPN 160 S235 siyah", 54, "m", 4]],
        )

        def run(path: Path) -> dict:
            with TestClient(app) as test_client:
                return analyze_ok(test_client, path)

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(run, [workbook_a, workbook_b] * 4))

        for index, payload in enumerate(results):
            expected = "BOQ-A1" if index % 2 == 0 else "BOQ-B1"
            assert [row["boq_no"] for row in payload["rows"]] == [expected]

    def test_two_different_analyses_stay_independent(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        first = write_workbook(
            tmp_path / "bir.xlsx",
            [["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5]],
        )
        second = write_workbook(
            tmp_path / "iki.xlsx",
            [
                ["BOQ-001", "BOX 100×100×4 S235 siyah", 96, "m", 5],
                ["BOQ-002", "HEA 200 S235 siyah", 132, "m", 4],
            ],
        )

        body_first = analyze_ok(client, first)
        body_second = analyze_ok(client, second)

        assert len(body_first["rows"]) == 1
        assert len(body_second["rows"]) == 2
        # İlk isteğin satırları ikinciye sızmamış olmalı.
        assert body_first["rows"] == body_second["rows"][:1]


def test_analyze_requires_file_field(client: TestClient) -> None:
    response = client.post("/api/analyze")

    assert response.status_code == 422
    assert error_of(response)["code"] == "validation-error"


def test_analyze_returns_json_media_type(client: TestClient, demo_workbook: Path) -> None:
    response = upload(client, demo_workbook)

    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-type"] != XLSX_MEDIA_TYPE
