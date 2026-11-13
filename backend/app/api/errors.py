"""API hata modeli ve hata yönetimi.

Sözleşme
--------
Her hata aynı gövdeyi taşır; frontend tek bir yerde işleyebilmelidir::

    {
      "error": {
        "code": "missing-column",
        "message": "Zorunlu kolon(lar) eksik: Birim",
        "detail": "Bulunan kolonlar: BOQ No, Açıklama, Miktar",
        "suggestion": "Şablondaki başlıkları kullanın: ...",
        "issues": []
      }
    }

``issues`` alanı satır düzeyi hataları taşır (Excel okuma, karar doğrulama).
Sunucunun iç yolları, dosya sistemi adları ve stack trace'leri **asla**
istemciye gitmez.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.calculation import CalculationError
from app.domain.catalog import CatalogError
from app.domain.decisions import DecisionError
from app.excel.reader import MetrajFileError, MetrajFileErrorCode

logger = logging.getLogger(__name__)

#: İstemciye gösterilebilir tek bir alan hatası.
GENERIC_ERROR_CODE = "internal-error"


class ApiError(Exception):
    """İstemciye güvenli biçimde raporlanacak API hatası.

    ``status_code`` HTTP durum kodudur; ``code`` makine tarafından okunabilir
    sabit bir değerdir (dosya düzeyi hata kodlarıyla aynı sözlüğü kullanır).
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        detail: str = "",
        suggestion: str = "",
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
        self.suggestion = suggestion
        self.issues = issues or []

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "detail": self.detail,
                "suggestion": self.suggestion,
                "issues": [normalize_issue(issue) for issue in self.issues],
            }
        }


#: Hata zarfındaki tek bir alan/satır sorununun **tam** alan kümesi.
#: Frontend tek tip işleyebilsin diye tüm anahtarlar her zaman bulunur.
_ISSUE_FIELDS: tuple[str, ...] = (
    "source_row",
    "boq_no",
    "column",
    "code",
    "message",
    "suggestion",
)


def make_issue(
    *,
    message: str,
    source_row: int | None = None,
    boq_no: str | None = None,
    column: str | None = None,
    code: str | None = None,
    suggestion: str = "",
) -> dict[str, Any]:
    """Tek bir hata sorununu sözleşmeye uygun sözlük olarak kurar."""
    return {
        "source_row": source_row,
        "boq_no": boq_no,
        "column": column,
        "code": code,
        "message": message,
        "suggestion": suggestion,
    }


def normalize_issue(issue: dict[str, Any] | Any) -> dict[str, Any]:
    """Eksik alanları ``None`` ile tamamlar; fazladan alanları atar.

    Eski ``row_no`` anahtarı ``boq_no``'ya taşınır (tek biçim kuralı).
    """
    data = dict(issue) if isinstance(issue, dict) else dict(getattr(issue, "__dict__", {}))
    if "row_no" in data:
        data.setdefault("boq_no", data.pop("row_no"))
    return {field: data.get(field) for field in _ISSUE_FIELDS}


#: Excel dosya hatalarının HTTP karşılığı.
_METRAJ_FILE_STATUS: dict[str, int] = {
    "not-found": 404,
    "unsupported-format": 415,
    "corrupt-file": 422,
    "file-too-complex": 422,
    "missing-sheet": 422,
    "no-header-row": 422,
    "missing-column": 422,
    "duplicate-column": 422,
}

#: Windows (``C:\...`` / ``C:/...``) ve POSIX (``/tmp/...``) yollarını yakalar.
_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s'\"]*)|(?:/(?:tmp|home|var|usr|private|root)/[^\s'\"]*)"
)


def _strip_paths(text: str) -> str:
    """Metinden sunucu dosya yollarını çıkarır.

    Okuma katmanı hata mesajına dosya adı/yolu yazabilir; istemci sunucunun
    dizin yapısını görmemelidir. Yer tutucu metin korunur ki mesaj anlaşılır
    kalsın.
    """
    if not text:
        return text
    return _PATH_PATTERN.sub("(dosya)", text)


def metraj_error_to_api(error: MetrajFileError) -> ApiError:
    """Excel okuma hatasını güvenli API hatasına çevirir.

    ``read_metraj`` mesajlarına dosya **yolu** yazabilir (ör. bulunamadı).
    Bu yol istemciye gitmez: metin ve ayrıntı, yol benzeri parçalardan
    temizlenir. Yalnızca dosya içeriği hakkında bilgi (başlıklar, sayfa adları)
    korunur.
    """
    if error.code is MetrajFileErrorCode.NOT_FOUND:
        # Sunucudaki geçici dosya yolu istemciyi ilgilendirmez.
        return ApiError(
            404,
            error.code.value,
            "Metraj dosyası işlenemedi.",
            suggestion="Dosyayı yeniden yükleyin.",
        )

    return ApiError(
        _METRAJ_FILE_STATUS.get(error.code.value, 422),
        error.code.value,
        _strip_paths(error.message),
        detail=_strip_paths(error.detail),
        suggestion=error.suggestion,
    )


