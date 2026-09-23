"""Test Fast Loop selection-locked mode using actual production API.

Run via Blender:
    blender --background --factory-startup --python dev/test_fast_loop_selection.py

Uses the same MockFastLoop binding strategy as test_fast_loop_hidden_faces.py
and test_fast_loop_edge_flow_uv.py to call real production methods without
invoking the interactive modal.
"""

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

from M8.ops.misc.fast_loop import M8_OT_FastLoop
from M8.property.preferences import SIZE_TOOL_Preferences


class MockFastLoop:
    """Mock container that binds all M8_OT_FastLoop helper methods for headless testing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# Bind all operator helper methods to MockFastLoop (same pattern as hidden_faces test)
for _attr_name, _attr_val in M8_OT_FastLoop.__dict__.items():
    if (callable(_attr_val)
            and not _attr_name.startswith("__")
            and _attr_name not in ("poll", "invoke", "modal",
                                   "draw_callback_2d", "draw_callback_3d")):
        setattr(MockFastLoop, _attr_name, _attr_val)


def _make_op(**kwargs):
    """Build a minimal MockFastLoop instance with sensible defaults."""
    defaults = dict(
        segments=1,
        mirrored=False,
        vertex_mode=False,
        guide_mode=False,
        use_even=False,
        flipped=False,
        perpendicular=False,
        use_curvature=False,
        enable_edge_flow=False,
        keep_selection=False,
        selection_locked=False,
        slide_offset=0.0,
        snap_enabled=False,
        snap_divisions=4,
        scale_factor=1.0,
        hovered_edge_idx=-1,
    )
    defaults.update(kwargs)
    return MockFastLoop(**defaults)


def run_test():
    print("=" * 60)
    print("M8 FAST LOOP SELECTION MODE TEST SUITE")
    print("=" * 60)

    print("[PASS] Successfully imported SIZE_TOOL_Preferences and M8_OT_FastLoop.")
    has_annotations = (
        'fast_loop_enable_edge_flow' in SIZE_TOOL_Preferences.__annotations__ and
        'fast_loop_keep_selection' in SIZE_TOOL_Preferences.__annotations__ and
        'fast_loop_reproject_uv_after_edge_flow' in SIZE_TOOL_Preferences.__annotations__
    )
    print("SIZE_TOOL_Preferences has fast_loop properties:", has_annotations)
    assert has_annotations, "Expected fast_loop properties in SIZE_TOOL_Preferences.__annotations__"

    # ------------------------------------------------------------------
    # Test 1: Ring discovery via get_oriented_edge_ring on a cylinder
    # ------------------------------------------------------------------
    print("\n--- Test 1: get_oriented_edge_ring on cylinder ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1.0, depth=2.0)
    obj = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Pick any lateral (non-cap) edge as start
    lateral = [e for e in bm.edges if not e.is_boundary
               and e.calc_length() < 1.5]
    assert lateral, "No lateral edges found on cylinder"
    start_edge = lateral[0]

    op = MockFastLoop()
    ring_map = op.get_oriented_edge_ring(bm, start_edge)
    assert len(ring_map) > 0, "Expected ring to contain edges"
    print(f"  Ring edges: {len(ring_map)}")
    print("[PASS] Test 1: get_oriented_edge_ring returned a non-empty ring.")

    # ------------------------------------------------------------------
    # Test 2: update_ring_and_preview — non-locked mode
    # ------------------------------------------------------------------
    print("\n--- Test 2: update_ring_and_preview (normal mode) ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=4.0)
    bpy.ops.object.mode_set(mode='EDIT')
    obj = bpy.context.active_object
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()

    vert_edges = [e for e in bm.edges if not e.hide
                  and abs(e.verts[0].co.x - e.verts[1].co.x) < 0.01]
    assert vert_edges, "No vertical edges found on grid"
    start_edge = vert_edges[len(vert_edges) // 2]

    op2 = _make_op(
        target_object=obj,
        bm=bm,
        bms={obj.name: bm},
        hovered_edge_idx=start_edge.index,
    )
    op2.update_ring_and_preview(bpy.context, start_edge.index,
                                (start_edge.verts[0].co + start_edge.verts[1].co) * 0.5)
    assert hasattr(op2, 'edge_ring_edges'), "update_ring_and_preview must set edge_ring_edges"
    assert len(op2.edge_ring_edges) > 0, "Expected ring edges after update_ring_and_preview"
    print(f"  Edge ring edges: {len(op2.edge_ring_edges)}")
    print("[PASS] Test 2: update_ring_and_preview populated edge_ring_edges.")

    # ------------------------------------------------------------------
    # Test 3: perform_cut (normal mode) increases vertex/face count
    # ------------------------------------------------------------------
    print("\n--- Test 3: perform_cut (normal mode) on grid ---")
    initial_verts = len(bm.verts)
    initial_faces = len(bm.faces)
    op2.perform_cut(bpy.context, shift=False)
    bmesh.update_edit_mesh(obj.data)

    bm2 = bmesh.from_edit_mesh(obj.data)
    new_verts = len(bm2.verts)
    new_faces = len(bm2.faces)
    print(f"  Before cut: verts={initial_verts}, faces={initial_faces}")
    print(f"  After  cut: verts={new_verts}, faces={new_faces}")
    assert new_verts > initial_verts, f"Verts should increase: {new_verts} > {initial_verts}"
    assert new_faces > initial_faces, f"Faces should increase: {new_faces} > {initial_faces}"
    print("[PASS] Test 3: perform_cut correctly subdivided the mesh.")

    # ------------------------------------------------------------------
    # Test 4: selection_locked mode preserves selected edge ring geometry
    # ------------------------------------------------------------------
    print("\n--- Test 4: selection_locked mode — perpendicular cut across selected loop ---")
    # Must switch to OBJECT mode before add_primitive creates a second object
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=4.0)
    bpy.ops.object.mode_set(mode='EDIT')
    cube = bpy.context.active_object
    bm_c = bmesh.from_edit_mesh(cube.data)
    bm_c.edges.ensure_lookup_table()
    bm_c.faces.ensure_lookup_table()

    # Select a horizontal equatorial edge loop (y near 0)
    for e in bm_c.edges:
        e.select = False
    sel_edges = [
        e for e in bm_c.edges
        if not e.hide
        and abs(e.verts[0].co.y - e.verts[1].co.y) < 0.01
        and abs((e.verts[0].co.y + e.verts[1].co.y) * 0.5) < 0.1
    ]
    for e in sel_edges:
        e.select = True
    bmesh.update_edit_mesh(cube.data)

    assert len(sel_edges) > 0, "No edges selected for locked-mode test"
    print(f"  Selected {len(sel_edges)} edges for locked loop")

    op_locked = _make_op(
        target_object=cube,
        bm=bm_c,
        bms={cube.name: bm_c},
        selection_locked=True,
        keep_selection=True,
        slide_offset=0.0,
        hovered_edge_idx=sel_edges[0].index,
        edge_ring_edge_indices=[e.index for e in sel_edges],
        edge_ring_edges=sel_edges,
        edge_ring_orientations={e.index: False for e in sel_edges},
    )

    # update_ring_and_preview in locked mode should respect the pre-selected edges
    op_locked.update_ring_and_preview(bpy.context, op_locked.hovered_edge_idx, None)

    initial_verts_c = len(bm_c.verts)
    initial_faces_c = len(bm_c.faces)
    op_locked.perform_cut(bpy.context, shift=False)
    bmesh.update_edit_mesh(cube.data)

    bm_c2 = bmesh.from_edit_mesh(cube.data)
    new_verts_c = len(bm_c2.verts)
    new_faces_c = len(bm_c2.faces)
    print(f"  Before locked cut: verts={initial_verts_c}, faces={initial_faces_c}")
    print(f"  After  locked cut: verts={new_verts_c}, faces={new_faces_c}")
    assert new_verts_c > initial_verts_c, \
        f"Locked cut should add verts: {new_verts_c} > {initial_verts_c}"
    assert new_faces_c > initial_faces_c, \
        f"Locked cut should add faces: {new_faces_c} > {initial_faces_c}"

    # keep_selection=True: the original selected edges should still be selected
    bm_c2.edges.ensure_lookup_table()
    still_selected = [e for e in bm_c2.edges if e.select]
    assert len(still_selected) > 0, \
        "keep_selection=True: at least some edges should remain selected after cut"
    print(f"  Edges still selected after cut: {len(still_selected)}")
    print("[PASS] Test 4: selection_locked cut added geometry and preserved selection.")

    # ------------------------------------------------------------------
    # Test 5: get_oriented_loop_selection — derives consistent orientations
    # ------------------------------------------------------------------
    print("\n--- Test 5: get_oriented_loop_selection orientation consistency ---")
    bm_c2.edges.ensure_lookup_table()
    sel_after = [e for e in bm_c2.edges if e.select and not e.hide]
    assert len(sel_after) > 0, (
        "Test 5 requires selected edges after locked cut (keep_selection=True must preserve selection); "
        f"found 0 selected edges. Check that perform_cut with keep_selection=True restores selection."
    )
    op5 = MockFastLoop()
    orientations = op5.get_oriented_loop_selection(bm_c2, sel_after)
    assert len(orientations) == len(sel_after), \
        f"Orientation map size mismatch: {len(orientations)} vs {len(sel_after)}"
    print(f"  Orientation map has {len(orientations)} entries.")
    print("[PASS] Test 5: get_oriented_loop_selection returns a complete orientation map.")

    bpy.ops.object.mode_set(mode='OBJECT')

    print("=" * 60)
    print("ALL FAST LOOP SELECTION MODE TESTS PASSED! 100% SUCCESS")
    print("=" * 60)


if __name__ == '__main__':
    run_test()
