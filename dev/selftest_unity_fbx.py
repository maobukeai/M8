# -*- coding: utf-8 -*-
"""
Comprehensive automated self-test for M8 Unity FBX Export Preset and Save Pie Menu UI.
Tests:
1. Default scale and preset values (scale == 1.0, FBX_SCALE_ALL, unit_scale == True)
2. Reset preset operator execution
3. Custom user scale retention & versioned migration healing
4. Export 1.0m cube and verify re-imported dimensions and scale are exactly (1.0, 1.0, 1.0)
5. Empty selection guard when use_selection is True
6. Save Pie menu alert=True elimination and toggle behavior
7. Bilingual i18n translation coverage for Unity FBX terms
8. Clean disable without saving user preferences
"""

import bpy
import os
import sys
import tempfile
import pathlib
import importlib
import addon_utils

print("==================================================")
print("=== M8 UNITY FBX EXPORT & SAVE PIE SELF-TEST ===")
print("==================================================")

root = pathlib.Path(__file__).resolve().parents[1]
parent_str = str(root.parent)
if parent_str not in sys.path:
    sys.path.insert(0, parent_str)

# 1. Enable M8 addon with default_set=True so bpy.context.preferences.addons is populated
#    in clean factory Blender. default_set=True only mutates this process's in-memory
#    config and does NOT write user preferences unless save_userpref() is called.
addon_name = "M8"
# If already enabled, pick the right name
for candidate in ["M8", "bl_ext.user_default.M8"]:
    if candidate in bpy.context.preferences.addons:
        addon_name = candidate
        break
else:
    # Not yet enabled – enable with default_set=True
    enabled = False
    for candidate in ["M8", "bl_ext.user_default.M8"]:
        try:
            addon_utils.enable(candidate, default_set=True)
            if candidate in bpy.context.preferences.addons:
                addon_name = candidate
                enabled = True
                break
        except Exception as e:
            print(f"  Could not enable {candidate}: {e}")
    if not enabled:
        print("FAILED: Could not enable M8 addon")
        sys.exit(1)

if addon_name not in bpy.context.preferences.addons:
    print(f"FAILED: {addon_name} not in preferences.addons after enable")
    sys.exit(1)

prefs = bpy.context.preferences.addons[addon_name].preferences
if prefs is None:
    print("FAILED: preferences object is None")
    sys.exit(1)
print(f"Loaded addon preferences from: {addon_name}")

# Import portable helper references using the local module name
save_pie_mod = importlib.import_module(f"{addon_name}.ops.file.save_pie_ops")
i18n_mod = importlib.import_module(f"{addon_name}.utils.i18n")
M8_OT_ExportFBX = save_pie_mod.M8_OT_ExportFBX
_get_m8_addon_prefs = save_pie_mod._get_m8_addon_prefs
_T = i18n_mod._T
ZH_TO_EN = i18n_mod.ZH_TO_EN

# TEST 1: Check Default Values (BEFORE any reset/autoheal)
print("\n[TEST 1] Checking Default Parameters...")
rna_default = prefs.bl_rna.properties['unity_fbx_global_scale'].default
assert abs(rna_default - 1.0) < 0.001, f"Expected RNA property default == 1.0, got {rna_default}"
assert abs(prefs.unity_fbx_global_scale - 1.0) < 0.001, f"Expected global_scale on enable == 1.0, got {prefs.unity_fbx_global_scale}"
assert prefs.unity_fbx_apply_unit_scale is True, "Expected apply_unit_scale == True"
assert str(prefs.unity_fbx_apply_scale_options) == "FBX_SCALE_ALL", f"Expected FBX_SCALE_ALL, got {prefs.unity_fbx_apply_scale_options}"
assert prefs.fbx_export_unity_preset is True, "Expected fbx_export_unity_preset default == True"
print("  -> PASS: Default scale is 1.0 with FBX_SCALE_ALL and apply_unit_scale=True")

# TEST 2: Reset Preset Operator
print("\n[TEST 2] Testing Reset Preset Operator...")
prefs.unity_fbx_global_scale = 5.0
res = bpy.ops.m8.reset_unity_fbx_preset()
assert res == {'FINISHED'}, f"Reset operator returned {res}"
assert abs(prefs.unity_fbx_global_scale - 1.0) < 0.001, f"After reset, expected global_scale == 1.0, got {prefs.unity_fbx_global_scale}"
print("  -> PASS: reset_unity_fbx_preset restores scale to 1.0")

# TEST 3: Toggle Preset Operator & Custom Value Retention
print("\n[TEST 3] Testing Toggle Preset Operator & Custom Value Retention...")
res = bpy.ops.m8.toggle_unity_fbx_preset()
assert res == {'FINISHED'}
assert prefs.fbx_export_unity_preset is False
res = bpy.ops.m8.toggle_unity_fbx_preset()
assert res == {'FINISHED'}
assert prefs.fbx_export_unity_preset is True

