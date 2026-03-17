import bpy

from ...ops.align.align_object import AlignObject
from ...ops.align.align_object_by_view import AlignObjectByView
from ...utils import get_panel_bl_idname
from ...utils.icon import get_custom_icon
from ...utils.view import screen_relevant_direction_3d_axis

AXIS = ("X", "Y", "Z")


def set_axis(layout, axis, icon, center=False):
    row = layout.row()
    op = row.operator(
        AlignObject.bl_idname,
        icon_value=get_custom_icon(icon),
        text="",
    )
    op.align_mode = "ALIGN"

    if axis == "CENTER":
        center = True
        axis = ("X", "Y", "Z")
    for i in axis:
        value = "MIN" if len(i) >= 2 else "MAX"
        if center:
            value = "CENTER"
        setattr(op, f"align_{i[-1].lower()}_method", value)
    a = {i[-1] for i in axis}
    row.label(text=str(a))
    op.align_mode = "ALIGN"
    op.align_location = True
    op.align_location_axis = a


def get_center_align(layout, icon):
    operator = layout.operator(AlignObject.bl_idname,
                               icon_value=get_custom_icon(icon),
                               text="",
                               )
    operator.align_mode = "ALIGN"
    operator.align_location = True
    for i in AXIS:
        setattr(operator, f"align_{i.lower()}_method", "CENTER")
    return operator


def draw_distribution_x(layout, x):
    op = layout.operator(AlignObject.bl_idname,
                         text="Distribution",
                         icon_value=get_custom_icon("Align_Distribution_X"))
    op.align_mode = "DISTRIBUTION"
    op.distribution_sorted_axis = str(AXIS.index(x[-1]))
    op.align_location_axis = {x[-1]}
    op.align_location = True


def draw_distribution_y(layout, y):
    op = layout.operator(AlignObject.bl_idname,
                         text="Distribution",
                         icon_value=get_custom_icon("Align_Distribution_Y"))
    op.align_mode = "DISTRIBUTION"
    op.distribution_sorted_axis = str(AXIS.index(y[-1]))
    op.align_location_axis = {y[-1]}
    op.align_location = True


def draw_distribution(layout, direction):
    (x, _), (y, _) = direction
    draw_distribution_x(layout, x)
    draw_distribution_y(layout, y)


def draw_center_align(layout, direction):
    (x, _), (y, _) = direction

    get_center_align(layout, "Align_Center_X").align_location_axis = {y[-1]}
    get_center_align(layout, "Align_Center_Y").align_location_axis = {x[-1]}


def draw_ground(layout, draw_key=False):
    from bpy.app.translations import pgettext_iface
    text = pgettext_iface("Ground")
    if draw_key:
        text = "(G)" + text
    op = layout.operator(AlignObject.bl_idname,
                         text=text,
                         icon="IMPORT")
    op.align_mode = "GROUND"
    op.ground_down_mode = "ALL"
    op.ground_plane_mode = "GROUND"
    op.align_location_axis = {"Z"}
    op.align_location = True


def draw_fall(layout, draw_key=False):
    from bpy.app.translations import pgettext_iface
    text = pgettext_iface("Fall")
    if draw_key:
        text = "(F)" + text
    op = layout.operator(AlignObject.bl_idname,
                         text=text,
                         icon="AXIS_TOP")
    op.align_mode = "GROUND"
    op.ground_down_mode = "ALL"
    op.ground_plane_mode = "RAY_CASTING"
    op.align_location_axis = {"Z"}
    op.align_location = True


def draw_cursor_active_original(layout, row=False):
    if row:
        layout = layout.row(align=True)
    draw_world(layout, row)
    draw_active(layout, row)
    draw_cursor(layout, row)


def draw_world(layout, icon_only):
    op = layout.operator(AlignObject.bl_idname,
                         text="" if icon_only else "World Original",
                         icon="OBJECT_ORIGIN")
    op.align_mode = "ORIGINAL"
    op.align_location = True


def draw_active(layout, icon_only):
    op = layout.operator(AlignObject.bl_idname,
                         text="" if icon_only else "Active",
                         icon="RESTRICT_SELECT_OFF")

    op.align_mode = "ACTIVE"
    op.align_location = True


def draw_cursor(layout, icon_only):
    op = layout.operator(AlignObject.bl_idname,
                         text="" if icon_only else "Cursor",
                         icon="PIVOT_CURSOR")
    op.align_mode = "CURSOR"
    op.align_location = True


def draw_right(layout, context):
    direction = screen_relevant_direction_3d_axis(context)
    row = layout.row(align=True)
    column = row.column(align=True)

    column.scale_y = column.scale_x = 1.51495
    draw_center_align(column, direction)

    # three 分布 地面
    col = row.column(align=True)
    draw_distribution(col, direction)
    draw_ground(col)

    # original cursor active original
    col = row.column(align=True)
    draw_cursor_active_original(col)
