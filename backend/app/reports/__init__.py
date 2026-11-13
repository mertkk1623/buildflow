"""Raporlama paketi — Excel ve PDF satın alma raporları.

Temel kural
-----------
Bu paket **hesap yapmaz**. Tek veri kaynağı, hesap motorunun ürettiği
:class:`app.domain.calculation.CalculationResult` nesnesidir.

Akış::

    CalculateRequest
        ↓  app.api.service.run_calculation   (doğrulama + mevcut hesap motoru)
    CalculationRun
        ↓  app.reports.models.build_report   (yalnızca alan seçimi)
    Report  ──►  app.reports.excel.build_excel  ──►  .xlsx baytları
            └─►  app.reports.pdf.build_pdf      ──►  PDF baytları

Excel ve PDF **aynı** ``Report`` nesnesini kullanır; iki çıktının
birbirinden ayrışması yapısal olarak mümkün değildir.

Bilinmeyen değer kuralı
-----------------------
``None`` asla ``0`` olarak gösterilmez:

* Excel'de hücre **boş** bırakılır,
* PDF'te hücrede ``—`` yer tutucusu görünür.
"""

from __future__ import annotations

from app.reports.excel import build_excel
from app.reports.formatting import (
    EMPTY_PLACEHOLDER,
    METRE_PLACES,
    PERCENT_PLACES,
    UNKNOWN_TEXT,
    WEIGHT_PLACES,
    format_datetime,
    format_decimal,
    format_integer,
    format_percent,
)
from app.reports.models import (
    CUTTING_DISCLAIMER,
    PARTIAL_DISCLAIMER,
    REPORT_DISCLAIMERS,
    WEIGHT_DISCLAIMER,
    Report,
    ReportGroup,
    ReportSkippedRow,
    ReportSourceRow,
    ReportSummary,
    build_report,
)
from app.reports.pdf import build_pdf
from app.reports.service import (
    EXCEL_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    ReportKindError,
    build_run_report,
    render_report,
    report_filename,
    report_media_type,
)

__all__ = [
    "CUTTING_DISCLAIMER",
    "EMPTY_PLACEHOLDER",
    "EXCEL_MEDIA_TYPE",
    "METRE_PLACES",
    "PARTIAL_DISCLAIMER",
    "PDF_MEDIA_TYPE",
    "PERCENT_PLACES",
    "REPORT_DISCLAIMERS",
    "Report",
    "ReportGroup",
    "ReportKindError",
    "ReportSkippedRow",
    "ReportSourceRow",
    "ReportSummary",
    "UNKNOWN_TEXT",
    "WEIGHT_DISCLAIMER",
    "WEIGHT_PLACES",
    "build_excel",
    "build_pdf",
    "build_report",
    "build_run_report",
    "format_datetime",
    "format_decimal",
    "format_integer",
    "format_percent",
    "render_report",
    "report_filename",
    "report_media_type",
]
