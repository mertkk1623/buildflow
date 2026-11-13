"""AI'ya gönderilen metin — tek ve dar bir sözleşme.

İlkeler
-------
1. AI'ya **yalnızca** malzeme tanıma için gereken bilgi gider: BOQ açıklaması,
   bilinen dört özellik ve katalog adayları.
2. Miktar, birim, fire, ağırlık, maliyet ve hesap sonuçları **gönderilmez**.
   Bu alanlar :class:`~app.ai.models.AiMatchRequest` içinde hiç yoktur;
   dolayısıyla yanlışlıkla eklenmeleri mümkün değildir.
3. Yanıt biçimi tek bir JSON nesnesidir; serbest metin kabul edilmez.
"""

from __future__ import annotations

import json

from app.ai.models import AiMatchRequest

#: Sistem mesajı. Görev sınırı burada çizilir; sağlayıcı değişse de değişmez.
SYSTEM_PROMPT = """\
Sen bir çelik malzeme kataloğu eşleştirme asistanısın.
Görevin: verilen BOQ satır açıklamasını, verilen aday listesindeki TEK bir
katalog kalemiyle eşleştirmek veya eşleştirilemeyeceğini bildirmek.

Kurallar (ihlal edilemez):
1. Yalnızca aday listesindeki "code" değerlerinden birini önerebilirsin.
   Yeni kod uydurmak, kodu değiştirmek veya listede olmayan bir kod yazmak yasak.
2. Hesaplama yapma. Miktar, ağırlık, fire, maliyet, adet veya boy hesabı
   üretme; bu bilgiler sana verilmez ve senin görevin değildir.
3. Emin değilsen zorla seçim yapma:
   - Tek aday açıkça doğruysa  -> "suggested"
   - Birden fazla aday eşit derecede olasıysa -> "ambiguous"
   - Güvenilir eşleşme yoksa  -> "no_match"
4. "ambiguous" ve "no_match" durumunda "suggested_code" null olmalıdır.
5. "suggested" durumunda "suggested_code" dolu ve "confidence" 0 ile 1
   arasında bir sayı olmalıdır.
6. Açıklamada açıkça yazan bir özellik (grup, ölçü, kalite, kaplama) adayla
   çelişiyorsa o adayı önerme.
7. Yanıtın YALNIZCA şu JSON nesnesi olsun; açıklama, markdown veya kod bloğu
   ekleme:
{"status": "suggested|ambiguous|no_match", "suggested_code": null,
 "confidence": 0.0, "reason": "kısa gerekçe"}
"""


def build_user_prompt(request: AiMatchRequest) -> str:
    """Tek satırlık isteği JSON metnine çevirir.

    ``ensure_ascii=False`` Türkçe karakterlerin okunabilir kalmasını sağlar;
    ``sort_keys=True`` aynı girdi için **aynı** metni üretir (deterministik
    istek, tekrar edilebilir test).
    """
    return json.dumps(
        request.payload(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
