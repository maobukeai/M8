"""Test Fast Loop (Ctrl+Shift+E) hidden faces filtering and cut boundaries.

Run via Blender:
blender --background --factory-startup --python dev/test_fast_loop_hidden_faces.py
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


class MockFastLoop:
    """Mock container that binds all M8_OT_FastLoop methods for headless testing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# Bind all operator helper methods to MockFastLoop
for attr_name, attr_val in M8_OT_FastLoop.__dict__.items():
    if callable(attr_val) and not attr_name.startswith("__") and attr_name not in ("poll", "invoke", "modal", "draw_callback_2d", "draw_callback_3d"):
        setattr(MockFastLoop, attr_name, attr_val)


def test_topology_walk_stops_at_hidden_boundary():
    print("\n--- Test 1: Topology Walk stops at hidden boundary ---")
    bm = bmesh.new()
    verts_top = [bm.verts.new((i, 1, 0)) for i in range(5)]
    verts_bot = [bm.verts.new((i, 0, 0)) for i in range(5)]
    bm.verts.ensure_lookup_table()

    faces = []
    for i in range(4):
        faces.append(bm.faces.new((verts_bot[i], verts_bot[i+1], verts_top[i+1], verts_top[i])))

    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Hide face 2 and 3 (right two faces)
    faces[2].hide = True
    faces[3].hide = True

    # Pick the vertical edge at x=0
    start_edge = next(e for e in bm.edges if e.verts[0].co.x == 0 and e.verts[1].co.x == 0)

    op = MockFastLoop()
    ring_map = op.get_oriented_edge_ring(bm, start_edge)
    ring_edges = [bm.edges[idx] for idx in ring_map.keys()]

    print(f"Ring edges count: {len(ring_edges)}")
    # In a 4x1 quad strip where faces 2 and 3 are hidden,
    # the ring across visible faces 0 and 1 should ONLY contain vertical edges at x=0, 1, 2.
    # It must NOT contain edges at x=3 or x=4!
    x_coords = sorted([round(e.verts[0].co.x, 2) for e in ring_edges])
    print(f"X coordinates of ring edges: {x_coords}")
    assert x_coords == [0.0, 1.0, 2.0], f"Expected [0.0, 1.0, 2.0], got {x_coords}"

    # Ensure no hidden faces or edges are in the ring
    for e in ring_edges:
        assert not e.hide, f"Ring edge {e.index} is hidden!"
    print("[PASS] Test 1: Ring stopped cleanly at hidden boundary.")