def decision_error_to_api(error: DecisionError) -> ApiError:
    """Karar hatası: hangi satır, hangi kod ve neden."""
    return ApiError(
        409,
        "invalid-decision",
        "Kullanıcı kararı geçersiz.",
        detail=str(error),
        suggestion=(
            "Yalnızca sunucunun döndürdüğü aday kodlar arasından seçim yapın. "
            "Karar, satırın açıklamasıyla çelişemez."
        ),
        issues=[
            make_issue(
                source_row=None,
                boq_no=error.row_no,
                code=error.code or None,
                message=error.message,
                suggestion=(
                    "Sunucunun döndürdüğü aday kodlardan birini seçin."
                ),
            )
        ],
    )


def _allowed_origin(request: Request) -> str | None:
    """İsteğin origin'i yapılandırmada izinliyse döndürür.

    Yalnızca en dış katmandaki (``ServerErrorMiddleware``) yakalanmamış hata
    yanıtlarında gerekir; diğer yanıtlar ``CORSMiddleware`` tarafından
    zaten başlıklandırılır. Böylece 500 yanıtı da tarayıcıda okunabilir kalır.
    """
    origin = request.headers.get("origin")
    if not origin:
        return None

    from app.config import get_settings

    allowed = get_settings().cors_origins
    return origin if origin in allowed else None


def install_error_handlers(app: FastAPI) -> None:
    """Tüm hata türlerini tek JSON biçimine bağlar."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(MetrajFileError)
    async def _metraj_error(_: Request, exc: MetrajFileError) -> JSONResponse:
        mapped = metraj_error_to_api(exc)
        return JSONResponse(status_code=mapped.status_code, content=mapped.to_payload())

    @app.exception_handler(DecisionError)
    async def _decision_error(_: Request, exc: DecisionError) -> JSONResponse:
        mapped = decision_error_to_api(exc)
        return JSONResponse(status_code=mapped.status_code, content=mapped.to_payload())

    @app.exception_handler(CalculationError)
    async def _calculation_error(_: Request, exc: CalculationError) -> JSONResponse:
        # Girdi sözleşmesi ihlali: istemcinin gönderdiği veri tutarsız.
        error = ApiError(
            422,
            "calculation-error",
            "Hesaplama girdisi geçersiz.",
            detail=str(exc),
            suggestion=(
                "Aynı BOQ numarası iki kez gönderilemez. Satır numaralarını "
                "kontrol edin."
            ),
        )
        return JSONResponse(status_code=422, content=error.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic hata ayrıntıları istemciye alan/konum bilgisiyle verilir;
        # sunucu yolu veya iç tip adı taşımaz.
        issues = [
            make_issue(
                message=(
                    f"{'.'.join(str(part) for part in error['loc'])}: "
                    f"{error['msg']}"
                ),
                suggestion="Alan tipini ve zorunluluğunu kontrol edin.",
            )
            for error in exc.errors()
        ]
        error = ApiError(
            422,
            "validation-error",
            "İstek gövdesi doğrulanamadı.",
            detail=f"{len(issues)} alan geçersiz.",
            suggestion="Gönderilen alanların tiplerini ve zorunluluğunu kontrol edin.",
            issues=issues,
        )
        return JSONResponse(status_code=422, content=error.to_payload())

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 404/405 gibi çerçeve hataları da aynı gövdeye oturur.
        detail = exc.detail if isinstance(exc.detail, str) else "İstek işlenemedi."
        error = ApiError(
            exc.status_code,
            "http-error",
            detail,
            suggestion="İstek yolunu ve HTTP metodunu kontrol edin.",
        )
        return JSONResponse(status_code=exc.status_code, content=error.to_payload())

    @app.exception_handler(CatalogError)
    async def _catalog_error(_: Request, exc: CatalogError) -> JSONResponse:
        # Katalog bozuksa bu bir sunucu hatasıdır; ayrıntı log'a yazılır,
        # istemciye yalnızca genel mesaj döner.
        logger.exception("Katalog yüklenemedi: %s", exc)
        error = ApiError(
            500,
            "catalog-error",
            "Malzeme kataloğu yüklenemedi.",
            suggestion="Lütfen daha sonra tekrar deneyin.",
        )
        return JSONResponse(status_code=500, content=error.to_payload())

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Beklenmeyen hata: istemciye iç ayrıntı verilmez, sunucuda loglanır.
        logger.exception("Beklenmeyen API hatası: %s", exc)
        error = ApiError(
            500,
            GENERIC_ERROR_CODE,
            "Beklenmeyen bir sunucu hatası oluştu.",
            suggestion="Lütfen daha sonra tekrar deneyin.",
        )
        headers: dict[str, str] = {}
        origin = _allowed_origin(request)
        if origin is not None:
            # Bu handler en dış katmanda çalışır; CORS başlığını kendisi ekler.
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
        return JSONResponse(
            status_code=500,
            content=error.to_payload(),
            headers=headers,
        )
