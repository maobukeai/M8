import bmesh
import bpy
from mathutils import Vector

from ....utils.bmesh import from_bm_get_active_location, from_bmesh_get_selected_max_min_location


class BmeshMeasure:
    active_location: Vector
    selected_verts_index: list[int]  # 选择了的顶点索引

    def __str__(self):
        return f"{self.__obj_name__} Vector({self.active_location[:]}) {self.max} {self.min}"

    def __repr__(self):
        return self.__str__()

    def __init__(self, obj: bpy.types.Object):
        self.__obj_name__ = obj.name
        bm = bmesh.from_edit_mesh(obj.data)
        self.active_location = from_bm_get_active_location(bm, obj.matrix_world)
        self.max, self.min = from_bmesh_get_selected_max_min_location(bm, obj.matrix_world)
        self.selected_verts_index = [v.index for v in bm.verts if v.select]
        bm.free()

    @property
    def center(self) -> Vector:
        return (self.max + self.min) / 2
