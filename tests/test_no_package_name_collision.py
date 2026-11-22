"""
tests/test_no_package_name_collision.py — حارس تعارض أسماء الحزم (P4)
======================================================================
المشكلة التي يمنعها: حزمتان بنفس الاسم على مسارين من مسارات sys.path (الجذر و backend/).
Python يحمّل **الأولى فقط** ويخزّنها في sys.modules، فينجح كل ملف اختبار منفرداً ويفشل
`unittest discover` (أو أي عملية تستورد المحرك الحي والمجلس معاً) بخطأ
`No module named 'agents.base_agent'` حسب ترتيب الاستيراد.

الفحوص (سلوكية — تُنفّذ الاستيراد فعلاً في عمليات مستقلة — + فحص AST ثابت للاستيرادات):
  1) لا اسم استيراد (حزمة نظامية أو وحدة) مشترك بين الجذر و backend/ — إلا ما في INTENTIONAL_SHIMS.
  2) المجلس `council` و `agents` (backend) يُستوردان معاً في عملية واحدة وبكلا ترتيبي sys.path،
     وكل حزمة تُحلّ من مكانها الصحيح.
  3) لا ملفات المجلس القديمة داخل `agents/` الجذرية (يعني أن الحذف/النقل تم فعلاً).
  4) لا استيراد قديم `from agents import <مجلس>` / `agents.<وحدة مجلس>` في أي ملف بايثون في المشروع.
  5) الأسماء المقصودة (`config`): الجذر يعيد تصدير backend/config.py ⇒ القيم متطابقة بكلا الترتيبين.

التشغيل: PYTHONPATH=. python -m unittest tests/test_no_package_name_collision.py -v
"""
import ast
import os
import subprocess
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

COUNCIL_MODULES = (
    "alpha_regime_agent", "beta_orderflow_agent", "gamma_redteam_critic",
    "delta_macro_sentinel", "omega_risk_governor",
)
COUNCIL_CLASSES = (
    "AlphaRegimeAgent", "BetaOrderFlowAgent", "GammaRedTeamCritic", "OmegaRiskGovernor",
    "MacroSentinelAgent", "SignalPayload", "RegimeOutput", "OrderFlowProposal", "CriticAssessment",
    "ExecutionParams", "AdaptiveThresholdEngine", "MacroRiskAssessment", "NewsRiskLevel",
)
# أسماء مشتركة عن قصد: الحزمة الجذرية تعيد تصدير وحدة backend (ARCHITECTURE.md §6) — يُفحَص تطابقها سلوكياً (5)
INTENTIONAL_SHIMS = {"config"}
# مجلدات لا تُفحص (ليست كود المشروع)
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", ".ruff_cache", ".tmp", ".taste-skill", ".hallmark",
    ".claude", ".codex", ".agents", "_archive", "openbb_source", "tradingagents_source", "public", "src",
    "platform", "logs", "docs", "mql5_shared_signals", "mql5_shared_signals_test",
}


def _import_kinds(base_dir: str) -> dict:
    """اسم الاستيراد ← 'package' (فيه __init__.py) | 'module' (name.py) داخل base_dir مباشرة."""
    kinds = {}
    for entry in os.listdir(base_dir):
        full = os.path.join(base_dir, entry)
        if os.path.isdir(full):
            if entry in SKIP_DIRS or entry.startswith((".", "_")):
                continue
            if os.path.isfile(os.path.join(full, "__init__.py")):
                kinds[entry] = "package"
        elif entry.endswith(".py") and not entry.startswith("_"):
            kinds[entry[:-3]] = "module"
    return kinds


def _run(code: str, order: str) -> subprocess.CompletedProcess:
    """ينفّذ code في عملية بايثون معزولة بترتيب sys.path المطلوب: 'root_first' أو 'backend_first'."""
    paths = [ROOT_DIR, BACKEND_DIR] if order == "root_first" else [BACKEND_DIR, ROOT_DIR]
    script = f"import sys; sys.path[:0] = {paths!r}\n{code}"
    return subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, timeout=180)


