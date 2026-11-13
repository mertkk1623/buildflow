# BuildFlow AI

Ä°nÅŸaat **metraj (BOQ)** dosyalarÄ±nÄ±, AI destekli malzeme tanÄ±ma ve ÅŸeffaf
hesaplamalarla **incelenmiÅŸ ve satÄ±n almaya hazÄ±r bir malzeme listesine**
dÃ¶nÃ¼ÅŸtÃ¼ren web uygulamasÄ±.

> KullanÄ±cÄ± bir BOQ yÃ¼kler. Uygulama malzeme aÃ§Ä±klamalarÄ±nÄ± yorumlar, malzeme
> kataloÄŸuyla eÅŸleÅŸtirir, belirsiz eÅŸleÅŸmeleri kullanÄ±cÄ±ya onaylatÄ±r, malzeme
> ihtiyacÄ±nÄ± hesaplar, tekrar eden kalemleri birleÅŸtirir ve Excel/PDF Ã§Ä±ktÄ±sÄ±
> Ã¼retir.

Bu bir inÅŸaat ERP'si, metraj/quantity-takeoff programÄ± veya statik tasarÄ±m
aracÄ± deÄŸildir. V1 kapsamÄ± `ROADMAP.md` dosyasÄ±nda tanÄ±mlÄ±dÄ±r.

## Durum

**AÅŸama 4.7 â€” frontend gerÃ§ek backend'e baÄŸlandÄ±.** ArayÃ¼z artÄ±k prototip veri
kullanmÄ±yor: ÅŸablon indirme, Excel yÃ¼kleme/analiz, AI Ã¶nerilerinin onayÄ±,
hesaplama ve Excel/PDF raporu uÃ§tan uca gerÃ§ek FastAPI servisi Ã¼zerinden
Ã§alÄ±ÅŸÄ±r.

| Endpoint | GÃ¶rev |
|---|---|
| `GET /api/health` | Servis durumu |
| `GET /api/template` | Standart metraj ÅŸablonunu indirir (`.xlsx`) |
| `POST /api/analyze` | Excel yÃ¼kler, okur, eÅŸleÅŸtirir ve `pending` satÄ±rlar iÃ§in AI Ã¶nerisi dÃ¶ndÃ¼rÃ¼r |
| `POST /api/calculate` | KullanÄ±cÄ± kararlarÄ±nÄ± doÄŸrular, satÄ±n alma listesini hesaplar |
| `POST /api/report/excel` | AynÄ± hesaplamadan Excel satÄ±n alma raporu indirir |
| `POST /api/report/pdf` | AynÄ± hesaplamadan PDF satÄ±n alma raporu indirir |

Frontend, bu altÄ± endpoint'in **tamamÄ±nÄ±** kullanÄ±r. KullanÄ±lmayan, planlanan ya
da sahte endpoint yoktur. VeritabanÄ±, kullanÄ±cÄ± giriÅŸi ve tedarikÃ§i yÃ¶netimi
V1 kapsamÄ± dÄ±ÅŸÄ±ndadÄ±r.

### AI eÅŸleÅŸtirme (AÅŸama 4.5)

AI **hesaplama yapmaz**. YalnÄ±zca BOQ aÃ§Ä±klamasÄ±nÄ± mevcut katalog adaylarÄ±yla
eÅŸleÅŸtirir ve sonucu bir **Ã¶neri** olarak dÃ¶ndÃ¼rÃ¼r.

- VarsayÄ±lan saÄŸlayÄ±cÄ± `none`: AI kapalÄ±dÄ±r, hiÃ§bir aÄŸ Ã§aÄŸrÄ±sÄ± yapÄ±lmaz ve
  yanÄ±t deterministik sonuÃ§la birebir aynÄ± kalÄ±r.
- AI yalnÄ±zca `pending` satÄ±rlar iÃ§in Ã§aÄŸrÄ±lÄ±r; `rule`/`excluded`/`invalid`
  satÄ±rlarda hiÃ§ Ã§aÄŸrÄ±lmaz.
