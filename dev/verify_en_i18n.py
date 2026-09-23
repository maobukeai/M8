import bpy
import sys
import os
import re

print("=== VERIFYING ENGLISH I18N IN BLENDER 5.2 ===")

# Find addon preferences
addon_prefs = None
for name in ["bl_ext.user_default.M8", "M8"]:
    addon = bpy.context.preferences.addons.get(name)
    if addon and getattr(addon, "preferences", None):
        addon_prefs = addon.preferences
        print(f"Found loaded addon: {name}")
        break

if not addon_prefs:
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        bpy.ops.preferences.addon_enable(module="M8")
        addon = bpy.context.preferences.addons.get("M8")
        if addon and getattr(addon, "preferences", None):
            addon_prefs = addon.preferences
            print("Enabled M8 addon successfully")
    except Exception as e:
        print(f"Failed to enable M8: {e}")

if not addon_prefs:
    print("ERROR: Addon preferences not found in bpy.context.preferences.addons!")
    sys.exit(1)

# Import i18n from the loaded extension module
try:
    from bl_ext.user_default.M8.utils.i18n import _T, get_addon_language, ZH_TO_EN
except ImportError:
    from M8.utils.i18n import _T, get_addon_language, ZH_TO_EN

# Test 1: Set addon_language to EN
addon_prefs.addon_language = "EN"
detected_lang = get_addon_language()
print(f"[TEST 1] Addon language set to 'EN'. Effective get_addon_language() = '{detected_lang}'")
assert detected_lang == "EN", f"Expected 'EN', got '{detected_lang}'"

# Test 2: Check _T dynamic translations in EN mode
fast_loop_keys = [
    "启用快速循环切刀",
    "默认启动属性 (Default Launch Settings)",
    "启动时自动进入选区模式",
    "默认段数 (Cuts)",
    "吸附等分数",
    "默认顶点模式",
    "默认引导模式",
    "默认等距模式",
    "默认反转方向",
    "默认对称镜像",
    "默认法向投影",
    "默认曲率平滑",
    "默认启用 EdgeFlow",
    "EdgeFlow 后重投影 UV",
    "EdgeFlow 参数 (Shift+左键 / EdgeFlow 开启时生效)",
    "张力",
    "迭代次数",
    "最小角度",
    "持久行为设置 (Persistent Behavior)",
    "选中边参与 Set Flow (S键)",
    "快捷键",
    "恢复默认",
    "显示快捷键详情(Fast Loop)",
    "启用细分快捷键 (Ctrl+0..4)",
    "启用对齐饼菜单 (Alt+A)",
    "启用着色饼菜单 (Z)",
    "启动时自动检测新版本",
]

chinese_char = re.compile(r'[\u4e00-\u9fff]')

failed = []
print("\n[TEST 2] Dynamic _T() evaluation in EN mode:")
for k in fast_loop_keys:
    val = _T(k)
    if chinese_char.search(val):
        failed.append((k, val))
        print(f"  FAIL: '{k}' -> '{val}' (contains Chinese)")
    else:
        print(f"  PASS: '{k}' -> '{val}'")

if failed:
    print(f"\n[FAIL] {len(failed)} keys failed English translation check!")
    sys.exit(1)
else:
    print("\n[PASS] All 27 keys evaluated dynamically to 100% pure English!")

# Test 3: Test drawing preferences UI tabs in EN mode
print("\n[TEST 3] Testing preferences draw methods in EN mode...")

class MockLayout:
    def __init__(self):
        self.rendered_texts = []
    def column(self, align=False): return self
    def row(self, align=False): return self
    def box(self): return self
    def grid_flow(self, **kwargs): return self
    def split(self, **kwargs): return self
    def label(self, text="", icon="NONE", **kwargs):
        if text: self.rendered_texts.append(("label", text))
    def prop(self, data, prop_name, text=None, **kwargs):
        if text: self.rendered_texts.append(("prop", prop_name, text))
    def operator(self, op_name, text="", **kwargs):
        if text: self.rendered_texts.append(("operator", op_name, text))
        import types
        return types.SimpleNamespace()
    def separator(self, factor=1.0): pass
    def menu(self, *args, **kwargs): pass

mock = MockLayout()
addon_prefs.draw_fast_loop_settings(mock)
addon_prefs.draw_subdivision_settings(mock)
addon_prefs.draw_align_settings(mock)
addon_prefs.draw_shading_settings(mock)
addon_prefs.draw_switch_editor_settings(mock)

# Inspect all rendered texts for Chinese characters
chinese_in_ui = []
for item in mock.rendered_texts:
    text = item[-1]
    if chinese_char.search(text):
        chinese_in_ui.append(item)

if chinese_in_ui:
    print(f"[FAIL] Found Chinese text in EN UI:")
    for item in chinese_in_ui:
        print(f"  {item}")
    sys.exit(1)
else:
    print(f"[PASS] All {len(mock.rendered_texts)} UI elements in Fast Loop, Subdivision, Align, Shading, and Switch Editor drawn with ZERO Chinese characters!")

# Test 4: Switch to ZH and verify it switches back cleanly
print("\n[TEST 4] Testing switch back to ZH mode...")
addon_prefs.addon_language = "ZH"
assert get_addon_language() == "ZH"
zh_val = _T("启用快速循环切刀")
assert zh_val == "启用快速循环切刀", f"Expected Chinese, got '{zh_val}'"
print("  PASS: Successfully switched back to ZH and verified Chinese output!")

print("\n=== ALL ENGLISH ADAPTATION VERIFICATIONS 100% PASSED ===")
