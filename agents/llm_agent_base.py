"""
agents/llm_agent_base.py — القاعدة المشتركة لفريق المحللين، محمَّلة بمسار صريح.

المشكلة الجذرية
---------------
المشروع يعرّف حزمتين بنفس الاسم: ``agents/`` و``backend/agents/`` (وكذلك
``core/`` و``backend/core/``). كلٌّ منهما يعرّف ``BaseAgent`` بواجهة مختلفة:

    agents/base_agent.py          → BaseAgent(llm_router, db=None)
    backend/agents/base_agent.py  → BaseAgent(name, interval_sec=5.0)  + run_cycle مجرّدة

فكان ``from agents.base_agent import BaseAgent`` داخل وحدات المحللين يُحلّ حسب
ترتيب sys.path: في سياق التشغيل الحقيقي (backend أولاً) يرث المحللون قاعدة
backend المجرّدة التي تفرض ``run_cycle`` وتتوقّع وسيطاً أولاً اسم الوكيل →
``TypeError: Can't instantiate abstract class`` عند إنشاء أي محلل.

الحل
----
تحميل الملف الجذري **بمساره الصريح** تحت اسم وحدة فريد، مع تسجيل
``core.llm_router`` الجذرية لأن حزمة ``core`` المحمّلة في التطبيق هي
``backend/core`` (ولا تحتوي llm_router). النتيجة: فريق المحللين يحصل على
قاعدته الصحيحة في أي سياق تشغيل، بلا لمس ملفات backend.
"""

from __future__ import annotations

import importlib.util
import os
import sys

_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_AGENTS_DIR)

_BASE_MODULE_NAME = "analyst_team_base_agent"
_ROUTER_MODULE_NAME = "analyst_team_llm_router"


def _load_from_path(module_name: str, file_path: str):
    """تحميل وحدة من مسار ملف صريح تحت اسم فريد (مع تخزينها مؤقتاً)."""
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"تعذّر تحميل الوحدة من المسار: {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_root_llm_router():
    """
    تسجيل ``core.llm_router`` الجذرية إن لم تكن الحزمة المحمّلة تحتويها.
    (التطبيق يحمّل ``backend/core`` وليس فيه llm_router أصلاً.)
    """
    if "core.llm_router" in sys.modules:
        return

    router_path = os.path.join(_PROJECT_ROOT, "core", "llm_router.py")
    if not os.path.isfile(router_path):
        return

    module = _load_from_path(_ROUTER_MODULE_NAME, router_path)
    sys.modules["core.llm_router"] = module

    core_package = sys.modules.get("core")
    if core_package is not None:
        setattr(core_package, "llm_router", module)


_ensure_root_llm_router()

_base_module = _load_from_path(
    _BASE_MODULE_NAME, os.path.join(_AGENTS_DIR, "base_agent.py")
)

BaseAgent = _base_module.BaseAgent

__all__ = ["BaseAgent"]