- AI'ya **yalnÄ±zca** aÃ§Ä±klama, bilinen dÃ¶rt Ã¶zellik (aile/Ã¶lÃ§Ã¼/kalite/kaplama)
  ve aday Ã¼rÃ¼nlerin tanÄ±tÄ±cÄ± Ã¶zellikleri gÃ¶nderilir. Miktar, birim, fire,
  aÄŸÄ±rlÄ±k ve maliyet ne istekte ne yanÄ±tta yer alÄ±r.
- YanÄ±t katÄ± bir ÅŸemaya gÃ¶re doÄŸrulanÄ±r: `status` âˆˆ {`suggested`, `ambiguous`,
  `no_match`}, `suggested_code`, `confidence`, `reason`. Fazla/eksik alan,
  katalog dÄ±ÅŸÄ± kod, bozuk JSON veya tutarsÄ±z durum **reddedilir**.
- **AI Ã¶nerisi hiÃ§bir zaman otomatik onaylanmaz.** `matched_code` alanÄ±
  AI'dan etkilenmez; satÄ±r `pending` kalÄ±r. KullanÄ±cÄ± onaylar, reddeder veya
  baÅŸka bir aday seÃ§er. KullanÄ±cÄ± kararÄ± `apply_decisions()` doÄŸrulamasÄ±ndan
  geÃ§er.
- AI eriÅŸilemezse (timeout, baÄŸlantÄ± hatasÄ±, bozuk yanÄ±t) analiz
  deterministik sonuÃ§la tamamlanÄ±r; ilgili satÄ±rlar `pending` kalÄ±r ve
  kullanÄ±cÄ±ya tek bir uyarÄ± gÃ¶sterilir.

AI'yÄ± etkinleÅŸtirmek iÃ§in `.env` dosyasÄ±nda:

```ini
BUILDFLOW_AI_PROVIDER=openai-compatible
BUILDFLOW_AI_BASE_URL=https://api.openai.com/v1
BUILDFLOW_AI_MODEL=gpt-4o-mini
BUILDFLOW_AI_API_KEY=...          # yalnÄ±zca ortam deÄŸiÅŸkeninden okunur
BUILDFLOW_AI_TIMEOUT_SECONDS=10
```

API anahtarÄ± yanÄ±tta, hata mesajÄ±nda ve logda **gÃ¶rÃ¼nmez**. Eksik ya da
geÃ§ersiz yapÄ±landÄ±rma uygulamayÄ± durdurmaz; sunucu uyarÄ± loglar ve AI'yÄ±
devre dÄ±ÅŸÄ± bÄ±rakÄ±r.

## Raporlama (AÅŸama 4.6)

`POST /api/report/excel` ve `POST /api/report/pdf`, `POST /api/calculate` ile
**aynÄ±** istek gÃ¶vdesini alÄ±r ve **aynÄ±** hesap Ã§ekirdeÄŸini Ã§alÄ±ÅŸtÄ±rÄ±r. Rapor
katmanÄ± hesap yapmaz; miktar, fire, aÄŸÄ±rlÄ±k ve ticari boy deÄŸerleri olduÄŸu
gibi taÅŸÄ±nÄ±r. BÃ¶ylece Ã¼Ã§ endpoint birbirinden ayrÄ±ÅŸamaz.

```powershell
# Excel raporu
curl.exe -X POST http://127.0.0.1:8000/api/report/excel `
  -H "Content-Type: application/json" `
  -d "@calculate-request.json" -o satin-alma.xlsx

# PDF raporu
curl.exe -X POST http://127.0.0.1:8000/api/report/pdf `
  -H "Content-Type: application/json" `
  -d "@calculate-request.json" -o satin-alma.pdf
```

OnaylanmÄ±ÅŸ kalem yoksa endpoint **422 `report-empty`** dÃ¶ner; boÅŸ bir
"satÄ±n alma listesi" Ã¼retilmez. Kararlar geÃ§ersizse `/api/calculate` ile aynÄ±
hata gÃ¶vdesi (409) dÃ¶ner.

### Rapor iÃ§eriÄŸi

Her iki biÃ§im de aynÄ± `Report` nesnesinden Ã¼retilir:

