import bpy
from ..utils.i18n import _T


def draw_edge_flow(context, layout):
    col = layout.column(align=True)
    if hasattr(bpy.ops.mesh, "set_edge_flow"):
        col.operator("mesh.set_edge_flow", text=_T("平滑边缘流"))
    if hasattr(bpy.ops.mesh, "set_edge_linear"):
        col.operator("mesh.set_edge_linear", text=_T("线性拉直"))
    if hasattr(bpy.ops.mesh, "set_edge_curve"):
        col.operator("mesh.set_edge_curve", text=_T("曲线边缘流"))


def draw_edge_flow_header(context, layout):
    layout.label(text="EdgeFlow", icon="MOD_SMOOTH")


REQUIRES_ADDON = [
    {
        "identifier": "EdgeFlow",
        "url": "https://extensions.blender.org/add-ons/edgeflow/",
        "draw": draw_edge_flow,
        "draw_header": draw_edge_flow_header,
    }
]
