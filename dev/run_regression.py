"""Run the M8 Blender regression smoke suite.

Run from Blender, for example:
blender --background --factory-startup --python dev/run_regression.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent
RESULT_PREFIX = "M8_REGRESSION_RESULT"

TESTS = (
    ("runtime", DEV_DIR / "selftest_runtime.py"),
    ("keymaps", DEV_DIR / "selftest_keymaps.py"),
)


def _load_script(name, path):
    module_name = f"_m8_regression_{name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _runtime_failed(result):
    if result.get("fatal"):
        return True
    if not result.get("registered"):
        return True
    if not result.get("unregistered"):
        return True
    for key in ("registration_errors", "missing_operators", "missing_types", "duplicate_bl_idnames"):
        if result.get(key):
            return True
    for key in ("health_check_result", "scene_audit_result"):
        value = result.get(key)
        if isinstance(value, str) and value.startswith("ERROR:"):
            return True
    return False


def _keymaps_failed(result):
    return bool(result.get("fatal") or result.get("failures"))


def _failed(name, result):
    if name == "runtime":
        return _runtime_failed(result)
    if name == "keymaps":
        return _keymaps_failed(result)
    return bool(result.get("fatal"))


def run():
    report = {
        "root": str(ROOT),
        "tests": {},
        "failed": [],
        "ok": False,
    }

    for name, path in TESTS:
        try:
            module = _load_script(name, path)
            result = module.run()
        except Exception as exc:
            result = {
                "fatal": str(exc),
                "traceback": traceback.format_exc(),
            }
        report["tests"][name] = result
        if _failed(name, result):
            report["failed"].append(name)

    report["ok"] = not report["failed"]
    return report


if __name__ == "__main__":
    result = run()
    print(RESULT_PREFIX + " " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not result.get("ok"):
        raise SystemExit(1)
