"""Local dependency bootstrap for docxkit.

The module deliberately avoids importing python-docx at import time. It checks
the current environment first and installs into ``scripts/.deps`` only when the
required package is missing or too old.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEPS_DIR = Path(__file__).resolve().parent.parent / ".deps"
REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"
MIN_VERSION = (1, 1)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in re.split(r"[.\-+]", str(value)):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts)


def _version_ok(value: str | None) -> bool:
    if not value or value == "unknown":
        return True
    return _version_tuple(value) >= MIN_VERSION


def _is_under_deps(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(DEPS_DIR.resolve())
    except AttributeError:
        return str(path.resolve()).startswith(str(DEPS_DIR.resolve()))


def _docx_info() -> dict[str, Any] | None:
    try:
        module = importlib.import_module("docx")
    except Exception:  # noqa: BLE001
        return None

    version = getattr(module, "__version__", None)
    if not version:
        try:
            version = importlib.metadata.version("python-docx")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"

    path = getattr(module, "__file__", None)
    resolved = Path(path).resolve() if path else None
    return {
        "source": "local" if resolved and _is_under_deps(resolved) else "global",
        "version": str(version),
        "path": str(resolved) if resolved else "",
        "deps_dir": str(DEPS_DIR),
    }


def _clear_docx_modules() -> None:
    for name in list(sys.modules):
        if name == "docx" or name.startswith("docx."):
            del sys.modules[name]


def _prepend_deps() -> None:
    deps = str(DEPS_DIR)
    while deps in sys.path:
        sys.path.remove(deps)
    sys.path.insert(0, deps)


def _install(verbose: bool) -> None:
    DEPS_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(DEPS_DIR),
        "--upgrade",
        "--quiet",
        "--disable-pip-version-check",
    ]
    if REQUIREMENTS.is_file():
        command.extend(["-r", str(REQUIREMENTS)])
    else:
        command.append("python-docx>=1.1,<2")

    if verbose:
        print(f"Installing python-docx into {DEPS_DIR} ...", file=sys.stderr)
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Failed to install python-docx into the local .deps directory. "
            "Check the Python environment and network access, or install "
            "python-docx manually and rerun."
        ) from exc


def ensure_deps(verbose: bool = False) -> dict[str, Any]:
    """Ensures python-docx is importable, installing it locally if needed.

    Returns a small dictionary describing the selected package and its path.
    """
    info = _docx_info()
    if info and _version_ok(info["version"]):
        return info

    _clear_docx_modules()

    if DEPS_DIR.is_dir():
        _prepend_deps()
        info = _docx_info()
        if info and _version_ok(info["version"]):
            return info
        _clear_docx_modules()

    _install(verbose)
    _prepend_deps()
    _clear_docx_modules()

    info = _docx_info()
    if not info:
        raise RuntimeError(
            "python-docx was installed but still cannot be imported. "
            "Run the doctor command for details."
        )
    return info


def doctor() -> dict[str, Any]:
    """Returns environment and dependency details for troubleshooting."""
    info = ensure_deps()
    try:
        from lxml import etree

        lxml_version = etree.__version__
    except Exception:  # noqa: BLE001
        lxml_version = "missing"

    return {
        **info,
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": sys.platform,
        "lxml": lxml_version,
        "requirements": str(REQUIREMENTS),
        "deps_exists": DEPS_DIR.is_dir(),
    }
