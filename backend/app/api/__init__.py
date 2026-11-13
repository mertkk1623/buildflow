"""API katmanı — HTTP sözleşmesi ile domain arasındaki tek sınır.

Bu paket domain'i **değiştirmez**: ``app.domain`` ve ``app.excel`` modülleri
FastAPI'den bağımsız kalır. Tüm dönüşüm buradaki açık eşleme katmanında
(:mod:`app.api.mapping`) yapılır.
"""

from app.api.errors import ApiError, install_error_handlers
from app.api.schemas import (
    AnalyzeResponse,
    CalculateRequest,
    CalculateResponse,
    ErrorResponse,
)

__all__ = [
    "AnalyzeResponse",
    "ApiError",
    "CalculateRequest",
    "CalculateResponse",
    "ErrorResponse",
    "install_error_handlers",
]
