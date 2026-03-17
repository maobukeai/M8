import bpy
from bpy.app.translations import pgettext_iface

from ...utils import get_panel_bl_idname
from ...utils.icon import get_custom_icon
from ...utils.view import screen_relevant_direction_3d_axis


def draw_hv_align(align, layout, horizontal_axis, vertical_axis):
    from ...ops.mesh.straighten import Straighten
    column = layout.column(align=True)
    for text, icon, axis in [
        ("Horizontal", "Align_Center_Y", horizontal_axis),
        ("Vertical", "Align_Center_X", vertical_axis),
    ]:
        row = column.row(align=True)
        row.label(text="", icon_value=get_custom_icon(icon))
        row.separator()
        ops = row.operator(align.bl_idname, text=pgettext_iface(text))
        ops.align_mode = "ALIGN"
        ops.align_location_axis = {axis}
        setattr(ops, f"align_{axis.lower()}_method", "CENTER")

    row = column.row(align=True)
    row.label(text="", icon="IPO_LINEAR")
    row.separator()
    row.operator(Straighten.bl_idname)


def get_align_active_icon() -> str:
    mesh_select_mode = bpy.context.scene.tool_settings.mesh_select_mode[:]
    if mesh_select_mode == (True, False, False):
        icon = "VERTEXSEL"
    elif mesh_select_mode == (False, True, False):
        icon = "EDGESEL"
    elif mesh_select_mode == (False, False, True):
        icon = "FACESEL"
    else:
        icon = "RESTRICT_SELECT_OFF"
    return icon


def draw_other_align(align, layout, horizontal_axis, vertical_axis):
    column = layout.column(align=True)
    for icon, align_mode in [
        ("CURSOR", "CURSOR"),
        ("OBJECT_ORIGIN", "ORIGINAL"),
        (get_align_active_icon(), "ACTIVE"),
    ]:
        row = column.row(align=True)
        row.label(text="", icon=icon)
        row.separator()
        ops = row.operator(align.bl_idname, text=pgettext_iface("Horizontal"))
        ops.align_mode = align_mode
        ops.align_location_axis = {horizontal_axis}
        setattr(ops, f"align_{horizontal_axis.lower()}_method", "CENTER")

        ops = row.operator(align.bl_idname, text=pgettext_iface("Vertical"))
        ops.align_mode = align_mode
        ops.align_location_axis = {vertical_axis}
        setattr(ops, f"align_{vertical_axis.lower()}_method", "CENTER")


def draw_right(layout):
    row = layout.row(align=True)
    from ...ops.align.align_mesh import AlignMesh

    (x, x_), (y, y_) = screen_relevant_direction_3d_axis(bpy.context)
    horizontal_axis = x.upper().replace("-", "")  # 水平
    vertical_axis = y.upper().replace("-", "")  # 垂直

    draw_other_align(AlignMesh, row.column(align=True), horizontal_axis, vertical_axis)
    rc = row.column(align=True)
    draw_hv_align(AlignMesh, rc, horizontal_axis, vertical_axis)
