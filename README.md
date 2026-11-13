# BuildFlow AI

İnşaat **metraj (BOQ)** dosyalarını, AI destekli malzeme tanıma ve şeffaf
hesaplamalarla **incelenmiş ve satın almaya hazır bir malzeme listesine**
dönüştüren web uygulaması.

> Kullanıcı bir BOQ yükler. Uygulama malzeme açıklamalarını yorumlar, malzeme
> kataloğuyla eşleştirir, belirsiz eşleşmeleri kullanıcıya onaylatır, malzeme
> ihtiyacını hesaplar, tekrar eden kalemleri birleştirir ve Excel/PDF çıktısı
> üretir.

Bu bir inşaat ERP'si, metraj/quantity-takeoff programı veya statik tasarım
aracı değildir. V1 kapsamı `ROADMAP.md` dosyasında tanımlıdır.

## Durum

**Faz 0 — Proje iskeleti tamamlanıyor.** Henüz ürün ekranı, hesap motoru,
AI entegrasyonu veya dışa aktarma yoktur. Mevcut tek işlevsellik, frontend ve
backend'in birlikte çalıştığını doğrulayan sağlık kontrolüdür.

## Teknoloji

| Katman | Teknoloji |
|---|---|
| Frontend | React + TypeScript + Vite |
| Stil | Tailwind CSS v4 |
| Backend | Python + FastAPI |
| Test | Pytest |
| Sürüm kontrolü | Git + GitHub |

Veritabanı, kimlik doğrulama ve abonelik altyapısı **V1 kapsamında değildir.**

## Klasör yapısı

```
BuildFlow-AI/
├── ROADMAP.md          Ürün ve geliştirme planı (tek doğruluk kaynağı)
├── frontend/           React + TypeScript + Tailwind
└── backend/            FastAPI + Pytest
```

## Gereksinimler

- **Node.js** 20.19+ (geliştirmede 26.x ile doğrulandı) ve **npm**
- **Python** 3.12+ (geliştirmede 3.15.2 ile doğrulandı)

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
sayede geliştirme sırasında CORS yapılandırması gerekmez.

> PowerShell `npm` komutunu engelliyorsa (`running scripts is disabled`)
> `npm.cmd run dev` kullanın.

## Testler

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

## Yol haritası

Geliştirme sırası `ROADMAP.md` içinde tanımlıdır:

0. Proje kurulumu ve ürün planı ← *şu an buradayız*
1. SaaS arayüz prototipi
2. Frontend uygulama iskeleti ve demo akışı
3. Backend ve deterministik hesap motoru
4. AI malzeme tanıma ve sonuç yorumlama
5. Dışa aktarma, son rötuşlar ve yayın

## Lisans

Henüz belirlenmedi.
