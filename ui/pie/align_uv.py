import bpy
from bpy.app.translations import pgettext_iface
from ...utils import get_menu_bl_idname
from ...utils.icon import get_custom_icon


class AlignUVPie(bpy.types.Menu):
    bl_idname = get_menu_bl_idname("ALIGN_UV")
    bl_label = "Align UV"
    bl_description = "Align UV"

    def draw(self, context):
        from ...ops.align.align_uv import AlignUV
        pie = self.layout.menu_pie()
        axis_items = {
            ("Align_Left", "A"): {"align_uv": {"U"}, "align_u_mode": "MIN"},
            ("Align_Right", "D"): {"align_uv": {"U"}, "align_u_mode": "MAX"},
            ("Align_Down", "S"): {"align_uv": {"V"}, "align_v_mode": "MIN"},
            ("Align_Up", "W"): {"align_uv": {"V"}, "align_v_mode": "MAX"},
        }
        for (axis, wasd), props in axis_items.items():
            name = pgettext_iface(axis.split("_")[1], msgctxt="M8_zh_HANS")

            ops = pie.operator(
                AlignUV.bl_idname,
                text=f"({wasd})" + name,
                icon_value=get_custom_icon(axis)
            )

            for k, v in props.items():
                setattr(ops, k, v)

        pie.separator()
        pie.separator()
        pie.separator()

        column = pie.column(align=True)
        for icon, mode in {
            "ALIGN_CENTER": "CENTER",
            "EVENT_ZEROKEY": "ZERO",
            "ORIENTATION_CURSOR": "CURSOR",
        }.items():
            row = column.row(align=True)
            row.label(icon=icon)
            ops = row.operator(AlignUV.bl_idname, text="U")
            ops.align_uv = {"U"}
            ops.align_u_mode = mode
            ops = row.operator(AlignUV.bl_idname, text="V")
            ops.align_uv = {"V"}
            ops.align_v_mode = mode
