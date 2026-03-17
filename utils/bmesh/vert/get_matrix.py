import bmesh
from bmesh.types import BMesh
from mathutils import Matrix

from ...math import location_to_matrix, from_x_z_vector_get_matrix, check_tow_direction_vector_perpendicular


def from_vert_get_matrix(bm: BMesh, obj_mat: Matrix = Matrix()) -> Matrix | None:
    from .. import get_link_verts, from_bmesh_verts_get_normal_and_loc
    from .. import get_max_difference_length_link_vert
    select_vert = [i for i in bm.verts if i.select]  # 选择的顶点
    is_only_one = len(select_vert) == 1  # 仅选择了一个顶点
    if is_only_one:
        # 处理只选择了一个顶点的情况
        to_vert = select_vert[0]  # 活动项和这个顶点是一样的
        loc_mat = location_to_matrix(to_vert.co)  # 活动点坐标
        link_edges = to_vert.link_edges
        link_faces = to_vert.link_faces

        if len(link_faces) == 0:
            """相邻没有面,只有线"""
            if len(link_edges) == 1:
                """
                选择的顶点只链接了一条边
                就是一条边的末尾
                仅固定Z方向
                会出现每次计算旋转值不同
                """
                bv = get_link_verts(to_vert)[0]  # 顶点B
                x = -to_vert.co

                # 尝试找链接顶点的链接顶点,就是第三个顶点,如果找到了就拿来当X轴
                tc = get_link_verts(bv, exclude=[to_vert])
                if tc:
                    tv = tc[0]
                    x = to_vert.co - tv.co

                z = bv.co - to_vert.co
                rot_matrix = from_x_z_vector_get_matrix(x, z)
                om = loc_mat @ rot_matrix
                return obj_mat @ om
            elif len(link_edges) == 2:
                """
                选择点相邻两条边
                
                1.如果相邻的两条边是平行的
                    Z轴取顶点的法线
                    X轴取指向一个顶点的矢量
                    仅固定X方向
                
                2.如果相邻的两条边不是平行的
                    那么就创建一个临时的三角面
                    使用创建的面的法线作为Z
                    再从面的中心指向顶点作为X
                    可以计算出一个指定的方向
                """
                a, b = get_link_verts(to_vert)

                av, bv = to_vert.co - a.co, to_vert.co - b.co  # 两个顶点的矢量
                if check_tow_direction_vector_perpendicular(av, bv):
                    rot_matrix = from_x_z_vector_get_matrix(to_vert.normal, av)
                    om = loc_mat @ rot_matrix
                    return obj_mat @ om
                else:
                    tm = bmesh.new()  # 创建一个临时的BMesh对象,用来创建一个三角形,然后按这个三角形的法线和位置来获取旋转矩阵
                    tm.verts.new(a.co)
                    tm.verts.new(b.co)
                    tm.verts.new(to_vert.co)
                    tm.verts.ensure_lookup_table()

                    tm.faces.new(tm.verts)
                    tm.faces.ensure_lookup_table()
                    tm.normal_update()
                    face = tm.faces[0]

                    from .. import from_verts_get_loc
                    x = from_verts_get_loc(tm.verts) - to_vert.co
                    z = face.normal

                    tm.free()
                    rot_matrix = from_x_z_vector_get_matrix(x, z)

                    om = loc_mat @ rot_matrix
                    return obj_mat @ om
            elif len(link_edges) >= 3:
                """
                超过3条相邻的边
                这个形状很奇怪,但是还是做一下对齐吧
                
                将多个相邻边法线计算作为Z方向
                然后将相差最多的相邻点作为X方向
                """
                tv = get_max_difference_length_link_vert(to_vert)  # 找个距离相差最大的点

                lvl = get_link_verts(to_vert)
                _, normal = from_bmesh_verts_get_normal_and_loc(lvl)

                x = tv.co - to_vert.co
                z = normal
                rot_matrix = from_x_z_vector_get_matrix(x, z)
                om = loc_mat @ rot_matrix
                return obj_mat @ om
            else:
                """
                  一个孤立的顶点,旋转取物体的矩阵
                """
                return obj_mat @ loc_mat
        elif len(link_faces) == 1:
            """
            相邻一个面
            直接取点法向作为Z
            选第一个相邻点作为X
            """
            z = to_vert.normal
            x = to_vert.co - get_link_verts(to_vert)[0].co

            rot_matrix = from_x_z_vector_get_matrix(x, z)
            om = loc_mat @ rot_matrix
            return obj_mat @ om

        """其它情况就不做过多判断了
        直接使用差最大的那条边
        """
        z = to_vert.normal

        tv = get_max_difference_length_link_vert(to_vert)  # 找个距离相差最大的点
        x = tv.co - to_vert.co

        rot_matrix = from_x_z_vector_get_matrix(x, z)
        om = loc_mat @ rot_matrix
        return obj_mat @ om
    elif len(select_vert) >= 2:  # 选择了超过两个顶点
        co_vector, _ = from_bmesh_verts_get_normal_and_loc(select_vert)  # 所选顶点的中心点
        a = select_vert[0].co  # 取第一个1
        x = co_vector - a
        z = select_vert[-1].normal  # 最后一个顶点的法向
        rot_matrix = from_x_z_vector_get_matrix(x, z)
        om = location_to_matrix(co_vector) @ rot_matrix
        return obj_mat @ om
    return None
