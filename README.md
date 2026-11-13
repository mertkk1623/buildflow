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

**Aşama 4.7 — frontend gerçek backend'e bağlandı.** Arayüz artık prototip veri
kullanmıyor: şablon indirme, Excel yükleme/analiz, AI önerilerinin onayı,
hesaplama ve Excel/PDF raporu uçtan uca gerçek FastAPI servisi üzerinden
çalışır.

| Endpoint | Görev |
|---|---|
| `GET /api/health` | Servis durumu |
| `GET /api/template` | Standart metraj şablonunu indirir (`.xlsx`) |
| `POST /api/analyze` | Excel yükler, okur, eşleştirir ve `pending` satırlar için AI önerisi döndürür |
| `POST /api/calculate` | Kullanıcı kararlarını doğrular, satın alma listesini hesaplar |
| `POST /api/report/excel` | Aynı hesaplamadan Excel satın alma raporu indirir |
| `POST /api/report/pdf` | Aynı hesaplamadan PDF satın alma raporu indirir |

Frontend, bu altı endpoint'in **tamamını** kullanır. Kullanılmayan, planlanan ya
da sahte endpoint yoktur. Veritabanı, kullanıcı girişi ve tedarikçi yönetimi
V1 kapsamı dışındadır.

### AI eşleştirme (Aşama 4.5)

AI **hesaplama yapmaz**. Yalnızca BOQ açıklamasını mevcut katalog adaylarıyla
eşleştirir ve sonucu bir **öneri** olarak döndürür.

- Varsayılan sağlayıcı `none`: AI kapalıdır, hiçbir ağ çağrısı yapılmaz ve
  yanıt deterministik sonuçla birebir aynı kalır.
- AI yalnızca `pending` satırlar için çağrılır; `rule`/`excluded`/`invalid`
  satırlarda hiç çağrılmaz.
- AI'ya **yalnızca** açıklama, bilinen dört özellik (aile/ölçü/kalite/kaplama)
  ve aday ürünlerin tanıtıcı özellikleri gönderilir. Miktar, birim, fire,
  ağırlık ve maliyet ne istekte ne yanıtta yer alır.
- Yanıt katı bir şemaya göre doğrulanır: `status` ∈ {`suggested`, `ambiguous`,
  `no_match`}, `suggested_code`, `confidence`, `reason`. Fazla/eksik alan,
  katalog dışı kod, bozuk JSON veya tutarsız durum **reddedilir**.
- **AI önerisi hiçbir zaman otomatik onaylanmaz.** `matched_code` alanı
  AI'dan etkilenmez; satır `pending` kalır. Kullanıcı onaylar, reddeder veya
  başka bir aday seçer. Kullanıcı kararı `apply_decisions()` doğrulamasından
  geçer.
- AI erişilemezse (timeout, bağlantı hatası, bozuk yanıt) analiz
  deterministik sonuçla tamamlanır; ilgili satırlar `pending` kalır ve
  kullanıcıya tek bir uyarı gösterilir.

AI'yı etkinleştirmek için `.env` dosyasında:

```ini
BUILDFLOW_AI_PROVIDER=openai-compatible
BUILDFLOW_AI_BASE_URL=https://api.openai.com/v1
BUILDFLOW_AI_MODEL=gpt-4o-mini
BUILDFLOW_AI_API_KEY=...          # yalnızca ortam değişkeninden okunur
BUILDFLOW_AI_TIMEOUT_SECONDS=10
```

API anahtarı yanıtta, hata mesajında ve logda **görünmez**. Eksik ya da
geçersiz yapılandırma uygulamayı durdurmaz; sunucu uyarı loglar ve AI'yı
devre dışı bırakır.

## Raporlama (Aşama 4.6)

`POST /api/report/excel` ve `POST /api/report/pdf`, `POST /api/calculate` ile
**aynı** istek gövdesini alır ve **aynı** hesap çekirdeğini çalıştırır. Rapor
katmanı hesap yapmaz; miktar, fire, ağırlık ve ticari boy değerleri olduğu
gibi taşınır. Böylece üç endpoint birbirinden ayrışamaz.

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

Onaylanmış kalem yoksa endpoint **422 `report-empty`** döner; boş bir
"satın alma listesi" üretilmez. Kararlar geçersizse `/api/calculate` ile aynı
hata gövdesi (409) döner.

### Rapor içeriği

Her iki biçim de aynı `Report` nesnesinden üretilir:

- **Özet** — satır/kalem/birleşme sayıları, toplam sipariş uzunluğu, bilinen
  teorik ağırlık, FULL/PARTIAL dağılımı.
