"""``POST /api/calculate`` testleri.

Kapsanan senaryolar:

1.  Geçerli kullanıcı kararıyla hesaplama (demo: 8 grup, 966 m, 18.005,820 kg)
2.  Geçersiz ürün kodu → 409
3.  Başka BOQ satırına ait karar → 409
4.  Açıklamayla çelişen onay → 409
5.  İstemciden sahte hesaplama sonucu → 422 (alanlar şemada yok)
6.  Decimal değerlerin JSON'da string taşınması
7.  FULL/PARTIAL durumları
8.  İki isteğin birbirinden bağımsızlığı
9.  Eşzamanlı isteklerde veri karışmaması
10. Kaynak satır izlenebilirliği (``source_boq_nos`` + ``sources``)
"""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.mapping import calculation_summary, group_to_out
from app.api.schemas import CalculateResponse
from app.domain.calculation import (
    CalculationInputRow,
    MatchStatus,
    WasteRate,
    calculate_purchase_list,
)
from app.domain.catalog import get_catalog
from tests.fixtures.api import (
    CLIENT_ROW_FIELDS,
    analyze_ok,
    calculate,
    client_rows,
    decide,
    error_of,
)
from tests.fixtures.demo_boq import EXPECTED_COUNTS, PREDEFINED_DECISIONS
from tests.fixtures.excel_files import build_demo_workbook

#: Demo metrajın kilitli hesap sonuçları (Aşama 4.2/4.3 ile birebir).
EXPECTED_ORDER_LENGTH_M = "966"
EXPECTED_WEIGHT_KG = "18005.820"
EXPECTED_GROUP_COUNT = 8
EXPECTED_MERGES = 5


def demo_decisions() -> list[dict[str, Any]]:
    """Demo dosyasının önceden tanımlı kararları — istemci biçiminde."""
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
    """Demo Excel'in analiz yanıtı (modül düzeyinde bir kez üretilir)."""
    from app.main import app

    directory = tmp_path_factory.mktemp("api-calculate")
    workbook = build_demo_workbook(directory / "demo.xlsx")
    with TestClient(app) as test_client:
        return analyze_ok(test_client, workbook)


