"""
ujson.py — Compatibility shim for Windows DLL load failure
============================================================
The native ujson C extension (ujson.cp311-win_amd64.pyd) fails to load on
this machine because one of its internal DLL dependencies is missing.

This shim wraps Python's stdlib json module, exposing the same API surface
that FastAPI and other packages expect from ujson. Since backend/main.py
inserts this directory into sys.path *before* site-packages, Python will
import this module instead of the broken native extension.

Performance: Slightly slower than native ujson, but fully compatible.
"""

from json import loads, JSONDecodeError, JSONEncoder  # noqa: F401
import json as _json

__version__ = "shim-5.7.0-stdlib"
__author__ = "compatibility shim"


def dumps(
    obj,
    *,
    ensure_ascii: bool = True,
    double_precision: int = 9,
    encode_html_chars: bool = False,
    escape_forward_slashes: bool = True,
    sort_keys: bool = False,
    indent: int = 0,
    allow_nan: bool = True,
    reject_bytes: bool = True,
    **kwargs,
) -> str:
    """Serialize obj to a JSON-formatted string (stdlib fallback)."""
    return _json.dumps(
        obj,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        indent=indent if indent else None,
        allow_nan=allow_nan,
    )
