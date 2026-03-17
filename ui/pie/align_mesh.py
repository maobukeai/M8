import bpy
from bpy.app.translations import pgettext_iface

from ...ops.align.align_mesh import AlignMesh
from ...utils import get_menu_bl_idname
from ...utils.icon import get_custom_icon
from ...utils.view import screen_relevant_direction_3d_axis


class AlignMeshPie(bpy.types.Menu):
    bl_idname = get_menu_bl_idname("ALIGN_MESH")
    bl_label = "Align Mesh"
    bl_description = "Quickly align to a specific position, to the active item, to the cursor, to the origin"

    def draw(self, context):
        from ...ops.mesh.relax import Relax
        from ..panel.align_mesh import draw_other_align, draw_hv_align
        from ...utils.addon import draw_addon
        pie = self.layout.menu_pie()

        (x, x_), (y, y_) = screen_relevant_direction_3d_axis(context)

        horizontal_axis = x.upper().replace("-", "")  # 水平
        vertical_axis = y.upper().replace("-", "")  # 垂直

        axis_items = {
            "Align_Left": (x_, "A"),
            "Align_Right": (x, "D"),
            "Align_Down": (y_, "S"),
            "Align_Up": (y, "W"),
        }
        for key, (axis, wasd) in axis_items.items():
            name = key.split("_")[1]
            value = "MIN" if len(axis) >= 2 else "MAX"
            axis_upper = axis.upper().replace("-", "")

            ops = pie.operator(AlignMesh.bl_idname, text=f"({wasd})" + pgettext_iface(name, msgctxt="M8_zh_HANS"),
                               icon_value=get_custom_icon(key))
            ops.align_mode = "ALIGN"
            ops.align_location_axis = {axis_upper}
            setattr(ops, f"align_{axis_upper.lower()}_method", value)

        draw_addon(context, pie, "EdgeFlow")

        pie.operator(Relax.bl_idname, icon="SEQ_LUMA_WAVEFORM")

        draw_hv_align(AlignMesh, pie.box().column(align=True), horizontal_axis, vertical_axis)
        draw_other_align(AlignMesh, pie.box().column(align=True), horizontal_axis, vertical_axis)
