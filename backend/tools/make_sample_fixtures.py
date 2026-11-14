"""Örnek proje metrajını ve frontend fixture'ını yeniden üretir.

Neden ayrı bir komut?
---------------------
Depoda iki türetilmiş dosya var:

1. ``templates/proje_ornek_metraj.xlsx`` — kullanıcıya inen örnek dosya,
2. ``frontend/src/test/fixtures/sample.ts`` — o dosyanın gerçek analiz çıktısı.

İkisi de elle düzenlenmemeli. Bu komut ikisini **tek kaynaktan**
(``app/excel/sample.py`` ve gerçek motor) üretir; böylece fixture ile dosya
birbirinden ayrışamaz.

Kullanım::

    cd backend
    python tools/make_sample_fixtures.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.api.service import analyze_file  # noqa: E402
from app.excel.sample import build_sample_workbook  # noqa: E402

TEMPLATE_DIR = REPO_ROOT / "templates"
PUBLIC_DIR = REPO_ROOT / "frontend" / "public" / "examples"
FIXTURE = REPO_ROOT / "frontend" / "src" / "test" / "fixtures" / "sample.ts"

#: Depoda kullanılan adlar: sunucu tarafı alt çizgili, statik kopya tireli.
COMMITTED_NAME = "proje_ornek_metraj.xlsx"
PUBLIC_NAME = "proje-ornek-metraj.xlsx"

FIXTURE_HEADER = '''/**
 * Örnek proje metrajının **gerçek backend çıktısı** — elle yazılmamıştır.
 *
 * Kaynak: `templates/proje_ornek_metraj.xlsx` (40 satır) → `/api/analyze`.
 * Satırlar, mesajlar ve adaylar sunucunun ürettiği JSON'dan birebir
 * kopyalanmıştır; arayüz bu sözleşmeyle test edilir.
 *
 * Yeniden üretmek için `backend/tools/make_sample_fixtures.py` çalıştırılır.
 */

import type { AnalyzeResponse } from '../../types/api'

'''


def main() -> int:
    committed = TEMPLATE_DIR / COMMITTED_NAME
    build_sample_workbook(committed)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(committed, PUBLIC_DIR / PUBLIC_NAME)

    analysis = analyze_file(committed)
    payload = analysis.model_dump(mode="json")
    FIXTURE.write_text(
        FIXTURE_HEADER
        + "/** 40 satır: 32 kural, 5 onay bekleyen, 3 kapsam dışı. */\n"
        + "export const SAMPLE_ANALYSIS: AnalyzeResponse = "
        + f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
        # Satır sonları platforma bağlı olmasın: `.gitattributes` LF bekliyor.
        newline="\n",
    )

    print(f"Örnek dosya yazıldı:  {committed.relative_to(REPO_ROOT)}")
    print(f"Statik kopya yazıldı: {(PUBLIC_DIR / PUBLIC_NAME).relative_to(REPO_ROOT)}")
    print(f"Fixture yazıldı:      {FIXTURE.relative_to(REPO_ROOT)}")
    print(
        f"Özet: {analysis.summary.total_rows} satır · "
        f"{analysis.summary.rule} kural · "
        f"{analysis.summary.pending} onay bekleyen · "
        f"{analysis.summary.excluded} kapsam dışı"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
