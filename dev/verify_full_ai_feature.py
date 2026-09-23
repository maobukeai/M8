import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run_step(title, cmd):
    print(f"\n[{title}] Running: {cmd}...")
    res = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(f"FAILED: {title}")
        print("STDOUT:\n", res.stdout)
        print("STDERR:\n", res.stderr)
        return False
    print(f"PASS: {title}")
    return True

def main():
    print("=" * 70)
    print("M8 AI ASSISTANT FULL FEATURE RIGOROUS VERIFICATION SUITE")
    print("=" * 70)

    steps = [
        ("Step 1: Python Syntax & Compilation (All 230 files)", "python _syntax_check.py"),
        ("Step 2: GitHub Update & Anti-Duplicate SOP Validation", "python dev/selftest_github_update.py"),
        ("Step 3: AI Assistant Unit & Parsing Tests", "python dev/test_ai_assistant.py"),
    ]

    all_passed = True
    for title, cmd in steps:
        if not run_step(title, cmd):
            all_passed = False
            break

    if all_passed:
        print("\n" + "=" * 70)
        print("ALL VERIFICATION SUITES PASSED WITH 0 ERRORS!")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("VERIFICATION SUITE DETECTED FAILURES!")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    main()
