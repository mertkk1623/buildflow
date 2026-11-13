"""API testleri için ortak yardımcılar.

Testler gerçek ``TestClient`` üzerinden gider: router, hata yönetimi ve
Pydantic serileştirmesi dahil tüm HTTP katmanı çalışır. Excel dosyaları
:mod:`tests.fixtures.excel_files` ile gerçek ``.xlsx`` olarak üretilir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

#: Excel MIME tipi — yüklemede istemcinin gönderdiği tip.
XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

#: İstemcinin ``/api/calculate`` isteğinde gönderebileceği **tek** satır alanları.
#: Bu liste bilinçli olarak dardır: eşleştirme durumu ve hesaplanmış değerler
#: istemciden kabul edilmez.
CLIENT_ROW_FIELDS: tuple[str, ...] = (
    "source_row",
    "boq_no",
    "description",
    "quantity",
    "unit",
    "waste_percent",
)


def upload(
    client: TestClient,
    path: str | Path,
    *,
    filename: str = "metraj.xlsx",
    content_type: str = XLSX_MEDIA_TYPE,
    field: str = "file",
) -> Any:
    """Dosyayı ``/api/analyze`` ucuna multipart olarak gönderir."""
    with Path(path).open("rb") as handle:
        return client.post(
            "/api/analyze",
            files={field: (filename, handle.read(), content_type)},
        )


def upload_bytes(
    client: TestClient,
    payload: bytes,
    *,
    filename: str = "metraj.xlsx",
    content_type: str = XLSX_MEDIA_TYPE,
) -> Any:
    """Bellekteki baytları yükler (bozuk/yanıltıcı dosya senaryoları)."""
    return client.post(
        "/api/analyze",
        files={"file": (filename, payload, content_type)},
    )


def analyze_ok(client: TestClient, path: str | Path) -> dict[str, Any]:
    """Analiz isteğini yapar ve 200 olduğunu doğrular."""
    response = upload(client, path)
    assert response.status_code == 200, response.text
    return response.json()


def client_rows(analyze_payload: dict[str, Any], *, include_excluded: bool = True) -> list[dict[str, Any]]:
    """Analiz yanıtından ``/api/calculate`` için **ham** satır listesi üretir.

    Yalnızca istemcinin göndermesine izin verilen alanlar kopyalanır; durum ve
    kod gibi sunucu ürettiği alanlar bilinçli olarak taşınmaz. Geçersiz satırlar
    (miktarı okunamayanlar) atlanır — bunlar zaten hesaplanamaz.
    """
    rows: list[dict[str, Any]] = []
    for row in analyze_payload["rows"]:
        if row["quantity"] is None or row["boq_no"] is None:
            continue
        if not include_excluded and row["status"] != "rule":
            continue
        rows.append({field: row[field] for field in CLIENT_ROW_FIELDS})
    return rows


def decide(boq_no: str, action: str, code: str | None = None, reason: str = "") -> dict[str, Any]:
    """Tek kullanıcı kararı — yalnızca izin verilen alanlar."""
    return {"boq_no": boq_no, "action": action, "code": code, "reason": reason}


def calculate(
    client: TestClient,
    rows: list[dict[str, Any]],
    decisions: list[dict[str, Any]] | None = None,
) -> Any:
    return client.post(
        "/api/calculate",
        json={"rows": rows, "decisions": decisions or []},
    )


def error_of(response: Any) -> dict[str, Any]:
    """Hata zarfını döndürür ve biçimini doğrular."""
    payload = response.json()
    assert set(payload) == {"error"}, payload
    body = payload["error"]
    assert set(body) == {"code", "message", "detail", "suggestion", "issues"}, body
    return body
