from bmesh.types import BMesh
from mathutils import Matrix
from mathutils.geometry import intersect_point_line

from ...math import location_to_matrix, from_x_z_vector_get_matrix

DEBUG_GET_MATRIX = False

def print_debug(*args):
    if DEBUG_GET_MATRIX:
        print(", ".join([str(i) for i in args]))


def from_edge_get_matrix(bm: BMesh, obj_mat: Matrix = Matrix()):
    from .. import from_bmesh_verts_get_normal_and_loc

    select_edges = [i for i in bm.edges if i.select]
    select_vert = [i for i in bm.verts if i.select]

    active = bm.select_history.active

    is_only_one = active and len(select_edges) == 1  # 仅选择了一个边

    if is_only_one:
        active_edge = select_edges[0]
        if len(active_edge.link_faces) == 0:
            print_debug("仅选择了一个边 独立的一个边,避免抽搐")
            loc, normal = from_bmesh_verts_get_normal_and_loc(active.verts)
            om = location_to_matrix(loc)
            return obj_mat @ om
        else:
            print_debug("仅选择了一个边 有相连的边")
            loc, normal = from_bmesh_verts_get_normal_and_loc(select_vert)
            to_a = loc - select_vert[0].co
            f_loc, _ = from_bmesh_verts_get_normal_and_loc(active_edge.link_faces[0].verts)
            to_b = loc - f_loc
            rot_matrix = from_x_z_vector_get_matrix(to_b, to_a, )
            om = location_to_matrix(loc) @ rot_matrix
            v = loc, to_b
            return obj_mat @ om
    elif len(select_edges) == 2:
        a, b = select_edges
        if len(a.link_faces) == 0 and len(b.link_faces) == 0:
            print_debug("选择了两个边 但是都没有相连的面")
            loc, _ = from_bmesh_verts_get_normal_and_loc([v for e in select_edges for v in e.verts])
            select_edge = select_edges[0]
            va, vb = select_edge.verts
            point_a, _ = intersect_point_line(loc, va.co, vb.co)

            rot_matrix = from_x_z_vector_get_matrix(va.co - vb.co, point_a)

            om = location_to_matrix(loc) @ rot_matrix
            return obj_mat @ om
        else:
            print_debug("选择了两个边 各有相连的面")
            loc, _ = from_bmesh_verts_get_normal_and_loc(select_vert)  # 所选顶点的中心点
            av, _ = from_bmesh_verts_get_normal_and_loc(a.verts)  # 所选顶点的中心点
            bv, _ = from_bmesh_verts_get_normal_and_loc(b.verts)  # 所选顶点的中心点
            al = loc - av
            bl = loc - b.verts[0].co
            rot_matrix = from_x_z_vector_get_matrix(bl, al)
            om = location_to_matrix(loc) @ rot_matrix
            return obj_mat @ om
    co_vector, _ = from_bmesh_verts_get_normal_and_loc(select_vert)  # 所选顶点的中心点
    a = select_vert[0].co  # 取第一个1
    x = co_vector - a
    z = select_vert[-1].normal  # 最后一个顶点的法向
    rot_matrix = from_x_z_vector_get_matrix(x, z)
    om = location_to_matrix(co_vector) @ rot_matrix
    return obj_mat @ om
