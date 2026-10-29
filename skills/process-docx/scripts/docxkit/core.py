"""High-level document operations built on python-docx."""

from __future__ import annotations

import copy
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Union

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Length, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from .ooxml import remove_element, set_run_east_asia_font

Block = Union[Paragraph, Table]  # noqa: UP007


def _as_doc(source: str | Path | DocumentType) -> DocumentType:
    if isinstance(source, DocumentType):
        return source
    return open_docx(source)


def open_docx(path: str | Path) -> DocumentType:
    """Opens an existing .docx document.

    Legacy .doc files are rejected because python-docx cannot read the binary
    Word format. Convert them to .docx first.
    """
    path = Path(path).expanduser()
    if path.suffix.lower() == ".doc":
        raise ValueError(
            "python-docx cannot read legacy .doc files. Convert the file to "
            ".docx with Word or LibreOffice first."
        )
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return Document(str(path))


def new_docx(template: str | Path | None = None) -> DocumentType:
    """Creates a blank document or opens a template as the starting point."""
    if template is not None:
        path = Path(template).expanduser()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return Document(str(path))
    return Document()


def save_docx(doc: DocumentType, path: str | Path) -> Path:
    """Saves a document and creates parent directories when needed."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target))
    return target


def _iter_block_items(parent_element: Any, owner: Any) -> Iterator[Block]:
    for child in parent_element.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, owner)
        elif child.tag == qn("w:tbl"):
            yield Table(child, owner)
        elif child.tag == qn("w:sdt"):
            content = child.find(qn("w:sdtContent"))
            if content is not None:
                yield from _iter_block_items(content, owner)
        elif child.tag == qn("w:customXml"):
            yield from _iter_block_items(child, owner)


def iter_blocks(doc: DocumentType) -> Iterator[Block]:
    """Yields paragraphs and tables in document order.

    Content controls and custom XML wrappers are traversed. Tables nested
    inside cells are not traversed; use cell.tables for those.
    """
    yield from _iter_block_items(doc.element.body, doc)


def _part_element(part: Any) -> Any:
    element = getattr(part, "_element", None)
    if element is None:
        element = getattr(part, "element", None)
    if element is None:
        raise TypeError(f"Cannot read XML from {type(part).__name__}")
    return element


def _block_text(block: Block, include_tables: bool) -> list[str]:
    if isinstance(block, Paragraph):
        return [block.text]
    if not include_tables:
        return []
    lines: list[str] = []
    for row in block.rows:
        lines.append("\t".join(cell.text for cell in row.cells))
    return lines


def extract_text(
    source: str | Path | DocumentType,
    *,
    include_tables: bool = True,
    include_headers: bool = False,
    include_footers: bool = False,
    keep_empty: bool = False,
) -> str:
    """Extracts plain text from a document in body order.

    Table rows are joined with tabs. Headers and footers are read per section
    and skipped when they are linked to the previous section.
    """
    doc = _as_doc(source)
    lines: list[str] = []

    for block in iter_blocks(doc):
        for line in _block_text(block, include_tables):
            if line or keep_empty:
                lines.append(line)

    for section in doc.sections:
        for enabled, part in (
            (include_headers, section.header),
            (include_footers, section.footer),
        ):
            if not enabled or part.is_linked_to_previous:
                continue
            for block in _iter_block_items(_part_element(part), part):
                for line in _block_text(block, include_tables):
                    if line or keep_empty:
                        lines.append(line)

    return "\n".join(lines).strip("\n")


def read_table(table: Table) -> list[list[str]]:
    """Returns table cell text as a list of rows."""
    return [[cell.text for cell in row.cells] for row in table.rows]


def write_table(table: Table, data: Sequence[Sequence[Any]]) -> None:
    """Writes values into an existing table without changing its size."""
    if len(data) > len(table.rows):
        raise ValueError("Data has more rows than the table.")
    for row_index, row in enumerate(data):
        if len(row) > len(table.columns):
            raise ValueError("Data has more columns than the table.")
        for col_index, value in enumerate(row):
            table.cell(row_index, col_index).text = str(value)


def add_table(
    doc: DocumentType,
    data: Sequence[Sequence[Any]],
    *,
    style: str | None = "Table Grid",
) -> Table:
    """Adds a table and fills it with the supplied rows."""
    if not data:
        raise ValueError("Table data must contain at least one row.")
    columns = max(len(row) for row in data)
    table = doc.add_table(rows=len(data), cols=columns)
    if style is not None:
        try:
            table.style = style
        except KeyError as exc:
            raise ValueError(f"Table style not found: {style}") from exc
    write_table(table, data)
    return table


def add_paragraph(
    doc: DocumentType, text: str = "", *, style: str | None = None
) -> Paragraph:
    """Adds a paragraph to the document body."""
    return doc.add_paragraph(text, style=style)


def add_heading(doc: DocumentType, text: str, *, level: int = 1) -> Paragraph:
    """Adds a heading paragraph."""
    return doc.add_heading(text, level=level)


def add_page_break(doc: DocumentType) -> Paragraph:
    """Adds a page break paragraph."""
    return doc.add_page_break()


def insert_paragraph_after(
    paragraph: Paragraph, text: str = "", *, style: str | None = None
) -> Paragraph:
    """Inserts a new paragraph immediately after an existing one."""
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style is not None:
        new_para.style = style
    if text:
        new_para.add_run(text)
    return new_para


def delete_paragraph(paragraph: Paragraph) -> None:
    """Removes a paragraph from its parent."""
    element = paragraph._p
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def duplicate_paragraph(paragraph: Paragraph, text: str | None = None) -> Paragraph:
    """Duplicates a paragraph immediately after the original.

    When text is supplied, the clone keeps the first run's character
    formatting but drops other inline content such as hyperlinks or bookmarks.
    """
    new_p = copy.deepcopy(paragraph._p)
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)

    if text is not None:
        first_rpr = None
        if new_para.runs:
            first_rpr = copy.deepcopy(new_para.runs[0]._r.rPr)
        for child in list(new_p):
            if child.tag != qn("w:pPr"):
                new_p.remove(child)
        run = new_para.add_run(text)
        if first_rpr is not None:
            run._r.insert(0, first_rpr)
    return new_para


def _replace_in_paragraph(
    paragraph: Paragraph, old: str, new: str, remaining: int
) -> tuple[int, int]:
    if not old or remaining == 0:
        return 0, remaining

    replaced = 0
    search_from = 0

    while remaining != 0:
        runs = [run for run in paragraph.runs if run.text]
        if not runs:
            break
        full = "".join(run.text for run in runs)
        index = full.find(old, search_from)
        if index < 0:
            break
        end = index + len(old)

        start_run = end_run = None
        start_offset = end_offset = 0
        position = 0
        for run_index, run in enumerate(runs):
            run_length = len(run.text)
            if start_run is None and index < position + run_length:
                start_run = run_index
                start_offset = index - position
            if end <= position + run_length:
                end_run = run_index
                end_offset = end - position
                break
            position += run_length

        if start_run is None or end_run is None:
            break

        if start_run == end_run:
            run = runs[start_run]
            run.text = run.text[:start_offset] + new + run.text[end_offset:]
        else:
            runs[start_run].text = runs[start_run].text[:start_offset] + new
            for run_index in range(start_run + 1, end_run):
                runs[run_index].text = ""
            runs[end_run].text = runs[end_run].text[end_offset:]

        replaced += 1
        if remaining > 0:
            remaining -= 1
        search_from = index + len(new)

    return replaced, remaining


def _replace_in_container(
    container: Any,
    old: str,
    new: str,
    remaining: int,
    include_tables: bool,
) -> tuple[int, int]:
    total = 0
    element = (
        container.element.body
        if isinstance(container, DocumentType)
        else _part_element(container)
    )
    for block in _iter_block_items(element, container):
        if isinstance(block, Paragraph):
            count, remaining = _replace_in_paragraph(block, old, new, remaining)
            total += count
        elif include_tables:
            for row in block.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        count, remaining = _replace_in_paragraph(
                            paragraph, old, new, remaining
                        )
                        total += count
        if remaining == 0:
            break
    return total, remaining


def replace_text(
    doc: DocumentType,
    old: str,
    new: str,
    *,
    count: int = -1,
    include_tables: bool = True,
    include_headers: bool = False,
) -> int:
    """Replaces literal text across runs, preserving the first run's format.

    The replacement never spans paragraph boundaries. Set count to a positive
    number to stop after that many replacements.
    """
    remaining = count
    total = 0

    body_count, remaining = _replace_in_container(
        doc, old, new, remaining, include_tables
    )
    total += body_count

    if include_headers and remaining != 0:
        for section in doc.sections:
            parts = []
            if section._sectPr.find(qn("w:headerReference")) is not None:
                parts.append(section.header)
            if section._sectPr.find(qn("w:footerReference")) is not None:
                parts.append(section.footer)
            for part in parts:
                if part.is_linked_to_previous:
                    continue
                part_count, remaining = _replace_in_container(
                    part, old, new, remaining, include_tables
                )
                total += part_count
                if remaining == 0:
                    break

    return total


def set_run_font(
    run: Run,
    *,
    name: str | None = None,
    size: float | Length | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    color: str | None = None,
    east_asia: str | None = None,
    subscript: bool | None = None,
    superscript: bool | None = None,
) -> None:
    """Applies common character formatting to a run."""
    if name is not None:
        run.font.name = name
    if size is not None:
        if isinstance(size, Length):
            run.font.size = size
        elif isinstance(size, (int, float)):
            run.font.size = Pt(size)
        else:
            raise TypeError("size must be a point value or a docx Length.")
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if underline is not None:
        run.font.underline = underline
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color.lstrip("#"))
    if east_asia is not None:
        set_run_east_asia_font(run, east_asia)
    if subscript is not None:
        run.font.subscript = subscript
    if superscript is not None:
        run.font.superscript = superscript


def set_paragraph_spacing(
    paragraph: Paragraph,
    *,
    before: float | None = None,
    after: float | None = None,
    line: float | Length | None = None,
) -> None:
    """Sets paragraph spacing. Point values and multiples are both supported."""
    fmt = paragraph.paragraph_format
    if before is not None:
        fmt.space_before = Pt(before)
    if after is not None:
        fmt.space_after = Pt(after)
    if line is not None:
        fmt.line_spacing = line


def set_page_margins(
    section: Any,
    *,
    top: float,
    bottom: float,
    left: float,
    right: float,
) -> None:
    """Sets page margins in centimeters."""
    section.top_margin = Cm(top)
    section.bottom_margin = Cm(bottom)
    section.left_margin = Cm(left)
    section.right_margin = Cm(right)


def set_page_size(section: Any, *, width: float, height: float) -> None:
    """Sets page width and height in centimeters."""
    section.page_width = Cm(width)
    section.page_height = Cm(height)


def _set_header_footer_text(part: Any, text: str) -> None:
    part.is_linked_to_previous = False
    if part.paragraphs:
        paragraph = part.paragraphs[0]
    else:
        paragraph = part.add_paragraph()
    rpr = None
    if paragraph.runs:
        rpr = copy.deepcopy(paragraph.runs[0]._r.rPr)
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)
    run = paragraph.add_run(text)
    if rpr is not None:
        run._r.insert(0, rpr)


def set_header_text(section: Any, text: str) -> None:
    """Sets the first header paragraph for a section."""
    _set_header_footer_text(section.header, text)


def set_footer_text(section: Any, text: str) -> None:
    """Sets the first footer paragraph for a section."""
    _set_header_footer_text(section.footer, text)


def extract_images(
    source: str | Path | DocumentType, out_dir: str | Path
) -> list[Path]:
    """Saves every embedded image in the package and returns the written paths."""
    doc = _as_doc(source)
    target_dir = Path(out_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    used: set[str] = set()
    for part in doc.part.package.parts:
        content_type = getattr(part, "content_type", "")
        if not str(part.partname).startswith("/word/media/"):
            continue
        if not content_type.startswith("image/"):
            continue
        name = Path(str(part.partname)).name
        stem, suffix = Path(name).stem, Path(name).suffix
        candidate = name
        counter = 2
        while candidate in used or (target_dir / candidate).exists():
            candidate = f"{stem}-{counter}{suffix}"
            counter += 1
        used.add(candidate)
        output = target_dir / candidate
        output.write_bytes(part.blob)
        saved.append(output)
    return saved


def list_styles(doc: DocumentType) -> list[dict[str, Any]]:
    """Returns style names, types, and built-in flags."""
    return [
        {
            "name": style.name,
            "type": str(style.type),
            "builtin": bool(style.builtin),
        }
        for style in doc.styles
    ]


def _remove_comment_anchors(element: Any) -> int:
    removed = 0
    for tag in ("w:commentRangeStart", "w:commentRangeEnd", "w:commentReference"):
        for node in list(element.iter(qn(tag))):
            if tag == "w:commentReference":
                removed += 1
            remove_element(node)

    for run in list(element.iter(qn("w:r"))):
        if (
            run.find(qn("w:t")) is None
            and run.find(qn("w:drawing")) is None
            and run.find(qn("w:br")) is None
            and run.find(qn("w:tab")) is None
            and run.find(qn("w:noBreakHyphen")) is None
        ):
            remove_element(run)
    return removed


def remove_comments(doc: DocumentType) -> int:
    """Removes comment anchors and comment package parts from a document.

    Returns the number of removed comment reference anchors. Comments in
    headers and footers are handled as well.
    """
    removed = _remove_comment_anchors(doc.element.body)
    for part in doc.part.package.parts:
        name = str(part.partname).lower()
        if not name.startswith(("/word/header", "/word/footer")):
            continue
        element = getattr(part, "_element", None)
        if element is not None:
            removed += _remove_comment_anchors(element)

    for relationship_id, relationship in list(doc.part.rels.items()):
        reltype = relationship.reltype.lower()
        if "comment" in reltype or "people" in reltype:
            doc.part.drop_rel(relationship_id)

    for part in list(doc.part.package.parts):
        name = str(part.partname).lower()
        if "comment" in name or "people" in name:
            doc.part.package.parts.remove(part)

    return removed
