# Excel Şablonları — Aşama 4.3

Bu klasördeki üç dosya **elle düzenlenmemelidir**; kodla üretilir.

| Dosya | Nedir | Üreten |
|---|---|---|
| `metraj_sablonu.xlsx` | Kullanıcıya verilecek boş metraj şablonu (4 örnek satır + kullanım sayfası) | `python -m app.excel -o metraj_sablonu.xlsx` |
| `ornek_metraj.xlsx` | 18 satırlık demo metraj; okuyucu ve hesap motoru doğrulaması için | `tests/fixtures/excel_files.py` → `build_demo_workbook()` |
| `proje_ornek_metraj.xlsx` | 40 satırlık kapsamlı örnek proje; ana sayfadaki "Hemen dene" ve indirme bağlantısının kaynağı | `python tools/make_sample_fixtures.py` |

## Şablonu yeniden üretmek

```powershell
cd backend
python -m app.excel -o ..\templates\metraj_sablonu.xlsx
```

## Örnek proje dosyasını yeniden üretmek

`proje_ornek_metraj.xlsx` tek bir kaynaktan üretilir (`app/excel/sample.py` →
`SAMPLE_ROWS`). Aynı komut üç türetilmiş çıktıyı birden tazeler:

1. `templates/proje_ornek_metraj.xlsx`
2. `frontend/public/examples/proje-ornek-metraj.xlsx` (statik indirme kopyası)
3. `frontend/src/test/fixtures/sample.ts` (dosyanın gerçek `/api/analyze` çıktısı)

```powershell
cd backend
python tools/make_sample_fixtures.py
```

Komut idempotenttir: veri kümesi değişmediyse çıktıların hiçbiri değişmez.
Satır eklemek veya açıklama düzeltmek için `app/excel/sample.py` düzenlenir,
ardından komut yeniden çalıştırılır.

## Şablon yapısı

`Metraj` sayfası — 1. satır başlık, 2. satırdan itibaren veri:

| Kolon | Zorunlu | Kural |
|---|---|---|
| `BOQ No` | Evet | Tekil; aynı numara iki satırda olamaz |
| `Açıklama` | Evet | Profil tipi, ölçü, kalite, kaplama |
| `Miktar` | Evet | Sıfırdan büyük sayı; ondalık virgül kabul edilir |
| `Birim` | Evet | `m`, `kg`, `t` (açılır liste) |
| `Fire (%)` | Hayır | 0–100 yüzde; **boş bırakılırsa sıfır sayılmaz** |

`Kullanım` sayfası — doldurma kılavuzu ve kural özeti.

Kolon adları `app/excel/models.py` içindeki `MetrajColumn` enum'undan gelir;
şablon ile okuyucu aynı kaynağı kullandığı için ayrışamaz.
