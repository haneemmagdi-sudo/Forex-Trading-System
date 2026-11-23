"""
council/tuning.py — قراءة كتل الإعداد المركزية لعملية المجلس بلا استيراد backend/config.py
=========================================================================================
المجلس يعمل في عملية منفصلة، و`import config` في الجذر يشير إلى حزمة config/ مختلفة (settings.py)،
وتحميل backend/config.py الفعلي له آثار جانبية (مجلدات، .env). لذلك تُقرأ الكتل الحرفية
(dict من أرقام/نصوص) عبر ast.literal_eval من الملف المصدر نفسه — مصدر حقيقة واحد، بلا آثار جانبية.
أي فشل (ملف غائب/كتلة غير حرفية) يعيد {} فتعمل القيم الافتراضية في الكود كما كانت.
"""
import ast
from pathlib import Path
from typing import Any, Dict

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "backend" / "config.py"
_cache: Dict[str, Dict[str, Any]] = {}


def get_block(name: str) -> Dict[str, Any]:
    """يعيد نسخة من كتلة إعداد باسمها (مثل ENTRY_UPGRADES_2026) أو {} عند تعذّر القراءة."""
    if name not in _cache:
        block: Dict[str, Any] = {}
        try:
            tree = ast.parse(_CONFIG_PATH.read_text(encoding="utf-8"))
            for node in tree.body:
                targets = []
                if isinstance(node, ast.Assign):
                    targets, value = node.targets, node.value
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    targets, value = [node.target], node.value
                else:
                    continue
                if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                    block = dict(ast.literal_eval(value))
                    break
        except Exception:
            block = {}
        _cache[name] = block
    return dict(_cache[name])


def get_value(block: str, key: str, default: Any) -> Any:
    return get_block(block).get(key, default)
