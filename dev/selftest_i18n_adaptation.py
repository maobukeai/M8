# -*- coding: utf-8 -*-
"""Comprehensive selftest for M8 i18n environment adaptation and coverage."""

import os
import sys
import ast
import json
import re
from unittest.mock import MagicMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Setup initial dummy bpy before importing utils
dummy_bpy = MagicMock()
dummy_bpy.context.preferences.view.language = "zh_CN"
dummy_bpy.app.translations.locale = "zh_CN"
dummy_addon_pref = MagicMock()
dummy_addon_pref.addon_language = "AUTO"
dummy_bpy.context.preferences.addons.get.return_value.preferences = dummy_addon_pref
dummy_bpy.context.preferences.addons.__getitem__.return_value.preferences = dummy_addon_pref

sys.modules['bpy'] = dummy_bpy
sys.modules['mathutils'] = MagicMock()

from utils.i18n import get_blender_locale, get_addon_language, _T, ZH_TO_EN
import utils.i18n as i18n_mod


def test_i18n_adaptation():
    print("--------------------------------------------------")
    print("[TEST 1] Testing Environment Adaptation Logic...")

    # Case A: AUTO mode with Chinese Blender (zh_CN)
    dummy_bpy.context.preferences.view.language = "zh_CN"
    dummy_bpy.app.translations.locale = "zh_CN"
    dummy_addon_pref.addon_language = "AUTO"
    assert get_addon_language() == "ZH", f"Expected ZH, got {get_addon_language()}"
    assert _T("保存历史快照") == "保存历史快照"
    print("  -> PASS: AUTO mode with Chinese Blender (zh_CN) -> ZH")

    # Case B: AUTO mode with Simplified Chinese variant (zh_HANS)
    dummy_bpy.context.preferences.view.language = "zh_HANS"
    dummy_bpy.app.translations.locale = "zh_HANS"
    dummy_addon_pref.addon_language = "AUTO"
    assert get_addon_language() == "ZH", f"Expected ZH, got {get_addon_language()}"
    print("  -> PASS: AUTO mode with Chinese Blender (zh_HANS) -> ZH")

    # Case C: AUTO mode with English Blender (en_US)
    dummy_bpy.context.preferences.view.language = "en_US"
    dummy_bpy.app.translations.locale = "en_US"
    dummy_addon_pref.addon_language = "AUTO"
    assert get_addon_language() == "EN", f"Expected EN, got {get_addon_language()}"
    assert _T("保存历史快照") == "Save Snapshot"
    assert _T("快速循环切刀 (Ctrl+Shift+E)") == "Fast Loop Cut (Ctrl+Shift+E)"
    print("  -> PASS: AUTO mode with English Blender (en_US) -> EN")

    # Case D: AUTO mode with DEFAULT locale (non-Chinese fallback)
    dummy_bpy.context.preferences.view.language = "DEFAULT"
    dummy_bpy.app.translations.locale = "en_US"
    dummy_addon_pref.addon_language = "AUTO"
    assert get_addon_language() == "EN", f"Expected EN, got {get_addon_language()}"
    print("  -> PASS: AUTO mode with DEFAULT locale -> EN")

    # Case E: Forced ZH mode even when Blender is English
    dummy_bpy.context.preferences.view.language = "en_US"
    dummy_bpy.app.translations.locale = "en_US"
    dummy_addon_pref.addon_language = "ZH"
    assert get_addon_language() == "ZH", f"Expected ZH, got {get_addon_language()}"
    assert _T("保存历史快照") == "保存历史快照"
    print("  -> PASS: Forced ZH mode in English Blender -> ZH")

    # Case F: Forced EN mode even when Blender is Chinese
    dummy_bpy.context.preferences.view.language = "zh_CN"
    dummy_bpy.app.translations.locale = "zh_CN"
    dummy_addon_pref.addon_language = "EN"
    assert get_addon_language() == "EN", f"Expected EN, got {get_addon_language()}"
    assert _T("保存历史快照") == "Save Snapshot"
    assert _T("EdgeFlow 参数 (Shift+左键 / EdgeFlow 开启时生效)") == "EdgeFlow Parameters (Shift+LMB / Active when EdgeFlow is enabled)"
    print("  -> PASS: Forced EN mode in Chinese Blender -> EN")