@pytest.fixture()
def demo_rows(demo_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    return client_rows(demo_analysis)


# ---------------------------------------------------------------------------
# 1. Geçerli kararlarla hesaplama
# ---------------------------------------------------------------------------


class TestValidCalculation:
    def test_demo_decisions_reproduce_locked_result(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        response = calculate(client, demo_rows, demo_decisions())

        assert response.status_code == 200, response.text
        body = response.json()
        summary = body["summary"]
        assert summary["groups"] == EXPECTED_GROUP_COUNT
        assert summary["calculated_rows"] == 13
        assert summary["skipped_rows"] == 5
        assert summary["merges"] == EXPECTED_MERGES
        assert summary["total_order_length_m"] == EXPECTED_ORDER_LENGTH_M
        assert summary["known_weight_kg"] == EXPECTED_WEIGHT_KG
        assert summary["weight_complete"] is True

    def test_group_codes_and_weights_match_domain(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        weights = {group["code"]: group["weight_kg"] for group in body["groups"]}

        assert weights == {
            "BOX-100-4-S235-B": "2246.40",
            "BOX-100-4-S235-G": "631.80",
            "IPE-200-S235": "1344.00",
            "IPE-240-S355": "1473.60",
            "HEA-200-S235": "9136.80",
            "UPN-160-S235": "1579.20",
            "FLAT-40x5-S235-B": "386.220",
            "BOX-150-100-5-S235-B": "1207.80",
        }

    def test_every_eligible_row_is_accounted_for(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()

        assert body["summary"]["input_rows"] == len(demo_rows) == 18
        assert (
            body["summary"]["calculated_rows"] + body["summary"]["skipped_rows"]
            == body["summary"]["input_rows"]
        )

    def test_skipped_rows_keep_reason_and_status(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        skipped = {row["boq_no"]: row for row in body["skipped"]}

        assert skipped["BOQ-009"]["status"] == "pending"
        assert skipped["BOQ-012"]["status"] == "excluded"
        assert skipped["BOQ-014"]["status"] == "excluded"
        assert skipped["BOQ-015"]["status"] == "excluded"
        assert skipped["BOQ-018"]["status"] == "rejected"
        for row in skipped.values():
            assert row["message"]
            assert row["match_status"] in {
                "rule",
                "ai-approved",
                "pending",
                "rejected",
                "excluded",
                "invalid",
            }

    def test_decisions_are_required_for_pending_rows(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """Karar verilmeyen ``pending`` satır sessizce onaylanmaz."""
        body = calculate(client, demo_rows, []).json()

        assert body["summary"]["calculated_rows"] == 10
        assert body["summary"]["skipped_rows"] == 8
        pending = [row for row in body["skipped"] if row["status"] == "pending"]
        assert {row["boq_no"] for row in pending} == {
            "BOQ-003",
            "BOQ-004",
            "BOQ-006",
            "BOQ-009",
        }

    def test_reject_decision_removes_row_from_calculation(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        decisions = demo_decisions() + [decide("BOQ-001", "reject", reason="Demo reddi")]
        body = calculate(client, demo_rows, decisions).json()

        assert "BOX-100-4-S235-B" in {group["code"] for group in body["groups"]}
        box = next(g for g in body["groups"] if g["code"] == "BOX-100-4-S235-B")
        assert box["source_boq_nos"] == ["BOQ-013"]
        assert any(
            row["boq_no"] == "BOQ-001" and row["status"] == "rejected"
            for row in body["skipped"]
        )


# ---------------------------------------------------------------------------
# 2–4. Geçersiz kararlar
# ---------------------------------------------------------------------------


class TestInvalidDecisions:
    def test_unknown_product_code_returns_409(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        decisions = [decide("BOQ-003", "approve", "IPE-999-S235")]

        response = calculate(client, demo_rows, decisions)

        assert response.status_code == 409
        body = error_of(response)
        assert body["code"] == "invalid-decision"
        assert "IPE-999-S235" in body["detail"]
        assert body["issues"][0]["boq_no"] == "BOQ-003"
        assert body["issues"][0]["code"] == "IPE-999-S235"

    def test_decision_for_row_outside_request_returns_409(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        decisions = [decide("BOQ-999", "approve", "IPE-200-S235")]

        response = calculate(client, demo_rows, decisions)

        assert response.status_code == 409
        body = error_of(response)
        assert body["code"] == "unknown-row"
        assert "BOQ-999" in body["detail"]

    def test_decision_cannot_be_moved_between_rows(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """Başka satırın onayı bu satıra uygulanamaz (açıklama çelişir)."""
        # BOQ-007 "UPN 160 S235 siyah" → IPE kodu açıkça çelişir.
        decisions = [decide("BOQ-007", "approve", "IPE-200-S235")]

        response = calculate(client, demo_rows, decisions)

        assert response.status_code == 409
        body = error_of(response)
        assert body["code"] == "invalid-decision"
        assert "çelişiyor" in body["detail"]

    def test_approve_without_code_returns_409(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        decisions = [decide("BOQ-003", "approve", None)]

        response = calculate(client, demo_rows, decisions)

        assert response.status_code == 409
        assert "kod" in error_of(response)["detail"].lower()

    def test_duplicate_decision_for_same_row_returns_422(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        decisions = [
            decide("BOQ-003", "approve", "IPE-200-S235"),
            decide("BOQ-003", "reject"),
        ]

        response = calculate(client, demo_rows, decisions)

        assert response.status_code == 422
        assert error_of(response)["code"] == "duplicate-decision"

    def test_quantity_quality_conflict_is_rejected(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """``BOQ-018`` S355 ister; katalogda IPE 200 yalnızca S235 var."""
        decisions = [decide("BOQ-018", "approve", "IPE-200-S235")]

        response = calculate(client, demo_rows, decisions)

        assert response.status_code == 409
        body = error_of(response)
        assert body["code"] == "invalid-decision"
        assert "kalite" in body["detail"]


# ---------------------------------------------------------------------------
# 5. Sahte istemci verisi
# ---------------------------------------------------------------------------


class TestClientCannotForgeResults:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("match_status", "ai-approved"),
            ("matched_code", "IPE-200-S235"),
            ("matchedCode", "IPE-200-S235"),
            ("weight_kg", "1"),
            ("weightKg", "1"),
            ("order_length_m", "1"),
            ("orderLengthM", "1"),
            ("gross_metres", "1"),
            ("status", "rule"),
            ("candidate_codes", ["IPE-200-S235"]),
            ("bar_count", "1"),
        ],
    )
    def test_forged_row_field_returns_422(
        self,
        client: TestClient,
        demo_rows: list[dict[str, Any]],
        field: str,
        value: Any,
    ) -> None:
        rows = [dict(demo_rows[0])]
        rows[0][field] = value

        response = calculate(client, rows, [])

        assert response.status_code == 422, response.text
        body = error_of(response)
        assert body["code"] == "validation-error"
        assert field in body["issues"][0]["message"]

    @pytest.mark.parametrize(
        "field,value",
        [
            ("match_status", "ai-approved"),
            ("matched_code", "IPE-200-S235"),
            ("status", "rejected"),
            ("weight_kg", "0"),
        ],
    )
    def test_forged_decision_field_returns_422(
        self,
        client: TestClient,
        demo_rows: list[dict[str, Any]],
        field: str,
        value: Any,
    ) -> None:
        decision = decide("BOQ-003", "approve", "IPE-200-S235")
        decision[field] = value

        response = calculate(client, demo_rows, [decision])

        assert response.status_code == 422, response.text
        assert error_of(response)["code"] == "validation-error"

    def test_client_cannot_mark_row_approved_by_sending_status(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """``matched_code`` gönderilse bile sunucu kendi eşleştirmesini yapar."""
        rows = [dict(row) for row in demo_rows]
        for row in rows:
            if row["boq_no"] == "BOQ-009":
                row["match_status"] = "ai-approved"
                row["matched_code"] = "FLAT-40x5-S235-B"

        response = calculate(client, rows, [])

        # Şema dışı alan → istek reddedilir; sunucu bu veriyi hiç görmez.
        assert response.status_code == 422

    def test_unknown_row_content_is_recomputed_not_trusted(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """Satır açıklaması değişirse sonuç da değişir; kod istemciden gelmez."""
        rows = [dict(row) for row in demo_rows]
        for row in rows:
            if row["boq_no"] == "BOQ-001":
                row["description"] = "HEA 200 S235 siyah"

        body = calculate(client, rows, demo_decisions()).json()

        codes = {group["code"] for group in body["groups"]}
        assert "HEA-200-S235" in codes
        assert "BOX-100-4-S235-B" in codes  # BOQ-013 hâlâ kutu profil
        box = next(g for g in body["groups"] if g["code"] == "BOX-100-4-S235-B")
        assert box["source_boq_nos"] == ["BOQ-013"]

    def test_quantities_come_from_client_but_are_recalculated(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """Miktar ham girdidir; ağırlık yine sunucuda hesaplanır."""
        baseline = calculate(client, demo_rows, demo_decisions()).json()
        baseline_hea = next(
            g for g in baseline["groups"] if g["code"] == "HEA-200-S235"
        )

        rows = [dict(row) for row in demo_rows]
        for row in rows:
            if row["boq_no"] == "BOQ-005":
                row["quantity"] = "264"  # 132 → 264 m

        body = calculate(client, rows, demo_decisions()).json()
        hea = next(g for g in body["groups"] if g["code"] == "HEA-200-S235")

        assert hea["source_boq_nos"] == ["BOQ-005", "BOQ-006"]
        # Sunucu, istemcinin verdiği miktarı kendi ekseninde yeniden hesaplar.
        assert Decimal(hea["total_gross_metres"]) > Decimal(
            baseline_hea["total_gross_metres"]
        )
        assert Decimal(hea["weight_kg"]) > Decimal(baseline_hea["weight_kg"])


# ---------------------------------------------------------------------------
# 6. Decimal serileştirmesi
# ---------------------------------------------------------------------------


class TestDecimalSerialization:
    def test_all_numeric_fields_are_json_strings(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        numeric = (
            "mass_kg_per_m",
            "commercial_length_m",
            "bar_count",
            "total_gross_metres",
            "order_length_m",
            "rounding_surplus_m",
            "weight_kg",
        )

        for group in body["groups"]:
            for field in numeric:
                value = group[field]
                if value is not None:
                    assert isinstance(value, str), (group["code"], field, value)

        summary_numeric = ("total_order_length_m", "known_weight_kg")
        for field in summary_numeric:
            value = body["summary"][field]
            if value is not None:
                assert isinstance(value, str)

    def test_no_scientific_notation(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        raw = calculate(client, demo_rows, demo_decisions()).text

        assert "E+" not in raw
        assert "e+" not in raw

    def test_missing_values_are_null_not_zero(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, []).json()
        pending_groups = [g for g in body["groups"]]

        # Demo'da PARTIAL grup yok; ama alanlar null/str ayrımını korur.
        for group in pending_groups:
            assert "weight_kg" in group
            if group["weight_kg"] is None:
                assert group["status"] == "PARTIAL"

    def test_source_quantities_are_strings(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        ipe = next(g for g in body["groups"] if g["code"] == "IPE-200-S235")
        source = ipe["sources"][0]

        assert source["source_quantity"] == "1240"
        assert isinstance(source["source_quantity"], str)
        assert isinstance(source["gross_quantity"], str)
        assert source["waste_percent"] == "3"

    def test_zero_waste_is_zero_not_null(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        rows = [dict(row) for row in demo_rows]
        rows[0]["waste_percent"] = "0"

        body = calculate(client, rows, demo_decisions()).json()
        group = next(g for g in body["groups"] if g["code"] == "BOX-100-4-S235-B")
        source = next(s for s in group["sources"] if s["boq_no"] == "BOQ-001")

        assert source["waste_percent"] == "0"
        assert source["waste_source"] == "row"


# ---------------------------------------------------------------------------
# 7. FULL / PARTIAL
# ---------------------------------------------------------------------------


class TestFullPartial:
    def test_demo_groups_are_all_full(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()

        assert body["summary"]["full_groups"] == EXPECTED_GROUP_COUNT
        assert body["summary"]["partial_groups"] == 0
        for group in body["groups"]:
            assert group["status"] == "FULL"
            assert group["missing_fields"] == []
            assert group["missing"] == []

    def test_approving_waste_less_row_makes_group_partial(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """``BOQ-012``'de fire yok. Onaylanırsa grup PARTIAL olur, sıfır varsayılmaz."""
        decisions = demo_decisions() + [
            decide("BOQ-012", "approve", "BOX-100-4-S235-B", "Fire yok, bilinçli onay.")
        ]

        response = calculate(client, demo_rows, decisions)

        assert response.status_code == 200, response.text
        body = response.json()
        box = next(g for g in body["groups"] if g["code"] == "BOX-100-4-S235-B")

        assert box["status"] == "PARTIAL"
        assert box["missing_fields"] == ["fire"]
        assert box["order_length_m"] is None
        assert box["weight_kg"] is None
        assert box["rounding_surplus_m"] is None
        # Satır yine de grupta izlenebilir; fire alanı null.
        skipped_source = next(s for s in box["sources"] if s["boq_no"] == "BOQ-012")
        assert skipped_source["waste_percent"] is None
        assert skipped_source["gross_metres"] is None
        assert skipped_source["waste_source"] == "none"

        assert body["summary"]["partial_groups"] == 1
        assert body["summary"]["full_groups"] == EXPECTED_GROUP_COUNT - 1
        assert body["summary"]["weight_complete"] is False
        assert any("PARTIAL" in warning for warning in body["warnings"])
        assert any("ağırlık" in warning for warning in body["warnings"])

    def test_partial_group_serialises_with_nulls_and_reason(self) -> None:
        """Bilinmeyen birim kütle → PARTIAL; alanlar null, neden açık.

        Katalog her kalemde ``kg/m`` ve ticari boy taşıdığı için API üzerinden
        PARTIAL üretilemez; bu senaryo hesap motorunun geçersiz kılma yoluyla
        kurulup **API modeli** üzerinden serileştirilir.
        """
        catalog = get_catalog()
        code = "IPE-200-S235"
        item = catalog.require(code)
        rows = [
            CalculationInputRow(
                row_no="BOQ-001",
                description=item.describe,
                quantity=Decimal("100"),
                unit="m",
                waste_rate=WasteRate.from_percent(5),
                status=MatchStatus.RULE,
                matched_code=code,
            )
        ]

        result = calculate_purchase_list(rows, catalog, mass_overrides={code: None})
        group = result.groups[0]
        assert group.status.value == "PARTIAL"

        payload = CalculateResponse(
            groups=[group_to_out(group)],
            skipped=[],
            summary=calculation_summary(result),
        ).model_dump(mode="json")

        out = payload["groups"][0]
        assert out["status"] == "PARTIAL"
        assert out["missing_fields"] == ["mass"]
        assert out["weight_kg"] is None
        assert out["order_length_m"] == "108"
        assert out["missing"][0]["message"]
        assert payload["summary"]["weight_complete"] is False

    def test_partial_warning_is_reported(self) -> None:
        catalog = get_catalog()
        code = "UPN-160-S235"
        item = catalog.require(code)
        rows = [
            CalculationInputRow(
                row_no="BOQ-001",
                description=item.describe,
                quantity=Decimal("50"),
                unit="m",
                waste_rate=WasteRate.from_percent(0),
                status=MatchStatus.RULE,
                matched_code=code,
            )
        ]
        result = calculate_purchase_list(
            rows, catalog, commercial_length_overrides={code: None}
        )

        out = group_to_out(result.groups[0])

        assert out.status == "PARTIAL"
        assert "commercial-length" in out.missing_fields
        assert out.order_length_m is None
        assert out.commercial_length_m is None


# ---------------------------------------------------------------------------
# 8. İstek bağımsızlığı
# ---------------------------------------------------------------------------


class TestRequestIndependence:
    def test_same_rows_different_decisions_give_different_results(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        approved = calculate(
            client, demo_rows, [decide("BOQ-003", "approve", "IPE-200-S235")]
        ).json()
        rejected = calculate(client, demo_rows, [decide("BOQ-003", "reject")]).json()

        assert "IPE-200-S235" in {g["code"] for g in approved["groups"]}
        assert "IPE-200-S235" not in {g["code"] for g in rejected["groups"]}
        assert approved["summary"]["calculated_rows"] != rejected["summary"]["calculated_rows"]

    def test_second_request_recomputes_from_scratch(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """Sunucu ilk isteğin satırlarını hatırlamaz: 2. istek kendi verisini taşır."""
        reduced = demo_rows[:3]
        reduced_decisions = [
            decision
            for decision in demo_decisions()
            if decision["boq_no"] in {row["boq_no"] for row in reduced}
        ]
        first = calculate(client, demo_rows, demo_decisions())
        second = calculate(client, reduced, reduced_decisions)

        assert first.json()["summary"]["input_rows"] == 18
        assert second.json()["summary"]["input_rows"] == 3
        assert second.json()["summary"]["input_rows"] != first.json()["summary"]["input_rows"]

    def test_analysis_does_not_affect_calculation(
        self, client: TestClient, demo_rows: list[dict[str, Any]], demo_analysis: dict[str, Any]
    ) -> None:
        """Analyze yanıtı değiştirilse bile calculate kendi girdisini kullanır."""
        before = calculate(client, demo_rows, demo_decisions()).json()
        # İstemci tarafındaki kopyayı boz (paylaşılan fixture'a dokunma).
        tampered = copy.deepcopy(demo_analysis)
        tampered["rows"].clear()
        after = calculate(client, demo_rows, demo_decisions()).json()

        assert before == after


# ---------------------------------------------------------------------------
# 9. Eşzamanlılık
# ---------------------------------------------------------------------------


class TestCalculateConcurrency:
    def test_concurrent_calculations_do_not_mix(
        self, demo_rows: list[dict[str, Any]]
    ) -> None:
        from app.main import app

        variants: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = [
            (demo_rows, demo_decisions()),
            (demo_rows[:2], []),
            (demo_rows[:5], [decide("BOQ-003", "approve", "IPE-200-S235")]),
        ]

        def run(pair: tuple[list[dict[str, Any]], list[dict[str, Any]]]) -> dict:
            rows, decisions = pair
            with TestClient(app) as test_client:
                response = calculate(test_client, rows, decisions)
                assert response.status_code == 200, response.text
                return response.json()

        jobs = variants * 3
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(run, jobs))

        for index, body in enumerate(results):
            expected_rows = len(variants[index % len(variants)][0])
            assert body["summary"]["input_rows"] == expected_rows

    def test_concurrent_analyze_and_calculate(
        self, demo_rows: list[dict[str, Any]], tmp_path: Path
    ) -> None:
        from app.main import app

        workbook = build_demo_workbook(tmp_path / "esz.xlsx")

        def analyze_job() -> int:
            with TestClient(app) as test_client:
                return len(analyze_ok(test_client, workbook)["rows"])

        def calculate_job() -> str:
            with TestClient(app) as test_client:
                body = calculate(test_client, demo_rows, demo_decisions()).json()
                return body["summary"]["known_weight_kg"]

        with ThreadPoolExecutor(max_workers=4) as executor:
            analyze_futures = [executor.submit(analyze_job) for _ in range(3)]
            calculate_futures = [executor.submit(calculate_job) for _ in range(3)]
            analyze_results = [future.result() for future in analyze_futures]
            calculate_results = [future.result() for future in calculate_futures]

        assert analyze_results == [18, 18, 18]
        assert calculate_results == [EXPECTED_WEIGHT_KG] * 3


# ---------------------------------------------------------------------------
# 10. İzlenebilirlik ve sözleşme
# ---------------------------------------------------------------------------


class TestCalculationTraceability:
    def test_sources_keep_boq_numbers(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        box = next(g for g in body["groups"] if g["code"] == "BOX-100-4-S235-B")

        assert box["merged"] is True
        assert box["source_boq_nos"] == ["BOQ-001", "BOQ-013"]
        assert [source["boq_no"] for source in box["sources"]] == ["BOQ-001", "BOQ-013"]

    def test_sources_keep_excel_row_numbers(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        """BOQ No ile birlikte Excel satır numarası da korunur."""
        body = calculate(client, demo_rows, demo_decisions()).json()
        box = next(g for g in body["groups"] if g["code"] == "BOX-100-4-S235-B")

        assert box["source_rows"] == [2, 14]
        assert [source["source_row"] for source in box["sources"]] == [2, 14]

    def test_skipped_rows_keep_excel_row_numbers(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        skipped = {row["boq_no"]: row for row in body["skipped"]}

        assert skipped["BOQ-009"]["source_row"] == 10
        assert skipped["BOQ-018"]["source_row"] == 19

    def test_source_rows_carry_conversion_and_waste(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        ipe = next(g for g in body["groups"] if g["code"] == "IPE-200-S235")
        source = ipe["sources"][0]

        assert source["boq_no"] == "BOQ-003"
        assert source["source_unit"] == "kg"
        assert source["waste_source"] == "row"
        assert source["net_metres"]
        assert source["gross_metres"]
        assert source["fire_quantity"]

    def test_weight_label_and_note_are_explicit(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()

        for group in body["groups"]:
            assert group["weight_label"] == "Teorik çıplak çelik ağırlığı"
            assert "kantar" in group["weight_note"]

    def test_galvanized_group_states_coating_exclusion(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        body = calculate(client, demo_rows, demo_decisions()).json()
        galvanized = next(g for g in body["groups"] if g["code"] == "BOX-100-4-S235-G")

        assert galvanized["coating"] == "galvaniz"
        assert "Galvaniz" in galvanized["weight_note"]

    def test_unknown_field_in_request_is_rejected(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        response = client.post(
            "/api/calculate",
            json={"rows": demo_rows, "decisions": [], "total_weight": "0"},
        )

        assert response.status_code == 422
        assert error_of(response)["code"] == "validation-error"

    def test_row_validation_rejects_zero_quantity(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        rows = [dict(demo_rows[0])]
        rows[0]["quantity"] = "0"

        response = calculate(client, rows, [])

        assert response.status_code == 422
        assert "quantity" in error_of(response)["issues"][0]["message"]

    def test_row_validation_rejects_bad_waste(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        rows = [dict(demo_rows[0])]
        rows[0]["waste_percent"] = "140"

        response = calculate(client, rows, [])

        assert response.status_code == 422

    def test_duplicate_boq_no_in_request_is_rejected(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        rows = [dict(demo_rows[0]), dict(demo_rows[0])]
        rows[1]["source_row"] = 99

        response = calculate(client, rows, [])

        assert response.status_code == 422
        body = error_of(response)
        assert "BOQ" in body["issues"][0]["message"] or "boq" in body["issues"][0]["message"]

    def test_duplicate_source_row_in_request_is_rejected(
        self, client: TestClient, demo_rows: list[dict[str, Any]]
    ) -> None:
        rows = [dict(demo_rows[0]), dict(demo_rows[1])]
        rows[1]["source_row"] = rows[0]["source_row"]

        response = calculate(client, rows, [])

        assert response.status_code == 422
        assert "source_row" in error_of(response)["issues"][0]["message"]

    def test_out_of_scope_unit_is_excluded_not_an_error(
        self, client: TestClient
    ) -> None:
        """``adet`` birimi hata değildir; satır kapsam dışı olarak raporlanır."""
        rows = [
            {
                "source_row": 2,
                "boq_no": "BOQ-001",
                "description": "profil 100×100",
                "quantity": "12",
                "unit": "adet",
                "waste_percent": "5",
            }
        ]

        response = calculate(client, rows, [])

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["groups"] == []
        assert body["skipped"][0]["status"] == "excluded"
        assert body["skipped"][0]["match_status"] == "excluded"

    def test_unknown_unit_text_is_excluded(self, client: TestClient) -> None:
        rows = [
            {
                "source_row": 2,
                "boq_no": "BOQ-001",
                "description": "BOX 100×100×4 S235 siyah",
                "quantity": "12",
                "unit": "lt",
                "waste_percent": "5",
            }
        ]

        response = calculate(client, rows, [])

        assert response.status_code == 200
        assert response.json()["skipped"][0]["status"] == "excluded"

    def test_missing_waste_still_excludes_row(self, client: TestClient) -> None:
        """Fire ``null`` sıfır sayılmaz; satır hesaba girmez."""
        rows = [
            {
                "source_row": 2,
                "boq_no": "BOQ-001",
                "description": "BOX 100×100×4 S235 siyah",
                "quantity": "96",
                "unit": "m",
                "waste_percent": None,
            }
        ]

        response = calculate(client, rows, [])

        assert response.status_code == 200
        assert response.json()["skipped"][0]["status"] == "excluded"

    def test_empty_row_list_is_rejected(self, client: TestClient) -> None:
        response = calculate(client, [], [])

        assert response.status_code == 422

    def test_client_row_fields_are_exactly_the_documented_allowlist(self) -> None:
        """Sözleşme bekçisi: şemaya yeni alan eklenirse bu test uyarır."""
        assert set(CLIENT_ROW_FIELDS) == {
            "source_row",
            "boq_no",
            "description",
            "quantity",
            "unit",
            "waste_percent",
        }
        from app.api.schemas import ClientRow

        assert set(ClientRow.model_fields) == set(CLIENT_ROW_FIELDS)


def test_demo_expected_counts_are_consistent() -> None:
    """Kilitli dağılım testi: karar sonrası 18 satır."""
    assert sum(EXPECTED_COUNTS.values()) == 18
