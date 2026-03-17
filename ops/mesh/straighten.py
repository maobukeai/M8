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
        """需要选择3个或者3个以上顶点"""
        is_mesh = context.mode == "EDIT_MESH"

        if is_mesh:
            bm = bmesh.from_edit_mesh(context.object.data)

            for face in bm.faces:
                if face.select:
                    return False

            count = 0
            for h in bm.select_history:
                if isinstance(h, bmesh.types.BMVert):
                    count += 1
                elif isinstance(h, bmesh.types.BMEdge):
                    count += 2
                elif isinstance(h, bmesh.types.BMFace):
                    return False

            if count >= 3:
                bm.free()
                return True
            count = 0
            for v in bm.verts:
                if v.select:
                    count += 1
                    if count >= 3:
                        bm.free()
                        return True
        return False

    def execute(self, context):
        import bmesh

        obj = context.object
        matrix = obj.matrix_world

        bm = bmesh.from_edit_mesh(obj.data)

        selected_verts = [v for v in bm.verts if v.select]

        pair = get_pair_edge_from_select_history(bm)

        if pair is None:
            pair = get_endpoints_of_consecutive_vertices(selected_verts)

        if pair is None:
            pair = get_furthest_two_vertices(selected_verts)
            print("获取两个最远端顶点")

        hub = Hub3DItem()

        continuously_edges = get_continuously_edges_list(bm)
        if continuously_edges and len(continuously_edges) > 1:  # 处理连续边的情况
            for edges in continuously_edges:
                verts = []
                for e in edges:
                    if e.verts[0] not in verts:
                        verts.append(e.verts[0])
                    if e.verts[1] not in verts:
                        verts.append(e.verts[1])
                pair = get_furthest_two_vertices(verts)
                straighten_single_strip(matrix, pair, verts, hub)
        elif pair:
            straighten_single_strip(matrix, pair, selected_verts, hub)
        else:
            self.report({"INFO"}, pgettext_iface("Locate point not found"))

        hub_3d(self.bl_idname, hub, timeout=1, area_restrictions=hash(context.area))

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}
