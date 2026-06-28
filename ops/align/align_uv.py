from __future__ import annotations

import bmesh.types
import bpy
from mathutils import Vector

from ...utils import get_operator_bl_idname
from ...utils.i18n import _T

UV_ALIGN_MODE_ENUMS = [
    ("MAX", "Max", "Select Max uv"),
    ("CENTER", "Center", "Select Center uv"),
    ("MIN", "Min", "Select Min uv"),
    ("ZERO", "Zero", "To Zero"),
    ("CURSOR", "Cursor", "To Cursor"),
]
IDENTIFIER_LIST = [i[0] for i in UV_ALIGN_MODE_ENUMS]


class AlignUV(bpy.types.Operator):
    bl_idname = get_operator_bl_idname("align_uv")
    bl_label = _T("对齐 UV")
    bl_options = {"REGISTER", "UNDO"}

    align_uv: bpy.props.EnumProperty(items=[
        ("U", "U", "Align U"),
        ("V", "V", "Align V"),
    ],
        options={"ENUM_FLAG"}
    )
    align_u_mode: bpy.props.EnumProperty(
        items=UV_ALIGN_MODE_ENUMS,
        name="U Align Mode"
    )
    align_v_mode: bpy.props.EnumProperty(
        items=UV_ALIGN_MODE_ENUMS,
        name="V Align Mode"
    )

    loops: "list[bmesh.types.BMLoop]" = None
    uv_data: "list" = None

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH":
            return False
        obj = context.object
        return obj and obj.type == "MESH" and obj.data.uv_layers.active

    def draw(self, context):
        column = self.layout.column(align=True)
        if "U" in self.align_uv:
            row = column.row(align=True)
            row.label(text="U")
            row.prop(self, "align_u_mode", expand=True)
        if "V" in self.align_uv:
            row = column.row(align=True)
            row.label(text="V")
            row.prop(self, "align_v_mode", expand=True)
        row = column.row(align=True)
        row.prop(self, "align_uv", expand=True)

    def invoke(self, context, event):
        bpy.ops.ed.undo_push(message="Push Undo")
        return self.execute(context)

    def execute(self, context):
        import bmesh

        obj = context.object
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = obj.data.uv_layers.active
        if uv_layer.name not in bm.loops.layers.uv:
            self.report({"ERROR"}, f"Bmesh in not found {uv_layer.name}")
            return {"CANCELLED"}
        layer = bm.loops.layers.uv[uv_layer.name]
        try:
            sync_from_mesh = getattr(bm, "uv_select_sync_from_mesh", None)
            if sync_from_mesh:
                sync_from_mesh()
        except Exception:
            pass
        self.init_uv_data(context, bm, layer)
        if not self.loops:
            self.report({"WARNING"}, _T("未选中任何 UV"))
            return {"CANCELLED"}
        for loop in self.loops:
            loop[layer].uv = self.mix_uv_co(loop[layer].uv)

        bmesh.update_edit_mesh(obj.data)
        obj.data.update()
        return {"FINISHED"}

    @staticmethod
    def _loop_uv_selected(loop, uv):
        if bool(getattr(uv, "select", False)):
            return True
        if bool(getattr(loop, "uv_select_vert", False)):
            return True
        if bool(getattr(loop, "uv_select_edge", False)):
            return True
        face = getattr(loop, "face", None)
        return bool(getattr(face, "uv_select", False))

    def init_uv_data(self, context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer):
        """
        1.测量最大最小值
        2.找到所有的uv列表

        bpy.data.screens["UV Editing"].areas[2].spaces[0].cursor_location[0]
        """
        max_uv = Vector((-999, -999))
        min_uv = Vector((999, 999))
        self.loops = []
        for face in bm.faces:
            for loop in face.loops:
                uv = loop[uv_layer]
                if self._loop_uv_selected(loop, uv):
                    u, v = uv.uv
                    if u > max_uv[0]:
                        max_uv[0] = u
                    if u < min_uv[0]:
                        min_uv[0] = u

                    if v > max_uv[1]:
                        max_uv[1] = v
                    if v < min_uv[1]:
                        min_uv[1] = v
                    # max_uv = Vectore((max(max_uv[0], u), max(max_uv[1], v)))
                    # min_uv = Vector((min(min_uv[0], u), min(min_uv[1], v)))
                    self.loops.append(loop)
        if not self.loops:
            self.uv_data = [Vector((0, 0))] * len(IDENTIFIER_LIST)
            return
        center_uv = (max_uv + min_uv) / 2
        space_data = getattr(context, "space_data", None)
        cursor = getattr(space_data, "cursor_location", Vector((0, 0)))
        zero = Vector((0, 0))
        self.uv_data = [max_uv, center_uv, min_uv, zero, cursor]

    def mix_uv_co(self, co: Vector) -> Vector:
        u, v = co
        if "U" in self.align_uv:
            index = IDENTIFIER_LIST.index(self.align_u_mode)
            u = self.uv_data[index][0]
        if "V" in self.align_uv:
            index = IDENTIFIER_LIST.index(self.align_v_mode)
            v = self.uv_data[index][1]
        return Vector((u, v))
