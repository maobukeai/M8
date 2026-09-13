# -*- coding: utf-8 -*-
"""
Comprehensive automated self-test for M8 Unity FBX Export Preset and Save Pie Menu UI.
Tests:
1. Default scale and preset values (scale == 1.0, FBX_SCALE_ALL, unit_scale == True)
2. Reset preset operator execution
3. Export 1.0m cube and verify re-imported dimensions and scale are exactly (1.0, 1.0, 1.0)
4. Empty selection guard when use_selection is True
5. Save Pie menu alert=True elimination and toggle behavior
6. Bilingual i18n translation coverage for Unity FBX terms
"""

import bpy
import os
import sys
import tempfile

print("==================================================")
print("=== M8 UNITY FBX EXPORT & SAVE PIE SELF-TEST ===")
print("==================================================")

# 1. Enable M8 addon
addon_name = None
for candidate in ["bl_ext.user_default.M8", "M8"]:
    if candidate in bpy.context.preferences.addons:
        addon_name = candidate
        break
    try:
        bpy.ops.preferences.addon_enable(module=candidate)
        if candidate in bpy.context.preferences.addons:
            addon_name = candidate
            break
    except Exception:
        pass

if not addon_name:
    print("FAILED: Could not enable M8 addon")
    sys.exit(1)

prefs = bpy.context.preferences.addons[addon_name].preferences
print(f"Loaded addon preferences from: {addon_name}")

# TEST 1: Check Default Values
print("\n[TEST 1] Checking Default Parameters...")
rna_default = prefs.bl_rna.properties['unity_fbx_global_scale'].default
assert rna_default == 1.0, f"Expected RNA property default == 1.0, got {rna_default}"

# Test auto-heal migration if value was old 100.0
if prefs.unity_fbx_global_scale == 100.0:
    from bl_ext.user_default.M8.ops.file.save_pie_ops import _get_m8_addon_prefs
    prefs.has_migrated_unity_scale = False
    _get_m8_addon_prefs()

assert prefs.unity_fbx_global_scale == 1.0, f"Expected global_scale == 1.0, got {prefs.unity_fbx_global_scale}"
assert prefs.unity_fbx_apply_unit_scale is True, "Expected apply_unit_scale == True"
assert str(prefs.unity_fbx_apply_scale_options) == "FBX_SCALE_ALL", f"Expected FBX_SCALE_ALL, got {prefs.unity_fbx_apply_scale_options}"
assert prefs.fbx_export_unity_preset is True, "Expected fbx_export_unity_preset default == True"
print("  -> PASS: Default scale is 1.0 with FBX_SCALE_ALL and apply_unit_scale=True")

# TEST 2: Reset Preset Operator
print("\n[TEST 2] Testing Reset Preset Operator...")
prefs.unity_fbx_global_scale = 5.0
res = bpy.ops.m8.reset_unity_fbx_preset()
assert res == {'FINISHED'}, f"Reset operator returned {res}"
assert prefs.unity_fbx_global_scale == 1.0, f"After reset, expected global_scale == 1.0, got {prefs.unity_fbx_global_scale}"
print("  -> PASS: reset_unity_fbx_preset restores scale to 1.0")

# TEST 3: Toggle Preset Operator
print("\n[TEST 3] Testing Toggle Preset Operator...")
res = bpy.ops.m8.toggle_unity_fbx_preset()
assert res == {'FINISHED'}
assert prefs.fbx_export_unity_preset is False
res = bpy.ops.m8.toggle_unity_fbx_preset()
assert res == {'FINISHED'}
assert prefs.fbx_export_unity_preset is True
print("  -> PASS: toggle_unity_fbx_preset works cleanly")

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

tmpdir = tempfile.gettempdir()
fbx_test_path = os.path.join(tmpdir, "m8_selftest_cube.fbx")
if os.path.exists(fbx_test_path):
    try: os.remove(fbx_test_path)
    except Exception: pass

# Build props
from bl_ext.user_default.M8.ops.file.save_pie_ops import M8_OT_ExportFBX
settings = {
    "use_selection": bool(getattr(prefs, "unity_fbx_use_selection", True)),
    "global_scale": float(getattr(prefs, "unity_fbx_global_scale", 1.0) or 1.0),
    "apply_unit_scale": bool(getattr(prefs, "unity_fbx_apply_unit_scale", True)),
    "apply_scale_options": str(getattr(prefs, "unity_fbx_apply_scale_options", "FBX_SCALE_ALL")),
    "use_triangles": bool(getattr(prefs, "unity_fbx_use_triangles", True)),
    "use_tspace": bool(getattr(prefs, "unity_fbx_use_tspace", True)),
    "bake_anim": bool(getattr(prefs, "unity_fbx_bake_anim", False)),
    "use_blend_dir": True,
    "export_dir": "",
    "open_folder": False,
    "reveal_file": False,
}

props = {
    "use_selection": settings["use_selection"],
    "global_scale": settings["global_scale"],
    "apply_unit_scale": settings["apply_unit_scale"],
    "apply_scale_options": settings["apply_scale_options"],
    "use_space_transform": True,
    "bake_space_transform": False,
    "axis_forward": "-Z",
    "axis_up": "Y",
    "add_leaf_bones": False,
    "use_mesh_modifiers": True,
    "use_mesh_modifiers_render": True,
    "use_triangles": settings["use_triangles"],
    "use_tspace": settings["use_tspace"],
    "mesh_smooth_type": "OFF",
    "bake_anim": settings["bake_anim"],
    "filepath": fbx_test_path,
    "check_existing": False,
}

bpy.ops.export_scene.fbx(**props)
assert os.path.exists(fbx_test_path), "FBX file was not generated"

# Re-import to check dimensions and scale
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_scene.fbx(filepath=fbx_test_path)
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
save_pie_py = os.path.join(os.path.dirname(__file__), "..", "ui", "pie", "save.py")
with open(save_pie_py, "r", encoding="utf-8") as f:
    save_code = f.read()

assert "sub.alert = True" not in save_code, "Found forbidden 'sub.alert = True' in ui/pie/save.py"
assert "CHECKBOX_HL" in save_code, "Expected CHECKBOX_HL in ui/pie/save.py"
assert "CHECKBOX_DEHL" in save_code, "Expected CHECKBOX_DEHL in ui/pie/save.py"
print("  -> PASS: ui/pie/save.py has 0 alert=True and uses clean checkbox icons")

# TEST 7: i18n Translation Coverage
print("\n[TEST 7] Testing i18n Coverage for Unity FBX...")
from bl_ext.user_default.M8.utils.i18n import _T, ZH_TO_EN

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

# Clean up temp file
try:
    if os.path.exists(fbx_test_path):
        os.remove(fbx_test_path)
except Exception:
    pass

print("\n==================================================")
print("=== ALL 7 TESTS PASSED SUCCESSFULLY (100%) ===")
print("==================================================")
