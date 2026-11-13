# Frontend Entegrasyonu

Frontend hiçbir değeri kendi üretmez. Ekranlarda görünen her sayı, etiket ve
durum sunucunun yanıtından gelir; istemci yalnızca **biçimlendirir**.

## Veri akışı

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
   dosya sunucuda üretilir, adı `Content-Disposition` başlığından
   okunur.

## Ekranlar

| # | Rota | Görev |
|---|---|---|
| — | `/` | Ürün tanıtımı, kapsam, akış özeti |
| 01 | `/upload` | Metraj yükleme, şablon indirme, satır/kolon gereksinimleri |
| 02 | `/analysis` | Sunucu yanıtının dağılımı: kural / onay bekleyen / hariç |
| 03 | `/review` | Satır bazlı karar: aday seç, onayla, reddet |
| 04 | `/results` | Malzeme grupları, birleşmeler, dışarıda kalanlar |
| 05 | `/export` | Excel ve PDF indirme |

## Backend sözleşmesi tek kaynaktır

`frontend/src/types/api.ts`, `backend/app/api/schemas.py`'nin birebir
karşılığıdır. Kararlar backend'de `apply_decisions()` doğrulamasından geçer;
istemciden gelen uydurma kod, katalog dışı eşleşme veya hesaplanmış alan sunucu
tarafından reddedilir (`422` / `409`). Ölçekli değerler (Decimal) JSON'da
**string** taşınır — kayan nokta yuvarlaması oluşmaz.

## Ortam değişkenleri

`frontend/.env.example` dosyasını `.env` olarak kopyalayın.

| Değişken | Varsayılan | Görev |
|---|---|---|
| `VITE_API_BASE_URL` | boş | Boşsa istekler görece `/api/...` gider ve Vite proxy'si devreye girer. Doluysa (ör. `http://127.0.0.1:8000`) doğrudan o adrese gidilir ve backend CORS izin listesi gerekir. |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` | Yalnızca geliştirme sunucusunun proxy hedefi. Üretim derlemesini etkilemez. |

Geliştirmede varsayılan davranış **proxy**'dir: tarayıcı isteği aynı origin'den
gider, CORS gerekmez.

## Hata yönetimi

Tüm hatalar tek `ApiError` tipinde toplanır (sunucu zarfı, bağlantı hatası,
iptal). Ekranlarda yalnızca sunucunun güvenli metinleri gösterilir — stack
trace, dosya yolu, sağlayıcı anahtarı veya ham gövde asla gösterilmez.
Karşılanan durumlar: geçersiz/büyük Excel, desteklenmeyen biçim, eksik veya
hatalı kolon, geçersiz karar, backend'e ulaşılamaması, AI sağlayıcı hatası,
PARTIAL (KISMİ) hesaplama ve rapor üretim hatası.

## Test yaklaşımı

Testler ağ çağrısını `fetch` düzeyinde taklit eder; sahte state kurulmaz. Her
test "ekranda ne var" ile "sunucuya ne gitti"yi aynı akışta doğrular. Beklenmeyen
bir istek testi açıkça düşürür, böylece sessiz sahte başarı oluşmaz. Fixture'lar
elle uydurulmadı: gerçek backend yanıtlarından üretildi
(`src/test/fixtures/`).
