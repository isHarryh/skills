"""Structural inspection for .docx documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx.document import Document as DocumentType
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree

from .core import _as_doc, iter_blocks, read_table
from .ooxml import paragraph_list_level


def _cm(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(value.cm, 2)
    except AttributeError:
        return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _part_text(part: Any) -> str:
    lines = [paragraph.text for paragraph in part.paragraphs if paragraph.text]
    for table in part.tables:
        for row in table.rows:
            lines.append("\t".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def _comments_info(doc: DocumentType) -> dict[str, Any]:
    for part in doc.part.package.parts:
        if str(part.partname).lower() != "/word/comments.xml":
            continue
        try:
            root = etree.fromstring(part.blob)
        except Exception:  # noqa: BLE001
            return {"count": 0, "authors": []}
        comments = root.findall(qn("w:comment"))
        authors = sorted(
            {
                comment.get(qn("w:author"))
                for comment in comments
                if comment.get(qn("w:author"))
            }
        )
        return {"count": len(comments), "authors": authors}
    return {"count": 0, "authors": []}


def inspect_docx(
    source: str | Path | DocumentType,
    *,
    max_paragraphs: int = 200,
    text_chars: int = 160,
) -> dict[str, Any]:
    """Returns a JSON-friendly structural summary of a document.

    Paragraph text is truncated to ``text_chars`` and the paragraph list is
    capped at ``max_paragraphs``. The total count is reported separately.
    """
    doc = _as_doc(source)
    path = Path(source).expanduser() if not isinstance(source, DocumentType) else None

    sections: list[dict[str, Any]] = []
    for index, section in enumerate(doc.sections):
        header_text = ""
        footer_text = ""
        if section._sectPr.find(qn("w:headerReference")) is not None:
            header_text = _part_text(section.header)
        if section._sectPr.find(qn("w:footerReference")) is not None:
            footer_text = _part_text(section.footer)
        sections.append(
            {
                "index": index,
                "page_width_cm": _cm(section.page_width),
                "page_height_cm": _cm(section.page_height),
                "margin_top_cm": _cm(section.top_margin),
                "margin_bottom_cm": _cm(section.bottom_margin),
                "margin_left_cm": _cm(section.left_margin),
                "margin_right_cm": _cm(section.right_margin),
                "orientation": str(section.orientation),
                "header": header_text[:text_chars],
                "footer": footer_text[:text_chars],
            }
        )

    paragraphs: list[dict[str, Any]] = []
    paragraph_total = 0
    tables: list[dict[str, Any]] = []
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            paragraph_total += 1
            if len(paragraphs) >= max_paragraphs:
                continue
            style_name = block.style.name if block.style is not None else ""
            heading = style_name.lower().startswith("heading") or style_name.startswith(
                "标题"
            )
            paragraphs.append(
                {
                    "index": paragraph_total - 1,
                    "style": style_name,
                    "text": block.text[:text_chars],
                    "text_length": len(block.text),
                    "heading": heading,
                    "list_level": paragraph_list_level(block),
                    "runs": len(block.runs),
                }
            )
        else:
            tables.append(
                {
                    "index": len(tables),
                    "rows": len(block.rows),
                    "columns": len(block.columns),
                    "first_row": [
                        cell.text[:text_chars] for cell in block.rows[0].cells
                    ]
                    if block.rows
                    else [],
                    "preview": read_table(block)[:3],
                }
            )

    images = [
        {
            "part": str(part.partname),
            "content_type": part.content_type,
            "bytes": len(part.blob),
        }
        for part in doc.part.package.parts
        if str(part.partname).startswith("/word/media/")
        and getattr(part, "content_type", "").startswith("image/")
    ]

    core = doc.core_properties
    return {
        "file": {
            "path": str(path.resolve()) if path else None,
            "size": path.stat().st_size if path and path.is_file() else None,
        },
        "core": {
            "title": core.title,
            "subject": core.subject,
            "author": core.author,
            "last_modified_by": core.last_modified_by,
            "created": _iso(core.created),
            "modified": _iso(core.modified),
            "revision": core.revision,
        },
        "sections": sections,
        "styles": [
            {
                "name": style.name,
                "type": str(style.type),
                "builtin": bool(style.builtin),
            }
            for style in doc.styles
        ],
        "paragraphs_total": paragraph_total,
        "paragraphs_truncated": paragraph_total > len(paragraphs),
        "paragraphs": paragraphs,
        "tables": tables,
        "images": images,
        "comments": _comments_info(doc),
    }
