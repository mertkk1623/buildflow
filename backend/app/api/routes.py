"""API yolları — ince HTTP kabuğu.

Tüm iş kuralı :mod:`app.api.service` içindedir; burada yalnızca HTTP sözleşmesi
(medya tipi, durum kodu, başlık) yönetilir. Böylece akış HTTP olmadan test
edilebilir ve güvenlik kuralları tek yerde kalır.

Yol güvenliği: şablon dosyasının yolu **koddan ve yapılandırmadan** gelir;
istemciden gelen hiçbir ad dosya sistemine girmez.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from app.api.errors import ApiError
from app.api.schemas import (
    AnalyzeResponse,
    CalculateRequest,
    CalculateResponse,
    HealthResponse,
)
from app.api.service import analyze_file, calculate, run_calculation
from app.api.uploads import UploadWorkspace, receive_upload
from app.ai.factory import provider_from_settings
from app.config import get_settings
from app.reports.service import (
    ReportKindError,
    build_run_report,
    render_report,
    report_filename,
    report_media_type,
)

logger = logging.getLogger(__name__)

#: İndirme sırasında sunulan sabit dosya adı (path traversal riski yok).
TEMPLATE_DOWNLOAD_NAME = "buildflow-metraj-sablonu.xlsx"

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Servisin ayakta olduğunu bildirir."""
    settings = get_settings()
    return HealthResponse(status="ok", environment=settings.environment)


@router.get(
    "/template",
    response_class=FileResponse,
    responses={
        200: {
            "content": {XLSX_MEDIA_TYPE: {}},
            "description": "Standart metraj şablonu",
        },
        404: {"description": "Şablon bulunamadı"},
    },
)
def download_template() -> FileResponse:
    """Hazır metraj şablonunu indirir.

    Dosya sunucuda sabittir ve adı yapılandırmadan gelir; istemci girdisi yola
    girmez. Hata durumunda sunucu yolu istemciye **söylenmez**.
    """
    template_path = get_settings().template_path

    if not template_path.is_file():
        logger.error("Metraj şablonu bulunamadı: %s", template_path)
        raise ApiError(
            404,
            "template-not-found",
            "Metraj şablonu sunucuda bulunamadı.",
            suggestion="Şablonu yeniden oluşturup sunucuyu başlatın.",
        )

    return FileResponse(
        path=template_path,
        media_type=XLSX_MEDIA_TYPE,
        filename=TEMPLATE_DOWNLOAD_NAME,
        headers={
            # Tarayıcı indirmeyi dosya olarak ele alsın.
            "Content-Disposition": f'attachment; filename="{TEMPLATE_DOWNLOAD_NAME}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        413: {"description": "Dosya çok büyük"},
        415: {"description": "Desteklenmeyen format"},
        422: {"description": "Dosya okunamadı veya yapısı geçersiz"},
    },
)
async def analyze(
    file: UploadFile = File(..., description="Metraj .xlsx dosyası"),
) -> AnalyzeResponse:
    """Excel metrajını okur ve eşleştirme raporunu döndürür.

    İşlem sonunda geçici dosya **her durumda** silinir (hata hâlinde de);
    sunucuda hiçbir analiz sonucu saklanmaz.

    AI yalnızca ``pending`` satırlar için devreye girer ve yalnızca **öneri**
    üretir. Sağlayıcı yapılandırılmamışsa (varsayılan) hiçbir ağ çağrısı
    yapılmaz ve yanıt deterministik sonuçla birebir aynı kalır.
    """
    settings = get_settings()
    provider = provider_from_settings(settings)

    with UploadWorkspace() as workspace:
        path = await receive_upload(
            workspace,
            file,
            max_bytes=settings.max_upload_bytes,
        )
        # Excel okuma, eşleştirme ve AI çağrıları **blocking** iştir; olay
        # döngüsünü meşgul etmemesi için ayrı iş parçacığında çalıştırılır.
        # Böylece eşzamanlı istekler birbirini kilitlemez.
        return await run_in_threadpool(analyze_file, path, provider=provider)


@router.post("/calculate", response_model=CalculateResponse)
def calculate_endpoint(request: CalculateRequest) -> CalculateResponse:
    """Kullanıcı kararlarını doğrular ve satın alma listesini hesaplar.

    İstemcinin gönderdiği hiçbir eşleştirme durumu veya hesaplanmış değer
    kullanılmaz: eşleştirme ve hesap sunucuda **yeniden** yapılır.
    """
    return calculate(request)


@router.post(
    "/report/excel",
    response_class=Response,
    responses={
        200: {
            "content": {XLSX_MEDIA_TYPE: {}},
            "description": "Excel satın alma raporu",
        },
        422: {"description": "Hesaplama doğrulanamadı veya rapor boş"},
    },
)
async def report_excel_endpoint(request: CalculateRequest) -> Response:
    """Excel satın alma raporunu indirir.

    Rapor, ``/api/calculate`` ile **aynı** çekirdekten üretilir; raporda
    yeniden hesap yapılmaz. Kararlar geçersizse ``/api/calculate`` ile aynı
    hata gövdesi döner.
    """
    return await _render_report(request, "excel")


@router.post(
    "/report/pdf",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF satın alma raporu",
        },
        422: {"description": "Hesaplama doğrulanamadı veya rapor boş"},
    },
)
async def report_pdf_endpoint(request: CalculateRequest) -> Response:
    """PDF satın alma raporunu indirir.

    Excel raporuyla **aynı** ``Report`` nesnesinden üretilir; iki çıktı
    birbirinden ayrışamaz.
    """
    return await _render_report(request, "pdf")


async def _render_report(request: CalculateRequest, kind: str) -> Response:
    """Ortak rapor üretimi: doğrula → hesapla → raporla → bayt döndür.

    Excel/PDF üretimi CPU yoğun ve blocking olduğu için iş parçacığında
    çalıştırılır; olay döngüsü meşgul edilmez.
    """
    run = await run_in_threadpool(run_calculation, request)

    # Boş rapor üretilmez: onaylanmış hiçbir kalem yoksa kullanıcıya boş bir
    # "satın alma listesi" vermek yanıltıcı olur.
    if not run.result.groups:
        raise ApiError(
            422,
            "report-empty",
            "Rapor oluşturulacak onaylanmış malzeme yok.",
            detail=(
                "Hesaplama sonucunda satın alma kalemi (grup) oluşmadı: "
                f"{run.result.skipped_count} satır hesaba alınmadı."
            ),
            suggestion=(
                "En az bir satırı onaylayıp yeniden hesaplayın; ardından "
                "raporu indirin."
            ),
        )

    report = await run_in_threadpool(build_run_report, run)

    try:
        payload = await run_in_threadpool(render_report, report, kind=kind)
        filename = report_filename(report, kind=kind)
        media_type = report_media_type(kind)
    except ReportKindError as error:  # pragma: no cover - kind koddan gelir
        raise ApiError(
            422,
            "unsupported-report-kind",
            "Desteklenmeyen rapor biçimi.",
            detail=str(error),
            suggestion="Yalnızca Excel veya PDF raporu isteyin.",
        ) from error

    return Response(
        content=payload,
        media_type=media_type,
        headers={
            # Dosya adı yalnızca sunucuda üretilir; istemci girdisi içermez.
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(len(payload)),
        },
    )

