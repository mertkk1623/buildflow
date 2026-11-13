"""Rapor üretim servisi — API ile rapor yazıcıları arasındaki tek köprü.

Temel kural
-----------
Bu modül **hesap yapmaz**. Girdi, :func:`app.api.service.run_calculation`
tarafından doğrulanmış çekirdek sonuçtur; çıktı ise bayt dizisidir.

Neden ayrı bir servis katmanı?
------------------------------
Router'ın yalnızca HTTP sözleşmesiyle uğraşmasını sağlar (Aşama 4.4 kuralı).
Rapor üretimi HTTP olmadan da test edilebilir.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.api.service import CalculationRun
from app.reports.excel import build_excel
from app.reports.models import Report, build_report
from app.reports.pdf import build_pdf

#: Rapor biçimleri ve dosya adı/medya tipi eşlemesi.
EXCEL_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
PDF_MEDIA_TYPE = "application/pdf"


class ReportKindError(ValueError):
    """Tanınmayan rapor biçimi istendi."""


def build_run_report(
    run: CalculationRun,
    *,
    generated_at: datetime | None = None,
) -> Report:
    """Doğrulanmış hesap çıktısını rapor modeline çevirir."""
    return build_report(
        run.result,
        generated_at=generated_at or datetime.now(timezone.utc).astimezone(),
        warnings=run.warnings,
        descriptions=run.descriptions,
    )


def render_report(report: Report, *, kind: str) -> bytes:
    """Raporu istenen biçimde baytlara çevirir.

    Parameters
    ----------
    kind:
        ``"excel"`` veya ``"pdf"``. Başka değer :class:`ReportKindError`
        yükseltir (router bunu 422'ye çevirir).
    """
    normalized = (kind or "").strip().lower()
    if normalized in {"excel", "xlsx"}:
        return build_excel(report)
    if normalized == "pdf":
        return build_pdf(report)
    raise ReportKindError(f"Desteklenmeyen rapor biçimi: {kind!r}")


def report_filename(report: Report, *, kind: str) -> str:
    """İndirilen dosyanın adı. Tarih damgası çakışmayı önler."""
    stamp = report.generated_at.strftime("%Y%m%d-%H%M")
    normalized = (kind or "").strip().lower()
    if normalized in {"excel", "xlsx"}:
        return f"buildflow-satin-alma-{stamp}.xlsx"
    if normalized == "pdf":
        return f"buildflow-satin-alma-{stamp}.pdf"
    raise ReportKindError(f"Desteklenmeyen rapor biçimi: {kind!r}")


def report_media_type(kind: str) -> str:
    normalized = (kind or "").strip().lower()
    if normalized in {"excel", "xlsx"}:
        return EXCEL_MEDIA_TYPE
    if normalized == "pdf":
        return PDF_MEDIA_TYPE
    raise ReportKindError(f"Desteklenmeyen rapor biçimi: {kind!r}")


__all__ = [
    "EXCEL_MEDIA_TYPE",
    "PDF_MEDIA_TYPE",
    "ReportKindError",
    "build_run_report",
    "render_report",
    "report_filename",
    "report_media_type",
]
