import sys
import os
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import M8

def run_tests():
    print("\n--- [Test 1] Addon Registration ---")
    M8.register()
    print("[PASS] M8 registered successfully.")

    print("\n--- [Test 2] Property Existence ---")
    scene = bpy.context.scene
    assert hasattr(scene, "m8"), "scene.m8 property group missing"
    assert hasattr(scene.m8, "uv_checker_scale"), "uv_checker_scale property missing"
    assert hasattr(scene.m8, "uv_checker_type"), "uv_checker_type property missing"
    print(f"[PASS] Properties exist. Default scale: {scene.m8.uv_checker_scale}, Default type: {scene.m8.uv_checker_type}")

    print("\n--- [Test 3] Toggle UV Checker ON ---")
    res = bpy.ops.m8.toggle_uv_checker()
    assert res == {'FINISHED'}, f"toggle_uv_checker failed: {res}"
    
    view_layer = bpy.context.view_layer
    assert view_layer.material_override is not None, "Material override was not set"
    assert view_layer.material_override.name == "M8_UV_Checker", f"Expected M8_UV_Checker, got {view_layer.material_override.name}"
    mat = view_layer.material_override
    mapping = mat.node_tree.nodes.get("M8_Mapping")
    assert mapping is not None, "M8_Mapping node missing in material node tree"
    assert abs(mapping.inputs['Scale'].default_value[0] - 2.0) < 0.001, "Mapping scale not matching default"
    print("[PASS] UV Checker turned ON successfully, material override and nodes verified.")

    print("\n--- [Test 4] Live Update Scale ---")
    scene.m8.uv_checker_scale = 5.5
    assert abs(mapping.inputs['Scale'].default_value[0] - 5.5) < 0.001, f"Mapping scale did not update: {mapping.inputs['Scale'].default_value[0]}"
    print(f"[PASS] Scale dynamically updated to {mapping.inputs['Scale'].default_value[0]}")

    print("\n--- [Test 5] Live Update Grid Type to COLOR_GRID & CHECKER ---")
    scene.m8.uv_checker_type = 'COLOR_GRID'
    mat = bpy.data.materials["M8_UV_Checker"]
    assert mat.get("m8_grid_type") == 'COLOR_GRID', "Grid type not set to COLOR_GRID"
    
    scene.m8.uv_checker_type = 'CHECKER'
    assert mat.get("m8_grid_type") == 'CHECKER', "Grid type not set to CHECKER"
    checker_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_CHECKER']
    assert len(checker_nodes) > 0, "ShaderNodeTexChecker missing when type is CHECKER"
    assert abs(checker_nodes[0].inputs['Scale'].default_value - 16.0) < 0.001, f"Expected scale 16.0, got {checker_nodes[0].inputs['Scale'].default_value}"
    print("[PASS] Grid types switched, scale is 16.0, and nodes reconstructed correctly.")

    print("\n--- [Test 6] Toggle UV Checker OFF ---")
    res = bpy.ops.m8.toggle_uv_checker()
    assert res == {'FINISHED'}, f"toggle_uv_checker off failed: {res}"
    assert view_layer.material_override is None, "Material override was not cleared"
    print("[PASS] UV Checker turned OFF successfully, material override cleared.")

    print("\n--- [Test 7] Addon Unregister ---")
    M8.unregister()
    print("[PASS] M8 unregistered cleanly.")

    print("\n=== ALL UV CHECKER TESTS PASSED ===")

if __name__ == "__main__":
    run_tests()
