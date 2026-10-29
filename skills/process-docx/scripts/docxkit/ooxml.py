"""Small OOXML helpers used by the higher-level docxkit API.

These functions are intentionally narrow. They cover formatting operations that
python-docx does not expose directly, while keeping the XML manipulation in one
place for easier extension.
"""

from __future__ import annotations

from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

_PPR_AFTER_PBDR = (
    "w:shd",
    "w:tabs",
    "w:suppressAutoHyphens",
    "w:kinsoku",
    "w:wordWrap",
    "w:overflowPunct",
    "w:topLinePunct",
    "w:autoSpaceDE",
    "w:autoSpaceDN",
    "w:bidi",
    "w:adjustRightInd",
    "w:snapToGrid",
    "w:spacing",
    "w:ind",
    "w:contextualSpacing",
    "w:mirrorIndents",
    "w:suppressOverlap",
    "w:jc",
    "w:textDirection",
    "w:textAlignment",
    "w:textboxTightWrap",
    "w:outlineLvl",
    "w:divId",
    "w:cnfStyle",
    "w:rPr",
    "w:sectPr",
    "w:pPrChange",
)

_PPR_AFTER_SHD = _PPR_AFTER_PBDR[1:]

_TCPR_AFTER_SHD = (
    "w:noWrap",
    "w:tcMar",
    "w:textDirection",
    "w:tcFitText",
    "w:vAlign",
    "w:hideMark",
    "w:headers",
    "w:cellIns",
    "w:cellDel",
    "w:cellMerge",
    "w:tcPrChange",
)


def set_run_east_asia_font(run: Any, name: str) -> None:
    """Sets the East Asian font name on a run."""
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), name)


def _level_from_ppr(ppr: Any) -> int | None:
    if ppr is None:
        return None
    numpr = ppr.find(qn("w:numPr"))
    if numpr is None:
        return None
    ilvl = numpr.find(qn("w:ilvl"))
    if ilvl is None:
        return 0
    try:
        return int(ilvl.get(qn("w:val")))
    except (TypeError, ValueError):
        return 0


def paragraph_list_level(paragraph: Any) -> int | None:
    """Returns the numbering level of a paragraph, or None for plain text.

    The direct paragraph properties are checked first; if they do not define a
    list, the paragraph style's numbering is used as a fallback.
    """
    level = _level_from_ppr(paragraph._p.pPr)
    if level is not None:
        return level
    style = getattr(paragraph, "style", None)
    if style is None:
        return None
    return _level_from_ppr(getattr(style.element, "pPr", None))


def set_paragraph_shading(paragraph: Any, fill: str) -> None:
    """Applies a solid background fill to a paragraph."""
    ppr = paragraph._p.get_or_add_pPr()
    old = ppr.find(qn("w:shd"))
    if old is not None:
        ppr.remove(old)

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill.lstrip("#"))
    ppr.insert_element_before(shd, *_PPR_AFTER_SHD)


def set_paragraph_border(
    paragraph: Any,
    *,
    top: bool = False,
    bottom: bool = False,
    left: bool = False,
    right: bool = False,
    sz: int = 8,
    color: str = "000000",
    space: int = 4,
) -> None:
    """Sets paragraph borders. ``sz`` is measured in eighths of a point.

    Calling this function replaces any existing paragraph border.
    """
    ppr = paragraph._p.get_or_add_pPr()
    old = ppr.find(qn("w:pBdr"))
    if old is not None:
        ppr.remove(old)

    edges = [
        ("w:top", top),
        ("w:left", left),
        ("w:bottom", bottom),
        ("w:right", right),
    ]
    if not any(enabled for _, enabled in edges):
        return

    borders = OxmlElement("w:pBdr")
    for tag, enabled in edges:
        if not enabled:
            continue
        edge = OxmlElement(tag)
        edge.set(qn("w:val"), "single")
        edge.set(qn("w:sz"), str(sz))
        edge.set(qn("w:space"), str(space))
        edge.set(qn("w:color"), color.lstrip("#"))
        borders.append(edge)

    ppr.insert_element_before(borders, *_PPR_AFTER_PBDR)


def set_cell_shading(cell: Any, fill: str) -> None:
    """Applies a solid background fill to a table cell."""
    tcpr = cell._tc.get_or_add_tcPr()
    old = tcpr.find(qn("w:shd"))
    if old is not None:
        tcpr.remove(old)

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill.lstrip("#"))
    tcpr.insert_element_before(shd, *_TCPR_AFTER_SHD)


def dump_xml(obj: Any, *, pretty: bool = True, max_chars: int | None = None) -> str:
    """Returns the OOXML for a document, paragraph, run, table, cell, or element."""
    if isinstance(obj, etree._Element):
        element = obj
    elif hasattr(obj, "element"):
        element = obj.element
    elif hasattr(obj, "_p"):
        element = obj._p
    elif hasattr(obj, "_tbl"):
        element = obj._tbl
    elif hasattr(obj, "_tr"):
        element = obj._tr
    elif hasattr(obj, "_tc"):
        element = obj._tc
    elif hasattr(obj, "_r"):
        element = obj._r
    elif hasattr(obj, "_sectPr"):
        element = obj._sectPr
    else:
        raise TypeError(f"Cannot extract XML from {type(obj).__name__}")

    text = etree.tostring(element, pretty_print=pretty, encoding="unicode")
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + "\n... (truncated)"
    return text


def remove_element(element: Any) -> None:
    """Removes an element from its parent when present."""
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)
