import bpy
from mathutils import Vector

from .select_mirror import get_select_mirror_info
from ....hub import clear_hub, Hub3DItem, hub_3d
from ....utils import get_pref
from ....utils.math import scale_to_matrix


class MirrorLattice:
    """
    1.找到需要镜像的点
    2.镜像矩阵
    3.预览

    uvw
    """
    cache_lattice_hub = {}
    lattice_info = {}

    @classmethod
    def lattice_poll(cls, context):
        return True

    @property
    def axis_to_uvw(self) -> str:
        return {
            "X": "U",
            "Y": "V",
            "Z": "W",
        }.get(self.axis)

    def load_lattice_preview(self, context):
        obj = context.edit_object
        self.lattice_info = get_select_mirror_info(obj.data)
        self.cache_lattice_hub = {}

    def update_lattice_preview(self, context, is_preview=True):
        pref = get_pref()
        key = (self.axis_mode, self.is_negative_axis, self.bisect, self.axis)

        if key in self.cache_lattice_hub:
            hub = self.cache_lattice_hub[key]
        else:
            hub = Hub3DItem(vert_size=pref.mirror_preview_vert_size, line_width=pref.mirror_preview_edge_width)
            is_negative_axis = self.is_negative_axis

            obj = context.edit_object
            axis_index = self.axis_index
            scale_vector = Vector((-1 if i == self.axis_index else 1 for i in range(3)))
            scale_matrix = scale_to_matrix(scale_vector)
            obj_matrix = obj.matrix_world
            matrix = obj_matrix @ scale_matrix

            axis = self.axis_to_uvw
            mirror_info = self.lattice_info
            for index, point in enumerate(obj.data.points):
                if point.select:
                    info = mirror_info[index]
                    m_index = info[axis]
                    m_t = info[f"{axis}_TYPE"]

                    nc = obj_matrix @ (scale_matrix @ point.co_deform)
                    if m_t == "CENTER":
                        ...
                    elif is_negative_axis:
                        if m_t == "POSITIVE":
                            hub.vert(nc)
                    else:
                        if m_t == "NEGATIVE":
                            hub.vert(nc)

            hub.depth_test = "LESS_EQUAL"
            self.cache_mesh_hub[key] = hub

        hub.alpha = pref.mirror_preview_alpha * 2 if is_preview else None
        area_hash = hash(context.area)
        timeout = None if is_preview else 1.0
        hub_3d(f"{self.bl_idname}_preview", hub, timeout=timeout, area_restrictions=area_hash)

    def draw_lattice(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        col = layout.column(align=True)

        axes = col.box()
        axes_col = axes.column(align=True)
        axes_col.row(align=True).prop(self, "axis_mode", expand=True)
        axes_col.row(align=True).prop(self, "axis", expand=True)

        opt = col.box()
        opt.use_property_split = False
        opt.prop(self, "is_negative_axis", text="反向")

    def update_lattice_hub(self, context):
        ...

    def clear_lattice_hub(self):
        clear_hub(self.bl_idname)
        clear_hub(f"{self.bl_idname}_active")
        clear_hub(f"{self.bl_idname}_preview")

    def execute_lattice(self, context):
        obj = context.edit_object

        scale_vector = Vector((-1 if i == self.axis_index else 1 for i in range(3)))
        scale_matrix = scale_to_matrix(scale_vector)
        matrix = scale_matrix

        is_negative_axis = self.is_negative_axis

        mirror_info = self.lattice_info
        axis = self.axis_to_uvw
        for index, point in enumerate(obj.data.points):
            if point.select:
                info = mirror_info[index]
                m_index = info[axis]
                m_t = info[f"{axis}_TYPE"]
                if m_t == "CENTER":
                    ...
                elif is_negative_axis:
                    if m_t == "POSITIVE":
                        obj.data.points[m_index].co_deform = matrix @ point.co_deform
                else:
                    if m_t == "NEGATIVE":
                        obj.data.points[m_index].co_deform = matrix @ point.co_deform
                # else:
                #     obj.data.points[m_index].co_deform = matrix @ point.co_deform
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        return {"FINISHED"}