- **Satın alma listesi** — malzeme kodu, açıklama, kaynak BOQ satırları, net,
  fire, brüt, ticari boy, sipariş adedi, sipariş uzunluğu, artan miktar,
  teorik ağırlık, FULL/PARTIAL, eksik bilgi ve uyarılar. Excel'de kalemler
  malzeme ailesine göre gruplanır ve her ailede alt toplam bandı bulunur.
- **Kaynak BOQ satırları** — her kalemin hangi satırlardan oluştuğu
  (izlenebilirlik), satır bazında miktar/fire/brüt ile.
- **Hesaba alınmayanlar** — onay bekleyen, reddedilen ve kapsam dışı satırlar
  gerekçeleriyle.

Raporlarda iki sınır açıkça yazılır:

1. Ağırlık, katalogdaki **teorik çıplak çelik kg/m** değerine dayalıdır;
   kantar veya sevkiyat ağırlığı değildir.
2. BuildFlow bu aşamada **kesim optimizasyonu veya nesting yapmaz**; sipariş
   miktarları ticari boya yuvarlanmış teorik ihtiyaçtır.

### Bilinmeyen değer kuralı

PARTIAL bir sonuçta bilinmeyen alan **asla sıfır gösterilmez**: Excel'de hücre
boş bırakılır, PDF'te `—` yer tutucusu kullanılır. Hiçbir grubun ağırlığı
bilinmiyorsa özet ağırlık alanı da boş kalır ve "Ağırlık durumu: KISMİ"
uyarısı görünür.

### Kütüphaneler ve font

| Bağımlılık | Gerekçe |
|---|---|
| `openpyxl` (mevcut) | Excel yazımı; zaten şablon üretiminde kullanılıyordu. |
| `fpdf2` | PDF üretimi. Saf Python, derleme gerektirmez, gömülü TTF destekler; `reportlab`/`weasyprint` gibi ağır ya da sistem kütüphanesi isteyen alternatifler tercih edilmedi. |
| `pypdf` (yalnızca geliştirme) | Testlerde PDF metnini çıkarıp Türkçe karakterleri ve sayfa numaralarını doğrulamak için. |
| DejaVu Sans / Bold | `app/reports/fonts/` altında projeye dahildir (Bitstream Vera türevi özgür lisans, `LICENSE-DejaVu.txt`). Sistem fontlarına bağımlılık yoktur. |

`app/domain` ve `app/excel` bu aşamada **değiştirilmedi**.

## Frontend entegrasyonu (Aşama 4.7)

Frontend hiçbir değeri kendi üretmez. Ekranlarda görünen her sayı, etiket ve
durum sunucunun yanıtından gelir; istemci yalnızca **biçimlendirir**.

### Veri akışı

```
Excel ──▶ POST /api/analyze ──▶ satır kararları (kullanıcı)
                                      │
                                      ▼
                        POST /api/calculate ──▶ satın alma listesi
                                      │
                                      ├──▶ POST /api/report/excel
                                      └──▶ POST /api/report/pdf
```

1. **Yükle** — `GET /api/template` şablonu indirir; `POST /api/analyze`
   dosyayı yükler. Yanıt satırları `rule` / `pending` / `excluded` / `invalid`
   olarak gelir. Deterministik eşleşmeler ile AI önerileri ayrı alanlardadır.
2. **Analiz** — yalnızca okuma; sunucunun döndürdüğü dağılım gösterilir.
3. **Eşleştirme** — `pending` satırlar için kullanıcı aday seçer, onaylar,
   reddeder veya kararını sıfırlar. **AI önerisi otomatik onaylanmaz**; hiçbir
   aday varsayılan seçili gelmez.
4. **Hesapla** — yalnızca ham satırlar (`source_row`, `boq_no`, `description`,
   `quantity`, `unit`, `waste_percent`) ve kararlar gönderilir. Eşleştirme
   durumu, hesaplanmış miktar veya ağırlık **hiç gönderilmez**.
5. **Dışa aktar** — rapor gövdesi `/api/calculate` gövdesiyle **birebir aynıdır**;
   dosya sunucuda üretilir, adı `Content-Disposition` başlığından okunur.

### Backend sözleşmesi tek kaynaktır

`src/types/api.ts`, `app/api/schemas.py`'nin birebir karşılığıdır. Kararlar
backend'de `apply_decisions()` doğrulamasından geçer; istemciden gelen uydurma
kod, katalog dışı eşleşme veya hesaplanmış alan sunucu tarafından reddedilir
(`422` / `409`). Ölçekli değerler (Decimal) JSON'da **string** taşınır —
kayan nokta yuvarlaması oluşmaz.

### Ortam değişkenleri

`frontend/.env.example` dosyasını `.env` olarak kopyalayın.

