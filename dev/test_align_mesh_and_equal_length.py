import sys
import os
import bpy
import bmesh
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import M8
from M8.utils.addon import check_addon_installed, check_addon_enabled, find_addon_module_identifier
from M8.ops.mesh.equal_edge_length import EqualEdgeLength
from M8.property.keymap_constants import ALIGN_PIE_KEYMAP_BINDINGS


def test_keymap_constants():
    print("\n--- Test 1: Keymap space_type for Mesh and Object Mode ---")
    mesh_binding = next(b for b in ALIGN_PIE_KEYMAP_BINDINGS if b[0] == "Mesh")
    obj_binding = next(b for b in ALIGN_PIE_KEYMAP_BINDINGS if b[0] == "Object Mode")
    assert mesh_binding[1] == "EMPTY", f"Expected Mesh space_type EMPTY, got {mesh_binding[1]}"
    assert obj_binding[1] == "EMPTY", f"Expected Object Mode space_type EMPTY, got {obj_binding[1]}"
    print("[PASS] Test 1: Keymap space_type is EMPTY for Mesh and Object Mode.")


def test_addon_detection():
    print("\n--- Test 2: EdgeFlow detection in utils/addon ---")
    # Even if EdgeFlow isn't installed in factory startup, check case normalization
    installed = check_addon_installed("EdgeFlow")
    enabled = check_addon_enabled("EdgeFlow")
    print(f"check_addon_installed('EdgeFlow'): {installed}")
    print(f"check_addon_enabled('EdgeFlow'): {enabled}")
    print("[PASS] Test 2: Addon detection functions ran safely without errors.")


def test_equal_edge_length_operator():
    print("\n--- Test 3: EqualEdgeLength Operator Execution ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=2.0)
    bpy.ops.object.mode_set(mode='EDIT')
    obj = bpy.context.active_object
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()

    # Deselect all, select 2 parallel edges of different lengths
    for e in bm.edges:
        e.select = False

    e1 = bm.edges[0]
    e2 = bm.edges[2]
    e1.select = True
    e2.select = True
    # Make e2 longer by moving one vertex
    e2.verts[1].co.x += 1.0
    bmesh.update_edit_mesh(obj.data)

    initial_len1 = e1.calc_length()
    initial_len2 = e2.calc_length()
    print(f"Initial lengths: e1={initial_len1:.4f}, e2={initial_len2:.4f}")
    assert abs(initial_len1 - initial_len2) > 0.01

    # Execute operator
    res = bpy.ops.m8.equal_edge_length(mode='AVERAGE')
    assert res == {'FINISHED'}

    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    e1 = bm.edges[0]
    e2 = bm.edges[2]
    final_len1 = e1.calc_length()
    final_len2 = e2.calc_length()
    print(f"Equalized lengths: e1={final_len1:.4f}, e2={final_len2:.4f}")
    assert abs(final_len1 - final_len2) < 1e-4, f"Lengths not equal: {final_len1} vs {final_len2}"
    print("[PASS] Test 3: EqualEdgeLength operator successfully equalized edge lengths.")


def test_pie_menu_draw():
    print("\n--- Test 4: AlignMeshPie menu draw layout ---")
    menu_cls = getattr(bpy.types, "M8_MT_ALIGN_MESH", None)
    assert menu_cls is not None, "M8_MT_ALIGN_MESH menu class not found!"
    print("[PASS] Test 4: M8_MT_ALIGN_MESH is registered.")


if __name__ == "__main__":
    M8.register()
    try:
        test_keymap_constants()
        test_addon_detection()
        test_equal_edge_length_operator()
        test_pie_menu_draw()
        print("\n============================================================")
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("============================================================")
    finally:
        M8.unregister()
