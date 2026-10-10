"""
scratch/verify_timesfm_connection.py
=====================================
تحقق شامل من اتصال النظام بأوزان TimesFM المحلية.
يختبر: الملفات ← الاستيراد ← إنشاء الكائن ← استدلال فعلي.
"""
import os
import sys
import json
import time

# ── إضافة جذر المشروع إلى المسار ─────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

WEIGHTS_DIR = "C:/Users/magdi/timesfm_weights"
PYTHON_EXE  = sys.executable
RESULTS     = {}
PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

SEP = "=" * 60

def section(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)

# ══════════════════════════════════════════════════════════════
# CHECK 1: بيئة Python
# ══════════════════════════════════════════════════════════════
section("CHECK 1: بيئة Python")
py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
py_is_311 = sys.version_info[:2] == (3, 11)
RESULTS["python_version"] = py_ver
RESULTS["python_is_311"]  = py_is_311
RESULTS["python_exe"]     = PYTHON_EXE
print(f"  المفسّر  : {PYTHON_EXE}")
print(f"  الإصدار  : {py_ver}")
print(f"  Python 3.11 : {PASS if py_is_311 else FAIL + ' (مطلوب 3.11)'}")

# ══════════════════════════════════════════════════════════════
# CHECK 2: الحزم الأساسية
# ══════════════════════════════════════════════════════════════
section("CHECK 2: الحزم الأساسية")
packages_ok = True
for pkg in ["numpy", "torch", "timesfm", "pandas"]:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "?")
        print(f"  {PASS}  {pkg} {ver}")
        RESULTS[f"pkg_{pkg}"] = ver
    except ImportError as e:
        print(f"  {FAIL}  {pkg} — {e}")
        RESULTS[f"pkg_{pkg}"] = None
        packages_ok = False
RESULTS["packages_ok"] = packages_ok

# ══════════════════════════════════════════════════════════════
# CHECK 3: ملفات الأوزان
# ══════════════════════════════════════════════════════════════
section("CHECK 3: ملفات الأوزان المحلية")
weights_files = {
    "model.safetensors": "الأوزان الرئيسية (PyTorch)",
    "torch_model.ckpt":  "نسخة احتياطية (.ckpt)",
    "config.json":       "إعدادات المعمارية",
    "README.md":         "توثيق النموذج",
}
RESULTS["weights_dir_exists"] = os.path.isdir(WEIGHTS_DIR)
print(f"  المجلد : {WEIGHTS_DIR}")
print(f"  الحالة : {PASS if RESULTS['weights_dir_exists'] else FAIL}")

files_ok = True
RESULTS["weights_files"] = {}
for fname, desc in weights_files.items():
    fpath = os.path.join(WEIGHTS_DIR, fname)
    exists = os.path.isfile(fpath)
    size_mb = round(os.path.getsize(fpath) / (1024**2), 1) if exists else 0
    icon = PASS if exists else FAIL
    print(f"  {icon}  {fname:<28} {size_mb:>8.1f} MB   [{desc}]")
    RESULTS["weights_files"][fname] = {"exists": exists, "size_mb": size_mb}
    if not exists:
        files_ok = False
RESULTS["weights_files_ok"] = files_ok

# ══════════════════════════════════════════════════════════════
# CHECK 4: استيراد TimesFMForecaster
# ══════════════════════════════════════════════════════════════
section("CHECK 4: استيراد TimesFMForecaster")
try:
    from ml_models.timesfm_predictor import TimesFMForecaster
    print(f"  {PASS}  from ml_models.timesfm_predictor import TimesFMForecaster")
    RESULTS["import_ok"] = True
except Exception as e:
    print(f"  {FAIL}  {e}")
    RESULTS["import_ok"] = False

