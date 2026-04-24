import bmesh
import bpy
import mathutils
from bpy.app.translations import pgettext_iface

from ...hub import hub_3d
from ...hub.view_3d import Hub3DItem
from ...utils import get_operator_bl_idname
from ...utils.bmesh import (
    get_furthest_two_vertices,
    get_endpoints_of_consecutive_vertices,
    get_pair_edge_from_select_history,
)
from ...utils.bmesh.edge import get_continuously_edges_list


def straighten_single_strip(matrix, pair, verts, hub):
    """拉直单条"""
    a, b = pair
    hub.edge_from_vert(a, b, matrix)
    for v in verts:
        if v not in pair:
            co, f = mathutils.geometry.intersect_point_line(v.co, a.co, b.co)

            hub.edge_from_vert(co, v, matrix, color=[0.700148, 0.435230, 0.800614, 1.000000])
            hub.vert(co, matrix, color=[8, 7, 1, 1])
            hub.vert(v, matrix, color=[0.800819, 0.374183, 0.766801, 1.000000])

            v.co = co


class Straighten(bpy.types.Operator):
    bl_idname = get_operator_bl_idname("straighten")
    bl_label = "Straighten"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """编辑模式下选中 3 个或以上顶点即可使用"""
        if context.mode != "EDIT_MESH":
            return False
        obj = context.object
        if not obj or obj.type != 'MESH':
            return False
        try:
            bm = bmesh.from_edit_mesh(obj.data)
            count = sum(1 for v in bm.verts if v.select)
            return count >= 3
        except Exception:
            return False

    def execute(self, context):
        obj = context.object
        matrix = obj.matrix_world

        bm = bmesh.from_edit_mesh(obj.data)

        selected_verts = [v for v in bm.verts if v.select]

        pair = get_pair_edge_from_select_history(bm)

        if pair is None:
            pair = get_endpoints_of_consecutive_vertices(selected_verts)

        if pair is None:
            pair = get_furthest_two_vertices(selected_verts)

        hub = Hub3DItem()

        continuously_edges = get_continuously_edges_list(bm)
        # >= 1 条连续边链都处理（原来 > 1 会跳过单条链的情况）
        if continuously_edges:
            for edges in continuously_edges:
                verts = []
                for e in edges:
                    if e.verts[0] not in verts:
                        verts.append(e.verts[0])
                    if e.verts[1] not in verts:
                        verts.append(e.verts[1])
                if len(verts) < 3:
                    continue
                strip_pair = get_furthest_two_vertices(verts)
                if strip_pair:
                    straighten_single_strip(matrix, strip_pair, verts, hub)
        elif pair:
            straighten_single_strip(matrix, pair, selected_verts, hub)
        else:
            self.report({"INFO"}, pgettext_iface("Locate point not found"))

        hub_3d(self.bl_idname, hub, timeout=1, area_restrictions=hash(context.area))

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}
