from bmesh.types import BMesh
from mathutils import Matrix

from ...math import location_to_matrix, from_x_z_vector_get_matrix


def from_face_get_matrix(bm: BMesh, obj_mat: Matrix = Matrix()):
    from .. import from_bmesh_verts_get_normal_and_loc, from_bmesh_face_get_optimal_edge

    select_vert = [i for i in bm.verts if i.select]
    select_faces = [i for i in bm.faces if i.select]

    is_only_one = len(select_faces) == 1  # 仅选择了一个顶点

    if is_only_one:
        active = select_faces[-1]
        edge = from_bmesh_face_get_optimal_edge(active)
        loc, _ = from_bmesh_verts_get_normal_and_loc(active.verts)
        l_loc, _ = from_bmesh_verts_get_normal_and_loc(edge.verts)  # 选中面的一个边作为方向
        rot_matrix = from_x_z_vector_get_matrix(loc - l_loc, active.normal)

        om = location_to_matrix(loc) @ rot_matrix

        return obj_mat @ om
    else:
        co_vector, _ = from_bmesh_verts_get_normal_and_loc(select_vert)  # 所选顶点的中心点
        x = select_faces[0].normal
        z = select_faces[-1].normal
        rot_matrix = from_x_z_vector_get_matrix(x, z)
        om = location_to_matrix(co_vector) @ rot_matrix
        return obj_mat @ om
