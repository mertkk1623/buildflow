# Raporlama (Excel / PDF)

`POST /api/report/excel` ve `POST /api/report/pdf`, `POST /api/calculate` ile
**aynı** istek gövdesini alır ve **aynı** hesap çekirdeğini çalıştırır. Rapor
katmanı hesap yapmaz; miktar, fire, ağırlık ve ticari boy değerleri olduğu gibi
taşınır.

Onaylanmış kalem yoksa endpoint **422 `report-empty`** döner; boş bir
"satın alma listesi" üretilmez. Kararlar geçersizse `/api/calculate` ile aynı
hata gövdesi (`409`) döner.

Komut örnekleri için bkz. [`api.md`](api.md).

## Rapor içeriği

Her iki biçim de aynı `Report` nesnesinden üretilir:

- **Özet** — satır/kalem/birleşme sayıları, toplam sipariş uzunluğu, bilinen
  teorik ağırlık, FULL/PARTIAL dağılımı.
- **Satın alma listesi** — malzeme kodu, açıklama, kaynak BOQ satırları, net,
  fire, brüt, ticari boy, sipariş adedi, sipariş uzunluğu, artan miktar, teorik
  ağırlık, FULL/PARTIAL, eksik bilgi ve uyarılar. Excel'de kalemler malzeme
  ailesine göre gruplanır ve her ailede alt toplam bandı bulunur.
- **Kaynak BOQ satırları** — her kalemin hangi satırlardan oluştuğu
  (izlenebilirlik), satır bazında miktar/fire/brüt ile.
- **Hesaba alınmayanlar** — onay bekleyen, reddedilen ve kapsam dışı satırlar
  gerekçeleriyle.

### Excel çalışma kitabı sayfaları

| Sayfa | İçerik |
|---|---|
| `Özet` | Girdi/hesaplanan/hariç satır sayıları, kalem ve birleşme sayıları, toplam sipariş uzunluğu, teorik ağırlık |
| `Satın Alma Listesi` | Aileye göre gruplanmış kalemler, alt toplam bantları |
| `Kaynak Satırlar` | Kalem → BOQ satırı izlenebilirliği |
| `Hesaba Alınmayanlar` | Dışarıda kalan satırlar ve nedenleri |

### PDF raporu

İki sayfalık özet rapor: kapak/özet + satın alma listesi + hesaba alınmayan
satırlar + varsayımlar ve sınırlar. Türkçe karakterler gömülü DejaVu fontuyla
üretilir; sistem fontlarına bağımlılık yoktur.

## İki açık sınır

Raporlarda bu iki sınır **açıkça yazılır**:

1. Ağırlık, katalogdaki **teorik çıplak çelik kg/m** değerine dayalıdır;
   kantar veya sevkiyat ağırlığı değildir. Galvaniz kaplama ağırlığı dahil
   değildir.
2. BuildFlow bu aşamada **kesim optimizasyonu veya nesting yapmaz**; sipariş
   miktarları ticari boya yuvarlanmış teorik ihtiyaçtır.

## Bilinmeyen değer kuralı

PARTIAL bir sonuçta bilinmeyen alan **asla sıfır gösterilmez**: Excel'de hücre
boş bırakılır, PDF'te `—` yer tutucusu kullanılır. Hiçbir grubun ağırlığı
bilinmiyorsa özet ağırlık alanı da boş kalır ve "Ağırlık durumu: KISMİ" uyarısı
görünür.

## Kütüphaneler ve font

| Bağımlılık | Gerekçe |
|---|---|
| `openpyxl` | Excel yazımı; zaten şablon üretiminde kullanılıyordu. |
| `fpdf2` | PDF üretimi. Saf Python, derleme gerektirmez, gömülü TTF destekler; `reportlab`/`weasyprint` gibi ağır ya da sistem kütüphanesi isteyen alternatifler tercih edilmedi. |
| `pypdf` (yalnızca geliştirme) | Testlerde PDF metnini çıkarıp Türkçe karakterleri ve sayfa numaralarını doğrulamak için. |
| DejaVu Sans / Bold | `backend/app/reports/fonts/` altında projeye dahildir (Bitstream Vera türevi özgür lisans, `LICENSE-DejaVu.txt`). Sistem fontlarına bağımlılık yoktur. |

## Örnek çıktılar

Gerçek uygulamadan üretilmiş dosyalar (demo metrajı, 14 hesaplanan satır):

- [`examples/ornek-satin-alma-raporu.xlsx`](examples/ornek-satin-alma-raporu.xlsx)
- [`examples/ornek-satin-alma-raporu.pdf`](examples/ornek-satin-alma-raporu.pdf)
