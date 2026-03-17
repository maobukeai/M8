import bmesh
import bpy
from bpy.app.translations import pgettext
from mathutils import Vector

from .mesh_ways.bmesh_measure import BmeshMeasure
from .mesh_ways.operator_property import OperatorProperty
from ...utils import get_operator_bl_idname
from ...utils.items import AXIS
from ...utils.translate import translate_lines_text


class UI:
    def draw(self, context):
        layout = self.layout

        if self.align_mode == "ALIGN":
            column = layout.column(align=True)

            for a in AXIS:
                if a in self.align_location_axis:
                    split = column.split(factor=0.15, align=True)
                    split.label(text=a)
                    split.row(align=True).prop(self, f"align_{a.lower()}_method", expand=True)

        split = layout.split(factor=0.15, align=True)
        split.label(text="Mode")
        split.row(align=True).prop(self, "align_mode", expand=True)

        split = layout.split(factor=0.15, align=True)
        split.label(text="Axis")
        split.row(align=True).prop(self, "align_location_axis", expand=True)


class AlignMesh(
    bpy.types.Operator,
    OperatorProperty,
    UI
):
    bl_idname = get_operator_bl_idname("align_mesh")
    bl_label = "Align Mesh"
    bl_options = {"REGISTER", "UNDO"}
    measure: BmeshMeasure

    @classmethod
    def description(cls, context, properties):
        axis = properties.align_location_axis
        at = translate_lines_text("Axis:") + str(axis)
        if properties.align_mode == "ORIGINAL":
            return translate_lines_text("Alignment to the origin (world axis)", at)
        elif properties.align_mode == "ACTIVE":
            return translate_lines_text(
                "Aligns to the active item",
                "or to the center of the selected grid if the active item is not selected",
                at
            )
        elif properties.align_mode == "CURSOR":
            return translate_lines_text("Align to Cursor", at)
        elif properties.align_mode == "ALIGN":
            return translate_lines_text(
                "Alignment according to the position of the bounding box of the selected mesh",
                "each axis can be set individually (minimum position, center position, maximum position)",
                "\n".join(f"{a}: {pgettext(getattr(properties, f'align_{a.lower()}_method'))}" for a in AXIS if
                          a in properties.align_location_axis)
            )
        return translate_lines_text("Align Mesh")

    @classmethod
    def poll(cls, context):
        if context.object.type == "MESH" and context.object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(context.object.data)
            for v in bm.verts:
                if v.select:
                    bm.free()
                    return True
        return False

    def invoke(self, context, event):
        self.measure = BmeshMeasure(context.object)
        return self.execute(context)

    def execute(self, context):
        getattr(self, f"align_to_{self.align_mode.lower()}")(context)
        return {"FINISHED"}

    def update_mesh(self, context: bpy.types.Context, location: Vector):
        context.view_layer.update()
        bm = bmesh.from_edit_mesh(context.object.data)
        bm.verts.ensure_lookup_table()

        mat = context.object.matrix_world

        for vi in self.measure.selected_verts_index:
            vert = bm.verts[vi]
            co = mat @ vert.co
            vert.co = mat.inverted() @ Vector((
                location[index] if axis in self.align_location_axis else co[index]
                for index, axis in enumerate(AXIS)
            ))

        bmesh.update_edit_mesh(context.object.data)
        bm.free()
        context.view_layer.update()

    def align_to_original(self, context):
        self.update_mesh(context, Vector())

    def align_to_active(self, context):
        self.update_mesh(context, self.measure.active_location)

    def align_to_align(self, context):
        self.update_mesh(context, self.align_location)

    def align_to_cursor(self, context):
        self.update_mesh(context, context.scene.cursor.location)

    @property
    def align_location(self) -> Vector:
        loc = {
            "MIN": self.measure.min,
            "CENTER": self.measure.center,
            "MAX": self.measure.max,
        }
        return Vector(
            [loc[getattr(self, f"align_{value.lower()}_method")][index] for index, value in enumerate(AXIS)]
        )
