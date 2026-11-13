# API Dokümantasyonu

BuildFlow AI'ın HTTP arayüzü. Frontend bu altı endpoint'in tamamını kullanır;
kullanılmayan veya planlanmış endpoint yoktur.

| Endpoint | Görev |
|---|---|
| `GET /api/health` | Servis durumu |
| `GET /api/template` | Standart metraj şablonunu indirir (`.xlsx`) |
| `POST /api/analyze` | Excel yükler, okur, eşleştirir ve `pending` satırlar için AI önerisi döndürür |
| `POST /api/calculate` | Kullanıcı kararlarını doğrular, satın alma listesini hesaplar |
| `POST /api/report/excel` | Aynı hesaplamadan Excel satın alma raporu indirir |
| `POST /api/report/pdf` | Aynı hesaplamadan PDF satın alma raporu indirir |

Etkileşimli (OpenAPI) dokümantasyon: <http://127.0.0.1:8000/docs>

---

## Hesap akışı

```
Excel ──▶ POST /api/analyze ──▶ satır kararları (kullanıcı)
                                      │
                                      ▼
                        POST /api/calculate ──▶ satın alma listesi
                                      │
                                      ├──▶ POST /api/report/excel
                                      └──▶ POST /api/report/pdf
```

Sunucu, eşleştirmeyi ve hesabı **her istekte yeniden yapar**. İstemciden gelen
eşleştirme durumu veya hesaplanmış değer kabul edilmez.

---

## POST /api/analyze

`multipart/form-data` ile tek bir `.xlsx` dosyası alır. En fazla **10 MB**.
İlk sayfa ya da `Metraj` adlı sayfa okunur.

Yanıt satırları dört durumdan birinde gelir: `rule`, `pending`, `excluded`,
`invalid`. Deterministik eşleşmeler ile AI önerileri **ayrı alanlarda** durur.

### `ai` özeti

`ai.enabled` yalnızca **yapılandırmayı** anlatır; "kaç satır işlendi" anlamına
gelmez. AI açık ama dosyada onay bekleyen satır yoksa sayaçlar sıfır döner ve
neden `ai.skipped_reason` alanında belirtilir:

| `skipped_reason` | Anlamı |
|---|---|
| `no-pending-rows` | Tüm satırlar deterministik çözüldü veya kapsam dışı kaldı; AI çağrısı yapılmadı |
| `missing-row-identity` | Pending satır var ama BOQ No/açıklama eksik; AI'ya gönderilemedi |

`skipped_reason` ve `skipped_message` alanları **yalnızca** böyle bir durumda
yanıtta bulunur; AI gerçekten çalıştıysa veya kapalıysa hiç gönderilmez. Bu,
alanları eklerken eski istemcileri bozmamak için bilinçli bir tercihtir.

```powershell
curl.exe -F "file=@..\templates\ornek_metraj.xlsx" http://127.0.0.1:8000/api/analyze
```

## POST /api/calculate

Gövde iki parçadan oluşur:

1. **Ham satırlar** — yalnızca `source_row`, `boq_no`, `description`,
   `quantity`, `unit`, `waste_percent`
2. **Kullanıcı kararları** — `boq_no`, `action`, `code`, `reason`

Eşleştirme durumu, hesaplanmış miktar veya ağırlık **hiç gönderilmez**.
Kararlar `apply_decisions()` doğrulamasından geçer; uydurma kod, katalog dışı
eşleşme veya hesaplanmış alan sunucu tarafından reddedilir.

Ölçekli değerler (Decimal) JSON'da **string** taşınır — kayan nokta yuvarlaması
oluşmaz.

### Hesaba alınmayan satırlar

`skipped` dizisindeki her satır `status` alanıyla **jenerik** durumunu taşır
(`pending`, `rejected`, `excluded`, `invalid`, `unknown-code`). `excluded`
durumunda gerçek neden ayrıca belirtilir:

| `exclusion_reason` | Etiket | Ne yapmalı |
|---|---|---|
| `waste` | Fire tanımsız | `waste_percent` doldurulmalı (fire sıfır varsayılmaz) |
| `unit` | Birim desteklenmiyor | Birim `m`, `kg` veya `t` olmalı |
| `catalog` | Katalogda karşılığı yok | Açıklamadaki ölçü/kalite/kaplama katalogda yok |
| `missing-mass` | Birim kütle yok | Katalogda `kg/m` tanımlı değil |

`exclusion_reason` ve `exclusion_reason_label` yalnızca `excluded` satırlarda
bulunur; `pending` satırda dışlama nedeni **yoktur** (henüz karar verilmedi).
`message` alanı her durumda satıra özgü, eyleme dönük açıklamayı taşır.

## POST /api/report/excel · POST /api/report/pdf

`POST /api/calculate` ile **aynı** istek gövdesini alır ve **aynı** hesap
çekirdeğini çalıştırır. Rapor katmanı hesap yapmaz; miktar, fire, ağırlık ve
ticari boy değerleri olduğu gibi taşınır. Böylece üç endpoint birbirinden
ayrışamaz.

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

Dosya adı `Content-Disposition` başlığından okunur.

---

## Hata kodları

Tüm hatalar tek zarf tipinde döner: `{"error": {code, message, detail,
suggestion, issues[]}}`. `issues[]` içindeki her öğe `source_row`, `boq_no`,
`column`, `code`, `message`, `suggestion` alanlarını taşır; tüm alanlar her
zaman bulunur (`null` olabilir) ki istemci tek tip işleyebilsin.

| Durum | Kod | Anlamı |
|---|---|---|
| `409` | karar hatası | Kullanıcı kararları geçersiz; `/api/calculate` ile aynı gövde |
| `422` | `report-empty` | Onaylanmış kalem yok; boş "satın alma listesi" üretilmez |
| `422` | doğrulama | Geçersiz/eksik alan, katalog dışı kod, hesaplanmış alan gönderimi |
| `422` | dosya | Desteklenmeyen biçim, bozuk Excel, hatalı kolon |

Ekranlarda yalnızca sunucunun güvenli metinleri gösterilir — stack trace, dosya
yolu, sağlayıcı anahtarı veya ham gövde asla gösterilmez.

---

## CORS

Geliştirmede varsayılan davranış **proxy**'dir: tarayıcı isteği aynı origin'den
gider, CORS gerekmez. `VITE_API_BASE_URL` doldurulursa backend'de
`BUILDFLOW_CORS_ORIGINS` listesine frontend adresi eklenmelidir. Joker (`*`)
kabul edilmez.
