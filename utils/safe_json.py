"""
Safe JSON read/write with atomic writes and corruption recovery.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar


T = TypeVar("T")


def safe_read_json(
    filepath: str | Path,
    default: Optional[T] = None,
    error_handler: Optional[Callable[[Exception], None]] = None,
) -> Any:
    """
    Read a JSON file safely. Returns `default` on any failure.

    :param filepath: path to JSON file
    :param default: value to return if read or decode fails
    :param error_handler: optional callback with the exception
    :returns: parsed JSON data or default
    """
    path = Path(filepath)
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        if error_handler:
            error_handler(exc)
        return default


def safe_write_json(
    filepath: str | Path,
    data: Any,
    *,
    atomic: bool = True,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> bool:
    """
    Write a JSON file safely. If `atomic` is True, writes to a temp file first,
    then renames (atomic on most POSIX filesystems; on Windows this is best-effort).

    :param filepath: target path
    :param data: JSON-serializable data
    :param atomic: if True, use atomic rename
    :param indent: JSON indent
    :param ensure_ascii: pass to json.dump
    :returns: True on success, False on failure
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not atomic:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            return True
        except OSError:
            return False

    # Atomic write via temp file + rename
    tmp = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json",
            prefix=path.stem + "_",
            dir=str(path.parent),
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            f.flush()
            os.fsync(fd)
        os.replace(tmp_path, str(path))
        return True
    except (OSError, ValueError) as exc:
        if tmp:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        print(f"[safe_json] Write error: {exc}")
        return False


def safe_read_json_with_backup(
    filepath: str | Path,
    backup_path: Optional[str | Path] = None,
    default: Any = None,
) -> Any:
    """
    Read JSON; if corrupted, try backup; if that also fails, return default.

    :param filepath: primary JSON file
    :param backup_path: backup file (default: filepath + ".bak")
    :param default: fallback value
    """
    data = safe_read_json(filepath, default=None)
    if data is not None:
        return data
    # Try backup
    backup = Path(backup_path or (str(filepath) + ".bak"))
    if backup.exists():
        data = safe_read_json(backup, default=None)
        if data is not None:
            return data
    return default


def merge_dicts(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep-merge `overlay` into `base`, preserving existing keys not present in overlay.

    :param base: original dict (modified in-place)
    :param overlay: overriding dict
    :returns: merged dict (same object as base)
    """
    for key, value in overlay.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            merge_dicts(base[key], value)
        else:
            base[key] = value
    return base
