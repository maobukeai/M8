import bmesh
import bpy
import numpy as np
from bmesh.types import BMesh, BMVert, BMFace, BMEdge, BMElemSeq
from mathutils import Vector, Matrix


def from_bm_get_active_location(bm: BMesh, matrix: Matrix) -> Vector:
    """从Bmesh获取活动位置
    如果有活动项,则反回活动项位置
    没有则反回选择的中心位置
    """
    active = bm.select_history.active
    if type(active) == BMVert:
        return matrix @ active.co
    elif type(active) == BMEdge:
        a, b = active.verts[0], active.verts[1]
        return matrix @ ((a.co + b.co) / 2)
    elif type(active) == BMFace:
        verts = [v.co for v in bm.select_history.active.verts[:]]
        return matrix @ (sum(verts, Vector()) / len(verts))
    else:
        a, b = from_bmesh_get_selected_max_min_location(bm, matrix)
        return (a + b) / 2


def from_bmesh_get_selected_max_min_location(bm: BMesh, matrix: Matrix) -> tuple[Vector, Vector]:
    """从Bmesh获取已选择的最大最小坐标
    return (max, min)
    """
    select_verts = [matrix @ v.co for v in bm.verts if v.select]
    return Vector(np.max(select_verts, axis=0)), Vector(np.min(select_verts, axis=0))


def from_bmesh_get_bound_box(bm: BMesh) -> list[Vector]:
    """获取边界框"""
    from ..bound import from_vector_get_bound_box
    cbb = bm.calc_bounding_box()
    return from_vector_get_bound_box(cbb)


def from_bmesh_active_select_get_matrix(bm: BMesh, obj: bpy.types.Object) -> Matrix:
    """从Bmesh中获取活动项的矩阵
    在对齐原点时使用

    每个模式计算方法都不同
    每个选择模式都有活动项计算方式,还有选择项计算方式
    """
    from ..math import location_to_matrix
    from .vert.get_matrix import from_vert_get_matrix
    from .edge.get_matrix import from_edge_get_matrix
    from .face.get_matrix import from_face_get_matrix

    mode = bm.select_mode

    obj_mat = obj.matrix_world.copy()

    select_vert = [i for i in bm.verts if i.select]
    select_edge = [i for i in bm.edges if i.select]
    select_faces = [i for i in bm.faces if i.select]
    if len(select_faces) == 1:
        return from_face_get_matrix(bm, obj_mat)
    elif len(select_edge) == 1:
        return from_edge_get_matrix(bm, obj_mat)

    # 前提条件,需要确保只有一个模式
    if len(mode) == 1:
        if "VERT" in mode:
            return from_vert_get_matrix(bm, obj_mat)
        elif "EDGE" in mode:
            return from_edge_get_matrix(bm, obj_mat)
        elif "FACE" in mode:
            return from_face_get_matrix(bm, obj_mat)

    # 其它情况 选择了多个网格模式 eg 选择了边和顶点模式
    """
    TODO 多个选择模式下的内容
    """
    sel = [i for i in bm.verts if i.select]
    if sel:
        loc, _ = from_bmesh_verts_get_normal_and_loc(sel)
        om = location_to_matrix(loc)
        return obj_mat @ om
    return Matrix()


def from_bmesh_verts_get_normal_and_loc(verts: "BMElemSeq[BMVert]") -> tuple[Vector, Vector]:
    """反回多个顶点的平均法线和位置
    """
    vl = len(verts)
    normal = Vector()
    loc = Vector()
    for v in verts:
        normal += v.normal
        loc += v.co

    normal /= vl
    loc /= vl
    return loc, normal


def from_verts_get_loc(verts: "BMElemSeq[BMVert]") -> Vector:
    """反回多个顶点的平均位置"""
    loc = Vector()
    for v in verts:
        loc += v.co
    loc /= len(verts)
    return loc


def from_bmesh_face_get_optimal_edge(face: bmesh.types.BMFace) -> bmesh.types.BMEdge:
    """通过面获取最"""
    edge, angle_diff = None, 999
    fl = len(face.loops)
    for index, loop in enumerate(face.loops):
        a, b = loop, face.loops[0] if index == fl - 1 else face.loops[index + 1]
        ad = abs(a.calc_angle() - b.calc_angle())
        if ad < angle_diff:
            edge = loop.edge
            angle_diff = ad
    if edge is None:
        Exception("没有找到合适的边")
    return edge


def check_bmesh_selected_vert(bm: BMesh) -> bool:
    """检查bmesh是否有选中的顶点"""
    for v in bm.verts:
        if v.select:
            return True
    return False


def get_link_verts(element: BMVert | BMEdge | BMFace, exclude=[]) -> list[BMVert]:
    """获取相邻的顶点
    如果不在排除列表中
    """
    if isinstance(element, BMVert):
        if exclude:
            return [i.verts[0] if i.verts[0] != element else i.verts[1] for i in element.link_edges if
                    i.verts[0] not in exclude and i.verts[1] not in exclude]
        return [i.verts[0] if i.verts[0] != element else i.verts[1] for i in element.link_edges]
    elif isinstance(element, BMEdge):
        if not exclude:
            Exception(f"输入的是一个边,但是没有排除的顶点 {exclude}")
        return element.verts[0] if (element.verts[0] not in exclude) else element.verts[1]
    elif isinstance(element, BMFace):
        # TODO()
        ...
    return []


