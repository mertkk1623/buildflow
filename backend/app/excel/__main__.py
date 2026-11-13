"""Komut satırı: metraj şablonu üret.

Kullanım::

    python -m app.excel --output "metraj_sablonu.xlsx"

Bu bir API değildir (Aşama 4.3 kapsamı dışında); yalnızca şablonu bir kez
üretmek/dağıtmak için pratik bir giriş noktasıdır.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.excel.template import build_metraj_template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.excel",
        description="BuildFlow AI metraj şablonunu (.xlsx) üretir.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="metraj_sablonu.xlsx",
        help="Yazılacak dosya yolu (varsayılan: metraj_sablonu.xlsx)",
    )
    arguments = parser.parse_args(argv)

    path = build_metraj_template(Path(arguments.output))
    print(f"Şablon yazıldı: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
