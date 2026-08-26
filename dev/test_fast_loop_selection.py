import sys
import os
import types
import bpy
import bmesh
import mathutils

script_dir = os.path.dirname(os.path.abspath(__file__))
addon_dir = os.path.dirname(script_dir)
parent_dir = os.path.dirname(addon_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

def run_test():
    print("=" * 60)
    print("M8 FAST LOOP SELECTION MODE TEST SUITE")
    print("=" * 60)

    from M8.property.preferences import SIZE_TOOL_Preferences
    from M8.ops.misc.fast_loop import M8_OT_FastLoop, get_prefs

    print("[PASS] Successfully imported SIZE_TOOL_Preferences and M8_OT_FastLoop.")
    has_annotations = (
        'fast_loop_auto_selection_mode' in SIZE_TOOL_Preferences.__annotations__ and
        'fast_loop_default_dual_offset' in SIZE_TOOL_Preferences.__annotations__ and
        'fast_loop_default_offset_factor' in SIZE_TOOL_Preferences.__annotations__
    )
    print("SIZE_TOOL_Preferences has new properties in __annotations__:", has_annotations)
    assert has_annotations, "Expected properties in SIZE_TOOL_Preferences.__annotations__"

    # 1. Setup Test Geometry (Cylinder with 16 segments)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0)
    obj = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Subdivide cylinder once horizontally to create an edge loop in the middle
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if not e.is_boundary and e.calc_length() > 1.5], cuts=1)
    bmesh.update_edit_mesh(obj.data)

    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Select the middle loop (where z is near 0)
    for e in bm.edges:
        e.select = False
    
    mid_edges = [e for e in bm.edges if abs(e.verts[0].co.z) < 0.05 and abs(e.verts[1].co.z) < 0.05]
    print(f"Selected middle loop edges count: {len(mid_edges)}")
    for e in mid_edges:
        e.select = True
    bmesh.update_edit_mesh(obj.data)

    # 2. Test Topology Analysis (analyze_selection)
    op = types.SimpleNamespace()
    op.target_object = obj
    op.edit_objects = [obj]
    op.bm = bmesh.from_edit_mesh(obj.data)
    op.bms = {obj.name: op.bm}
    op.offset_factor = 0.2
    op.dual_offset = True
    op.use_curvature = False
    op.keep_selection = False
    op.snap_enabled = False
    op.snap_divisions = 8
    op.selection_face_cuts = []
    op.selection_transverse_map = {}
    op.dimension_draws = []
    op.preview_points = []
    op.preview_lines = []

    # Run analyze_selection
    M8_OT_FastLoop.analyze_selection(op, bpy.context)
    print(f"[PASS] analyze_selection executed:")
    print(f"  - selection_face_cuts count: {len(op.selection_face_cuts)}")
    print(f"  - selection_transverse_map size: {len(op.selection_transverse_map)}")
    assert len(op.selection_face_cuts) > 0, "Expected face cuts to be detected"
    assert len(op.selection_transverse_map) > 0, "Expected transverse edges to be mapped"

    # 3. Test Preview Calculation (update_selection_preview)
    M8_OT_FastLoop.update_selection_preview(op, bpy.context)
    print(f"[PASS] update_selection_preview executed:")
    print(f"  - preview_lines count: {len(op.preview_lines)}")
    print(f"  - preview_points count: {len(op.preview_points)}")
    print(f"  - dimension_draws count: {len(op.dimension_draws)}")
    assert len(op.preview_lines) > 0, "Expected preview lines to be generated"
    assert len(op.preview_points) > 0, "Expected preview points to be generated"

    # 4. Test Cut Execution (Dual Offset)
    initial_verts = len(op.bm.verts)
    initial_faces = len(op.bm.faces)
    initial_edges = len(op.bm.edges)
    print(f"Initial cylinder mesh: verts={initial_verts}, edges={initial_edges}, faces={initial_faces}")

    M8_OT_FastLoop.perform_selection_cut(op, bpy.context, shift=False)
    bmesh.update_edit_mesh(obj.data)

    bm_after = bmesh.from_edit_mesh(obj.data)
    new_verts = len(bm_after.verts)
    new_faces = len(bm_after.faces)
    new_edges = len(bm_after.edges)
    print(f"[PASS] perform_selection_cut (Dual Offset) executed successfully:")
    print(f"  - Mesh after cut: verts={new_verts}, edges={new_edges}, faces={new_faces}")
    assert new_verts > initial_verts, f"Verts should increase: {new_verts} > {initial_verts}"
    assert new_faces > initial_faces, f"Faces should increase: {new_faces} > {initial_faces}"

    # 5. Test Single Offset Cut on fresh cube
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm_c = bmesh.from_edit_mesh(cube.data)
    bm_c.edges.ensure_lookup_table()
    
    # Subdivide cube once
    bmesh.ops.subdivide_edges(bm_c, edges=bm_c.edges[:], cuts=1)
    bmesh.update_edit_mesh(cube.data)
    
    bm_c = bmesh.from_edit_mesh(cube.data)
    bm_c.edges.ensure_lookup_table()
    for e in bm_c.edges:
        e.select = False
    # Select loop around middle equator
    eq_edges = [e for e in bm_c.edges if abs(e.verts[0].co.z) < 0.05 and abs(e.verts[1].co.z) < 0.05]
    for e in eq_edges:
        e.select = True
    bmesh.update_edit_mesh(cube.data)

    op_c = types.SimpleNamespace()
    op_c.target_object = cube
    op_c.edit_objects = [cube]
    op_c.bm = bmesh.from_edit_mesh(cube.data)
    op_c.bms = {cube.name: op_c.bm}
    op_c.offset_factor = 0.3
    op_c.dual_offset = False # Single offset
    op_c.use_curvature = True
    op_c.keep_selection = True
    op_c.snap_enabled = False
    op_c.snap_divisions = 8
    op_c.selection_face_cuts = []
    op_c.selection_transverse_map = {}
    op_c.dimension_draws = []
    op_c.preview_points = []
    op_c.preview_lines = []

    M8_OT_FastLoop.analyze_selection(op_c, bpy.context)
    M8_OT_FastLoop.update_selection_preview(op_c, bpy.context)
    M8_OT_FastLoop.perform_selection_cut(op_c, bpy.context, shift=False)
    bmesh.update_edit_mesh(cube.data)

    bm_c_after = bmesh.from_edit_mesh(cube.data)
    print(f"[PASS] perform_selection_cut (Single Offset + Curvature) executed successfully:")
    print(f"  - Cube after cut: verts={len(bm_c_after.verts)}, faces={len(bm_c_after.faces)}")
    assert len(bm_c_after.verts) > 26

    print("=" * 60)
    print("ALL FAST LOOP SELECTION MODE TESTS PASSED! 100% SUCCESS")
    print("=" * 60)

if __name__ == '__main__':
    run_test()