def get_max_difference_length_link_vert(vert: BMVert) -> BMVert:
    """获取所输入顶点相邻的最大相差距离的顶点
    就是输入顶点的相邻点
    那个和输入顶点位置差最大就反回那个

    如果多条边长,只有一条边短就反回短的那个
    如果多条边短,只有一条边长,就反回长的那个


    """
    if len(vert.link_edges) == 0:
        Exception(f"输入顶点没有相连的边!! {vert}")

    from ..math import find_max_difference
    length_map = {get_edge_length(e): e for e in vert.link_edges}  # {长度:边}
    diff_length = find_max_difference(list(length_map.keys()))

    if len(length_map) == 1:  # 如果长度都一样会出现错误
        return get_link_verts(vert)[0]

    edge = length_map[diff_length]
    res = edge.verts[0] if (edge.verts[0] != vert) else edge.verts[1]
    return res


def get_edge_length(edge: BMEdge):
    """获取边长"""
    return (edge.verts[0].co - edge.verts[1].co).length


def four_to_three(draw_data: dict) -> dict:
    """
    将四边面转换为三角面
    以便进行绘制
    """
    import bmesh

    verts, sequences = draw_data["faces"]["verts"], draw_data["faces"]["sequences"]

    bm = bmesh.new(use_operators=True)
    for index, v in enumerate(verts):
        v = bm.verts.new(v)
        v.index = index
    bm.verts.ensure_lookup_table()
    for s in sequences:
        vv = list((bm.verts[i] for i in s))
        bm.faces.new(vv)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    sequences = [[v.index for v in f.verts] for f in bm.faces]
    draw_data["faces"]["sequences"] = sequences
    bm.free()
    return draw_data


def from_bmesh_get_draw_info(bm: BMesh) -> dict:
    """从bmesh里面获取绘制的信息
    在绘制插件时使用"""
    info = {
        "faces": {"verts": [], "sequences": []}
    }

    for face in bm.faces:
        sequences = []
        for v in face.loops:
            co = Vector(v.vert.co)
            if co not in info["faces"]["verts"]:
                info["faces"]["verts"].append(co)
            index = info["faces"]["verts"].index(co)
            sequences.append(index)
        info["faces"]["sequences"].append(sequences)
    return info


def get_furthest_two_vertices(selected_verts: "[BMVert]") -> "[BMVert] | None":
    """获取两个最远端顶点"""
    if len(selected_verts) < 2:
        print("请至少选择两个顶点")
        return None
    else:
        max_distance_sq = 0.0
        pair = None

        # 遍历所有顶点对
        for i in range(len(selected_verts)):
            v1 = selected_verts[i]
            for j in range(i + 1, len(selected_verts)):
                v2 = selected_verts[j]
                # 计算平方距离
                distance_sq = (v1.co - v2.co).length_squared
                if distance_sq > max_distance_sq:
                    max_distance_sq = distance_sq
                    pair = (v1, v2)
        # if pair:
        #     # 计算实际距离
        #     distance = max_distance_sq ** 0.5
        #     print(f"最远点对：\n顶点A: {pair[0].co}\n顶点B: {pair[1].co}\n距离: {distance}")
        return pair


def get_endpoints_of_consecutive_vertices(selected_verts: [BMVert]) -> "[BMVert,BMVert]|None":
    """获取连续顶点的端点
    反回两个端点
    如果不是连续的将会反回None
    """
    endpoints = [None, None]

    for v in selected_verts:
        if len(v.link_edges) == 0:  # 找到一个孤立顶点,不会有连续的顶点路径
            return None
        select_v = [e for e in v.link_edges if e.select]  # 相邻的选择边
        sl = len(select_v)
        if sl == 1:
            edge = select_v[0]
            va, vb = edge.verts

            ov = vb if va == v else va  # 另外一个顶点

            if ov in selected_verts:  # 另外一个顶点在所选里面
                if endpoints == [None, None]:
                    endpoints[0] = v
                elif endpoints[1] is None:
                    endpoints[1] = v
                elif endpoints[0] is not None and endpoints[1] is not None:
                    # 找到了第三个端点
                    return None
            else:
                return None
        elif sl == 2:
            ...  # 两个相邻的不需要检查
        else:
            # 相领的选择边大于3,一定不是连续的
            return None

    if (endpoints[0] is not None) and (endpoints[1] is not None):
        return endpoints
    return None


def get_pair_edge_from_select_history(bm: bmesh.types.BMesh) -> "(bmesh.types.BMVert,bmesh.types.BMVert)|None":
    """从所选历史中获取对边"""
    verts = [h for h in bm.select_history if isinstance(h, bmesh.types.BMVert)]
    if len(verts) >= 2:
        return verts[-2:]
    return None
