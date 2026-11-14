"""Komut satırı: metraj şablonu veya örnek proje metrajı üret.

Kullanım::

    python -m app.excel --output "metraj_sablonu.xlsx"
    python -m app.excel --sample -o "proje_ornek_metraj.xlsx"

Bu bir API değildir (Aşama 4.3 kapsamı dışında); yalnızca dosyaları bir kez
üretmek/dağıtmak için pratik bir giriş noktasıdır.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.excel.sample import SAMPLE_FILENAME, build_sample_workbook
from app.excel.template import build_metraj_template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.excel",
        description="BuildFlow AI metraj dosyalarını (.xlsx) üretir.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Yazılacak dosya yolu (varsayılan: metraj_sablonu.xlsx)",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Boş şablon yerine dolu örnek proje metrajını üret.",
    )
    arguments = parser.parse_args(argv)

    if arguments.sample:
        target = Path(arguments.output or SAMPLE_FILENAME)
        path = build_sample_workbook(target)
        print(f"Örnek metraj yazıldı: {path}")
        return 0

    target = Path(arguments.output or "metraj_sablonu.xlsx")
    path = build_metraj_template(target)
    print(f"Şablon yazıldı: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
