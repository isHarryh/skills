"""A small end-to-end check for the docxkit public API."""

from __future__ import annotations

import struct
import tempfile
import zlib
from pathlib import Path

from .core import (
    add_heading,
    add_paragraph,
    add_table,
    delete_paragraph,
    duplicate_paragraph,
    extract_images,
    extract_text,
    insert_paragraph_after,
    new_docx,
    open_docx,
    read_table,
    replace_text,
    save_docx,
    set_footer_text,
    set_header_text,
    set_page_margins,
    set_page_size,
    set_run_font,
)
from .inspection import inspect_docx
from .ooxml import set_cell_shading, set_paragraph_border, set_paragraph_shading


def _png_1x1() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00\xff\x00\x00\xff"
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def run_selftest() -> int:
    """Creates, edits, saves, and reopens a document, asserting the results."""
    with tempfile.TemporaryDirectory(prefix="docxkit-selftest-") as tmp:
        root = Path(tmp)

        doc = new_docx()
        add_heading(doc, "Selftest heading", level=1)
        paragraph = add_paragraph(doc)
        first = paragraph.add_run("Hello ")
        set_run_font(first, bold=True, size=12, east_asia="宋体")
        paragraph.add_run("world")
        set_paragraph_shading(paragraph, "F2F2F2")
        set_paragraph_border(paragraph, bottom=True)

        inserted = insert_paragraph_after(paragraph, "Inserted paragraph")
        if inserted.text != "Inserted paragraph":
            raise AssertionError("insert_paragraph_after failed.")
        delete_paragraph(inserted)

        duplicate = duplicate_paragraph(paragraph, text="Copied paragraph")
        if duplicate.text != "Copied paragraph":
            raise AssertionError("duplicate_paragraph did not set the new text.")

        table = add_table(doc, [["A", "B"], ["1", "2"]])
        if read_table(table)[0] != ["A", "B"]:
            raise AssertionError("Table write/read round-trip failed.")
        set_cell_shading(table.cell(0, 0), "E2EFDA")
        set_page_margins(doc.sections[0], top=2, bottom=2, left=2, right=2)
        set_page_size(doc.sections[0], width=21, height=29.7)

        set_header_text(doc.sections[0], "Selftest header")
        set_footer_text(doc.sections[0], "Selftest footer")

        image_path = root / "dot.png"
        image_path.write_bytes(_png_1x1())
        doc.add_picture(str(image_path))

        output = root / "selftest.docx"
        save_docx(doc, output)
        if not output.is_file():
            raise AssertionError("Document was not saved.")

        reopened = open_docx(output)
        if "Hello world" not in extract_text(reopened):
            raise AssertionError("Saved text could not be read back.")

        replaced = replace_text(reopened, "Hello world", "Hi there")
        if replaced != 1:
            raise AssertionError(f"Expected one replacement, got {replaced}.")
        if "Hi there" not in extract_text(reopened):
            raise AssertionError("Replacement was not applied across runs.")

        summary = inspect_docx(reopened)
        if summary["tables"][0]["rows"] != 2:
            raise AssertionError("Inspection did not report the table.")
        if not summary["images"]:
            raise AssertionError("Inspection did not report the image.")

        assets = extract_images(reopened, root / "assets")
        if len(assets) != 1:
            raise AssertionError(f"Expected one image, got {len(assets)}.")

        save_docx(reopened, root / "selftest-edited.docx")

    print("selftest: ok")
    return 0
