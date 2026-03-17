import bpy
import bmesh
from mathutils import Vector

from ...utils.ray_cast import mouse_2d_ray_cast


class M8_OT_DoubleClickEditSwitch(bpy.types.Operator):
    bl_idname = "m8.double_click_edit_switch"
    bl_label = "Double Click Edit Switch"
    bl_options = {"REGISTER", "UNDO"}

    def _get_pref(self):
        root_pkg = (__package__ or "").split(".")[0]
        addon = bpy.context.preferences.addons.get(root_pkg)
        return addon.preferences if addon else None

    @classmethod
    def poll(cls, context):
        return bool(context.area and context.area.type == "VIEW_3D")

    def _try_edge_loop_ring_select(self, context, event):
        ts = context.tool_settings
        if not ts or not getattr(ts, "mesh_select_mode", None):
            return False

        if not ts.mesh_select_mode[1]:
            return False

        x = getattr(event, "mouse_region_x", None)
        y = getattr(event, "mouse_region_y", None)
        if x is None or y is None:
            return False

        extend = bool(getattr(event, "shift", False))

        try:
            if not extend:
                bpy.ops.mesh.select_all(action="DESELECT")
        except Exception:
            return False

        try:
            bpy.ops.view3d.select(
                location=(x, y),
                extend=extend,
                deselect=False,
                toggle=False,
                center=False,
                enumerate=False,
                object=False,
            )
        except TypeError:
            try:
                bpy.ops.view3d.select(
                    location=(x, y),
                    extend=extend,
                    deselect=False,
                    toggle=False,
                    center=False,
                    object=False,
                )
            except Exception:
                return False
        except Exception:
            return False

        obj = context.object
        if not obj or obj.type != "MESH" or obj.mode != "EDIT":
            return False

        try:
            bm = bmesh.from_edit_mesh(obj.data)
        except Exception:
            return False

        sel_initial = sum(1 for e in bm.edges if e.select)
        if sel_initial == 0:
            return False

        try:
            bpy.ops.mesh.loop_multi_select(ring=True)
        except Exception:
            return False

        bm = bmesh.from_edit_mesh(obj.data)
        sel_after_ring = sum(1 for e in bm.edges if e.select)
        return sel_after_ring >= sel_initial

    def invoke(self, context, event):
        pref = self._get_pref()
        if not pref or not getattr(pref, "activate_switch_mode", True) or not getattr(pref, "switch_mode_double_click_edit_switch", False):
            return {"PASS_THROUGH"}

        if context.mode != "EDIT_MESH":
            return {"PASS_THROUGH"}

        active = context.object
        if not active:
            return {"PASS_THROUGH"}

        if not hasattr(event, "mouse_region_x") or not hasattr(event, "mouse_region_y"):
            return {"PASS_THROUGH"}

        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        hit, _, _, _, obj, _ = mouse_2d_ray_cast(context, mouse)
        if not hit or not obj:
            return {"PASS_THROUGH"}

        if obj == active:
            if getattr(pref, "switch_mode_double_click_edge_loop_ring", True):
                if self._try_edge_loop_ring_select(context, event):
                    return {"FINISHED"}
            return {"PASS_THROUGH"}

        try:
            if obj.name not in context.view_layer.objects:
                return {"PASS_THROUGH"}
        except Exception:
            pass

        if not obj.visible_get():
            return {"PASS_THROUGH"}

        if obj.type != "MESH":
            return {"PASS_THROUGH"}

        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            return {"PASS_THROUGH"}

        try:
            bpy.ops.object.select_all(action="DESELECT")
        except Exception:
            pass

        try:
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except Exception:
            return {"CANCELLED"}

        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except Exception:
            return {"CANCELLED"}

        return {"FINISHED"}