class TestNoPackageNameCollision(unittest.TestCase):

    # ── 1) أسماء مشتركة بين الجذر و backend ──
    def test_no_shared_import_names_between_root_and_backend(self):
        root, backend = _import_kinds(ROOT_DIR), _import_kinds(BACKEND_DIR)
        shared = sorted((set(root) & set(backend)) - INTENTIONAL_SHIMS)
        details = [f"  '{n}': الجذر={root[n]} (…/{n}) ↔ backend={backend[n]} (backend/{n})" for n in shared]
        self.assertEqual(
            shared, [],
            "تعارض أسماء استيراد بين الجذر و backend/ — حزمة واحدة فقط ستُحمَّل حسب ترتيب sys.path:\n"
            + "\n".join(details)
            + "\nالحل: أعد تسمية أحدهما (مثل agents/ → council/ في P4) ثم احذف المجلد القديم.",
        )

    # ── 2) الاستيراد المشترك فعلاً في عملية واحدة ──
    def _both_packages_import(self, order):
        code = (
            "import council, agents\n"
            "from council import AlphaRegimeAgent, OmegaRiskGovernor\n"
            "from agents.base_agent import BaseAgent\n"
            "import council.delta_macro_sentinel as d\n"
            "import os\n"
            f"root={ROOT_DIR!r}; backend={BACKEND_DIR!r}\n"
            "assert os.path.dirname(council.__file__) == os.path.join(root, 'council'), council.__file__\n"
            "assert os.path.dirname(agents.__file__) == os.path.join(backend, 'agents'), agents.__file__\n"
            "assert BaseAgent.__module__ == 'agents.base_agent'\n"
            "print('OK')\n"
        )
        out = _run(code, order)
        self.assertEqual(out.returncode, 0, f"[{order}]\n{out.stderr[-900:]}")
        self.assertEqual(out.stdout.strip().splitlines()[-1], "OK")

    def test_council_and_backend_agents_import_together_root_first(self):
        self._both_packages_import("root_first")

    def test_council_and_backend_agents_import_together_backend_first(self):
        self._both_packages_import("backend_first")

    # ── 3) لا بقايا للمجلس في agents/ الجذرية ──
    def test_old_root_agents_folder_has_no_council_modules(self):
        old = os.path.join(ROOT_DIR, "agents")
        leftovers = [f for f in COUNCIL_MODULES if os.path.isfile(os.path.join(old, f + ".py"))]
        self.assertEqual(
            leftovers, [],
            f"ملفات المجلس ما زالت داخل agents/ الجذرية: {leftovers} — نفّذ git mv agents council "
            "(أو احذف المجلد القديم بعد النقل)",
        )
        self.assertFalse(os.path.isfile(os.path.join(old, "__init__.py")),
                         "agents/__init__.py الجذرية ما زالت موجودة ⇒ التعارض مع backend/agents قائم")

    # ── 4) لا استيرادات قديمة للمجلس ──
    def test_no_legacy_council_imports_anywhere(self):
        violations = []
        for d, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(d, f)
                try:
                    with open(path, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read())
                except (SyntaxError, UnicodeDecodeError):
                    continue
                rel = os.path.relpath(path, ROOT_DIR)
                for n in ast.walk(tree):
                    if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                        mod = n.module
                        if mod == "agents" and any(a.name in COUNCIL_CLASSES for a in n.names):
                            violations.append(f"{rel}:{n.lineno} from agents import <council>")
                        elif mod.startswith("agents.") and mod.split(".")[1] in COUNCIL_MODULES:
                            violations.append(f"{rel}:{n.lineno} from {mod} import …")
                    elif isinstance(n, ast.Import):
                        for a in n.names:
                            if a.name.startswith("agents.") and a.name.split(".")[1] in COUNCIL_MODULES:
                                violations.append(f"{rel}:{n.lineno} import {a.name}")
        self.assertEqual(violations, [], "استيرادات قديمة (استبدلها بـ council):\n  " + "\n  ".join(violations))

    # ── 5) الأسماء المقصودة: تطابق القيم بكلا الترتيبين ──
    def test_intentional_shims_resolve_to_identical_values_in_both_orders(self):
        if not os.path.isfile(os.path.join(ROOT_DIR, "config", "__init__.py")):
            self.skipTest("لا توجد حزمة config/ جذرية — لا shim لفحصه")
        code = "import config, json; print(json.dumps([config.STRATEGY, config.META_GATE], sort_keys=True, default=str))"
        outs = []
        for order in ("root_first", "backend_first"):
            r = _run(code, order)
            self.assertEqual(r.returncode, 0, f"[{order}]\n{r.stderr[-600:]}")
            outs.append(r.stdout.strip().splitlines()[-1])
        self.assertEqual(outs[0], outs[1], "config يعطي قيماً مختلفة حسب ترتيب sys.path")


if __name__ == "__main__":
    unittest.main(verbosity=2)
