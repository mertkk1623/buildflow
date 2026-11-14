# Geliştirme

Yerel kurulum, çalıştırma, testler ve sürekli entegrasyon.

## Gereksinimler

- **Node.js** 22.22.2+ (geliştirmede 26.13.1 ile doğrulandı) ve **npm**
- **Python** 3.12+ (geliştirmede 3.15.2 ile doğrulandı)

Node 22.22.2 alt sınırı `jsdom@31` motor gereksiniminden gelir.

## Kurulum

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Ortam değişkenleri gerekirse `.env.example` dosyasını `.env` olarak kopyalayın.
`.env` dosyası Git'e eklenmez.

### 2. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env   # isteğe bağlı; varsayılanlar yerel backend'e uyar
```

## Çalıştırma

İki terminal kullanın.

**Terminal 1 — backend:**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

- API: <http://127.0.0.1:8000>
- Sağlık kontrolü: <http://127.0.0.1:8000/api/health>
- Etkileşimli dokümantasyon: <http://127.0.0.1:8000/docs>

**Terminal 2 — frontend:**

```powershell
cd frontend
npm run dev
```

Arayüz: <http://localhost:5173>

Vite, `/api` isteklerini `http://127.0.0.1:8000` adresine yönlendirir; bu
sayede geliştirme sırasında tarayıcı isteği aynı origin'den gider. CORS
yapılandırması yine de dar tutulur: yalnızca `BUILDFLOW_CORS_ORIGINS` içinde
açıkça listelenen origin'ler izinlidir (varsayılan: Vite 5173). Joker (`*`)
reddedilir.

> PowerShell `npm` komutunu engelliyorsa (`running scripts is disabled`)
> `npm.cmd run dev` kullanın.

## Frontend komutları

```powershell
cd frontend
npm install          # ilk kurulum
npm run dev          # geliştirme sunucusu (http://localhost:5173)
npm test             # Vitest - 178 test, 9 dosya
npm run build        # tsc -b && vite build
```

## Testler

```powershell
# Backend - 993 test
cd backend
.\.venv\Scripts\Activate.ps1
pytest

# Backend lint
python -m pyflakes app tests tools

# Frontend - 202 test / 10 dosya
cd ..\frontend
npm test

# Frontend üretim derlemesi
npm run build
```

## Sürekli entegrasyon

`.github/workflows/ci.yml` her `main` push'unda ve pull request'te dört
kontrolü çalıştırır:

| İş | Adımlar |
|---|---|
| `backend` | Python 3.12 · `pip install -e ".[dev]"` · `pytest` · `pyflakes app tests tools` |
| `frontend` | Node 22.23.5 · `npm ci` · `npm test` · `npm run build` |

`pyflakes` backend'in `dev` bağımlılıkları arasındadır; `.[dev]` kurulumuyla
birlikte gelir. Aynı komutlar yerelde de çalıştırılabilir.