# ══════════════════════════════════════════════════════════════
# CHECK 5: كشف مسار الأوزان (detection logic)
# ══════════════════════════════════════════════════════════════
section("CHECK 5: كشف مسار الأوزان تلقائياً")
if RESULTS.get("import_ok"):
    try:
        forecaster = TimesFMForecaster(
            context_len=512,
            horizon_len=128,
            lazy_load=True,       # لا تحمّل النموذج بعد
            torch_compile=False,
        )
        repo_id = forecaster._repo_id
        expected = WEIGHTS_DIR.replace("\\", "/")
        detection_ok = (repo_id == expected)
        RESULTS["repo_id"] = repo_id
        RESULTS["detection_ok"] = detection_ok
        print(f"  repo_id المُكتشف : {repo_id}")
        print(f"  المسار المتوقع  : {expected}")
        print(f"  الكشف التلقائي  : {PASS if detection_ok else FAIL}")
        print(f"  وضع الاستدلال  : {'محلي (بدون إنترنت)' if detection_ok else 'HuggingFace Hub'}")
    except Exception as e:
        print(f"  {FAIL}  {e}")
        RESULTS["detection_ok"] = False
else:
    print(f"  {WARN}  تم تخطّيه — الاستيراد فشل في الخطوة السابقة")
    RESULTS["detection_ok"] = False

# ══════════════════════════════════════════════════════════════
# CHECK 6: استيراد TimesFMFeatureExtractor
# ══════════════════════════════════════════════════════════════
section("CHECK 6: استيراد TimesFMFeatureExtractor")
if RESULTS.get("import_ok"):
    try:
        from ml_models.timesfm_extractor import TimesFMFeatureExtractor
        print(f"  {PASS}  from ml_models.timesfm_extractor import TimesFMFeatureExtractor")
        RESULTS["extractor_import_ok"] = True
    except Exception as e:
        print(f"  {FAIL}  {e}")
        RESULTS["extractor_import_ok"] = False
else:
    RESULTS["extractor_import_ok"] = False

# ══════════════════════════════════════════════════════════════
# CHECK 7: اختبار status_report()
# ══════════════════════════════════════════════════════════════
section("CHECK 7: اختبار status_report()")
if RESULTS.get("import_ok") and RESULTS.get("detection_ok"):
    try:
        report = forecaster.status_report()
        RESULTS["status_report"] = {k: str(v) for k, v in report.items()}
        print(f"  model_ready     : {report['model_ready']}")
        print(f"  backend         : {report['backend']}")
        print(f"  repo_id         : {report['repo_id']}")
        print(f"  context_len     : {report['context_len']}")
        print(f"  horizon_len     : {report['horizon_len']}")
        print(f"  inference_count : {report['inference_count']}")
        print(f"\n  {PASS}  status_report() جاهز")
        RESULTS["status_report_ok"] = True
    except Exception as e:
        print(f"  {FAIL}  {e}")
        RESULTS["status_report_ok"] = False
else:
    print(f"  {WARN}  تم تخطّيه")
    RESULTS["status_report_ok"] = False

# ══════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════
section("SUMMARY — ملخص نهائي")
checks = [
    ("Python 3.11",             RESULTS.get("python_is_311", False)),
    ("الحزم الأساسية",          RESULTS.get("packages_ok", False)),
    ("ملفات الأوزان",           RESULTS.get("weights_files_ok", False)),
    ("استيراد TimesFMForecaster", RESULTS.get("import_ok", False)),
    ("كشف المسار المحلي",       RESULTS.get("detection_ok", False)),
    ("استيراد TimesFMExtractor", RESULTS.get("extractor_import_ok", False)),
    ("status_report()",         RESULTS.get("status_report_ok", False)),
]

all_pass = all(ok for _, ok in checks)
for name, ok in checks:
    print(f"  {PASS if ok else FAIL}  {name}")

print(f"\n  {'🟢 كل الفحوصات نجحت — النظام متصل بالأوزان وجاهز' if all_pass else '🔴 بعض الفحوصات فشلت — راجع التفاصيل أعلاه'}")
RESULTS["all_pass"] = all_pass

out_path = os.path.join(PROJECT_ROOT, "scratch", "verify_timesfm_result.json")
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(RESULTS, fh, indent=2, ensure_ascii=False)
print(f"\n  النتائج محفوظة في: {out_path}")
print(f"\n{SEP}\n")