- **Ã–zet** â€” satÄ±r/kalem/birleÅŸme sayÄ±larÄ±, toplam sipariÅŸ uzunluÄŸu, bilinen
  teorik aÄŸÄ±rlÄ±k, FULL/PARTIAL daÄŸÄ±lÄ±mÄ±.
- **SatÄ±n alma listesi** â€” malzeme kodu, aÃ§Ä±klama, kaynak BOQ satÄ±rlarÄ±, net,
  fire, brÃ¼t, ticari boy, sipariÅŸ adedi, sipariÅŸ uzunluÄŸu, artan miktar,
  teorik aÄŸÄ±rlÄ±k, FULL/PARTIAL, eksik bilgi ve uyarÄ±lar. Excel'de kalemler
  malzeme ailesine gÃ¶re gruplanÄ±r ve her ailede alt toplam bandÄ± bulunur.
- **Kaynak BOQ satÄ±rlarÄ±** â€” her kalemin hangi satÄ±rlardan oluÅŸtuÄŸu
  (izlenebilirlik), satÄ±r bazÄ±nda miktar/fire/brÃ¼t ile.
- **Hesaba alÄ±nmayanlar** â€” onay bekleyen, reddedilen ve kapsam dÄ±ÅŸÄ± satÄ±rlar
  gerekÃ§eleriyle.

Raporlarda iki sÄ±nÄ±r aÃ§Ä±kÃ§a yazÄ±lÄ±r:

1. AÄŸÄ±rlÄ±k, katalogdaki **teorik Ã§Ä±plak Ã§elik kg/m** deÄŸerine dayalÄ±dÄ±r;
   kantar veya sevkiyat aÄŸÄ±rlÄ±ÄŸÄ± deÄŸildir.
2. BuildFlow bu aÅŸamada **kesim optimizasyonu veya nesting yapmaz**; sipariÅŸ
   miktarlarÄ± ticari boya yuvarlanmÄ±ÅŸ teorik ihtiyaÃ§tÄ±r.

### Bilinmeyen deÄŸer kuralÄ±

PARTIAL bir sonuÃ§ta bilinmeyen alan **asla sÄ±fÄ±r gÃ¶sterilmez**: Excel'de hÃ¼cre
boÅŸ bÄ±rakÄ±lÄ±r, PDF'te `â€”` yer tutucusu kullanÄ±lÄ±r. HiÃ§bir grubun aÄŸÄ±rlÄ±ÄŸÄ±
bilinmiyorsa Ã¶zet aÄŸÄ±rlÄ±k alanÄ± da boÅŸ kalÄ±r ve "AÄŸÄ±rlÄ±k durumu: KISMÄ°"
uyarÄ±sÄ± gÃ¶rÃ¼nÃ¼r.

### KÃ¼tÃ¼phaneler ve font

| BaÄŸÄ±mlÄ±lÄ±k | GerekÃ§e |
|---|---|
| `openpyxl` (mevcut) | Excel yazÄ±mÄ±; zaten ÅŸablon Ã¼retiminde kullanÄ±lÄ±yordu. |
| `fpdf2` | PDF Ã¼retimi. Saf Python, derleme gerektirmez, gÃ¶mÃ¼lÃ¼ TTF destekler; `reportlab`/`weasyprint` gibi aÄŸÄ±r ya da sistem kÃ¼tÃ¼phanesi isteyen alternatifler tercih edilmedi. |
| `pypdf` (yalnÄ±zca geliÅŸtirme) | Testlerde PDF metnini Ã§Ä±karÄ±p TÃ¼rkÃ§e karakterleri ve sayfa numaralarÄ±nÄ± doÄŸrulamak iÃ§in. |
| DejaVu Sans / Bold | `app/reports/fonts/` altÄ±nda projeye dahildir (Bitstream Vera tÃ¼revi Ã¶zgÃ¼r lisans, `LICENSE-DejaVu.txt`). Sistem fontlarÄ±na baÄŸÄ±mlÄ±lÄ±k yoktur. |

`app/domain` ve `app/excel` bu aÅŸamada **deÄŸiÅŸtirilmedi**.

## Frontend entegrasyonu (AÅŸama 4.7)

