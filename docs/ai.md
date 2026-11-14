# AI Eşleştirme

BuildFlow AI'da AI'ın görevi dar ve sınırlıdır: malzeme açıklamasını yorumlamak
ve katalog adayı **önermek**. AI hesap yapmaz.

## Ne yapar, ne yapmaz

AI **hesaplama yapmaz**. Yalnızca BOQ açıklamasını mevcut katalog adaylarıyla
eşleştirir ve sonucu bir **öneri** olarak döndürür.

- Varsayılan sağlayıcı `none`: AI kapalıdır, hiçbir ağ çağrısı yapılmaz ve yanıt
  deterministik sonuçla birebir aynı kalır.
- AI yalnızca `pending` satırlar için çağrılır; `rule` / `excluded` / `invalid`
  satırlarda hiç çağrılmaz.
- AI'ya **yalnızca** açıklama, bilinen dört özellik (aile / ölçü / kalite /
  kaplama) ve aday ürünlerin tanıtıcı özellikleri gönderilir. Miktar, birim,
  fire, ağırlık ve maliyet ne istekte ne yanıtta yer alır.
- **AI önerisi hiçbir zaman otomatik onaylanmaz.** `matched_code` alanı AI'dan
  etkilenmez; satır `pending` kalır. Kullanıcı onaylar, reddeder veya başka bir
  aday seçer. Kullanıcı kararı `apply_decisions()` doğrulamasından geçer.
- AI erişilemezse (timeout, bağlantı hatası, bozuk yanıt) analiz deterministik
  sonuçla tamamlanır; ilgili satırlar `pending` kalır ve kullanıcıya tek bir
  uyarı gösterilir.

### AI açık ama iş yok

`ai.enabled=true` **"AI çağrıldı" demek değildir**; yalnızca yapılandırmayı
anlatır. Dosyada onay bekleyen satır yoksa hiçbir istek yapılmaz (ağ trafiği ve
maliyet yok) ve yanıt bunu `ai.skipped_reason` ile açıklar:

- `no-pending-rows` — tüm satırlar deterministik çözüldü ya da fire/birim/katalog
  nedeniyle kapsam dışı kaldı.
- `missing-row-identity` — pending satır var ama BOQ No veya açıklama eksik
  olduğu için AI'ya gönderilemedi.

Bu bir hata değildir. Alanlar yalnızca bu durumda yanıtta bulunur; AI gerçekten
çalıştığında veya kapalıyken gönderilmez. Arayüz bunu bilgi kutusu olarak
gösterir, hata olarak sunmaz.

## Yanıt doğrulaması

Yanıt katı bir şemaya göre doğrulanır:

- `status` ∈ {`suggested`, `ambiguous`, `no_match`}
- `suggested_code`, `confidence`, `reason`

Fazla/eksik alan, katalog dışı kod, bozuk JSON veya tutarsız durum
**reddedilir**.

Öneri güveni **kalibre edilmiş bir doğruluk oranı değildir**; yalnızca
açıklamanın katalogla örtüşme derecesini gösterir.

## Yapılandırma

AI'yı etkinleştirmek için `.env` dosyasında (örnek: Deploy.com):

```ini
BUILDFLOW_AI_PROVIDER=openai-compatible
BUILDFLOW_AI_BASE_URL=https://api-cdn.deploy.com/api/v1
BUILDFLOW_AI_MODEL=deepseek-ai/deepseek-v4.1-flash-1017
BUILDFLOW_AI_API_KEY=...          # yalnızca ortam değişkeninden okunur
BUILDFLOW_AI_TIMEOUT_SECONDS=10
```

Sağlayıcı **OpenAI uyumlu** herhangi bir uç nokta olabilir. İstem
gövdesinde gönderilen alanlar:

| Alan | Değer | Not |
|---|---|---|
| `model` | yapılandırmadan | — |
| `messages` | sistem + kullanıcı | — |
| `temperature` | `0` | deterministik öneri |
| `max_completion_tokens` | `512` | Deploy.com alan adı |
| `reasoning_effort` | `none` | düşünmeyi kapatır (Deploy varsayılanı `high`) |

`response_format` **gönderilmez**: Deploy.com dokümanı bu alanı listelemez.
JSON biçimi istemle istenir ve :mod:`app.ai.validate` içinde katı şemayla
doğrulanır; model yanıtı kod bloğuna sarar veya kısa bir giriş cümlesi eklerse
tek JSON nesnesi çıkarılır, şema katılığı korunur.

### Hata kodları

| HTTP | Dönen kod | Anlamı |
|---|---|---|
| `400` | `provider-invalid-request` | Gövde/alan hatası |
| `401` | `provider-auth-failed` | Anahtar geçersiz/süresi dolmuş |
| `402`, `405` | `provider-insufficient-balance` | Bakiye/kota yok |
| `429` | `provider-rate-limited` | Hız sınırı |
| `5xx` | `provider-error` | Sunucu arızası |

Yanıt gövdesi **hiç okunmaz**; yalnızca durum kodu sınıflanır. Böylece
sağlayıcı metni (PII/anahtar izi) hiçbir yere taşınmaz.

API anahtarı yanıtta, hata mesajında ve logda **görünmez**. Eksik ya da geçersiz
yapılandırma uygulamayı durdurmaz; sunucu uyarı loglar ve AI'yı devre dışı
bırakır.

## Sağlayıcıdan bağımsızlık

AI entegrasyonu küçük bir servis katmanı arkasında izole edilmiştir
(`backend/app/ai/`), böylece sağlayıcı değiştirilebilir:

| Dosya | Görev |
|---|---|
| `providers.py` | Sağlayıcı istemcisi (OpenAI uyumlu) |
| `prompt.py` | İstem oluşturma |
| `validate.py` | Katı yanıt şeması doğrulaması |
| `engine.py` | Eşleştirme akışı ve fallback |
| `factory.py` | Yapılandırmadan sağlayıcı seçimi |
| `models.py` | AI veri tipleri |

## V1 kapsamı dışında

AI'ın **sonuç yorumlama** yeteneği (hesaplanmış sayıları özetleyen kısa metin)
`ROADMAP.md`'de hedef olarak tanımlıdır ancak bu sürümde **uygulanmamıştır**.
V1'de AI yalnızca malzeme eşleştirmesi yapar.
