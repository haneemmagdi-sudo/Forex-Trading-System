# core package — Unified namespace bridging backend and root
import os
_root_core = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "core"))
if os.path.isdir(_root_core) and _root_core not in __path__:
    __path__.append(_root_core)
