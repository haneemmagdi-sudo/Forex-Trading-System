"""
core package — Central Infrastructure and Broker Integration Bridge.
"""

import sys
import os

# Ensure backend/ is on sys.path so backend.core sub-modules resolve correctly.
_backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
_backend_dir = os.path.normpath(_backend_dir)
_backend_core = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "backend", "core"))
if os.path.isdir(_backend_core) and _backend_core not in __path__:
    __path__.append(_backend_core)

from core.llm_router import LLMRouter, LLMResponse, AllProvidersExhaustedError
from core.mt5_broker import get_broker, MT5Broker

__all__ = [
    "LLMRouter",
    "LLMResponse",
    "AllProvidersExhaustedError",
    "get_broker",
    "MT5Broker",
]
