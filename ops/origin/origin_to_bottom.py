import bmesh
import bpy
from bmesh.types import BMesh
from bpy.props import BoolProperty
from mathutils import Vector

from .public_origin import PublicOrigin
from ...utils import get_operator_bl_idname
from ...utils.math import location_to_matrix, scale_to_matrix, rotation_to_matrix


class OriginToBottom(PublicOrigin):
    bl_idname = get_operator_bl_idname("origin_to_bottom")
    bl_label = "To Bottom"
    bl_description = "Press ctrl or alt to use the object's Z-axis as the bottom"

    origin_to_geometry: BoolProperty(default=True, name="Origin to Geometry")
    reset_rotation: BoolProperty(default=True, name="Reset Rotation")

    @classmethod
    def poll(cls, context):
        """只允许在物体模式下对网格进行操作"""
        if context.mode == "OBJECT" and super().poll(context):
            for obj in context.selected_objects:
                if obj.type == "MESH":
                    return True
        return False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.only_location = self.only_rotation = self.calculate_rotation = False

    def execute(self, context):
        self.calculate_rotation = not (self.only_location or self.only_rotation)
        self.only_location = self.only_rotation = False
        context.view_layer.update()
        if self.origin_to_geometry:
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
        context.view_layer.update()
        return super().execute(context)

    def get_obj_matrix(self, obj: bpy.types.Object):
        if obj.type != "MESH":
            return None

        matrix = obj.matrix_world
        loc = obj.matrix_world.translation

        bm = bmesh.new()
        bm.from_mesh(obj.data)

        def get_min_z(b_mesh: BMesh) -> float:
            min_z: float | None = None

            for vert in b_mesh.verts:
                co = vert.co
                if min_z is None:
                    min_z = co.z
                if co.z < min_z:
                    min_z = co.z
            return min_z

        if self.calculate_rotation:
            bm.transform(matrix)
            z = get_min_z(bm)
            diff_mat = location_to_matrix(Vector((0, 0, (z - loc.z))))
            bm.free()
            mat = diff_mat @ matrix
        else:
            z = get_min_z(bm)
            bm.free()
            lm = location_to_matrix(Vector((0, 0, z)))
            mat = matrix @ lm

        l, r, s = (
            location_to_matrix(mat.translation),
            rotation_to_matrix(mat.to_euler()),
            scale_to_matrix(mat.to_scale())
        )

        return l @ s if self.reset_rotation else l @ r @ s
