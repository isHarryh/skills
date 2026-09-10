#!/usr/bin/env python3
"""Render a PDF file to per-page JPG images.

Self-contained bootstrap: the pymupdf dependency is installed into a local ``.deps`` directory next to this script,
so the user's global Python environment is never touched.
Re-running the script reuses the cached dependency and works offline afterwards.

Usage:
    python pdf2img.py <input.pdf> [-o OUTPUT_DIR] [--dpi 150] [--quality 95]

Output: OUTPUT_DIR/p001.jpg ...
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from io import TextIOWrapper
from pathlib import Path

DEPS_DIR = Path(__file__).resolve().parent / ".deps"


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            assert isinstance(stream, TextIOWrapper)
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _ensure_pymupdf() -> None:
    for name in ("pymupdf", "fitz"):
        try:
            __import__(name)
            return
        except ImportError:
            continue

    DEPS_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install",
            "--target", str(DEPS_DIR),
            "--quiet",
            "--disable-pip-version-check",
            "pymupdf",
        ],
    )
    if str(DEPS_DIR) not in sys.path:
        sys.path.insert(0, str(DEPS_DIR))


def main() -> int:
    _ensure_utf8_stdio()
    _ensure_pymupdf()

    parser = argparse.ArgumentParser(description="Render a PDF to per-page images.")
    parser.add_argument("pdf", type=Path, help="path to the input PDF file")
    parser.add_argument("-o", "--out", type=Path, default=None, help="output directory (default: <pdf-dir>/pages)")
    parser.add_argument("--dpi", type=int, default=150, help="render DPI (default: 150)")
    parser.add_argument("--quality", type=int, default=95,help="JPG quality, 1-100 (default: 95)")
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"Error: Given PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        import pymupdf as mupdf
    except ImportError:
        try:
            import fitz as mupdf
        except ImportError:
            print("Error: Failed to import mupdf. This may caused by library installation failure.", file=sys.stderr)
            return 1

    out_dir = Path(args.out or (args.pdf.resolve().parent / "pages"))
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = mupdf.open(args.pdf)
    total = doc.page_count
    width = max(3, len(str(total)))
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=args.dpi, alpha=False)
        pix.save(out_dir / f"p{index:0{width}d}.jpg", jpg_quality=args.quality)
    doc.close()

    print(f"Success: {total} pages were saved into {out_dir.absolute()} (dpi={args.dpi}, quality={args.quality})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
