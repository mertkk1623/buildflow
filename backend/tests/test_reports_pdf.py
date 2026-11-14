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
from app.reports.service import build_run_report, render_report
from tests.fixtures.reports import (
    EXPECTED_GROUPS,
    EXPECTED_ORDER_LENGTH_M,
    EXPECTED_WEIGHT_KG,
    FIXED_NOW,
    demo_report,
    demo_request,
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
# 6b. Hesaba alınmayan satırlar: kaydırma ve dinamik yükseklik
# ---------------------------------------------------------------------------


class TestSkippedRowLayout:
    """Uzun neden metinleri hücre içinde kaymalı; satırlar üst üste binmemeli.

    Bu senaryo gerçek raporun 2. sayfasında görülen hatayı kilitler: uzun
    ``message`` metni tek satırlık yüksekliğe sığdırılmaya çalışılıyor ve
    komşu satırın üzerine biniyordu.
    """

    #: Raporun 2. sayfasında uzun nedene sahip gerçek satırlar.
    LONG_REASON_ROWS = ("BOQ-012", "BOQ-014", "BOQ-015")

    def _skipped_page_text(self, report) -> str:
        pages = [
            page.extract_text()
            for page in PdfReader(BytesIO(build_pdf(report))).pages
        ]
        for text in pages:
            if "Hesaba Alınmayan Satırlar" in text:
                return text
        raise AssertionError("Hesaba Alınmayan Satırlar bölümü bulunamadı")

    def test_long_reason_is_not_truncated(self) -> None:
        """Neden metni kesilmemeli: son cümlesi de metinde bulunmalı."""
        report = demo_report()
        text = self._skipped_page_text(report)

        for row in report.skipped:
            if row.boq_no in self.LONG_REASON_ROWS:
                # Mesajın son parçası (kesilirse kaybolur) metinde olmalı.
                tail = row.message.split("; ")[-1].strip(". ")
                assert tail in text.replace("\n", " ").replace("  ", " "), (
                    row.boq_no,
                    tail,
                )

    def test_wrapped_lines_never_collide(self) -> None:
        """Kaydırılan satırlar birbirine girmemeli — **ölçülen** satır aralığı.

        Hatanın kesin imzası: uzun metin 4.2 mm'lik tek satıra sığdırılmaya
        çalışıldığında satır tabanları arasındaki fark 2.55 pt'ye düşüyordu
        (normal satır yüksekliği 11.9 pt). Bu test dikey konumları okuyup
        aralığın asgari çizgi yüksekliğinin altına inmediğini doğrular.

        Yalnızca metin çıkarmak yetmez: ``pypdf`` üst üste binmiş metni de
        okur. Bu yüzden konumlar (``tm[5]``) karşılaştırılır.
        """
        report = demo_report()
        reader = PdfReader(BytesIO(build_pdf(report)))
        page = next(
            p
            for p in reader.pages
            if "Hesaba Alınmayan Satırlar" in p.extract_text()
        )

        # Sabitler burada **literal** tutulur (modülden import edilmez):
        # böylece sabitler geri alınsa bile test ImportError ile değil,
        # gerçek geometri iddiasıyla başarısız olur.
        # A4 yatay gövde: 297 - 2*12 = 273 mm. "Neden" sütunu = 273 - 140 mm.
        reason_column_x = 273.0 - 140.0
        # 4.2 mm'lik satır yüksekliği pt cinsinden.
        line_height_pt = 4.2 * 72 / 25.4
        offsets: list[float] = []

        def visit(text, cm, tm, font_dict, font_size):
            if text.strip() and float(tm[4]) >= reason_column_x:
                offsets.append(round(float(tm[5]), 2))

        page.extract_text(visitor_text=visit)
        assert offsets, "neden sütununda metin bulunamadı"

        unique = sorted(set(offsets), reverse=True)
        gaps = [round(a - b, 2) for a, b in zip(unique, unique[1:])]
        assert gaps
        assert min(gaps) >= line_height_pt - 0.6, (
            f"satır aralığı çok küçük: {min(gaps)} pt < {line_height_pt} pt "
            f"(konumlar: {unique})"
        )

    def test_row_heights_grow_with_content(self) -> None:
        """Daha uzun neden metni daha yüksek satır üretmeli (dinamik yükseklik)."""
        from dataclasses import replace

        from app.reports.pdf import _skipped_columns, _skipped_row_height

        report = demo_report()
        short = report.skipped[0]
        long_message = "neden " * 120
        long_row = replace(short, message=long_message)

        pdf = _measure_pdf()
        columns = _skipped_columns()

        short_height = _skipped_row_height(
            pdf,
            columns,
            (
                short.boq_no,
                short.description,
                short.reason_label,
                short.exclusion_reason_label or "—",
                short.message,
            ),
        )
        long_height = _skipped_row_height(
            pdf,
            columns,
            (
                long_row.boq_no,
                long_row.description,
                long_row.reason_label,
                long_row.exclusion_reason_label or "—",
                long_row.message,
            ),
        )

        assert long_height > short_height, (short_height, long_height)

    def test_skipped_section_repeats_header_on_continuation_page(self) -> None:
        """Tablo sonraki sayfaya taşarsa başlık satırı orada da bulunmalı."""
        from dataclasses import replace

        from app.reports.models import ReportSkippedRow

        base = demo_report()
        long_message = (
            "Satır hesap kapsamı dışında bırakıldı; hesaplamaya alınmaz. "
            "Neden: açıklama katalogdaki bir aileyle eşleşmiyor. Benzer ölçü "
            "veya kaplamaya otomatik düşürme yapılmaz."
        )
        rows = tuple(
            ReportSkippedRow(
                boq_no=f"BOQ-2{index:02d}",
                description="muhtelif bağlantı elemanı",
                reason="excluded",
                reason_label="Kapsam dışı",
                message=long_message,
                exclusion_reason="catalog",
                exclusion_reason_label="Katalogda karşılığı yok",
            )
            for index in range(20)
        )
        report = replace(base, skipped=rows)

        reader = PdfReader(BytesIO(build_pdf(report)))
        skipped_pages = [
            page.extract_text()
            for page in reader.pages
            if "BOQ-2" in page.extract_text()
        ]

        assert len(skipped_pages) >= 2, "tablo birden fazla sayfaya taşmalı"
        for text in skipped_pages:
            assert "Neden kodu" in text, "başlık devam sayfasında yinelenmeli"
            assert "Neden" in text

    def test_skipped_rows_do_not_shrink_table_below_minimum(self) -> None:
        """Çok kısa neden bile okunabilir asgari yükseklikte kalmalı."""
        from app.reports.pdf import (
            _SKIPPED_MIN_ROW_HEIGHT,
            _skipped_columns,
            _skipped_row_height,
        )

        column_count = len(_skipped_columns())
        height = _skipped_row_height(
            _measure_pdf(), _skipped_columns(), tuple("" for _ in range(column_count))
        )

        assert height >= _SKIPPED_MIN_ROW_HEIGHT


def _measure_pdf():
    """Yükseklik ölçümü için font yüklenmiş boş bir PDF."""
    from app.reports.pdf import _BOLD, _REGULAR, FONT_DIR, ReportPdf

    pdf = ReportPdf(title="ölçüm", generated_at_text="—")
    pdf.add_font(_REGULAR, "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font(_BOLD, "", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()
    return pdf


# ---------------------------------------------------------------------------
# 6c. PDF katmanı hesap yapmaz: toplamlar hesaplama motorundan gelir
# ---------------------------------------------------------------------------


class TestReportTotalsComeFromEngine:
    """PDF/Excel toplamları **onaylara** bağlıdır, PDF düzenine değil.

    Neden bu test var?
    ------------------
    Aynı 18 satırlık demo metraj, farklı kullanıcı onaylarıyla iki farklı
    meşru toplam üretir:

    * ``BOQ-009`` onaylı, ``BOQ-018`` kararsız → 14 hesaplanan satır,
      1.086,000 m / 18.194,220 kg (sahada üretilen canlı rapor).
    * ``BOQ-009`` onay bekliyor, ``BOQ-018`` reddedildi → 13 hesaplanan
      satır, 966,000 m / 18.005,820 kg (test fixture'ı).

    İkisi de doğrudur; fark PDF kodundan değil **girdi onaylarından** gelir.
    Bu test, aynı girdi + aynı onay verildiğinde PDF, Excel ve hesaplama
    motorunun birebir aynı toplamı verdiğini kilitler. Böylece ileride
    "PDF toplamı değişti" şüphesi doğduğunda kaynağın rapor katmanı mı
    yoksa onaylar mı olduğu tek adımda ayrılabilir.
    """

    #: Canlı raporun onay imzası: BOQ-009 onaylı, BOQ-018 kararsız.
    LIVE_APPROVED = ("BOQ-009",)
    LIVE_WITHOUT_DECISION = ("BOQ-018",)

    def _run_with(self, *, approve: tuple[str, ...], skip_decision: tuple[str, ...]):
        """Demo metrajı verilen onay kümesiyle hesaplar."""
        from decimal import Decimal

        from app.api.schemas import (
            CalculateRequest,
            ClientDecision,
            ClientRow,
        )
        from app.api.service import run_calculation
        from tests.fixtures.demo_boq import DEMO_ROWS

        base = demo_request()
        rows = [
            ClientRow(
                source_row=index + 2,
                boq_no=row.no,
                description=row.description,
                quantity=row.quantity,
                unit=row.unit,
                waste_percent=(
                    row.waste_rate * Decimal(100)
                    if row.waste_rate is not None
                    else None
                ),
            )
            for index, row in enumerate(DEMO_ROWS)
        ]
        decisions = [
            decision
            for decision in base.decisions
            if decision.boq_no not in skip_decision
        ]
        codes = {
            "BOQ-009": "FLAT-40x5-S235-B",
        }
        for boq_no in approve:
            decisions.append(
                ClientDecision(
                    boq_no=boq_no,
                    action="approve",
                    code=codes[boq_no],
                    reason="test onayı",
                )
            )
        return run_calculation(CalculateRequest(rows=rows, decisions=decisions))

    @staticmethod
    def _pdf_totals(payload: bytes) -> tuple[str, str]:
        """PDF metninden özet toplamlarını çıkarır."""
        import re

        text = " ".join(
            page.extract_text() for page in PdfReader(BytesIO(payload)).pages
        )
        match = re.search(
            r"Toplam sipariş uzunluğu\s+([\d.,]+ m)\s+Bilinen teorik ağırlık\s+([\d.,]+ kg)",
            text,
        )
        assert match, "özet toplamları PDF'te bulunamadı"
        return match.group(1), match.group(2)

    def test_pdf_and_excel_totals_match_engine_for_same_approvals(self) -> None:
        """Aynı girdi + aynı onay → motor, PDF ve Excel aynı toplamı verir."""
        from openpyxl import load_workbook

        run = self._run_with(
            approve=self.LIVE_APPROVED,
            skip_decision=self.LIVE_WITHOUT_DECISION,
        )
        result = run.result
        report = build_run_report(run, generated_at=FIXED_NOW)

        expected_order = sum(
            group.order_length_m
            for group in result.groups
            if group.order_length_m is not None
        )
        expected_weight = sum(
            group.weight_kg for group in result.groups if group.weight_kg is not None
        )

        # Motorun kendi toplamı — rapor katmanından bağımsız referans.
        assert expected_order == 1086
        assert str(expected_weight) == "18194.220"

        pdf_order, pdf_weight = self._pdf_totals(render_report(report, kind="pdf"))
        assert pdf_order == "1.086,000 m"
        assert pdf_weight == "18.194,220 kg"

        # Excel aynı toplamı vermeli: iki çıktı biçimi ayrışmamalı.
        workbook = load_workbook(BytesIO(render_report(report, kind="excel")))
        sheet = workbook[workbook.sheetnames[0]]
        labels = {
            str(row[0]): row[1]
            for row in sheet.iter_rows(values_only=True)
            if row and row[0]
        }
        assert labels["Toplam sipariş uzunluğu (m)"] == 1086
        assert str(labels["Bilinen teorik ağırlık (kg)"]) in {
            "18194.220",
            "18194.22",
        }

    def test_engine_totals_are_independent_of_pdf_layout(self) -> None:
        """PDF düzeni değişse de motorun toplamı değişmez.

        Aynı ``CalculationRun`` nesnesinden üretilen rapor, PDF çizim
        kodundan **önce** hesaplanmış toplamı taşır; PDF yalnızca biçimler.
        """
        run = self._run_with(
            approve=self.LIVE_APPROVED,
            skip_decision=self.LIVE_WITHOUT_DECISION,
        )
        report = build_run_report(run, generated_at=FIXED_NOW)

        # Rapor modelindeki toplamlar, motordan gelen değerlerle aynı olmalı.
        assert report.summary.total_order_length_m == 1086
        assert str(report.summary.known_weight_kg) == "18194.220"
        assert report.summary.calculated_rows == 14
        assert report.summary.skipped_rows == 4


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
