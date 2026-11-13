"""PDF satın alma raporu testleri.

Kapsam
------
1.  Geçerli bir PDF üretilmesi (imza, sayfa sayısı).
2.  Türkçe karakterlerin **metinden** doğrulanması (``pypdf``).
3.  Özet ve malzeme tablosunun varlığı, değerlerin hesapla eşitliği.
4.  FULL / PARTIAL durumlarının açık gösterimi.
5.  Bilinmeyen değerlerin ``0`` değil ``—`` olması.
6.  Sayfa numarası (``Sayfa X / Y``) ve uzun tablonun sayfalara bölünmesi.
7.  Zorunlu iki açıklamanın (ağırlık / kesim) raporda bulunması.
8.  Boş hesabın güvenli biçimde raporlanması.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfReader

from app.reports.formatting import EMPTY_PLACEHOLDER, format_decimal
from app.reports.models import (
    CUTTING_DISCLAIMER,
    PARTIAL_DISCLAIMER,
    WEIGHT_DISCLAIMER,
    build_report,
)
from app.reports.pdf import build_pdf
from tests.fixtures.reports import (
    EXPECTED_GROUPS,
    EXPECTED_ORDER_LENGTH_M,
    EXPECTED_WEIGHT_KG,
    FIXED_NOW,
    demo_report,
    empty_result,
    partial_missing_commercial_length,
    partial_missing_mass,
    partial_missing_waste,
)

#: Turkish characters that must survive the font embedding + extraction.
TURKISH_SPECIALS = "ğüşıöçĞÜŞİÖÇ"


@pytest.fixture(scope="module")
def demo_payload() -> bytes:
    return build_pdf(demo_report())


@pytest.fixture(scope="module")
def demo_pages(demo_payload: bytes) -> list[str]:
    reader = PdfReader(BytesIO(demo_payload))
    return [page.extract_text() for page in reader.pages]


def _text(payload: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(payload)).pages)


# ---------------------------------------------------------------------------
# 1. Dosya üretimi
# ---------------------------------------------------------------------------


class TestPdfStructure:
    def test_payload_is_a_pdf(self, demo_payload: bytes) -> None:
        assert demo_payload.startswith(b"%PDF-")
        assert demo_payload.rstrip().endswith(b"%%EOF")
        assert len(demo_payload) > 10_000

    def test_a4_landscape_page_size(self, demo_payload: bytes) -> None:
        page = PdfReader(BytesIO(demo_payload)).pages[0]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        assert width > height, "A4 yatay beklenir"
        # A4 = 595 × 842 pt
        assert 840 < width < 845
        assert 594 < height < 598

    def test_fonts_are_embedded(self, demo_payload: bytes) -> None:
        """Sistem fontuna bağımlı olunmamalı: font dosyaya gömülür."""
        reader = PdfReader(BytesIO(demo_payload))
        page = reader.pages[0]
        resources = page["/Resources"]
        assert "/Font" in resources
        names = {
            str(font.get_object().get("/BaseFont", ""))
            for font in resources["/Font"].values()
        }
        assert any("DejaVu" in name for name in names), names

    def test_report_has_multiple_pages_when_needed(
        self, demo_payload: bytes
    ) -> None:
        assert len(PdfReader(BytesIO(demo_payload)).pages) >= 2


# ---------------------------------------------------------------------------
# 2. Türkçe karakterler
# ---------------------------------------------------------------------------


class TestTurkishCharacters:
    def test_section_titles_are_correct(self, demo_pages: list[str]) -> None:
        first = demo_pages[0]
        assert "Satın Alma Raporu" in first
        assert "Özet" in first
        assert "Satın Alma Listesi" in first

    def test_diacritics_survive_extraction(self, demo_pages: list[str]) -> None:
        text = "\n".join(demo_pages)
        # "Açıklama", "Sipariş", "Ağırlık", "Durum", "Hesaplanan"
        assert "Açıklama" in text
        assert "Sipariş" in text
        assert "Ağırlık" in text

    def test_product_label_diacritics(self, demo_pages: list[str]) -> None:
        text = "\n".join(demo_pages)
        assert "Kutu profil" in text
        assert "galvaniz" in text
        assert "siyah" in text

    def test_special_characters_are_all_present(self) -> None:
        """Her Türkçe özel karakter fontta var ve metne dönüyor."""
        from decimal import Decimal as D

        from app.reports.models import Report, ReportSummary

        report = Report(
            generated_at=FIXED_NOW,
            summary=ReportSummary(
                input_rows=0,
                calculated_rows=0,
                skipped_rows=0,
                group_count=0,
                merged_group_count=0,
                merge_count=0,
                full_groups=0,
                partial_groups=0,
                total_order_length_m=None,
                known_weight_kg=D(0),
                weight_complete=True,
            ),
            groups=(),
            skipped=(),
            warnings=(f"Karakter testi: {TURKISH_SPECIALS} · ×",),
            disclaimers=(),
        )
        text = _text(build_pdf(report))
        for character in TURKISH_SPECIALS:
            assert character in text, character
        assert "×" in text

    def test_multiplication_sign_in_size_labels(
        self, demo_pages: list[str]
    ) -> None:
        assert "100×100×4" in "\n".join(demo_pages)


# ---------------------------------------------------------------------------
# 3. İçerik = hesap
# ---------------------------------------------------------------------------


class TestConsistencyWithCalculation:
    def test_summary_counters(self, demo_pages: list[str]) -> None:
        text = demo_pages[0]
        assert f"Satın alma kalemi\n{EXPECTED_GROUPS}" in text
        assert "FULL grup\n8" in text
        assert "PARTIAL grup\n0" in text

    def test_total_order_length_uses_turkish_format(
        self, demo_pages: list[str]
    ) -> None:
        expected = format_decimal(EXPECTED_ORDER_LENGTH_M, 3)
        assert expected == "966,000"
        assert f"{expected} m" in demo_pages[0]

    def test_total_weight_uses_turkish_format(
        self, demo_pages: list[str]
    ) -> None:
        expected = format_decimal(EXPECTED_WEIGHT_KG, 3)
        assert expected == "18.005,820"
        assert f"{expected} kg" in demo_pages[0]

    def test_every_group_appears_with_its_values(
        self, demo_pages: list[str]
    ) -> None:
        text = "\n".join(demo_pages)
        for group in demo_report().groups:
            assert group.code in text
            assert format_decimal(group.weight_kg, 3) in text
            assert format_decimal(group.order_length_m, 3) in text

    def test_merged_groups_list_all_boq_numbers(
        self, demo_pages: list[str]
    ) -> None:
        text = "\n".join(demo_pages)
        for group in demo_report().groups:
            if not group.merged:
                continue
            assert group.boq_trace in text

    def test_skipped_rows_section_is_present(self, demo_pages: list[str]) -> None:
        text = "\n".join(demo_pages)
        assert "Hesaba Alınmayan Satırlar" in text
        assert "BOQ-009" in text
        assert "Onay bekliyor" in text


# ---------------------------------------------------------------------------
# 4. Zorunlu açıklamalar
# ---------------------------------------------------------------------------


class TestDisclaimers:
    def test_weight_disclaimer(self, demo_pages: list[str]) -> None:
        text = " ".join(demo_pages)
        assert "teorik çıplak çelik" in text
        assert "kantar" in text
        assert WEIGHT_DISCLAIMER.split(";")[0] in text

    def test_no_cutting_optimisation_disclaimer(
        self, demo_pages: list[str]
    ) -> None:
        text = " ".join(demo_pages)
        assert "kesim optimizasyonu" in text
        assert "nesting" in text
        assert CUTTING_DISCLAIMER.split(";")[0] in text

    def test_partial_disclaimer(self, demo_pages: list[str]) -> None:
        text = " ".join(demo_pages)
        assert "PARTIAL" in text
        assert "sıfır" in text
        assert PARTIAL_DISCLAIMER.split(";")[0] in text


# ---------------------------------------------------------------------------
# 5. PARTIAL: bilinmeyen değer sıfır değil
# ---------------------------------------------------------------------------


class TestPartialExposure:
    def test_unknown_values_use_placeholder(self) -> None:
        case = partial_missing_commercial_length()
        text = _text(build_pdf(case.report))
        assert EMPTY_PLACEHOLDER in text
        # Sipariş/artan/ağırlık bilinmiyor; hiçbiri "0,000" olmamalı.
        assert "Sipariş" in text

    def test_no_zero_for_unknown_columns(self) -> None:
        """PARTIAL satırda bilinmeyen sayısal hücre ``0`` görünmemeli."""
        for case in (
            partial_missing_commercial_length(),
            partial_missing_mass(),
            partial_missing_waste(),
        ):
            text = _text(build_pdf(case.report))
            group = case.report.groups[0]
            assert group.status_label in text
            if group.weight_kg is None:
                # Ağırlık bilinmiyorsa özet "0,000 kg" yazmamalı.
                assert "0,000 kg" not in text

    def test_status_column_shows_partial(self) -> None:
        case = partial_missing_waste()
        text = _text(build_pdf(case.report))
        assert "PARTIAL" in text
        # Uyarı bölümünde gerekçe görünür.
        assert "Fire oranı tanımsız" in text
        assert "sıfır varsayılmadı" in text

    def test_weight_status_is_partial(self) -> None:
        case = partial_missing_commercial_length()
        text = _text(build_pdf(case.report))
        assert "KISMİ" in text

    def test_full_groups_are_labelled_full(self, demo_pages: list[str]) -> None:
        text = "\n".join(demo_pages)
        assert text.count("FULL") >= EXPECTED_GROUPS


# ---------------------------------------------------------------------------
# 6. Sayfalama
# ---------------------------------------------------------------------------


class TestPagination:
    def test_every_page_has_page_number(self, demo_payload: bytes) -> None:
        reader = PdfReader(BytesIO(demo_payload))
        total = len(reader.pages)
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            assert f"Sayfa {index} / {total}" in text, (index, total)

    def test_long_table_breaks_across_pages(self) -> None:
        """Uzun liste sayfalara bölünür ve her sayfada başlık yinelenir."""
        result = demo_report()
        # Aynı raporu 200 kalemle yeniden üretmek yerine aynı grubu çoğaltırız.
        many = _replicate_groups(result, factor=25)
        reader = PdfReader(BytesIO(build_pdf(many)))
        assert len(reader.pages) >= 3

        # Malzeme satırı içeren her sayfada tablo başlığı bulunur.
        codes = {group.code for group in many.groups}
        for page in reader.pages:
            text = page.extract_text()
            has_group = any(code in text for code in codes)
            if not has_group:
                continue
            assert "Malzeme Kodu" in text
            assert "Durum" in text

    def test_no_page_is_empty(self, demo_payload: bytes) -> None:
        for page in PdfReader(BytesIO(demo_payload)).pages:
            assert page.extract_text().strip()


# ---------------------------------------------------------------------------
# 7. Güvenli kenar durumlar
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_result_produces_valid_pdf(self) -> None:
        report = build_report(empty_result(), generated_at=FIXED_NOW)
        payload = build_pdf(report)
        text = _text(payload)

        assert payload.startswith(b"%PDF-")
        assert "Satın Alma Raporu" in text
        assert "Satın Alma Listesi" in text
        # Ağırlık bilinmiyor → 0 yazılmaz.
        assert "0,000 kg" not in text
        assert EMPTY_PLACEHOLDER in text

    def test_rebuild_is_stable(self) -> None:
        report = demo_report()
        first = _text(build_pdf(report))
        second = _text(build_pdf(report))
        assert first == second

    def test_warnings_are_visible(self) -> None:
        report = build_report(
            empty_result(),
            generated_at=FIXED_NOW,
            warnings=("Test uyarısı: kısmi hesap.",),
        )
        assert "Test uyarısı: kısmi hesap." in _text(build_pdf(report))


# ---------------------------------------------------------------------------
# Yardımcı
# ---------------------------------------------------------------------------


def _replicate_groups(report, *, factor: int):
    """Aynı raporun kalemlerini çoğaltır — sayfalama testi için.

    Bu bir hesap değildir; yalnızca yerleşim sınaması için rapor kopyalanır.
    Kodlar benzersiz tutulur ki satırlar ayırt edilebilsin.
    """
    from dataclasses import replace

    groups = tuple(
        replace(
            group,
            code=f"{group.code}-{copy_index}",
            source_boq_nos=tuple(
                f"{boq}-{copy_index}" for boq in group.source_boq_nos
            ),
        )
        for copy_index in range(factor)
        for group in report.groups
    )
    return replace(
        report,
        groups=groups,
        summary=replace(
            report.summary,
            group_count=len(groups),
            merge_count=sum(len(group.source_rows) for group in groups)
            - len(groups),
        ),
    )
