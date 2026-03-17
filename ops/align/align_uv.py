import bmesh.types
import bpy
from mathutils import Vector

from ...utils import get_operator_bl_idname

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
    bl_label = "Align UV"
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
        self.init_uv_data(context, bm, layer)
        for loop in self.loops:
            loop[layer].uv = self.mix_uv_co(loop[layer].uv)

        bmesh.update_edit_mesh(obj.data)
        obj.data.update()
        return {"FINISHED"}

    def init_uv_data(self, context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLoopUV):
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
                is_select = getattr(uv, "select", False)
                is_uv_select_vert = getattr(loop, "uv_select_vert", False)
                is_uv_select_edge = getattr(loop, "uv_select_edge", False)
                if is_select or is_uv_select_vert or is_uv_select_edge:
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
        center_uv = (max_uv + min_uv) / 2
        cursor = context.space_data.cursor_location
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