Frontend hiÃ§bir deÄŸeri kendi Ã¼retmez. Ekranlarda gÃ¶rÃ¼nen her sayÄ±, etiket ve
durum sunucunun yanÄ±tÄ±ndan gelir; istemci yalnÄ±zca **biÃ§imlendirir**.

### Veri akÄ±ÅŸÄ±

```
Excel â”€â”€â–¶ POST /api/analyze â”€â”€â–¶ satÄ±r kararlarÄ± (kullanÄ±cÄ±)
                                      â”‚
                                      â–¼
                        POST /api/calculate â”€â”€â–¶ satÄ±n alma listesi
                                      â”‚
                                      â”œâ”€â”€â–¶ POST /api/report/excel
                                      â””â”€â”€â–¶ POST /api/report/pdf
```

1. **YÃ¼kle** â€” `GET /api/template` ÅŸablonu indirir; `POST /api/analyze`
   dosyayÄ± yÃ¼kler. YanÄ±t satÄ±rlarÄ± `rule` / `pending` / `excluded` / `invalid`
   olarak gelir. Deterministik eÅŸleÅŸmeler ile AI Ã¶nerileri ayrÄ± alanlardadÄ±r.
2. **Analiz** â€” yalnÄ±zca okuma; sunucunun dÃ¶ndÃ¼rdÃ¼ÄŸÃ¼ daÄŸÄ±lÄ±m gÃ¶sterilir.
3. **EÅŸleÅŸtirme** â€” `pending` satÄ±rlar iÃ§in kullanÄ±cÄ± aday seÃ§er, onaylar,
   reddeder veya kararÄ±nÄ± sÄ±fÄ±rlar. **AI Ã¶nerisi otomatik onaylanmaz**; hiÃ§bir
   aday varsayÄ±lan seÃ§ili gelmez.
4. **Hesapla** â€” yalnÄ±zca ham satÄ±rlar (`source_row`, `boq_no`, `description`,
   `quantity`, `unit`, `waste_percent`) ve kararlar gÃ¶nderilir. EÅŸleÅŸtirme
   durumu, hesaplanmÄ±ÅŸ miktar veya aÄŸÄ±rlÄ±k **hiÃ§ gÃ¶nderilmez**.
5. **DÄ±ÅŸa aktar** â€” rapor gÃ¶vdesi `/api/calculate` gÃ¶vdesiyle **birebir aynÄ±dÄ±r**;
   dosya sunucuda Ã¼retilir, adÄ± `Content-Disposition` baÅŸlÄ±ÄŸÄ±ndan okunur.

### Backend sÃ¶zleÅŸmesi tek kaynaktÄ±r

`src/types/api.ts`, `app/api/schemas.py`'nin birebir karÅŸÄ±lÄ±ÄŸÄ±dÄ±r. Kararlar
backend'de `apply_decisions()` doÄŸrulamasÄ±ndan geÃ§er; istemciden gelen uydurma
kod, katalog dÄ±ÅŸÄ± eÅŸleÅŸme veya hesaplanmÄ±ÅŸ alan sunucu tarafÄ±ndan reddedilir
(`422` / `409`). Ã–lÃ§ekli deÄŸerler (Decimal) JSON'da **string** taÅŸÄ±nÄ±r â€”
kayan nokta yuvarlamasÄ± oluÅŸmaz.

### Ortam deÄŸiÅŸkenleri

`frontend/.env.example` dosyasÄ±nÄ± `.env` olarak kopyalayÄ±n.

| DeÄŸiÅŸken | VarsayÄ±lan | GÃ¶rev |
|---|---|---|
| `VITE_API_BASE_URL` | boÅŸ | BoÅŸsa istekler gÃ¶rece `/api/...` gider ve Vite proxy'si devreye girer. Doluysa (Ã¶r. `http://127.0.0.1:8000`) doÄŸrudan o adrese gidilir ve backend CORS izin listesi gerekir. |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` | YalnÄ±zca geliÅŸtirme sunucusunun proxy hedefi. Ãœretim derlemesini etkilemez. |

