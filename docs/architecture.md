# Mimari

BuildFlow AI iki bağımsız uygulamadan oluşur: React tabanlı bir frontend ve
FastAPI tabanlı bir backend. Hesap mantığı her ikisinden de ayrıdır.

## Klasör yapısı

```
BuildFlow-AI/
├── ROADMAP.md              Ürün ve geliştirme planı (tek doğruluk kaynağı)
├── docs/                   Geliştirici dokümantasyonu
│   ├── api.md              Endpoint sözleşmeleri ve hata kodları
│   ├── ai.md               AI eşleştirme ve sağlayıcı yapılandırması
│   ├── architecture.md     Bu dosya
│   ├── development.md      Kurulum, çalıştırma, testler, CI
│   ├── frontend.md         Frontend entegrasyonu ve ekranlar
│   ├── reports.md          Excel/PDF raporlama
│   ├── examples/           Gerçek uygulamadan üretilmiş örnek çıktılar
│   └── images/             Uygulama ekran görüntüleri
├── templates/              Excel metraj şablonu ve demo metrajı
├── frontend/               React + TypeScript + Tailwind
│   └── src/
│       ├── pages/          Beş akış adımı + ana sayfa
│       ├── components/     UI ve workflow bileşenleri
│       ├── state/          Akış durumu
│       ├── lib/            API istemcisi, biçimlendirme, adımlar
│       └── types/          Backend şemasının TypeScript karşılığı
└── backend/                FastAPI + Pytest
    └── app/
        ├── api/            HTTP katmanı: rotalar, şemalar, hata zarfı
        ├── domain/         Deterministik hesap çekirdeği
        ├── excel/          Metraj okuyucu ve şablon üretici
        ├── ai/             Sağlayıcıdan bağımsız eşleştirme katmanı
        ├── reports/        Excel/PDF rapor üretimi ve gömülü fontlar
        └── data/           Malzeme kataloğu
```

## Katmanlar

```
Frontend (React)
      │  HTTP / JSON
      ▼
API katmanı  (app/api)        ← şema doğrulama, hata zarfı
      │
      ├──▶ domain  (app/domain)    ← hesap, eşleştirme, birim, fire
      ├──▶ excel   (app/excel)     ← okuma, şablon
      ├──▶ ai      (app/ai)        ← yalnızca öneri
      └──▶ reports (app/reports)   ← Excel/PDF üretimi
```

### Mimari kurallar

- Hesap mantığı FastAPI rotalarından ve UI bileşenlerinden **bağımsızdır**.
- AI entegrasyonu küçük bir arayüz arkasında izole edilmiştir; sağlayıcı
  değiştirilebilir.
- Dosya yüklemeleri ve AI yanıtları sistem sınırlarında doğrulanır.
- V1'de veritabanı, kimlik doğrulama ve abonelik altyapısı **yoktur**.
- API anahtarları yalnızca ortam değişkeninden okunur; asla commit edilmez.

### Hesap çekirdeği

`app/domain` içinde:

| Modül | Görev |
|---|---|
| `units.py` | Birim dönüşümü (m, kg, t) |
| `sizes.py` | Ölçü normalizasyonu (aileye özgü) |
| `normalize.py` | Açıklama normalizasyonu |
| `catalog.py` | Katalog yükleme ve doğrulama |
| `matching.py` | Deterministik eşleştirme |
| `decisions.py` | Kullanıcı kararlarının doğrulanması |
| `calculation.py` | Fire, birleştirme, ticari boy yuvarlaması |
| `models.py` | Alan tipleri |

Hesap `Decimal` ile yapılır; yuvarlama yalnızca gösterimde uygulanır.

## Malzeme kataloğu

V1 kataloğu **14 doğrulanmış kalem** içerir ve şu aileleri kapsar: BOX, IPE,
HEA, UPN, FLAT (lama). Her kg/m değeri izlenebilir bir üretici veya standart
tablo kaynağına dayanır.

Bir katalog kalemi dört özellikle tanımlanır: **grup + ölçü + kalite + kaplama**.
`IPE 200` ile `HEA 200` farklı malzemedir; `S235` ile `S355` farklı
malzemedir; siyah ile galvaniz farklı varyanttır.