# Test custom user scale preservation (custom value should not be clobbered)
prefs.unity_fbx_global_scale = 2.5
_get_m8_addon_prefs()
assert abs(prefs.unity_fbx_global_scale - 2.5) < 0.001, f"Custom user scale 2.5 must be preserved, got {prefs.unity_fbx_global_scale}"
# Reset back to standard 1.0
bpy.ops.m8.reset_unity_fbx_preset()
print("  -> PASS: toggle_unity_fbx_preset and custom scale retention verified")

# TEST 4: Export 1.0m Cube & Verify 1:1 Scale
print("\n[TEST 4] Testing FBX Export Geometry & Scale Alignment...")
# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create 1m cube
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "TestCube1m"
cube.select_set(True)

# Use tempfile.mkdtemp so each test run gets a fresh dedicated directory
tmpdir = tempfile.mkdtemp(prefix="m8_selftest_")
fbx_test_path = os.path.join(tmpdir, "m8_selftest_cube.fbx")

settings = M8_OT_ExportFBX._get_unity_settings(None, prefs)
props = M8_OT_ExportFBX._build_unity_export_props(None, settings, filepath=fbx_test_path)

bpy.ops.export_scene.fbx(**props)
assert os.path.exists(fbx_test_path), "FBX file was not generated"

# Re-import: inspect bpy.data.objects by name/set difference (context.object may be None)
objs_before = set(o.name for o in bpy.data.objects)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_scene.fbx(filepath=fbx_test_path)
objs_after = set(o.name for o in bpy.data.objects)
new_obj_names = objs_after - objs_before

imported_objs = [bpy.data.objects[n] for n in new_obj_names if bpy.data.objects[n].type == 'MESH']
if not imported_objs:
    # fallback: use selected_objects
    imported_objs = [o for o in bpy.context.selected_objects if o.type == 'MESH']
assert len(imported_objs) > 0, "No mesh object imported"
imp = imported_objs[0]

print(f"  Imported Object Name: {imp.name}")
print(f"  Dimensions: {imp.dimensions}")
print(f"  Scale: {imp.scale}")

for axis_idx, axis_name in enumerate(['X', 'Y', 'Z']):
    dim = imp.dimensions[axis_idx]
    scl = imp.scale[axis_idx]
    assert abs(dim - 1.0) < 0.001, f"Expected dimension {axis_name} == 1.0, got {dim}"
    assert abs(scl - 1.0) < 0.001, f"Expected scale {axis_name} == 1.0, got {scl}"

print("  -> PASS: 1.0m cube exported & re-imported with exact 1.0 dimensions and 1.0 scale!")

# TEST 5: Empty Selection Guard
print("\n[TEST 5] Testing Empty Selection Guard...")
bpy.ops.object.select_all(action='DESELECT')
assert len(bpy.context.selected_objects) == 0

# Call export operator with use_selection=True
export_res = bpy.ops.m8.export_fbx()
assert export_res == {'CANCELLED'}, f"Expected CANCELLED when 0 objects selected, got {export_res}"
print("  -> PASS: Export correctly cancelled when nothing selected (protected from empty file overwrite)")

# TEST 6: Save Pie Menu UI Code Audit
print("\n[TEST 6] Auditing Save Pie UI code...")
save_pie_py = root / "ui" / "pie" / "save.py"
with open(str(save_pie_py), "r", encoding="utf-8") as f:
    save_code = f.read()

assert "sub.alert = True" not in save_code, "Found forbidden 'sub.alert = True' in ui/pie/save.py"
assert "CHECKBOX_HL" in save_code, "Expected CHECKBOX_HL in ui/pie/save.py"
assert "CHECKBOX_DEHL" in save_code, "Expected CHECKBOX_DEHL in ui/pie/save.py"
print("  -> PASS: ui/pie/save.py has 0 alert=True and uses clean checkbox icons")

# TEST 7: i18n Translation Coverage
print("\n[TEST 7] Testing i18n Coverage for Unity FBX...")
required_keys = [
    "Unity 预设 (开启)",
    "Unity 预设 (关闭)",
    "未选择任何物体，无法导出（已启用仅导出选中项）",
    "FBX 导出使用 Unity 预设",
    "重置为 Unity 推荐设置",
    "重置 Unity FBX 预设",
    "已重置 Unity FBX 为标准设置",
    "全局缩放",
    "应用单位",
    "应用缩放方式",
    "三角化",
    "导出切线",
    "导出动画",
]

for k in required_keys:
    assert k in ZH_TO_EN, f"Missing i18n translation key: {k}"
    en_val = ZH_TO_EN[k]
    assert en_val and en_val != k, f"Invalid English translation for {k}: {en_val}"

print(f"  -> PASS: All {len(required_keys)} Unity FBX keys present in i18n dictionary with valid English translations")

try:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
except Exception:
    pass

addon_utils.disable(addon_name, default_set=True)
print("Disabled M8 cleanly without modifying user preferences file.")

print("\n==================================================")
print("=== ALL 7 TESTS PASSED SUCCESSFULLY (100%) ===")
print("==================================================")