GeliÅŸtirmede varsayÄ±lan davranÄ±ÅŸ **proxy**'dir: tarayÄ±cÄ± isteÄŸi aynÄ± origin'den
gider, CORS gerekmez. `VITE_API_BASE_URL` doldurulursa backend'de
`BUILDFLOW_CORS_ORIGINS` listesine frontend adresi eklenmelidir; joker (`*`)
kabul edilmez.

### Hata yÃ¶netimi

TÃ¼m hatalar tek `ApiError` tipinde toplanÄ±r (sunucu zarfÄ±, baÄŸlantÄ± hatasÄ±,
iptal). Ekranlarda yalnÄ±zca sunucunun gÃ¼venli metinleri gÃ¶sterilir â€” stack
trace, dosya yolu, saÄŸlayÄ±cÄ± anahtarÄ± veya ham gÃ¶vde asla gÃ¶sterilmez.
KarÅŸÄ±lanan durumlar: geÃ§ersiz/bÃ¼yÃ¼k Excel, desteklenmeyen biÃ§im, eksik veya
hatalÄ± kolon, geÃ§ersiz karar, backend'e ulaÅŸÄ±lamamasÄ±, AI saÄŸlayÄ±cÄ± hatasÄ±,
PARTIAL (KISMÄ°) hesaplama ve rapor Ã¼retim hatasÄ±.

### Frontend komutlarÄ±

```powershell
cd frontend
npm install          # ilk kurulum
npm run dev          # geliÅŸtirme sunucusu (http://localhost:5173)
npm test             # Vitest - 177 test, 9 dosya
npm run build        # tsc -b && vite build
```

> PowerShell `npm` betiklerini engelliyorsa `npm.cmd` kullanÄ±n.

### Test yaklaÅŸÄ±mÄ±

Testler aÄŸ Ã§aÄŸrÄ±sÄ±nÄ± `fetch` dÃ¼zeyinde taklit eder; sahte state kurulmaz. Her
test "ekranda ne var" ile "sunucuya ne gitti"yi aynÄ± akÄ±ÅŸta doÄŸrular. Beklenmeyen
bir istek testi aÃ§Ä±kÃ§a dÃ¼ÅŸÃ¼rÃ¼r, bÃ¶ylece sessiz sahte baÅŸarÄ± oluÅŸmaz. Fixture'lar
elle uydurulmadÄ±: gerÃ§ek backend yanÄ±tlarÄ±ndan Ã¼retildi (`src/test/fixtures/`).

## Teknoloji

| Katman | Teknoloji |
|---|---|
| Frontend | React + TypeScript + Vite |
| Stil | Tailwind CSS v4 |
| Backend | Python + FastAPI |
| Raporlama | openpyxl (Excel) + fpdf2 (PDF) |
| Test | Pytest (backend) + Vitest (frontend) |
| SÃ¼rÃ¼m kontrolÃ¼ | Git + GitHub |

VeritabanÄ±, kimlik doÄŸrulama ve abonelik altyapÄ±sÄ± **V1 kapsamÄ±nda deÄŸildir.**

## KlasÃ¶r yapÄ±sÄ±

```
BuildFlow-AI/
â”œâ”€â”€ ROADMAP.md          ÃœrÃ¼n ve geliÅŸtirme planÄ± (tek doÄŸruluk kaynaÄŸÄ±)
â”œâ”€â”€ frontend/           React + TypeScript + Tailwind
â””â”€â”€ backend/            FastAPI + Pytest
```

## Gereksinimler

- **Node.js** 22.12+ (geliÅŸtirmede 26.13.1 ile doÄŸrulandÄ±) ve **npm**
- **Python** 3.12+ (geliÅŸtirmede 3.15.2 ile doÄŸrulandÄ±)

## Kurulum

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Ortam deÄŸiÅŸkenleri gerekirse `.env.example` dosyasÄ±nÄ± `.env` olarak kopyalayÄ±n.
`.env` dosyasÄ± Git'e eklenmez.

