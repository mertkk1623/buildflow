"""FastAPI uygulama giriş noktası.

Kapsam: Aşama 4.4 API katmanı. İş mantığı ``app.domain`` ve ``app.excel``
içinde kalır; bu modül yalnızca uygulamayı kurar:

* router (``/api/health``, ``/api/template``, ``/api/analyze``,
  ``/api/calculate``, ``/api/report/excel``, ``/api/report/pdf``),
* tek biçimli hata yönetimi,
* CORS (yalnızca yapılandırmada açıkça verilen origin'ler).

Sunucu durum saklamaz: analiz sonucu bellekte tutulmaz, oturum yoktur.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_error_handlers
from app.api.routes import router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "BuildFlow AI metraj analizi ve satın alma listesi API'si. "
        "Stateless iki aşamalı akış: /api/analyze → /api/calculate."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Kimlik doğrulama/çerez yok; kimlik bilgisi taşınmaz.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    # Frontend indirme dosya adını okuyabilsin diye açıkça listelenir.
    expose_headers=["Content-Disposition"],
)

install_error_handlers(app)
app.include_router(router)
