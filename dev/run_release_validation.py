"""M8 Release Validation Entrypoint.

Runs all test suites in isolated subprocesses so that:
- Mock-bpy unit suites (test_ai_assistant.py) that overwrite sys.modules['bpy']
  cannot poison real Blender integration suites.
- Each suite runs as __main__ with --background --factory-startup --offline-mode
  --python-exit-code 1 when run under Blender.
- Runtime/keymap integrity is validated through the existing run_regression.py
  (the strict quality gate), not a loose standalone runner.
- Individual stdout/stderr logs and a JSON summary are saved to --output-dir
  (default: a new temp directory).

Usage (under Blender):
    blender --background --factory-startup --python-exit-code 1 \\
            --python dev/run_release_validation.py -- --output-dir /tmp/m8_validation

Usage (with python + blender path):
    python dev/run_release_validation.py --blender /path/to/blender --output-dir /tmp/m8_validation

Design rules:
- Missing declared test files MUST fail (not silently skip).
- Timeout is enforced per subprocess.
- Do NOT claim PASS for skipped branches.
- Intentional mock 'ERROR:' diagnostic logs in unit suites are NOT treated as
  failures when the subprocess exit code is 0.
- Failure injection tests use proper healthy base payloads before injecting errors.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV_DIR = Path(__file__).resolve().parent

SUBPROCESS_TIMEOUT = 300  # seconds per suite

# ---------------------------------------------------------------------------
# Test suite registry
# ---------------------------------------------------------------------------
# Each entry: (name, script_path, run_under_blender)
# run_under_blender=True  → launched via blender --python <script>
# run_under_blender=False → launched via sys.executable <script> (mock-bpy suites)

BLENDER_SUITES: list[tuple[str, Path]] = [
    ("runtime",            DEV_DIR / "run_regression.py"),
    ("unity_fbx",          DEV_DIR / "selftest_unity_fbx.py"),
    ("armature_mirror",    DEV_DIR / "selftest_armature_mirror.py"),
    ("preferences_ui",     DEV_DIR / "test_all_preferences_ui.py"),
    ("fast_loop_selection",DEV_DIR / "test_fast_loop_selection.py"),
    ("fast_loop_edge_flow",DEV_DIR / "test_fast_loop_edge_flow_uv.py"),
    ("fast_loop_hidden",   DEV_DIR / "test_fast_loop_hidden_faces.py"),
    ("normal_transfer",    DEV_DIR / "selftest_normal_transfer.py"),
    ("uv_checker",         DEV_DIR / "test_uv_checker.py"),
    ("seamless_material",  DEV_DIR / "test_seamless_material.py"),
    ("align_mesh",         DEV_DIR / "test_align_mesh_and_equal_length.py"),
    ("npanel",             DEV_DIR / "selftest_npanel.py"),
    ("github_update",      DEV_DIR / "selftest_github_update.py"),
    ("i18n",               DEV_DIR / "selftest_i18n_adaptation.py"),
]

# Mock-bpy unit suites: run with plain Python (NOT Blender) so they can safely
# overwrite sys.modules['bpy'] without polluting the Blender integration suites.
UNIT_SUITES: list[tuple[str, Path]] = [
    ("ai_assistant_unit",  DEV_DIR / "test_ai_assistant.py"),
]


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def _detect_blender_binary() -> str | None:
    """Return bpy.app.binary_path if running inside Blender, else None."""
    try:
        import bpy  # type: ignore
        bp = getattr(bpy.app, "binary_path", None)
        if bp and Path(bp).is_file():
            return bp
    except ImportError:
        pass
    return None


def _run_subprocess(
    name: str,
    script: Path,
    blender_bin: str | None,
    output_dir: Path,
    use_blender: bool = True,
) -> dict:
    """
    Run *script* in an isolated subprocess and return a result dict.
    Logs stdout/stderr to output_dir/<name>.{out,err}.
    """
    log_out = output_dir / f"{name}.out"
    log_err = output_dir / f"{name}.err"

    if use_blender:
        if not blender_bin:
            return {
                "ok": False,
                "exit_code": None,
                "error": "Blender binary not found; pass --blender or run inside Blender",
            }
        cmd = [
            blender_bin,
            "--background",
            "--factory-startup",
            "--offline-mode",
            "--python-exit-code", "1",
            "--python", str(script),
        ]
    else:
        # Plain Python for mock-bpy unit suites
        cmd = [sys.executable, str(script)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SUBPROCESS_TIMEOUT,
        )
        log_out.write_text(result.stdout or "", encoding="utf-8")
        log_err.write_text(result.stderr or "", encoding="utf-8")

        ok = result.returncode == 0
        return {
            "ok": ok,
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired as exc:
        msg = f"Timed out after {SUBPROCESS_TIMEOUT}s"
        log_err.write_text(msg, encoding="utf-8")
        return {"ok": False, "exit_code": None, "error": msg}
    except Exception as exc:
        msg = f"Subprocess error: {exc}"
        log_err.write_text(msg, encoding="utf-8")
        return {"ok": False, "exit_code": None, "error": msg}


# ---------------------------------------------------------------------------
# Syntax check (in-process, safe – does not exec the files)
# ---------------------------------------------------------------------------

def _run_syntax_check() -> tuple[bool, str]:
    import py_compile
    errors: list[str] = []
    total = 0
    for dirpath, dirs, filenames in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("dist", "__pycache__")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            total += 1
            filepath = os.path.join(dirpath, filename)
            try:
                py_compile.compile(filepath, doraise=True)
            except py_compile.PyCompileError as e:
                rel = os.path.relpath(filepath, ROOT)
                errors.append(f"{rel}: {e}")
    if errors:
        return False, f"Syntax errors in {len(errors)}/{total} files: {errors}"
    return True, f"All {total} python files compile OK."


# ---------------------------------------------------------------------------
# Failure injection gate (verifies _failed / _runtime_failed logic)
# ---------------------------------------------------------------------------

def _run_failure_injection_gate() -> tuple[bool, str]:
    """
    Verify that _failed / _runtime_failed from run_regression.py strictly
    reject ERROR / CANCELLED / fatal payloads and correctly handle healthy
    base payloads that include benign diagnostic text.
    """
    # Load run_regression via importlib (avoids relative import __main__ issue)
    rr_path = DEV_DIR / "run_regression.py"
    spec = importlib.util.spec_from_file_location("_m8_run_regression_gate", rr_path)
    if spec is None or spec.loader is None:
        return False, f"Cannot load {rr_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    _failed = mod._failed
    _runtime_failed = mod._runtime_failed

    # ------------------------------------------------------------------
    # BAD payloads: every one must be rejected
    # ------------------------------------------------------------------
    bad_payloads = [
        {"fatal": "Simulated crash"},
        {"registered": False, "unregistered": True},
        {"registered": True, "unregistered": False},
        {"registered": True, "unregistered": True, "registration_errors": ["SomeClass"]},
        {"registered": True, "unregistered": True, "missing_operators": ["op.foo"]},
        {"registered": True, "unregistered": True, "missing_types": ["PanelFoo"]},
        {"registered": True, "unregistered": True,
         "health_check_result": "ERROR: Health check failed"},
        {"registered": True, "unregistered": True,
         "scene_audit_result": "ERROR: Scene audit failed"},
        {"registered": True, "unregistered": True, "custom_check": "CANCELLED"},
        {"registered": True, "unregistered": True, "list_check": ["CANCELLED"]},
        {"registered": True, "unregistered": True, "error_list": ["ERROR: Something broke"]},
        {"ok": False},
        {"registered": True, "unregistered": True, "ok": False},
    ]

    for p in bad_payloads:
        if not (_failed("runtime", p) or _runtime_failed(p)):
            return False, f"Gate FAILED to reject bad payload: {p}"

    # ------------------------------------------------------------------
    # HEALTHY payloads: must NOT be rejected
    # Benign WARNING/info messages in diagnostic strings should be allowed.
    # ------------------------------------------------------------------
    healthy_payloads = [
        {"registered": True, "unregistered": True, "ok": True},
        {"registered": True, "unregistered": True,
         "health_check_result": "WARNING: GPU headless mode (expected in --background)"},
        {"registered": True, "unregistered": True,
         "health_check_result": "All checks passed."},
    ]

    for p in healthy_payloads:
        if _runtime_failed(p):
            return False, f"Gate INCORRECTLY rejected healthy payload: {p}"

    # ------------------------------------------------------------------
    # Failure injection: actual invalid syntax in a TEMP source tree
    # (never edits the real repo)
    # ------------------------------------------------------------------
    try:
        with tempfile.TemporaryDirectory(prefix="m8_syntax_inject_") as tmpdir:
            bad_py = Path(tmpdir) / "bad_syntax.py"
            bad_py.write_text("def foo(\n    # unclosed parenthesis\n", encoding="utf-8")
            import py_compile
            try:
                py_compile.compile(str(bad_py), doraise=True)
                return False, "py_compile should have raised for intentionally bad syntax"
            except py_compile.PyCompileError:
                pass  # expected
    except Exception as e:
        return False, f"Syntax injection test failed: {e}"

    return True, "All failure injection gate checks passed."


# ---------------------------------------------------------------------------
# Main validation pipeline
# ---------------------------------------------------------------------------

def run_all_validations(blender_bin: str | None, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "status": "PASS",
        "blender_binary": blender_bin,
        "output_dir": str(output_dir),
        "syntax": None,
        "failure_injection_gate": None,
        "suites": {},
        "failed_suites": [],
    }

    print("=" * 70)
    print("M8 RELEASE VALIDATION PIPELINE")
    print(f"Blender: {blender_bin or '(not found)'}")
    print(f"Output:  {output_dir}")
    print("=" * 70)

    # ---------------------------------------------------------------
    # Step 1: Syntax check
    # ---------------------------------------------------------------
    print("\n[STEP 1] Syntax Verification...")
    try:
        syntax_ok, syntax_msg = _run_syntax_check()
    except Exception as e:
        syntax_ok, syntax_msg = False, f"Exception: {e}"
    report["syntax"] = {"ok": syntax_ok, "message": syntax_msg}
    status_str = "PASS" if syntax_ok else "FAIL"
    print(f"  Result: {status_str} – {syntax_msg}")
    if not syntax_ok:
        report["status"] = "FAIL"
        report["failed_suites"].append("syntax")

    # ---------------------------------------------------------------
    # Step 2: Failure injection gate
    # ---------------------------------------------------------------
    print("\n[STEP 2] Failure Injection Gate...")
    try:
        gate_ok, gate_msg = _run_failure_injection_gate()
    except Exception as e:
        gate_ok, gate_msg = False, f"Exception: {e}\n{traceback.format_exc()}"
    report["failure_injection_gate"] = {"ok": gate_ok, "message": gate_msg}
    status_str = "PASS" if gate_ok else "FAIL"
    print(f"  Result: {status_str} – {gate_msg}")
    if not gate_ok:
        report["status"] = "FAIL"
        report["failed_suites"].append("failure_injection_gate")

    # ---------------------------------------------------------------
    # Step 3: Mock-bpy unit suites (standalone Python)
    # ---------------------------------------------------------------
    print("\n[STEP 3] Unit Suites (standalone Python, mock bpy)...")
    for name, path in UNIT_SUITES:
        if not path.is_file():
            # Missing file → hard failure (not silent skip)
            print(f"  [FAIL] {name}: MISSING file {path.name}")
            report["suites"][name] = {"ok": False, "error": f"File not found: {path}"}
            report["status"] = "FAIL"
            report["failed_suites"].append(name)
            continue
        print(f"  Running {name}...")
        result = _run_subprocess(name, path, blender_bin, output_dir, use_blender=False)
        report["suites"][name] = result
        status_str = "PASS" if result["ok"] else "FAIL"
        print(f"  [{status_str}] {name} (exit={result.get('exit_code')})")
        if not result["ok"]:
            report["status"] = "FAIL"
            report["failed_suites"].append(name)

    # ---------------------------------------------------------------
    # Step 4: Blender integration suites
    # ---------------------------------------------------------------
    print("\n[STEP 4] Blender Integration Suites...")
    for name, path in BLENDER_SUITES:
        if not path.is_file():
            print(f"  [FAIL] {name}: MISSING file {path.name}")
            report["suites"][name] = {"ok": False, "error": f"File not found: {path}"}
            report["status"] = "FAIL"
            report["failed_suites"].append(name)
            continue
        print(f"  Running {name}...")
        result = _run_subprocess(name, path, blender_bin, output_dir, use_blender=True)
        report["suites"][name] = result
        status_str = "PASS" if result["ok"] else "FAIL"
        print(f"  [{status_str}] {name} (exit={result.get('exit_code')})")
        if not result["ok"]:
            report["status"] = "FAIL"
            report["failed_suites"].append(name)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    summary_path = output_dir / "validation_summary.json"
    # Don't include full stdout/stderr in JSON summary (saved separately per suite)
    summary = {k: (v if k not in ("suites",) else {
        sn: {sk: sv for sk, sv in sd.items() if sk not in ("stdout", "stderr")}
        for sn, sd in v.items()
    }) for k, v in report.items()}
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"M8 VALIDATION SUMMARY: {report['status']}")
    if report["failed_suites"]:
        print(f"FAILED SUITES: {report['failed_suites']}")
    print(f"Full logs: {output_dir}")
    print("=" * 70)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="M8 Release Validation Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--blender",
        default=None,
        help="Path to Blender binary. Auto-detected when running inside Blender.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for logs and JSON summary. Default: new temp directory.",
    )

    # When run via blender --python, sys.argv contains blender's own args before '--'.
    # argparse must only see the script's args.
    try:
        sep_idx = sys.argv.index("--")
        args_to_parse = sys.argv[sep_idx + 1:]
    except ValueError:
        args_to_parse = sys.argv[1:]

    args = parser.parse_args(args_to_parse)

    blender_bin: str | None = args.blender or _detect_blender_binary()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(tempfile.mkdtemp(prefix="m8_validation_"))

    result = run_all_validations(blender_bin, output_dir)
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
