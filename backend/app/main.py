"""FastAPI uygulama giriş noktası.

Faz 0 kapsamı: yalnızca sağlık kontrolü. İş mantığı, hesap motoru ve AI
entegrasyonu sonraki fazlarda ayrı modüller olarak eklenecektir.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Servisin ayakta olduğunu bildirir."""
    return {"status": "ok", "environment": settings.environment}
