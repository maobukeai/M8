import bpy

from ...ops.align.align_object_by_view import AlignObjectByView
from ...utils import get_menu_bl_idname
from ...utils.translate import translate_lines_text
from ...utils.view import screen_relevant_direction_3d_axis


class AlignObjectPie(bpy.types.Menu):
    bl_label = "Align Object"
    bl_idname = get_menu_bl_idname("ALIGN_OBJECT")

    @classmethod
    def description(cls, context, properties):
        return translate_lines_text(
            "Align objects, either according to the selected bounding box of all objects",
            "or using the usual origin, active item, and cursor alignment",
            "Align to ground, distributed alignment",
        )

    def draw(self, context):
        from ..panel.align_object import (
            draw_ground,
            draw_distribution_y,
            draw_distribution_x,
            draw_center_align,
            draw_fall,
            draw_cursor_active_original,
        )
        from ...utils.icon import get_custom_icon
        from bpy.app.translations import pgettext_iface

        layout = self.layout
        pie = layout.menu_pie()

        for axis, wasd in {
            "Align_Left": "A",
            "Align_Right": "D",
            "Align_Down": "S",
            "Align_Up": "W",
        }.items():
            text = axis.replace("Align_", "").replace("_", "")
            pie.operator(
                AlignObjectByView.bl_idname,
                icon_value=get_custom_icon(axis),
                text=f"({wasd})" + pgettext_iface(text, msgctxt="M8_zh_HANS")
            ).align_mode = axis

        direction = screen_relevant_direction_3d_axis(context)
        (x, x_), (y, y_) = direction
        draw_distribution_y(pie, y)

        col = pie.column(align=True)
        col.scale_y = 1.3
        draw_center_align(col, direction)

        draw_distribution_x(pie, x)

        col = pie.column(align=True)
        col.scale_y = 1.5
        col.scale_x = 1.3
        column = col.column(align=True)
        draw_fall(column, True)
        draw_ground(column, True)
        row = column.row(align=True)

        row.scale_x = 1.3
        draw_cursor_active_original(row, True)