| Değişken | Varsayılan | Görev |
|---|---|---|
| `VITE_API_BASE_URL` | boş | Boşsa istekler görece `/api/...` gider ve Vite proxy'si devreye girer. Doluysa (ör. `http://127.0.0.1:8000`) doğrudan o adrese gidilir ve backend CORS izin listesi gerekir. |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` | Yalnızca geliştirme sunucusunun proxy hedefi. Üretim derlemesini etkilemez. |

Geliştirmede varsayılan davranış **proxy**'dir: tarayıcı isteği aynı origin'den
gider, CORS gerekmez. `VITE_API_BASE_URL` doldurulursa backend'de
`BUILDFLOW_CORS_ORIGINS` listesine frontend adresi eklenmelidir; joker (`*`)
kabul edilmez.

### Hata yönetimi

Tüm hatalar tek `ApiError` tipinde toplanır (sunucu zarfı, bağlantı hatası,
iptal). Ekranlarda yalnızca sunucunun güvenli metinleri gösterilir — stack
trace, dosya yolu, sağlayıcı anahtarı veya ham gövde asla gösterilmez.
Karşılanan durumlar: geçersiz/büyük Excel, desteklenmeyen biçim, eksik veya
hatalı kolon, geçersiz karar, backend'e ulaşılamaması, AI sağlayıcı hatası,
PARTIAL (KISMİ) hesaplama ve rapor üretim hatası.

### Frontend komutları

```powershell
cd frontend
npm install          # ilk kurulum
npm run dev          # geliştirme sunucusu (http://localhost:5173)
npm test             # Vitest - 178 test, 9 dosya
npm run build        # tsc -b && vite build
```

> PowerShell `npm` betiklerini engelliyorsa `npm.cmd` kullanın.

### Test yaklaşımı

Testler ağ çağrısını `fetch` düzeyinde taklit eder; sahte state kurulmaz. Her
test "ekranda ne var" ile "sunucuya ne gitti"yi aynı akışta doğrular. Beklenmeyen
bir istek testi açıkça düşürür, böylece sessiz sahte başarı oluşmaz. Fixture'lar
elle uydurulmadı: gerçek backend yanıtlarından üretildi (`src/test/fixtures/`).

## Teknoloji

| Katman | Teknoloji |
|---|---|
| Frontend | React + TypeScript + Vite |
| Stil | Tailwind CSS v4 |
| Backend | Python + FastAPI |
| Raporlama | openpyxl (Excel) + fpdf2 (PDF) |
| Test | Pytest (backend) + Vitest (frontend) |
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

- **Node.js** 22.12+ (geliştirmede 26.13.1 ile doğrulandı) ve **npm**
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

Örnek istekler:

```powershell
# Metraj dosyasını analiz et
curl.exe -F "file=@..\templates\ornek_metraj.xlsx" http://127.0.0.1:8000/api/analyze

# Şablonu indir
curl.exe -o metraj_sablonu.xlsx http://127.0.0.1:8000/api/template
```

`POST /api/calculate` gövdesi, analiz yanıtındaki **ham** satırlar (yalnızca
`source_row`, `boq_no`, `description`, `quantity`, `unit`, `waste_percent`) ve
kullanıcı kararlarından (`boq_no`, `action`, `code`, `reason`) oluşur. Sunucu
eşleştirmeyi ve hesabı her istekte yeniden yapar; istemciden gelen eşleştirme
durumu veya hesaplanmış değer kabul edilmez.

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

## Testler

```powershell
# Backend - 871 test
cd backend
.\.venv\Scripts\Activate.ps1
pytest

# Backend lint
python -m pyflakes app tests

# Frontend - 178 test / 9 dosya
cd ..\frontend
npm test

# Frontend üretim derlemesi
npm run build
```

Ayrıntılı doğrulama (gerçek `.xlsx` yükleme, Excel/PDF indirme, hata
senaryoları) için bkz. **Frontend entegrasyonu (Aşama 4.7)** bölümü.

### Sürekli entegrasyon

`.github/workflows/ci.yml` her `main` push'unda ve pull request'te dört
kontrolü çalıştırır:

| İş | Adımlar |
|---|---|
| `backend` | Python 3.12 · `pip install -e ".[dev]"` · `pytest` · `pyflakes app tests` |
| `frontend` | Node 22.12 · `npm ci` · `npm test` · `npm run build` |

`pyflakes` backend'in `dev` bağımlılıkları arasındadır; `.[dev]` kurulumuyla
birlikte gelir. Aynı komutlar yerelde de çalıştırılabilir.

## Yol haritası

Geliştirme sırası `ROADMAP.md` içinde tanımlıdır:

0. Proje kurulumu ve ürün planı
1. SaaS arayüz prototipi
2. Frontend uygulama iskeleti ve demo akışı
3. Backend ve deterministik hesap motoru
4. AI malzeme tanıma ve sonuç yorumlama
5. Dışa aktarma (Excel/PDF raporlama), son rötuşlar ve yayın
