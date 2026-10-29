"""Command-line interface for docxkit."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ._bootstrap import doctor
from .core import (
    extract_images,
    extract_text,
    new_docx,
    open_docx,
    replace_text,
    save_docx,
)
from .inspection import inspect_docx
from .selftest import run_selftest


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _print_doctor(info: dict) -> None:
    print(f"python:       {info['python']}")
    print(f"executable:   {info['executable']}")
    print(f"platform:     {info['platform']}")
    print(f"python-docx:  {info['version']}")
    print(f"source:       {info['source']}")
    print(f"package path: {info['path']}")
    print(f"lxml:         {info['lxml']}")
    print(f"deps dir:     {info['deps_dir']}")
    print(f"deps exists:  {info['deps_exists']}")
    print(f"requirements: {info['requirements']}")


def _print_inspection(summary: dict) -> None:
    file_info = summary["file"]
    print(f"file:         {file_info['path'] or '(in-memory document)'}")
    if file_info["size"] is not None:
        print(f"size:         {file_info['size']} bytes")
    print(f"sections:     {len(summary['sections'])}")
    print(f"paragraphs:   {summary['paragraphs_total']}")
    print(f"tables:       {len(summary['tables'])}")
    print(f"images:       {len(summary['images'])}")
    print(f"comments:     {summary['comments']['count']}")
    print(f"styles:       {len(summary['styles'])}")

    headings = [
        paragraph["text"]
        for paragraph in summary["paragraphs"]
        if paragraph["heading"] and paragraph["text"]
    ]
    if headings:
        print("headings:")
        for text in headings[:12]:
            print(f"  - {text}")
    if summary["tables"]:
        print("tables:")
        for table in summary["tables"][:8]:
            print(
                f"  - table {table['index']}: "
                f"{table['rows']} rows x {table['columns']} columns"
            )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docx_tool.py",
        description="Read, inspect, create, and edit .docx documents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor", help="show Python and python-docx dependency details"
    )
    doctor_parser.add_argument("--json", action="store_true", help="print JSON")

    inspect_parser = subparsers.add_parser(
        "inspect", help="print a structural summary of a document"
    )
    inspect_parser.add_argument("path", type=Path)
    inspect_parser.add_argument(
        "--json", action="store_true", help="print the full JSON summary"
    )
    inspect_parser.add_argument(
        "--max-paragraphs", type=int, default=200, help="paragraph preview limit"
    )
    inspect_parser.add_argument(
        "--text-chars", type=int, default=160, help="character limit per preview"
    )

    text_parser = subparsers.add_parser("text", help="extract plain text")
    text_parser.add_argument("path", type=Path)
    text_parser.add_argument("-o", "--output", type=Path, help="write text to a file")
    text_parser.add_argument(
        "--no-tables", action="store_true", help="omit table cell text"
    )
    text_parser.add_argument(
        "--headers", action="store_true", help="include section headers"
    )
    text_parser.add_argument(
        "--footers", action="store_true", help="include section footers"
    )
    text_parser.add_argument(
        "--keep-empty", action="store_true", help="keep empty paragraphs"
    )

    replace_parser = subparsers.add_parser(
        "replace", help="replace literal text and save a new document"
    )
    replace_parser.add_argument("path", type=Path)
    replace_parser.add_argument("old")
    replace_parser.add_argument("new")
    replace_parser.add_argument("-o", "--output", type=Path)
    replace_parser.add_argument(
        "--count", type=int, default=-1, help="maximum replacements; -1 means all"
    )
    replace_parser.add_argument(
        "--no-tables", action="store_true", help="skip table cells"
    )
    replace_parser.add_argument(
        "--headers", action="store_true", help="include headers and footers"
    )

    new_parser = subparsers.add_parser("new", help="create a blank document")
    new_parser.add_argument("path", type=Path)
    new_parser.add_argument(
        "--template", type=Path, help="start from an existing .docx template"
    )

    images_parser = subparsers.add_parser(
        "images", help="extract embedded images from a document"
    )
    images_parser.add_argument("path", type=Path)
    images_parser.add_argument(
        "-o", "--output", type=Path, required=True, help="output directory"
    )

    subparsers.add_parser("selftest", help="run the built-in end-to-end check")
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.command == "doctor":
        info = doctor()
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            _print_doctor(info)
        return 0

    if args.command == "inspect":
        summary = inspect_docx(
            args.path,
            max_paragraphs=args.max_paragraphs,
            text_chars=args.text_chars,
        )
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            _print_inspection(summary)
        return 0

    if args.command == "text":
        text = extract_text(
            args.path,
            include_tables=not args.no_tables,
            include_headers=args.headers,
            include_footers=args.footers,
            keep_empty=args.keep_empty,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(text)
        return 0

    if args.command == "replace":
        doc = open_docx(args.path)
        count = replace_text(
            doc,
            args.old,
            args.new,
            count=args.count,
            include_tables=not args.no_tables,
            include_headers=args.headers,
        )
        output = args.output or args.path.with_name(
            f"{args.path.stem}.replaced{args.path.suffix}"
        )
        save_docx(doc, output)
        print(f"replacements: {count}")
        print(f"output:       {output}")
        return 0

    if args.command == "new":
        doc = new_docx(args.template)
        save_docx(doc, args.path)
        print(f"created: {args.path}")
        return 0

    if args.command == "images":
        paths = extract_images(args.path, args.output)
        for path in paths:
            print(path)
        print(f"images: {len(paths)}")
        return 0

    if args.command == "selftest":
        return run_selftest()

    raise ValueError(f"Unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the CLI and returns a process exit code."""
    _ensure_utf8_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1