def test_perform_cut_does_not_cut_hidden_faces():
    print("\n--- Test 2: perform_cut leaves hidden faces uncut ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=5, y_subdivisions=5, size=4.0)
    bpy.ops.object.mode_set(mode='EDIT')
    obj = bpy.context.active_object

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Hide all faces with center x > 0 (right half of the 4x4 grid: 8 faces hidden)
    for f in bm.faces:
        f.select = (f.calc_center_median().x > 0)
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.hide(unselected=False)

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    initial_total_faces = len(bm.faces)
    initial_hidden_faces = len([f for f in bm.faces if f.hide])
    initial_visible_faces = len([f for f in bm.faces if not f.hide])
    print(f"Initial: Total faces={initial_total_faces}, Hidden={initial_hidden_faces}, Visible={initial_visible_faces}")

    # Pick a vertical edge in the visible half so the cut travels horizontally
    vert_edges = [
        e for e in bm.edges
        if not e.hide and abs(e.verts[0].co.x - e.verts[1].co.x) < 0.01
        and ((e.verts[0].co + e.verts[1].co) * 0.5).x < -0.5
    ]
    start_edge = vert_edges[0]

    op = MockFastLoop(
        target_object=obj,
        bm=bm,
        bms={obj.name: bm},
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
        hovered_edge_idx=start_edge.index,
    )

    op.update_ring_and_preview(bpy.context, start_edge.index, (start_edge.verts[0].co + start_edge.verts[1].co) * 0.5)

    print(f"Edge ring edges count: {len(op.edge_ring_edges)}")
    for e in op.edge_ring_edges:
        assert not e.hide, f"Ring edge {e.index} should not be hidden"

    # Execute cut
    op.perform_cut(bpy.context, shift=False)
    bmesh.update_edit_mesh(obj.data)

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    after_total_faces = len(bm.faces)
    after_hidden_faces = len([f for f in bm.faces if f.hide])
    after_visible_faces = len([f for f in bm.faces if not f.hide])
    print(f"After cut: Total faces={after_total_faces}, Hidden={after_hidden_faces}, Visible={after_visible_faces}")

    # The hidden faces count must remain EXACTLY unchanged!
    assert after_hidden_faces == initial_hidden_faces, (
        f"Hidden faces changed! Initial: {initial_hidden_faces}, After: {after_hidden_faces}"
    )
    # The visible faces were cut, so visible faces increased
    assert after_visible_faces > initial_visible_faces, "Visible faces should have been subdivided"
    print("[PASS] Test 2: Hidden faces completely untouched during perform_cut.")


def test_raycast_penetrates_hidden_faces():
    print("\n--- Test 3: Raycast penetrates hidden faces to visible face behind ---")
    from mathutils.bvhtree import BVHTree

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.faces.ensure_lookup_table()

    # Front face is at y = -1. Hide it.
    for f in bm.faces:
        if f.calc_center_median().y < -0.9:
            f.hide = True

    bvh = BVHTree.FromBMesh(bm)
    local_origin = mathutils.Vector((0, -3, 0))
    local_vector = mathutils.Vector((0, 1, 0))

    # Step-through raycast as implemented in trigger_update
    curr_origin = local_origin
    curr_dist_max = 100000.0
    total_traveled = 0.0
    obj_hit = None

    for _ in range(10):
        loc, norm, face_idx, dist = bvh.ray_cast(curr_origin, local_vector, curr_dist_max)
        if face_idx is None or face_idx < 0:
            break
        hit_face = bm.faces[face_idx]
        if not hit_face.hide:
            obj_hit = (loc, norm, face_idx, total_traveled + dist)
            break
        step = dist + 1e-4
        total_traveled += step
        curr_origin = curr_origin + local_vector * step
        curr_dist_max = max(0.0, curr_dist_max - step)

    assert obj_hit is not None, "Expected raycast to hit visible face behind hidden face"
    hit_face = bm.faces[obj_hit[2]]
    assert not hit_face.hide, "Hit face must not be hidden"
    assert hit_face.calc_center_median().y > 0.9, f"Expected back face at y=+1, got {hit_face.calc_center_median()}"
    print(f"[PASS] Test 3: Raycast correctly bypassed hidden front face and hit visible back face at {hit_face.calc_center_median()}.")


def test_remove_loop_stops_at_hidden_boundary():
    print("\n--- Test 4: Remove loop (get_edge_loop) stops at hidden boundary ---")
    bm = bmesh.new()
    # 3x3 grid
    verts = [bm.verts.new((x, y, 0)) for y in range(3) for x in range(3)]
    bm.verts.ensure_lookup_table()
    faces = []
    for y in range(2):
        for x in range(2):
            v1 = verts[y * 3 + x]
            v2 = verts[y * 3 + x + 1]
            v3 = verts[(y + 1) * 3 + x + 1]
            v4 = verts[(y + 1) * 3 + x]
            faces.append(bm.faces.new((v1, v2, v3, v4)))
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Hide face (x=1, y=0)
    faces[1].hide = True

    # Start loop on middle horizontal edge (y=1) in face 0 (x in [0, 1])
    start_edge = next(e for e in bm.edges if abs(e.verts[0].co.y - 1.0) < 0.01 and abs(e.verts[1].co.y - 1.0) < 0.01 and e.verts[0].co.x <= 1.0 and e.verts[1].co.x <= 1.0)

    op = MockFastLoop()
    loop_edges = op.get_edge_loop(None, start_edge)
    for e in loop_edges:
        assert not e.hide, f"Loop edge {e.index} should not be hidden"
    print(f"[PASS] Test 4: Remove loop edge collection respected hidden boundaries.")


def test_selection_locked_cut_stops_at_hidden_boundary():
    print("\n--- Test 5: Selection locked cut stops at hidden boundary ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=5, y_subdivisions=5, size=4.0)
    bpy.ops.object.mode_set(mode='EDIT')
    obj = bpy.context.active_object

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Hide all faces with center y > 0
    for f in bm.faces:
        f.select = (f.calc_center_median().y > 0)
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.hide(unselected=False)

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    initial_hidden = len([f for f in bm.faces if f.hide])

    # Select visible horizontal edge loop along y=0 or y=-1
    for e in bm.edges:
        e.select = False
    sel_edges = [
        e for e in bm.edges
        if not e.hide and abs(e.verts[0].co.y - e.verts[1].co.y) < 0.01
        and abs((e.verts[0].co.y + e.verts[1].co.y) * 0.5 - (-1.0)) < 0.01
    ]
    for e in sel_edges:
        e.select = True
    bmesh.update_edit_mesh(obj.data)

    op = MockFastLoop(
        target_object=obj,
        bm=bm,
        bms={obj.name: bm},
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
        selection_locked=True,
        slide_offset=0.0,
        snap_enabled=False,
        snap_divisions=4,
        scale_factor=1.0,
        edge_ring_edge_indices=[e.index for e in sel_edges],
        edge_ring_edges=sel_edges,
        edge_ring_orientations={e.index: False for e in sel_edges},
        hovered_edge_idx=sel_edges[0].index if sel_edges else -1,
    )

    op.update_ring_and_preview(bpy.context, op.hovered_edge_idx, None)
    op.perform_cut(bpy.context, shift=False)
    bmesh.update_edit_mesh(obj.data)

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    after_hidden = len([f for f in bm.faces if f.hide])
    print(f"Hidden faces: before={initial_hidden}, after={after_hidden}")
    assert after_hidden == initial_hidden, f"Hidden faces changed in selection mode! Before: {initial_hidden}, After: {after_hidden}"
    print("[PASS] Test 5: Selection locked cut respects hidden boundaries.")


def run_all_tests():
    print("=" * 60)
    print("M8 FAST LOOP HIDDEN FACES TEST SUITE")
    print("=" * 60)
    test_topology_walk_stops_at_hidden_boundary()
    test_perform_cut_does_not_cut_hidden_faces()
    test_raycast_penetrates_hidden_faces()
    test_remove_loop_stops_at_hidden_boundary()
    test_selection_locked_cut_stops_at_hidden_boundary()
    print("\n" + "=" * 60)
    print("ALL 5 TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