### 2. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env   # isteÄŸe baÄŸlÄ±; varsayÄ±lanlar yerel backend'e uyar
```

## Ã‡alÄ±ÅŸtÄ±rma

Ä°ki terminal kullanÄ±n.

**Terminal 1 â€” backend:**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

- API: <http://127.0.0.1:8000>
- SaÄŸlÄ±k kontrolÃ¼: <http://127.0.0.1:8000/api/health>
- EtkileÅŸimli dokÃ¼mantasyon: <http://127.0.0.1:8000/docs>

Ã–rnek istekler:

```powershell
# Metraj dosyasÄ±nÄ± analiz et
curl.exe -F "file=@..\templates\ornek_metraj.xlsx" http://127.0.0.1:8000/api/analyze

# Åablonu indir
curl.exe -o metraj_sablonu.xlsx http://127.0.0.1:8000/api/template
```

`POST /api/calculate` gÃ¶vdesi, analiz yanÄ±tÄ±ndaki **ham** satÄ±rlar (yalnÄ±zca
`source_row`, `boq_no`, `description`, `quantity`, `unit`, `waste_percent`) ve
kullanÄ±cÄ± kararlarÄ±ndan (`boq_no`, `action`, `code`, `reason`) oluÅŸur. Sunucu
eÅŸleÅŸtirmeyi ve hesabÄ± her istekte yeniden yapar; istemciden gelen eÅŸleÅŸtirme
durumu veya hesaplanmÄ±ÅŸ deÄŸer kabul edilmez.

**Terminal 2 â€” frontend:**

```powershell
cd frontend
npm run dev
```

ArayÃ¼z: <http://localhost:5173>

Vite, `/api` isteklerini `http://127.0.0.1:8000` adresine yÃ¶nlendirir; bu
sayede geliÅŸtirme sÄ±rasÄ±nda tarayÄ±cÄ± isteÄŸi aynÄ± origin'den gider. CORS
yapÄ±landÄ±rmasÄ± yine de dar tutulur: yalnÄ±zca `BUILDFLOW_CORS_ORIGINS` iÃ§inde
aÃ§Ä±kÃ§a listelenen origin'ler izinlidir (varsayÄ±lan: Vite 5173). Joker (`*`)
reddedilir.

> PowerShell `npm` komutunu engelliyorsa (`running scripts is disabled`)
> `npm.cmd run dev` kullanÄ±n.

## Testler

```powershell
# Backend - 871 test
cd backend
.\.venv\Scripts\Activate.ps1
pytest

# Backend lint
python -m pyflakes app tests

# Frontend - 177 test / 9 dosya
cd ..\frontend
npm test

# Frontend Ã¼retim derlemesi
npm run build
```

AyrÄ±ntÄ±lÄ± doÄŸrulama (gerÃ§ek `.xlsx` yÃ¼kleme, Excel/PDF indirme, hata
senaryolarÄ±) iÃ§in bkz. **Frontend entegrasyonu (AÅŸama 4.7)** bÃ¶lÃ¼mÃ¼.

### SÃ¼rekli entegrasyon

`.github/workflows/ci.yml` her `main` push'unda ve pull request'te dÃ¶rt
kontrolÃ¼ Ã§alÄ±ÅŸtÄ±rÄ±r:

| Ä°ÅŸ | AdÄ±mlar |
|---|---|
| `backend` | Python 3.12 Â· `pip install -e ".[dev]"` Â· `pytest` Â· `pyflakes app tests` |
| `frontend` | Node 22.12 Â· `npm ci` Â· `npm test` Â· `npm run build` |

`pyflakes` backend'in `dev` baÄŸÄ±mlÄ±lÄ±klarÄ± arasÄ±ndadÄ±r; `.[dev]` kurulumuyla
birlikte gelir. AynÄ± komutlar yerelde de Ã§alÄ±ÅŸtÄ±rÄ±labilir.

## Yol haritasÄ±

GeliÅŸtirme sÄ±rasÄ± `ROADMAP.md` iÃ§inde tanÄ±mlÄ±dÄ±r:

0. Proje kurulumu ve Ã¼rÃ¼n planÄ±
1. SaaS arayÃ¼z prototipi
2. Frontend uygulama iskeleti ve demo akÄ±ÅŸÄ±
3. Backend ve deterministik hesap motoru
4. AI malzeme tanÄ±ma ve sonuÃ§ yorumlama
5. DÄ±ÅŸa aktarma (Excel/PDF raporlama), son rÃ¶tuÅŸlar ve yayÄ±n