def test_ui_ast_coverage():
    print("--------------------------------------------------")
    print("[TEST 2] Testing AST UI Strings Coverage in ZH_TO_EN...")

    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    ignore_dirs = {'.git', '__pycache__', 'dist', 'tests', 'dev', 'release', '.mission', 'scratch'}
    ignore_files = {'_syntax_check.py', 'i18n.py', 'export_missing.py', 'apply_i18n.py', 'generate_161.py'}

    extracted = {}

    class UIStringVisitor(ast.NodeVisitor):
        def __init__(self, filename):
            self.filename = filename

        def visit_Call(self, node):
            for kw in node.keywords:
                if kw.arg in ('name', 'text', 'description', 'title', 'message') and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    s = kw.value.value.strip()
                    if chinese_pattern.search(s):
                        extracted.setdefault(s, []).append(f'{self.filename}:{kw.value.lineno}')
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'report':
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    s = node.args[1].value.strip()
                    if chinese_pattern.search(s):
                        extracted.setdefault(s, []).append(f'{self.filename}:{node.args[1].lineno}')
            if (isinstance(node.func, ast.Name) and node.func.id == '_T') or (isinstance(node.func, ast.Attribute) and node.func.attr == '_T'):
                if len(node.args) >= 1 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    s = node.args[0].value.strip()
                    if chinese_pattern.search(s):
                        extracted.setdefault(s, []).append(f'{self.filename}:{node.args[0].lineno}')
            self.generic_visit(node)

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('bl_label', 'bl_description', 'bl_context'):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        s = node.value.value.strip()
                        if chinese_pattern.search(s):
                            extracted.setdefault(s, []).append(f'{self.filename}:{node.value.lineno}')
            self.generic_visit(node)

        def visit_Tuple(self, node):
            if len(node.elts) in (2, 3):
                if all(isinstance(elt, ast.Constant) and isinstance(elt.value, str) for elt in node.elts):
                    if len(node.elts) >= 2 and chinese_pattern.search(node.elts[1].value):
                        extracted.setdefault(node.elts[1].value.strip(), []).append(f'{self.filename}:{node.elts[1].lineno}')
                    if len(node.elts) == 3 and chinese_pattern.search(node.elts[2].value):
                        extracted.setdefault(node.elts[2].value.strip(), []).append(f'{self.filename}:{node.elts[2].lineno}')
            self.generic_visit(node)

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for file in files:
            if file.endswith('.py') and file not in ignore_files:
                filepath = os.path.join(root, file).replace('\\', '/')
                try:
                    with open(filepath, 'r', encoding='utf-8') as pf:
                        tree = ast.parse(pf.read(), filename=filepath)
                    visitor = UIStringVisitor(filepath)
                    visitor.visit(tree)
                except Exception:
                    pass

    missing = {k: v for k, v in extracted.items() if k not in ZH_TO_EN}
    print(f"  -> Total UI strings analyzed: {len(extracted)}")
    print(f"  -> Missing in ZH_TO_EN: {len(missing)}")
    if missing:
        for k, locs in list(missing.items())[:10]:
            print(f"     UNTRANSLATED: {k} (at {locs[0]})")
    assert len(missing) == 0, f"Found {len(missing)} untranslated UI strings!"
    print("  -> PASS: 100% of UI Chinese strings are mapped in ZH_TO_EN!")


if __name__ == "__main__":
    try:
        test_i18n_adaptation()
        test_ui_ast_coverage()
        print("==================================================")
        print("All i18n Adaptation & Coverage Selftests Passed!")
        print("==================================================")
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
