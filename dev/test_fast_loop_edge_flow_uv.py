import sys
import os
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
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

for attr_name, attr_val in M8_OT_FastLoop.__dict__.items():
    if callable(attr_val) and not attr_name.startswith("__") and attr_name not in ("poll", "invoke", "modal", "draw_callback_2d", "draw_callback_3d"):
        setattr(MockFastLoop, attr_name, attr_val)

def test_reproject_flow_uvs():
    print("\n--- Test: Edge Flow UV Reprojection ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=2.0)
    bpy.ops.object.mode_set(mode='EDIT')
    obj = bpy.context.active_object

    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Ensure UV map exists
    if not bm.loops.layers.uv.active:
        bm.loops.layers.uv.new("UVMap")
    bmesh.update_edit_mesh(obj.data)

    # Mock bpy.ops.mesh.set_edge_flow so it triggers reproject_flow_uvs
    class DummyOps:
        @staticmethod
        def set_edge_flow(*args, **kwargs):
            return {'FINISHED'}

    bpy.ops.mesh.set_edge_flow = DummyOps.set_edge_flow

    bm = bmesh.from_edit_mesh(obj.data)
    start_edge = bm.edges[0]

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
        enable_edge_flow=True,
        keep_selection=False,
        selection_locked=False,
        slide_offset=0.0,
        snap_enabled=False,
        snap_divisions=4,
        scale_factor=1.0,
        hovered_edge_idx=start_edge.index,
    )

    op.update_ring_and_preview(bpy.context, start_edge.index, (start_edge.verts[0].co + start_edge.verts[1].co) * 0.5)
    
    # This should call perform_cut, which invokes reproject_flow_uvs()
    op.perform_cut(bpy.context, shift=False)
    print("[PASS] perform_cut with edge flow and UV reprojection completed successfully!")

if __name__ == "__main__":
    try:
        test_reproject_flow_uvs()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
