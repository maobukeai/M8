# -*- coding: utf-8 -*-
"""
M8 智能法向传递系统 (Smart Normal Transfer)
通过生成对齐的理想几何代理体（平面/柱面/平滑曲面），结合专属顶点组与数据传递修改器（DATA_TRANSFER），
彻底解决硬表面建模中三角扇面极点、圆盘顶面与倒角过渡处的黑斑、阴影拉扯（Shading Artifacts）问题。
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from ...utils.logger import get_logger
from ...utils.i18n import _T

logger = get_logger()

HELPER_COLLECTION_NAME = "_M8_Normal_Helpers"
MODIFIER_PREFIX = "M8_Normal"
VG_PREFIX = "VG_M8_Normal"


def _hide_collection_in_view_layer(view_layer, col_name, hide=True):
    """在当前视图层中递归查找并设置指定集合的视口显隐状态（大纲眼睛图标）"""
    def _walk(layer_col):
        if layer_col.name == col_name:
            layer_col.hide_viewport = hide
            return True
        for child in layer_col.children:
            if _walk(child):
                return True
        return False

    try:
        if view_layer and hasattr(view_layer, "layer_collection"):
            _walk(view_layer.layer_collection)
    except Exception:
        pass


def _get_or_create_helper_collection(scene):
    """获取或创建专门收纳辅助物体的隐藏集合，默认在视口与大纲中静默隐藏"""
    col = bpy.data.collections.get(HELPER_COLLECTION_NAME)
    if not col:
        col = bpy.data.collections.new(HELPER_COLLECTION_NAME)
        scene.collection.children.link(col)
    col.hide_viewport = True
    col.hide_render = True
    vl = getattr(bpy.context, "view_layer", None)
    if vl:
        _hide_collection_in_view_layer(vl, HELPER_COLLECTION_NAME, hide=True)
    return col


def _extract_boundary_loops(boundary_edges):
    """从给定的一组边界边中提取连续的线环回路列表，返回 [(ordered_verts, is_closed)]"""
    edge_set = set(boundary_edges)
    loops = []
    while edge_set:
        start_edge = edge_set.pop()
        ordered_verts = [start_edge.verts[0]]
        curr_v = start_edge.verts[1]
        is_closed = False
        while True:
            ordered_verts.append(curr_v)
            next_edge = None
            for e in curr_v.link_edges:
                if e in edge_set:
                    next_edge = e
                    break
            if not next_edge:
                break
            edge_set.remove(next_edge)
            curr_v = next_edge.other_vert(curr_v)
            if curr_v == start_edge.verts[0]:
                is_closed = True
                break
        loops.append((ordered_verts, is_closed))
    return loops


def _loop_polygon_area(loop_verts):
    """计算 3D 空间闭合多边形线环所包围的几何面积（基于空间向量叉积）"""
    if len(loop_verts) < 3:
        return 0.0
    total = Vector((0.0, 0.0, 0.0))
    for i in range(len(loop_verts)):
        v1 = loop_verts[i].co
        v2 = loop_verts[(i + 1) % len(loop_verts)].co
        total += v1.cross(v2)
    return total.length * 0.5


def _loop_perimeter(loop_verts):
    """计算线环的几何总物理周长"""
    if len(loop_verts) < 2:
        return 0.0
    p = 0.0
    for i in range(len(loop_verts)):
        v1 = loop_verts[i].co
        v2 = loop_verts[(i + 1) % len(loop_verts)].co
        p += (v2 - v1).length
    return p


def _calculate_ordered_boundary_loop(bm, selected_faces):
    """
    从选中的面集合中提取最外层闭合外边界线环并排序，返回有序的顶点列表。
    当存在内孔（如垫片、环形开孔零件）时，基于 3D 多边形几何面积与总周长双重判据，
    自动过滤内部小开孔，精准锁定包围面积最大的最外层线环。
    """
    face_set = set(selected_faces)
    boundary_edges = []
    for f in face_set:
        for e in f.edges:
            sel_neighbors = sum(1 for neighbor in e.link_faces if neighbor in face_set)
            if sel_neighbors == 1:
                # 过滤布尔切削伴生的微小退化边（长度 < 1e-5）
                if (e.verts[0].co - e.verts[1].co).length > 1e-5:
                    boundary_edges.append(e)

    if not boundary_edges:
        return []

    loops = _extract_boundary_loops(boundary_edges)
    if not loops:
        return []

    closed_loops = [l for l, is_closed in loops if is_closed]
    if closed_loops:
        # 优先选取包围几何面积与周长最大的最外圈线环（杜绝高密细分内孔误选）
        raw_loop = max(closed_loops, key=lambda l: (_loop_polygon_area(l), _loop_perimeter(l)))
    else:
        # 若未闭合（开放边界片），选取物理周长最长的线环
        raw_loop = max(loops, key=lambda x: _loop_perimeter(x[0]))[0]

    # 清理偶发的布尔容差共位点
    clean_loop = []
    for v in raw_loop:
        if not clean_loop or (v.co - clean_loop[-1].co).length > 1e-5:
            clean_loop.append(v)
    return clean_loop


def _align_helper_normals_to_target(bm_helper, bm_target, selected_faces, flip_normal=False):
    """
    统一法向对齐算法（多面面积加权点积多数投票）：
    基于 BVH 树加速近邻点采样与多数投票，使辅助几何代理体的法向朝向与原网格选区表面 100% 保持一致，
    彻底消除内凹曲面、管道内壁、局部圆弧或三角消解导致的法向反向现象；
    同时响应 flip_normal 参数，支持用户在需要时一键反转法向。
    """
    if not bm_helper.faces or not selected_faces:
        return

    # 1. 确保辅助体内部所有面法向朝向一致
    try:
        bmesh.ops.recalc_face_normals(bm_helper, faces=list(bm_helper.faces))
    except Exception:
        pass
    bm_helper.faces.ensure_lookup_table()
    for f in bm_helper.faces:
        f.normal_update()

    # 2. 构建目标选区的 BVH 树加速精准表面法线采样
    try:
        target_verts_co = [v.co for v in bm_target.verts]
        target_polys = [[v.index for v in f.verts] for f in selected_faces]
        bvh = BVHTree.FromPolygons(target_verts_co, target_polys)
    except Exception:
        bvh = None

    weighted_dot_sum = 0.0
    valid_face_count = 0

    if bvh:
        for hf in bm_helper.faces:
            h_center = hf.calc_center_median()
            loc, norm, idx, dist = bvh.find_nearest(h_center)
            if loc is not None and norm is not None and norm.length > 1e-4:
                area = hf.calc_area()
                weighted_dot_sum += area * hf.normal.dot(norm)
                valid_face_count += 1

    if not bvh or valid_face_count == 0:
        for hf in bm_helper.faces:
            h_center = hf.calc_center_median()
            closest_f = min(selected_faces, key=lambda sf: (sf.calc_center_median() - h_center).length_squared)
            area = hf.calc_area()
            weighted_dot_sum += area * hf.normal.dot(closest_f.normal)

    # 3. 多数投票判断全局朝向：若加权点积为负，说明辅助体整体朝向与原模型选区表面相反，必须翻转
    should_flip = (weighted_dot_sum < 0.0)
    if flip_normal:
        should_flip = not should_flip

    if should_flip:
        for f in bm_helper.faces:
            f.normal_flip()

    bm_helper.faces.ensure_lookup_table()
    for f in bm_helper.faces:
        f.normal_update()


def _cluster_faces_into_islands(bm, selected_faces, max_dihedral_angle=None):
    """
    将选中的面按拓扑连通性与可选的二面角阈值聚类为独立的面岛列表。
    若指定 max_dihedral_angle（度），则当两相邻面法向夹角超过该阈值时（或两面间为硬表面标记边/Sharp Edge），
    自动将其拆分为不同岛屿，使复杂硬表面的各个不同朝向折面（如 45° 倒角、90° 侧板）分别获得独立专属代理。
    """
    face_set = set(selected_faces)
    visited = set()
    islands = []
    cos_thresh = math.cos(math.radians(max_dihedral_angle)) if max_dihedral_angle is not None else None

    for f in selected_faces:
        if f in visited:
            continue
        island = []
        stack = [f]
        visited.add(f)
        while stack:
            curr = stack.pop()
            island.append(curr)
            for e in curr.edges:
                if cos_thresh is not None and not e.smooth:
                    continue
                for neighbor in e.link_faces:
                    if neighbor in face_set and neighbor not in visited:
                        if cos_thresh is not None:
                            if curr.normal.dot(neighbor.normal) < cos_thresh:
                                continue
                        visited.add(neighbor)
                        stack.append(neighbor)
        islands.append(island)
    return islands


def _build_planar_helper_mesh(bm_target, selected_faces, center=None, avg_norm=None, max_dihedral_angle=35.0):
    """
    针对平面/圆盘区域构建完美平整的单面代理几何体。
    自适应支持多岛屿（Multi-Island）与跨折角多折面（Dihedral Clustering）：
    自动聚类分离的面岛与不同朝向的折面，为每个独立平面生成专属投影代理；
    凹多边形与复杂布尔切削面板自动验证并安全兜底至 Delaunay triangle_fill 或 Bounding Quad；
    代理面严格使用 Flat Shading 保证垂直无渐变。
    """
    bm_helper = bmesh.new()
    islands = _cluster_faces_into_islands(bm_target, selected_faces, max_dihedral_angle=max_dihedral_angle)
    if not islands:
        return bm_helper

    for island_faces in islands:
        _build_single_planar_geometry(bm_helper, bm_target, island_faces, avg_norm=avg_norm)

    bm_helper.faces.ensure_lookup_table()
    for f in bm_helper.faces:
        f.smooth = False

    return bm_helper


def _build_single_planar_geometry(bm_helper, bm_target, island_faces, avg_norm=None):
    """
    为单组共面岛屿在 bm_helper 中构建平整代理几何体：
    1. 提取最外层轮廓线环并计算平面投影；
    2. 针对凸多边形直接生成 N-gon；
    3. 针对凹多边形与带孔复杂硬表面面板，使用高质量 Delaunay triangle_fill；
    4. 终极极值保底：若存在自交或极端退化边，生成局部 2D 投影外接平整四边形 (Bounding Quad)，
       确保 100% 覆盖原选区并赋予绝对垂直恒定的标准平面法向。
    """
    island_verts = list({v for f in island_faces for v in f.verts})
    if not island_verts:
        return
    island_center = sum((v.co for v in island_verts), Vector((0, 0, 0))) / len(island_verts)
    island_norm = sum((f.normal * f.calc_area() for f in island_faces), Vector((0, 0, 0)))
    if island_norm.length > 1e-6:
        island_norm.normalize()
    elif avg_norm and avg_norm.length > 1e-6:
        island_norm = avg_norm.copy().normalized()
    else:
        island_norm = Vector((0, 0, 1))

    ordered_verts = _calculate_ordered_boundary_loop(bm_target, island_faces)

    if len(ordered_verts) >= 3:
        proj_coords = []
        for v in ordered_verts:
            p = v.co
            dist = (p - island_center).dot(island_norm)
            p_proj = p - (island_norm * dist)
            proj_coords.append(p_proj)

        helper_verts = [bm_helper.verts.new(co) for co in proj_coords]
        bm_helper.verts.ensure_lookup_table()
        island_edges = []
        for i in range(len(helper_verts)):
            try:
                e = bm_helper.edges.new([helper_verts[i], helper_verts[(i + 1) % len(helper_verts)]])
                island_edges.append(e)
            except Exception:
                pass
        bm_helper.edges.ensure_lookup_table()

        face_created = False
        try:
            face = bm_helper.faces.new(helper_verts)
            face.normal_update()
            # 检查新生成的 N-gon 面法向是否有效（非零向量且与目标法向高度一致）
            if face.normal.length > 0.5 and abs(face.normal.dot(island_norm)) > 0.8:
                if face.normal.dot(island_norm) < 0:
                    face.normal_flip()
                face.smooth = False
                face_created = True
            else:
                bm_helper.faces.remove(face)
                bm_helper.faces.ensure_lookup_table()
        except Exception:
            face_created = False

        if not face_created:
            filled_faces = []
            try:
                res_fill = bmesh.ops.triangle_fill(bm_helper, use_beauty=True, edges=island_edges)
                for geom in res_fill.get("geom", []):
                    if isinstance(geom, bmesh.types.BMFace):
                        geom.normal_update()
                        if geom.normal.dot(island_norm) < 0:
                            geom.normal_flip()
                        geom.smooth = False
                        filled_faces.append(geom)
            except Exception:
                pass

            # 极端工况终极保底：若 N-gon 与 triangle_fill 均未能产出有效面，生成该岛屿的平整外接四边面 (Bounding Quad)
            if not filled_faces:
                tangent = island_norm.orthogonal().normalized()
                bitangent = island_norm.cross(tangent).normalized()
                u_vals = [(v.co - island_center).dot(tangent) for v in island_verts]
                v_vals = [(v.co - island_center).dot(bitangent) for v in island_verts]
                min_u, max_u = min(u_vals, default=-1.0), max(u_vals, default=1.0)
                min_v, max_v = min(v_vals, default=-1.0), max(v_vals, default=1.0)
                pad_u = max(1e-3, (max_u - min_u) * 0.05)
                pad_v = max(1e-3, (max_v - min_v) * 0.05)
                min_u -= pad_u
                max_u += pad_u
                min_v -= pad_v
                max_v += pad_v
                q_coords = [
                    island_center + tangent * min_u + bitangent * min_v,
                    island_center + tangent * max_u + bitangent * min_v,
                    island_center + tangent * max_u + bitangent * max_v,
                    island_center + tangent * min_u + bitangent * max_v,
                ]
                q_verts = [bm_helper.verts.new(co) for co in q_coords]
                bm_helper.verts.ensure_lookup_table()
                try:
                    q_face = bm_helper.faces.new(q_verts)
                    if q_face.normal.dot(island_norm) < 0:
                        q_face.normal_flip()
                    q_face.smooth = False
                except Exception:
                    pass
    else:
        # 回退方案：生成贴合 bounding 的正圆形平整面
        radius = max(((v.co - island_center).length for v in island_verts), default=1.0) * 1.05
        tangent = island_norm.orthogonal().normalized()
        bitangent = island_norm.cross(tangent).normalized()
        segments = 32
        circle_coords = []
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            pos = island_center + tangent * (radius * math.cos(angle)) + bitangent * (radius * math.sin(angle))
            circle_coords.append(pos)
        c_verts = [bm_helper.verts.new(co) for co in circle_coords]
        bm_helper.verts.ensure_lookup_table()
        try:
            face = bm_helper.faces.new(c_verts)
            if face.normal.dot(island_norm) < 0:
                face.normal_flip()
            face.smooth = False
        except Exception:
            pass


def _merge_bmesh_into(dst_bm, src_bm):
    """将 src_bm 中的所有顶点与面合并复制进 dst_bm"""
    if not src_bm or not src_bm.faces:
        return
    src_bm.verts.ensure_lookup_table()
    src_bm.faces.ensure_lookup_table()
    vmap = {}
    for v in src_bm.verts:
        vmap[v] = dst_bm.verts.new(v.co.copy())
    dst_bm.verts.ensure_lookup_table()
    for f in src_bm.faces:
        try:
            new_f = dst_bm.faces.new([vmap[v] for v in f.verts])
            new_f.smooth = f.smooth
        except Exception:
            pass
    dst_bm.faces.ensure_lookup_table()


def _classify_face_island(isl, axis_override="AUTO"):
    """
    自适应分析单个独立几何面岛的拓扑与曲率特征，精准分类为:
    - 'PLANAR': 严格平面/圆盘/阶梯环台阶（法向离散度极低且加权点积 > 0.985）
    - 'CYLINDER': 真圆柱筒/局部圆弧槽/沉头孔壁（法向垂直于中轴且截面真圆度 r_ratio <= 1.15）
    - 'SMOOTH_EXTRACT': 自由曲面/变径过渡/倒角曲率带（需要拓扑净化与四边面重构）
    """
    if not isl:
        return "PLANAR"

    # 1. 平面特征检测 (包含面积加权点积与分位数抗噪)
    isl_area = sum(f.calc_area() for f in isl)
    isl_avg_norm = sum((f.normal * f.calc_area() for f in isl), Vector((0, 0, 0)))
    if isl_avg_norm.length > 1e-6:
        isl_avg_norm.normalize()
    else:
        isl_avg_norm = Vector((0, 0, 1))

    face_dot_areas = sorted(
        [(f.normal.dot(isl_avg_norm), f.calc_area()) for f in isl],
        key=lambda x: x[0],
    )
    area_weighted_dot = sum(d * a for d, a in face_dot_areas) / max(1e-9, isl_area)
    cum_area = 0.0
    p05_dot = 1.0
    for d, a in face_dot_areas:
        cum_area += a
        if cum_area >= 0.05 * isl_area:
            p05_dot = d
            break

    if area_weighted_dot > 0.985 and p05_dot > 0.94:
        return "PLANAR"

    # 2. 圆柱特征检测
    detected_axis = _detect_cylinder_axis(isl, axis_override=axis_override)
    dots = [abs(f.normal.dot(detected_axis)) for f in isl]
    mean_dot = sum(dots) / max(1, len(dots))
    dots_sorted = sorted(dots)
    p80_dot = dots_sorted[int(len(dots_sorted) * 0.8)] if dots_sorted else 0.0

    if mean_dot < 0.18 and p80_dot < 0.22:
        is_circular = True
        try:
            import numpy as np
            A = np.array([detected_axis.x, detected_axis.y, detected_axis.z], dtype=np.float64)
            if abs(A[0]) < 0.9:
                U = np.cross(A, [1.0, 0.0, 0.0])
            else:
                U = np.cross(A, [0.0, 1.0, 0.0])
            norm_u = np.linalg.norm(U)
            if norm_u > 1e-6:
                U = U / norm_u
            V = np.cross(A, U)

            side_faces = [f for f in isl if abs(f.normal.dot(detected_axis)) < 0.7]
            target_side = side_faces if side_faces else isl
            side_verts = list({v for f in target_side for v in f.verts})
            if len(side_verts) >= 6:
                coords = np.array([[v.co.x, v.co.y, v.co.z] for v in side_verts], dtype=np.float64)
                u_coords = coords @ U
                v_coords = coords @ V
                u_c = np.mean(u_coords)
                v_c = np.mean(v_coords)
                radii = np.sqrt((u_coords - u_c) ** 2 + (v_coords - v_c) ** 2)
                r_mean = float(np.mean(radii))
                if r_mean > 1e-4:
                    r_ratio = float(np.max(radii) / max(1e-4, np.min(radii)))
                    r_rel_std = float(np.std(radii) / r_mean)
                    if r_ratio > 1.15 and r_rel_std > 0.06:
                        is_circular = False
        except Exception as e:
            logger.debug(f"Island circularity check fallback: {e}")

        if is_circular:
            return "CYLINDER"

    return "SMOOTH_EXTRACT"


def _detect_cylinder_axis(selected_faces, axis_override="AUTO"):
    """
    通过法线外积主成分分析 (Cross-Product PCA) 与协方差矩阵解算出圆柱主轴（支持任意 3D 姿态与任意端盖大小）。
    """
    if axis_override == "X":
        return Vector((1, 0, 0))
    elif axis_override == "Y":
        return Vector((0, 1, 0))
    elif axis_override == "Z":
        return Vector((0, 0, 1))

    if not selected_faces:
        return Vector((0, 0, 1))

    try:
        import numpy as np
        # 过滤布尔切削产生的零面积退化碎面与失真法向
        valid_faces = [f for f in selected_faces if f.calc_area() > 1e-8 and f.normal.length > 0.5]
        target_faces = valid_faces if len(valid_faces) >= 3 else selected_faces

        # 1. 优先采用法线外积主轴分析（侧壁法线两两外积严格平行于中轴，端盖大面积下绝不失真）
        crosses = []
        n_faces = len(target_faces)
        step = max(1, n_faces // 30)
        for i in range(0, n_faces, step):
            for j in range(i + 1, min(i + 15, n_faces)):
                c = target_faces[i].normal.cross(target_faces[j].normal)
                if c.length > 0.15:
                    crosses.append(c.normalized())

        if len(crosses) >= 3:
            C = np.zeros((3, 3))
            for c in crosses:
                cv = np.array([c.x, c.y, c.z], dtype=np.float64)
                C += np.outer(cv, cv)
            evals, evecs = np.linalg.eigh(C)
            best_axis = evecs[:, np.argmax(evals)]
            if np.linalg.norm(best_axis) > 1e-5:
                return Vector((float(best_axis[0]), float(best_axis[1]), float(best_axis[2]))).normalized()

        # 2. 回退方案：传统法向协方差求最小特征值
        normals = np.array([[f.normal.x, f.normal.y, f.normal.z] for f in target_faces])
        areas = np.array([f.calc_area() for f in target_faces])

        M = np.zeros((3, 3))
        for n, a in zip(normals, areas):
            M += a * np.outer(n, n)

        eigenvalues, eigenvectors = np.linalg.eigh(M)
        axis_idx = int(np.argmin(eigenvalues))
        A = eigenvectors[:, axis_idx]
        if np.linalg.norm(A) < 1e-5:
            return Vector((0, 0, 1))
        return Vector((float(A[0]), float(A[1]), float(A[2]))).normalized()
    except Exception as e:
        logger.debug(f"Numpy cylinder axis fit fallback: {e}")
        axes = [Vector((0, 0, 1)), Vector((0, 1, 0)), Vector((1, 0, 0))]
        scores = []
        for ax in axes:
            score = sum((f.normal.dot(ax)) ** 2 for f in selected_faces)
            scores.append((score, ax))
        scores.sort(key=lambda x: x[0])
        return scores[0][1]


def _build_single_cylinder_geometry(
    bm_helper,
    bm_target,
    selected_faces,
    segments=32,
    axis_override="AUTO",
    cap_mode="AUTO",
    arc_mode="AUTO",
):
    """为单组圆柱/圆弧选区在 bm_helper 中构建拟合几何体"""
    base_verts = list({v for f in selected_faces for v in f.verts})
    if len(base_verts) < 3:
        return

    import numpy as np
    coords = np.array([[v.co.x, v.co.y, v.co.z] for v in base_verts])

    # 1. 解算圆柱中轴 A
    A_vec = _detect_cylinder_axis(selected_faces, axis_override)
    A = np.array([A_vec.x, A_vec.y, A_vec.z], dtype=np.float64)
    norm_A = np.linalg.norm(A)
    if norm_A > 1e-6:
        A = A / norm_A
    else:
        A = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    # 2. 构建垂直于中轴的正交基 (U, V)
    if abs(A[0]) < 0.9:
        U = np.cross(A, [1.0, 0.0, 0.0])
    else:
        U = np.cross(A, [0.0, 1.0, 0.0])
    U = U / np.linalg.norm(U)
    V = np.cross(A, U)

    # 3. 过滤出侧面点（过滤端盖法向点），保证半径拟合精确
    side_faces = [f for f in selected_faces if abs(f.normal.dot(A_vec)) < 0.7]
    has_top_cap = any(f.normal.dot(A_vec) > 0.7 for f in selected_faces)
    has_bottom_cap = any(f.normal.dot(A_vec) < -0.7 for f in selected_faces)

    if side_faces:
        fit_verts = list({v for f in side_faces for v in f.verts})
        fit_coords = np.array([[v.co.x, v.co.y, v.co.z] for v in fit_verts])
    else:
        fit_coords = coords

    h = coords @ A
    u_fit = fit_coords @ U
    v_fit = fit_coords @ V

    # 4. 2D 最小二乘代数圆拟合: u^2 + v^2 = a*u + b*v + c
    z_fit = u_fit ** 2 + v_fit ** 2
    X_fit = np.column_stack([u_fit, v_fit, np.ones_like(u_fit)])
    try:
        fit, _, _, _ = np.linalg.lstsq(X_fit, z_fit, rcond=None)
        u_c = float(fit[0] / 2.0)
        v_c = float(fit[1] / 2.0)
        radius = float(np.sqrt(max(1e-4, fit[2] + u_c ** 2 + v_c ** 2)))
    except Exception:
        u_c = float(np.mean(u_fit))
        v_c = float(np.mean(v_fit))
        radius = float(np.mean(np.sqrt((u_fit - u_c) ** 2 + (v_fit - v_c) ** 2)))

    # 5. 计算沿中轴的高度区间与三维中心
    h_min = float(np.min(h))
    h_max = float(np.max(h))
    height = max(1e-4, h_max - h_min)
    h_mid = (h_min + h_max) / 2.0

    center_3d = u_c * U + v_c * V + h_mid * A

    # 6. 端盖自适应决策
    if cap_mode == "AUTO":
        need_top = has_top_cap
        need_bottom = has_bottom_cap
    elif cap_mode == "NONE":
        need_top = False
        need_bottom = False
    elif cap_mode == "BOTH":
        need_top = True
        need_bottom = True
    elif cap_mode == "TOP_ONLY":
        need_top = True
        need_bottom = False
    else:  # BOTTOM_ONLY
        need_top = False
        need_bottom = True

    # 7. 圆周角度跨度分析 (Angular Span)
    angles = np.arctan2(v_fit - v_c, u_fit - u_c)
    angles = np.sort(angles)
    diffs = np.diff(angles)
    wrap_gap = (angles[0] + 2.0 * math.pi) - angles[-1]
    all_gaps = list(diffs) + [wrap_gap]
    max_gap_idx = int(np.argmax(all_gaps))
    max_gap = all_gaps[max_gap_idx]

    # 若最大空隙 < 45度，视为整圈封闭圆柱；否则为局部圆弧
    is_360 = (max_gap < math.radians(45.0)) if arc_mode == "AUTO" else (arc_mode == "FULL_360")

    mat_rot = Matrix((
        [U[0], V[0], A_vec.x, 0],
        [U[1], V[1], A_vec.y, 0],
        [U[2], V[2], A_vec.z, 0],
        [0,    0,    0,       1]
    ))
    trans = Matrix.Translation(Vector((float(center_3d[0]), float(center_3d[1]), float(center_3d[2]))))
    mat = trans @ mat_rot
    depth = height * 1.04  # 沿高度微幅延展 4% 防止边缘插值失真

    if is_360:
        # 生成整圆柱筒（开端盖或按自适应决策独立加盖）
        cone_res = bmesh.ops.create_cone(
            bm_helper,
            cap_ends=False,
            cap_tris=False,
            segments=max(3, segments),
            radius1=radius,
            radius2=radius,
            depth=depth,
            matrix=mat,
        )
        cone_verts = cone_res.get("verts", [])
        bm_helper.verts.ensure_lookup_table()
        # 若需要端盖，独立创建端盖面，避免端盖平滑拉扯侧壁法向
        if need_top:
            top_verts = [v for v in cone_verts if (v.co - Vector(center_3d)).dot(A_vec) > 0]
            if len(top_verts) >= 3:
                top_verts.sort(key=lambda v: math.atan2((v.co - Vector(center_3d)).dot(Vector(V)), (v.co - Vector(center_3d)).dot(Vector(U))))
                try:
                    f_top = bm_helper.faces.new(top_verts)
                    if f_top.normal.dot(A_vec) < 0:
                        f_top.normal_flip()
                    f_top.smooth = False
                except Exception:
                    pass
        if need_bottom:
            bot_verts = [v for v in cone_verts if (v.co - Vector(center_3d)).dot(A_vec) < 0]
            if len(bot_verts) >= 3:
                bot_verts.sort(key=lambda v: math.atan2((v.co - Vector(center_3d)).dot(Vector(V)), (v.co - Vector(center_3d)).dot(Vector(U))), reverse=True)
                try:
                    f_bot = bm_helper.faces.new(bot_verts)
                    if f_bot.normal.dot(A_vec) > 0:
                        f_bot.normal_flip()
                    f_bot.smooth = False
                except Exception:
                    pass

        cone_vert_set = set(cone_verts)
        for f in bm_helper.faces:
            if all(v in cone_vert_set for v in f.verts):
                f.smooth = True
    else:
        # 生成局部开放圆弧面片 (Arc Sheet)
        if max_gap_idx < len(diffs):
            theta_start = float(angles[max_gap_idx + 1])
            theta_end = float(angles[max_gap_idx] + 2.0 * math.pi)
        else:
            theta_start = float(angles[0])
            theta_end = float(angles[-1])

        span = theta_end - theta_start
        # 弧度两端向外延展 3% 防止插值边缘失真
        theta_start -= 0.03 * span
        theta_end += 0.03 * span
        arc_segs = max(3, int(segments * (span / (2.0 * math.pi))))

        # 生成圆弧面片四边形带
        bot_row = []
        top_row = []
        for i in range(arc_segs + 1):
            t = theta_start + (theta_end - theta_start) * (i / arc_segs)
            local_pos_bot = Vector((radius * math.cos(t), radius * math.sin(t), -depth / 2.0))
            local_pos_top = Vector((radius * math.cos(t), radius * math.sin(t), depth / 2.0))
            bot_row.append(bm_helper.verts.new(mat @ local_pos_bot))
            top_row.append(bm_helper.verts.new(mat @ local_pos_top))

        bm_helper.verts.ensure_lookup_table()
        for i in range(arc_segs):
            arc_f = bm_helper.faces.new([bot_row[i], bot_row[i + 1], top_row[i + 1], top_row[i]])
            arc_f.smooth = True


def _build_cylinder_helper_mesh(
    bm_target,
    selected_faces,
    segments=32,
    axis_override="AUTO",
    cap_mode="AUTO",
    arc_mode="AUTO",
):
    """
    基于点云二维代数圆拟合与主轴解算，自适应生成标准几何圆柱/圆弧代理体：
    1. 多圆柱自适应（Multi-Cylinder）：支持同一物体上多个独立圆柱孔/轴筒并发拟合，各自生成专属辅助圆柱；
    2. 端盖自适应：若用户未选中端盖（只选侧壁），则生成开顶开底的纯净圆筒，彻底消除端盖对侧壁法线的拉扯与暗斑；
    3. 弧度自适应：若用户仅选局部圆弧，自适应生成开放弧面片（Arc Sheet），非强制 360° 封闭。
    """
    bm_helper = bmesh.new()
    islands = _cluster_faces_into_islands(bm_target, selected_faces)
    if not islands:
        return bm_helper

    if len(islands) > 1:
        # 为每个独立圆柱岛屿分别计算并生成辅助几何体
        for isl in islands:
            isl_verts = list({v for f in isl for v in f.verts})
            if len(isl_verts) < 3:
                continue
            isl_axis = _detect_cylinder_axis(isl, axis_override)
            isl_center = sum((v.co for v in isl_verts), Vector()) / len(isl_verts)
            isl_segs = segments if segments > 0 else _detect_cylinder_segments(bm_target, isl, isl_axis, isl_center)
            _build_single_cylinder_geometry(
                bm_helper=bm_helper,
                bm_target=bm_target,
                selected_faces=isl,
                segments=isl_segs,
                axis_override=axis_override,
                cap_mode=cap_mode,
                arc_mode=arc_mode,
            )
    else:
        _build_single_cylinder_geometry(
            bm_helper=bm_helper,
            bm_target=bm_target,
            selected_faces=selected_faces,
            segments=segments,
            axis_override=axis_override,
            cap_mode=cap_mode,
            arc_mode=arc_mode,
        )

    bm_helper.faces.ensure_lookup_table()
    return bm_helper


def _detect_cylinder_segments(bm, selected_faces, axis, center):
    """
    自适应探测圆柱选区的原生环形分段数：
    1. 优先从垂直于圆柱中轴的闭合边界线环提取点数（如 16, 24, 32, 64）；
    2. 若为局部弧片，计算相邻面法向在正交基上的角位移中位数 Δθ，解算 N = round(2π / Δθ)；
    3. 限制在合理范围 [3, 256]，不确定时安全回退 32。
    """
    if not selected_faces:
        return 32

    # 1. 尝试从边界环提取精准分段
    boundary_edges = [
        e for e in bm.edges
        if e.select and len([f for f in e.link_faces if f in selected_faces]) == 1
    ]
    loops = _extract_boundary_loops(boundary_edges)
    closed_loops = [l for l, is_closed in loops if is_closed]
    if closed_loops:
        # 优先寻找沿轴高度方差最小且包围周长最充分的横截面环（排查并过滤侧壁局部开孔或凹陷）
        best_loop = None
        best_score = float("-inf")
        for loop_verts in closed_loops:
            if len(loop_verts) >= 3:
                h_vals = [(v.co - center).dot(axis) for v in loop_verts]
                h_spread = max(h_vals) - min(h_vals)
                peri = _loop_perimeter(loop_verts)
                # 环越平坦 (h_spread 小) 且 周长越大，得分越高
                score = peri / (h_spread + 0.05)
                if score > best_score:
                    best_score = score
                    best_loop = loop_verts
        if best_loop:
            return max(3, min(256, len(best_loop)))

    # 2. 从相邻面法向夹角解算局部弧度步长
    try:
        import numpy as np
        A = np.array([axis.x, axis.y, axis.z], dtype=np.float64)
        if abs(A[0]) < 0.9:
            U = np.cross(A, [1.0, 0.0, 0.0])
        else:
            U = np.cross(A, [0.0, 1.0, 0.0])
        norm_u = np.linalg.norm(U)
        if norm_u > 1e-6:
            U = U / norm_u
        V = np.cross(A, U)

        face_thetas = []
        for f in selected_faces:
            fn = np.array([f.normal.x, f.normal.y, f.normal.z], dtype=np.float64)
            u_proj = float(np.dot(fn, U))
            v_proj = float(np.dot(fn, V))
            if u_proj ** 2 + v_proj ** 2 > 0.05:  # 排除端盖面
                face_thetas.append(math.atan2(v_proj, u_proj))

        if len(face_thetas) >= 2:
            face_thetas = np.sort(np.array(face_thetas))
            diffs = np.diff(face_thetas)
            positive_diffs = diffs[diffs > math.radians(2.0)]
            if len(positive_diffs) > 0:
                step = float(np.median(positive_diffs))
                if step > 1e-3:
                    n_est = int(round(2.0 * math.pi / step))
                    if 3 <= n_est <= 256:
                        return n_est
    except Exception as e:
        logger.debug(f"Segment detection fallback: {e}")

    return 32


def _build_bridged_boundary_helper(boundary_edges, selected_faces, profile_cuts=0, original_bvh=None):
    """
    当存在两端闭合边界环（如圆柱/管道侧壁、环带过渡面）时，
    智能去除中间所有杂乱三角面、过渡线与手切冗余结构，直接在两端边界之间构建纯净四边形放样网格。
    """
    bm_bridge = bmesh.new()
    vmap = {}
    for e in boundary_edges:
        for v in e.verts:
            if v not in vmap:
                vmap[v] = bm_bridge.verts.new(v.co.copy())
    bm_bridge.verts.ensure_lookup_table()

    for e in boundary_edges:
        v0 = vmap[e.verts[0]]
        v1 = vmap[e.verts[1]]
        if v0 != v1 and not bm_bridge.edges.get([v0, v1]):
            try:
                bm_bridge.edges.new([v0, v1])
            except Exception:
                pass
    bm_bridge.edges.ensure_lookup_table()

    orig_edges = set(bm_bridge.edges)
    bmesh.ops.bridge_loops(bm_bridge, edges=list(bm_bridge.edges))
    bm_bridge.faces.ensure_lookup_table()
    bm_bridge.edges.ensure_lookup_table()
    bm_bridge.verts.ensure_lookup_table()

    # 若需要剖面等距分段且原曲面有弯曲弧度，对桥接边进行细分并吸附回原曲面
    if profile_cuts > 0:
        bridge_edges = [e for e in bm_bridge.edges if e not in orig_edges]
        if bridge_edges:
            bmesh.ops.subdivide_edges(bm_bridge, edges=bridge_edges, cuts=profile_cuts, use_grid_fill=True)
            bm_bridge.faces.ensure_lookup_table()
            bm_bridge.edges.ensure_lookup_table()
            bm_bridge.verts.ensure_lookup_table()
            if original_bvh:
                for v in bm_bridge.verts:
                    if not v.is_boundary:
                        loc, norm, idx, dist = original_bvh.find_nearest(v.co)
                        if loc:
                            v.co = loc

    # 规范化法向朝向，与原表面法向方向一致（使用多面投票替代单一单面判断）
    bmesh.ops.recalc_face_normals(bm_bridge, faces=list(bm_bridge.faces))
    if selected_faces and bm_bridge.faces:
        dot_sum = 0.0
        for f in bm_bridge.faces:
            fc = f.calc_center_median()
            closest_f = min(selected_faces, key=lambda sf: (sf.calc_center_median() - fc).length_squared)
            dot_sum += f.normal.dot(closest_f.normal)
        if dot_sum < 0.0:
            for f in bm_bridge.faces:
                f.normal_flip()

    for f in bm_bridge.faces:
        f.smooth = True

    return bm_bridge


def _clean_arbitrary_extracted_mesh(bm_target, selected_faces, dissolve_angle=5.0, join_tris=True, iterations=5, factor=0.5):
    """
    通用拓扑净化：提取所选面，消解对角斜线、合并三角面为四边形、
    融解近共面/平直冗余边环并清理 2 度顶点，最后保持外边界固定并松弛内部。
    """
    bm_helper = bmesh.new()
    vert_map = {}
    for f in selected_faces:
        for v in f.verts:
            if v not in vert_map:
                vert_map[v] = bm_helper.verts.new(v.co.copy())
    bm_helper.verts.ensure_lookup_table()

    for f in selected_faces:
        try:
            bm_helper.faces.new([vert_map[v] for v in f.verts])
        except Exception:
            pass
    bm_helper.faces.ensure_lookup_table()
    bm_helper.edges.ensure_lookup_table()
    bm_helper.verts.ensure_lookup_table()

    # 1. 三角面合并为四边形 (join_triangles)
    if join_tris:
        try:
            bmesh.ops.join_triangles(
                bm_helper,
                faces=list(bm_helper.faces),
                cmp_sharp=False,
                cmp_uvs=False,
                cmp_vcols=False,
                cmp_materials=False,
                angle_face_threshold=math.radians(80),
                angle_shape_threshold=math.radians(80),
            )
            bm_helper.faces.ensure_lookup_table()
            bm_helper.edges.ensure_lookup_table()
            bm_helper.verts.ensure_lookup_table()
        except Exception:
            pass

    # 2. 融解严格共面的内部冗余边 (仅针对非边界内部边，使用 use_verts=False 保护顶点坐标与流向)
    if dissolve_angle > 0:
        try:
            internal_edges = [
                e for e in bm_helper.edges
                if len(e.link_faces) == 2 and not e.is_boundary
            ]
            rad_thresh = math.radians(min(dissolve_angle, 1.0))
            edges_to_dissolve = []
            for e in internal_edges:
                f1, f2 = e.link_faces
                if f1.normal.angle(f2.normal) < rad_thresh:
                    edges_to_dissolve.append(e)
            if edges_to_dissolve:
                bmesh.ops.dissolve_edges(bm_helper, edges=edges_to_dissolve, use_verts=False)
                bm_helper.faces.ensure_lookup_table()
                bm_helper.edges.ensure_lookup_table()
                bm_helper.verts.ensure_lookup_table()
        except Exception:
            pass

    # 4. 融解 2 度冗余非边界中间点
    try:
        verts_2 = [v for v in bm_helper.verts if len(v.link_edges) == 2 and not v.is_boundary]
        if verts_2:
            bmesh.ops.dissolve_verts(bm_helper, verts=verts_2)
            bm_helper.faces.ensure_lookup_table()
            bm_helper.edges.ensure_lookup_table()
            bm_helper.verts.ensure_lookup_table()
    except Exception:
        pass

    # 5. 内部点高阶松弛（严格锁定外轮廓边界点，确保外形尺寸 100% 稳定不缩水）
    internal_verts = [v for v in bm_helper.verts if not v.is_boundary]
    if internal_verts and iterations > 0:
        for _ in range(iterations):
            try:
                bmesh.ops.smooth_vert(
                    bm_helper,
                    verts=internal_verts,
                    factor=factor,
                    use_axis_x=True,
                    use_axis_y=True,
                    use_axis_z=True,
                )
            except Exception:
                break

    bm_helper.faces.ensure_lookup_table()
    for f in bm_helper.faces:
        f.smooth = True

    return bm_helper


def _build_raw_smooth_extract_helper(bm_target, selected_faces, iterations=5, factor=0.5):
    """原始提取模式：仅复制面并在边界锁定下执行松弛平滑"""
    bm_helper = bmesh.new()
    vert_map = {}
    for f in selected_faces:
        for v in f.verts:
            if v not in vert_map:
                vert_map[v] = bm_helper.verts.new(v.co.copy())
    bm_helper.verts.ensure_lookup_table()

    for f in selected_faces:
        try:
            bm_helper.faces.new([vert_map[v] for v in f.verts])
        except Exception:
            pass

    bm_helper.faces.ensure_lookup_table()
    bm_helper.edges.ensure_lookup_table()
    bm_helper.verts.ensure_lookup_table()

    boundary_verts = set()
    for e in bm_helper.edges:
        if len(e.link_faces) == 1:
            boundary_verts.add(e.verts[0])
            boundary_verts.add(e.verts[1])

    internal_verts = [v for v in bm_helper.verts if v not in boundary_verts]
    verts_to_smooth = internal_verts if internal_verts else list(bm_helper.verts)

    if verts_to_smooth and iterations > 0:
        for _ in range(max(1, iterations)):
            try:
                bmesh.ops.smooth_vert(
                    bm_helper,
                    verts=verts_to_smooth,
                    factor=factor,
                    use_axis_x=True,
                    use_axis_y=True,
                    use_axis_z=True,
                )
            except Exception:
                break

    bm_helper.faces.ensure_lookup_table()
    for f in bm_helper.faces:
        f.smooth = True

    return bm_helper


def _reconstruct_dense_quad_helper(
    bm_helper,
    bm_target,
    selected_faces,
    subdiv_levels=2,
    smooth_factor=0.5,
    snap_to_surface=True,
):
    """
    将提取面辅助网格重置为 100% 纯四边形拓扑（All-Quads），
    并通过多级细分获得高密度平滑网格，同时利用 BVH 树投影保持原曲面几何轮廓，
    彻底消除三角扇面、手切折痕与法向阴影阶梯感。
    """
    if not bm_helper or not bm_helper.faces or subdiv_levels <= 0:
        return bm_helper

    # 1. 尝试先合并相邻三角面以获得最佳的四边形初始流向
    try:
        bmesh.ops.join_triangles(
            bm_helper,
            faces=list(bm_helper.faces),
            cmp_sharp=False,
            cmp_uvs=False,
            cmp_vcols=False,
            cmp_materials=False,
            angle_face_threshold=math.radians(80),
            angle_shape_threshold=math.radians(80),
        )
        bm_helper.faces.ensure_lookup_table()
    except Exception:
        pass

    # 2. 构建目标表面选区的 BVH 树用于吸附与曲面拟合
    bvh = None
    if snap_to_surface and selected_faces and bm_target:
        try:
            target_verts_co = [v.co for v in bm_target.verts]
            target_polys = [[v.index for v in f.verts] for f in selected_faces]
            bvh = BVHTree.FromPolygons(target_verts_co, target_polys)
        except Exception:
            bvh = None

    # 3. 利用 Blender 核心 Catmull-Clark 算法执行高阶四边面重构与多级细分
    temp_me = None
    temp_obj = None
    bm_dense = None

    try:
        temp_me = bpy.data.meshes.new("_m8_temp_quad_subdiv_mesh")
        bm_helper.to_mesh(temp_me)
        temp_me.update()

        temp_obj = bpy.data.objects.new("_m8_temp_quad_subdiv_obj", temp_me)
        bpy.context.scene.collection.objects.link(temp_obj)

        sub_mod = temp_obj.modifiers.new("M8_QuadSubsurf", "SUBSURF")
        sub_mod.levels = max(1, min(4, int(subdiv_levels)))
        sub_mod.render_levels = sub_mod.levels
        sub_mod.subdivision_type = "CATMULL_CLARK"
        sub_mod.boundary_smooth = "PRESERVE_CORNERS"

        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = temp_obj.evaluated_get(depsgraph)

        bm_dense = bmesh.new()
        bm_dense.from_mesh(eval_obj.data)
        bm_dense.faces.ensure_lookup_table()
        bm_dense.verts.ensure_lookup_table()

        # 4. 顶点吸附与原曲面光顺混合
        if bvh and snap_to_surface:
            blend_w = max(0.0, min(1.0, 1.0 - smooth_factor * 0.5))
            for v in bm_dense.verts:
                loc, norm, idx, dist = bvh.find_nearest(v.co)
                if loc is not None:
                    v.co = v.co.lerp(loc, blend_w)

        # 成功构建后释放旧 bm_helper，返回新的密集四边面网格
        bm_helper.free()
        bm_helper = bm_dense
        bm_dense = None

    except Exception as e:
        logger.debug(f"Catmull-Clark quad remesh fallback: {e}")
        try:
            bmesh.ops.subdivide_edges(
                bm_helper,
                edges=list(bm_helper.edges),
                cuts=subdiv_levels,
                use_grid_fill=True,
                use_only_quads=True,
            )
            bm_helper.faces.ensure_lookup_table()
        except Exception:
            pass
    finally:
        if bm_dense:
            try:
                bm_dense.free()
            except Exception:
                pass
        if temp_obj:
            try:
                bpy.data.objects.remove(temp_obj, do_unlink=True)
            except Exception:
                pass
        if temp_me:
            try:
                bpy.data.meshes.remove(temp_me)
            except Exception:
                pass

    bm_helper.faces.ensure_lookup_table()
    for f in bm_helper.faces:
        f.smooth = True

    return bm_helper


def _apply_cage_envelope_push(
    bm_helper,
    bm_target,
    selected_faces,
    cage_offset=0.002,
    auto_wrap_outside=True,
):
    """
    辅助网格法向外壳包裹与防内缩补偿系统 (Normal Cage Envelope & Anti-Shrink Push):
    1. 计算目标选区 BVH 树；
    2. 针对细分平滑后凹陷进模型内部的顶点 (d · n < 0)，自动推移至外表面；
    3. 沿平滑顶点法线应用用户指定的向外包裹偏移 cage_offset，使辅助体像一层透明轻壳均匀包裹在模型外部。
    """
    if not bm_helper or not bm_helper.faces:
        return

    bvh = None
    if auto_wrap_outside and bm_target and selected_faces:
        try:
            target_verts_co = [v.co for v in bm_target.verts]
            target_polys = [[v.index for v in f.verts] for f in selected_faces]
            bvh = BVHTree.FromPolygons(target_verts_co, target_polys)
        except Exception:
            bvh = None

    bm_helper.verts.ensure_lookup_table()
    bm_helper.faces.ensure_lookup_table()
    bm_helper.normal_update()

    # 1. 智能防内缩保护 (Anti-Shrink Protection)
    if bvh and auto_wrap_outside:
        for v in bm_helper.verts:
            loc, norm, idx, dist = bvh.find_nearest(v.co)
            if loc is not None and norm is not None and norm.length > 1e-4:
                norm_u = norm.normalized()
                disp = v.co - loc
                signed_dist = disp.dot(norm_u)
                if signed_dist < 0.0:
                    # 强力纠偏：推至原模型外侧微量安全边界 (至少处于表面偏外 0.0005m)
                    v.co = loc + norm_u * 0.0005

    # 2. 沿平滑顶点法向应用用户可调的 cage_offset
    if abs(cage_offset) > 1e-6:
        bm_helper.normal_update()
        for v in bm_helper.verts:
            v_norm = v.normal
            if v_norm.length > 1e-4:
                v.co += v_norm.normalized() * cage_offset
            else:
                avg_fn = sum((f.normal for f in v.link_faces), Vector((0, 0, 0)))
                if avg_fn.length > 1e-4:
                    v.co += avg_fn.normalized() * cage_offset

    bm_helper.normal_update()


def _build_smooth_extract_helper_mesh(
    bm_target,
    selected_faces,
    clean_mode="AUTO",
    profile_cuts=0,
    dissolve_angle=5.0,
    iterations=5,
    factor=0.5,
    quad_remesh=True,
    quad_subdiv=2,
    snap_to_surface=True,
    smooth_factor=0.5,
    cage_offset=0.002,
    auto_wrap_outside=True,
):
    """
    智能提取面并重置为高密平滑纯四边面网格：
    - AUTO: 智能分析形态（双边界环放样，单环封面，复杂曲面消解），并彻底重构为密集平滑纯四边面；
    - BRIDGE: 纯净边界放样，去除中间所有手切线与三角面；
    - DISSOLVE: 拓扑净化消解冗余边与对角线；
    - RAW: 原样提取保留结构；
    - CAGE ENVELOPE: 自动防内缩与法向外壳包裹，杜绝凹陷进模型内部。
    """
    if not selected_faces:
        return bmesh.new()

    # 提取外轮廓边界边
    boundary_edges = [
        e for e in bm_target.edges
        if len([f for f in e.link_faces if f in selected_faces]) == 1
    ]
    loops = _extract_boundary_loops(boundary_edges)
    closed_loops = [l for l, is_closed in loops if is_closed]

    original_bvh = None
    if profile_cuts > 0:
        try:
            original_bvh = BVHTree.FromPolygons(
                [v.co for v in bm_target.verts],
                [[v.index for v in f.verts] for f in selected_faces]
            )
        except Exception:
            pass

    bm_helper = None

    # 1. 双闭合边界环（如圆柱侧壁、管道、回转体过渡带）
    is_simple_uniform_tube = (
        len(closed_loops) == 2
        and len(closed_loops[0]) == len(closed_loops[1])
        and abs(len(selected_faces) - len(closed_loops[0])) <= 2
    )
    if clean_mode == "BRIDGE" or (clean_mode == "AUTO" and is_simple_uniform_tube):
        try:
            bm_helper = _build_bridged_boundary_helper(
                boundary_edges,
                selected_faces,
                profile_cuts=profile_cuts,
                original_bvh=original_bvh,
            )
        except Exception as e:
            logger.debug(f"Bridged boundary fallback to cleanup: {e}")

    # 2. 单闭合环盖子/圆盘
    if not bm_helper and clean_mode == "AUTO" and len(closed_loops) == 1:
        try:
            loop_verts = closed_loops[0]
            center = sum((v.co for v in loop_verts), Vector()) / len(loop_verts)
            avg_norm = sum((f.normal for f in selected_faces), Vector()).normalized()
            max_dist = max(abs((v.co - center).dot(avg_norm)) for v in loop_verts)
            span = max((v.co - center).length for v in loop_verts)
            if span > 1e-5 and (max_dist / span) < 0.05:
                bm_cap = bmesh.new()
                vmap = {v: bm_cap.verts.new(v.co.copy()) for v in loop_verts}
                bm_cap.verts.ensure_lookup_table()
                new_verts = [vmap[v] for v in loop_verts]
                f_cap = bm_cap.faces.new(new_verts)
                if f_cap.normal.dot(avg_norm) < 0:
                    f_cap.normal_flip()
                bm_cap.faces.ensure_lookup_table()
                for f in bm_cap.faces:
                    f.smooth = False
                bm_helper = bm_cap
        except Exception as e:
            logger.debug(f"Planar cap helper fallback: {e}")

    # 3. 复杂曲面/开放带状拓扑净化
    if not bm_helper and clean_mode in ("AUTO", "DISSOLVE"):
        bm_helper = _clean_arbitrary_extracted_mesh(
            bm_target,
            selected_faces,
            dissolve_angle=dissolve_angle,
            join_tris=True,
            iterations=iterations,
            factor=factor,
        )

    # 4. RAW 原始保留模式
    if not bm_helper:
        bm_helper = _build_raw_smooth_extract_helper(
            bm_target,
            selected_faces,
            iterations=iterations,
            factor=factor,
        )

    # 5. 高阶全四边面拓扑重置与多级平滑细分 (100% All-Quads & Dense Smooth)
    if quad_remesh and quad_subdiv > 0 and bm_helper and bm_helper.faces:
        bm_helper = _reconstruct_dense_quad_helper(
            bm_helper,
            bm_target,
            selected_faces,
            subdiv_levels=quad_subdiv,
            smooth_factor=smooth_factor,
            snap_to_surface=snap_to_surface,
        )

    # 6. 外壳包裹膨胀与防内缩补偿 (Cage Envelope & Anti-Shrink)
    _apply_cage_envelope_push(
        bm_helper,
        bm_target,
        selected_faces,
        cage_offset=cage_offset,
        auto_wrap_outside=auto_wrap_outside,
    )

    return bm_helper


class M8_OT_SmartNormalTransfer(bpy.types.Operator):
    bl_idname = "m8.smart_normal_transfer"
    bl_label = _T("M8 智能法向修正")
    bl_description = _T("智能分析所选面形态，自动生成平整/柱面/平滑代理体并通过数据传递修改器消除法向暗斑与拉扯")
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name=_T("修正模式"),
        items=[
            ("AUTO", _T("智能自适应"), _T("自动分析所选面离散度与曲度，自适应选用最适合的代理体")),
            ("PLANAR", _T("平面轮廓拍平"), _T("生成无内部极点三角边的单面大平面，专治圆盘/平面的阴影黑斑")),
            ("CYLINDER", _T("圆柱拟合"), _T("数学拟合并生成纯净标准几何圆柱体，彻底消除柱面三角面拉扯")),
            ("SMOOTH_EXTRACT", _T("提取面平滑"), _T("提取选中面，固定边界外轮廓并松弛平滑内部折痕")),
        ],
        default="AUTO",
    )

    cylinder_segments: bpy.props.IntProperty(
        name=_T("圆柱分段数"),
        description=_T("生成圆柱几何体的环形分段数（0 为自动自适应原模型分段，亦可手动指定如 16, 24, 64）"),
        default=0,
        min=0,
        max=256,
    )

    axis_override: bpy.props.EnumProperty(
        name=_T("圆柱中轴方向"),
        items=[
            ("AUTO", _T("自动解算"), _T("根据几何点云法线协方差自动解算中轴矢量（支持任意三维倾斜）")),
            ("Z", "Z 轴", _T("沿局部 Z 轴方向生成圆柱")),
            ("Y", "Y 轴", _T("沿局部 Y 轴方向生成圆柱")),
            ("X", "X 轴", _T("沿局部 X 轴方向生成圆柱")),
        ],
        default="AUTO",
    )

    cylinder_cap_mode: bpy.props.EnumProperty(
        name=_T("端盖闭合"),
        description=_T("圆柱两端端盖处理方式：AUTO 自动根据选中面判断；无端盖可消除顶底边缘阴影拉扯"),
        items=[
            ("AUTO", _T("自适应"), _T("自动检测是否选中顶盖/底盖，未选中时保持开孔筒状")),
            ("NONE", _T("无端盖 (开孔筒状)"), _T("完全不生成端盖，侧壁顶底法向纯净水平")),
            ("BOTH", _T("双端封闭"), _T("强制生成顶底封闭圆柱体")),
            ("TOP_ONLY", _T("仅封顶"), _T("仅在顶部生成端盖")),
            ("BOTTOM_ONLY", _T("仅封底"), _T("仅在底部生成端盖")),
        ],
        default="AUTO",
    )

    cylinder_arc_mode: bpy.props.EnumProperty(
        name=_T("弧度范围"),
        description=_T("圆柱弧度跨度处理方式：AUTO 自动根据选中面弧度判断整圆或局部弧片"),
        items=[
            ("AUTO", _T("自适应"), _T("自动检测选中面角度跨度，选局部则生成弧片，选整圈生成整柱")),
            ("FULL_360", _T("360° 整圆"), _T("强制生成 360° 完整圆柱")),
            ("ARC", _T("局部弧片"), _T("仅生成贴合选区的局部弧面片")),
        ],
        default="AUTO",
    )

    extract_clean_mode: bpy.props.EnumProperty(
        name=_T("提取净化模式"),
        description=_T("提取面处理方式：AUTO 智能分析形态（双边界环则纯净放样，单环则封面，复杂曲面则消解三角与冗余切线）"),
        items=[
            ("AUTO", _T("自适应净化"), _T("智能分析形态：双边界环则放样桥接，单环则封面，其他则拓扑净化消解多余结构")),
            ("BRIDGE", _T("纯净边界放样"), _T("仅保留两端外轮廓，彻底去除中间所有三角面、横向切割与多余结构")),
            ("DISSOLVE", _T("拓扑净化消解"), _T("消除三角面对角斜线并融解共面多余边，保留原曲面轮廓")),
            ("RAW", _T("原样提取"), _T("保留原始所有结构，仅做松弛平滑")),
        ],
        default="AUTO",
    )

    profile_cuts: bpy.props.IntProperty(
        name=_T("剖面中间分段"),
        description=_T("边界放样桥接时在剖面方向添加的等距分段数（0 为直通最简；曲面过渡可设为 1~16 并贴合原曲面）"),
        default=0,
        min=0,
        max=16,
    )

    dissolve_angle: bpy.props.FloatProperty(
        name=_T("融解角度阈值"),
        description=_T("拓扑净化时共面或平坦内部边融解的夹角阈值（度）"),
        default=5.0,
        min=0.1,
        max=45.0,
    )

    smooth_iterations: bpy.props.IntProperty(
        name=_T("平滑迭代次数"),
        description=_T("提取面平滑模式下的内部松弛平滑迭代次数"),
        default=5,
        min=1,
        max=50,
    )

    quad_remesh: bpy.props.BoolProperty(
        name=_T("重置为四边面"),
        description=_T("将提取面重构为 100% 纯四边形拓扑并高密细分，彻底消除三角面与法向阴影折痕"),
        default=True,
    )

    quad_subdiv: bpy.props.IntProperty(
        name=_T("四边面细分层级"),
        description=_T("四边面细分级别（层级越高，面的数量越多，曲率过渡越细腻平滑）"),
        default=2,
        min=0,
        max=4,
    )

    snap_to_surface: bpy.props.BoolProperty(
        name=_T("贴合原曲面"),
        description=_T("细分重构后顶点贴合回原网格曲面（默认关闭以保持高阶曲面自然圆润，彻底消除低模折痕与波纹）"),
        default=False,
    )

    quad_smooth_factor: bpy.props.FloatProperty(
        name=_T("曲面光顺度"),
        description=_T("细分曲面自由光顺与几何贴合度的混合比重 (0=完全贴合原形, 1=全自由光顺)"),
        default=0.5,
        min=0.0,
        max=1.0,
    )

    grow_steps: bpy.props.IntProperty(
        name=_T("扩展选区 (圈数)"),
        description=_T("向外扩展顶点圈数，将相邻倒角过渡边缘一同纳入法向修正"),
        default=0,
        min=0,
        max=10,
    )

    flip_normal: bpy.props.BoolProperty(
        name=_T("反转法向"),
        description=_T("反转辅助代理体的法线朝向（用于内凹腔体、反向曲面或特殊硬表面着色需求）"),
        default=False,
    )

    show_helper: bpy.props.BoolProperty(
        name=_T("显示辅助体"),
        description=_T("在视口中显示生成的几何辅助代理体（默认隐藏，保持视口清爽干净）"),
        default=False,
    )

    apply_and_clean: bpy.props.BoolProperty(
        name=_T("立即烘焙并清理"),
        description=_T("应用数据传递修改器并将法向固化在网格上，同时自动清理删除临时辅助体"),
        default=False,
    )

    cage_offset: bpy.props.FloatProperty(
        name=_T("向外包裹偏移"),
        description=_T("将辅助代理体沿法向向外推开微量距离，确保辅助体始终包裹在原模型外侧（Cage Envelope），彻底杜绝曲面平滑收缩导致穿插进模型内部"),
        default=0.002,
        min=-0.1,
        max=1.0,
        soft_min=0.0,
        soft_max=0.05,
        step=0.1,
        precision=4,
        unit="LENGTH",
    )

    auto_wrap_outside: bpy.props.BoolProperty(
        name=_T("防内缩外壳保护"),
        description=_T("智能检测并自动纠正因细分与松弛平滑导致凹陷进原模型内部的顶点，强制保证辅助体处于模型外表面"),
        default=True,
    )

    stack_mode: bpy.props.EnumProperty(
        name=_T("叠加模式"),
        description=_T("处理与已有法向传递修改器的关系：智能叠加（不同区域自动新建修改器并叠加，相同区域覆盖更新）；新建叠加（强制新建）；固化前序并新建（先烘焙已有修改器进网格，保持堆栈极简）；覆盖更新（覆盖已有修改器）"),
        items=[
            ("AUTO_STACK", _T("智能叠加"), _T("自动检测选区：不同区域自动新建修改器并叠加，相同区域覆盖更新")),
            ("STACK", _T("新建叠加"), _T("为当前选区新建独立的修改器、顶点组与辅助体，与已有修改器叠加共存")),
            ("APPLY_PREVIOUS", _T("固化前序并新建"), _T("先将物体上已有的 M8 修改器烘焙固化进网格，再为当前选区新建修改器（保持堆栈清爽无冗余）")),
            ("REPLACE", _T("覆盖更新"), _T("覆盖更新当前/上一个同类修改器，适合反复微调同一区域")),
        ],
        default="AUTO_STACK",
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        col.prop(self, "mode", expand=True)

        layout.separator()
        if self.mode in ("AUTO", "CYLINDER"):
            box_cyl = layout.box()
            box_cyl.label(text=_T("圆柱拟合参数"), icon="MESH_CYLINDER")
            box_cyl.prop(self, "cylinder_segments")
            box_cyl.prop(self, "axis_override")
            box_cyl.prop(self, "cylinder_cap_mode")
            box_cyl.prop(self, "cylinder_arc_mode")

        if self.mode in ("AUTO", "SMOOTH_EXTRACT"):
            box_smooth = layout.box()
            box_smooth.label(text=_T("提取与四边面平滑"), icon="MOD_SMOOTH")
            box_smooth.prop(self, "extract_clean_mode")
            if self.extract_clean_mode in ("AUTO", "BRIDGE"):
                box_smooth.prop(self, "profile_cuts")
            if self.extract_clean_mode in ("AUTO", "DISSOLVE"):
                box_smooth.prop(self, "dissolve_angle")
            box_smooth.prop(self, "smooth_iterations")

            box_quad = box_smooth.box()
            box_quad.prop(self, "quad_remesh", icon="MESH_GRID")
            if self.quad_remesh:
                box_quad.prop(self, "quad_subdiv")
                box_quad.prop(self, "snap_to_surface")
                box_quad.prop(self, "quad_smooth_factor")

            box_cage = box_smooth.box()
            box_cage.label(text=_T("外壳包裹与防内缩 (Cage)"), icon="OUTLINER_OB_SURFACE")
            box_cage.prop(self, "cage_offset")
            box_cage.prop(self, "auto_wrap_outside")

        layout.separator()
        layout.prop(self, "grow_steps")

        row = layout.row()
        row.prop(self, "flip_normal", icon="ARROW_LEFTRIGHT")
        row.prop(self, "show_helper", icon="HIDE_OFF" if self.show_helper else "HIDE_ON")

        box_stack = layout.box()
        box_stack.prop(self, "stack_mode", icon="DUPLICATE")

        box = layout.box()
        box.alert = bool(self.apply_and_clean)
        box.prop(self, "apply_and_clean", icon="CHECKMARK")

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            self.report({"WARNING"}, _T("必须在网格编辑模式下执行"))
            return {"CANCELLED"}

        obj = context.edit_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, _T("当前编辑对象不是网格"))
            return {"CANCELLED"}

        me = obj.data
        bm = bmesh.from_edit_mesh(me)

        selected_faces = [f for f in bm.faces if f.select]
        if not selected_faces:
            selected_verts = [v for v in bm.verts if v.select]
            if selected_verts:
                vert_set = set(selected_verts)
                selected_faces = [f for f in bm.faces if sum(1 for v in f.verts if v in vert_set) >= min(3, len(f.verts))]
            if not selected_faces:
                self.report({"WARNING"}, _T("请先选择需要修正法向的面"))
                return {"CANCELLED"}

        # 0. 过滤布尔切削留下的零面积退化碎面（面积 < 1e-12）
        valid_faces = [f for f in selected_faces if f.calc_area() > 1e-12]
        if not valid_faces:
            valid_faces = selected_faces

        # 1. 几何特征分析
        total_area = sum(f.calc_area() for f in valid_faces)
        avg_norm = sum((f.normal * f.calc_area() for f in valid_faces), Vector((0, 0, 0)))
        if avg_norm.length > 1e-6:
            avg_norm.normalize()
        else:
            avg_norm = Vector((0, 0, 1))

        base_verts = {v for f in selected_faces for v in f.verts}
        center = sum((v.co for v in base_verts), Vector((0, 0, 0))) / max(1, len(base_verts))
        selected_face_indices = {f.index for f in selected_faces}

        # 2 & 4. 几何代理体自适应构建（支持工业级复杂硬表面多特征混合分治与阶梯沉孔自适应）
        actual_mode = self.mode
        bm_helper = bmesh.new()
        try:
            if self.mode == "PLANAR":
                actual_mode = "PLANAR"
                islands = _cluster_faces_into_islands(bm, valid_faces, max_dihedral_angle=35.0)
                for isl in islands:
                    _build_single_planar_geometry(bm_helper, bm, isl, avg_norm=avg_norm)
            elif self.mode == "CYLINDER":
                actual_mode = "CYLINDER"
                islands = _cluster_faces_into_islands(bm, valid_faces)
                for isl in islands:
                    isl_axis = _detect_cylinder_axis(isl, self.axis_override)
                    isl_verts = {v for f in isl for v in f.verts}
                    isl_center = sum((v.co for v in isl_verts), Vector()) / max(1, len(isl_verts))
                    isl_segs = self.cylinder_segments if self.cylinder_segments > 0 else _detect_cylinder_segments(bm, isl, isl_axis, isl_center)
                    _build_single_cylinder_geometry(
                        bm_helper, bm, isl,
                        segments=isl_segs,
                        axis_override=self.axis_override,
                        cap_mode=self.cylinder_cap_mode,
                        arc_mode=self.cylinder_arc_mode,
                    )
            elif self.mode == "SMOOTH_EXTRACT":
                actual_mode = "SMOOTH_EXTRACT"
                bm_sub = _build_smooth_extract_helper_mesh(
                    bm, valid_faces,
                    clean_mode=self.extract_clean_mode,
                    profile_cuts=self.profile_cuts,
                    dissolve_angle=self.dissolve_angle,
                    iterations=self.smooth_iterations,
                    quad_remesh=self.quad_remesh,
                    quad_subdiv=self.quad_subdiv,
                    snap_to_surface=self.snap_to_surface,
                    smooth_factor=self.quad_smooth_factor,
                    cage_offset=self.cage_offset,
                    auto_wrap_outside=self.auto_wrap_outside,
                )
                _merge_bmesh_into(bm_helper, bm_sub)
                bm_sub.free()
            else:
                # 智能全自适应混合多特征分治架构 (AUTO Hybrid Architecture)
                # 自动按二面角 35° 解耦阶梯沉孔、面板与倒角，使同一选区内的不同几何特征各获专属代理
                islands = _cluster_faces_into_islands(bm, valid_faces, max_dihedral_angle=35.0)
                classified_counts = {"PLANAR": 0, "CYLINDER": 0, "SMOOTH_EXTRACT": 0}
                for isl in islands:
                    itype = _classify_face_island(isl, axis_override=self.axis_override)
                    classified_counts[itype] += 1
                    if itype == "PLANAR":
                        _build_single_planar_geometry(bm_helper, bm, isl, avg_norm=avg_norm)
                    elif itype == "CYLINDER":
                        isl_axis = _detect_cylinder_axis(isl, self.axis_override)
                        isl_verts = {v for f in isl for v in f.verts}
                        isl_center = sum((v.co for v in isl_verts), Vector()) / max(1, len(isl_verts))
                        isl_segs = self.cylinder_segments if self.cylinder_segments > 0 else _detect_cylinder_segments(bm, isl, isl_axis, isl_center)
                        _build_single_cylinder_geometry(
                            bm_helper, bm, isl,
                            segments=isl_segs,
                            axis_override=self.axis_override,
                            cap_mode=self.cylinder_cap_mode,
                            arc_mode=self.cylinder_arc_mode,
                        )
                    else:
                        bm_sub = _build_smooth_extract_helper_mesh(
                            bm, isl,
                            clean_mode=self.extract_clean_mode,
                            profile_cuts=self.profile_cuts,
                            dissolve_angle=self.dissolve_angle,
                            iterations=self.smooth_iterations,
                            quad_remesh=self.quad_remesh,
                            quad_subdiv=self.quad_subdiv,
                            snap_to_surface=self.snap_to_surface,
                            smooth_factor=self.quad_smooth_factor,
                            cage_offset=self.cage_offset,
                            auto_wrap_outside=self.auto_wrap_outside,
                        )
                        _merge_bmesh_into(bm_helper, bm_sub)
                        bm_sub.free()

                if classified_counts["PLANAR"] > 0 and classified_counts["CYLINDER"] == 0 and classified_counts["SMOOTH_EXTRACT"] == 0:
                    actual_mode = "PLANAR"
                elif classified_counts["CYLINDER"] > 0 and classified_counts["PLANAR"] == 0 and classified_counts["SMOOTH_EXTRACT"] == 0:
                    actual_mode = "CYLINDER"
                elif classified_counts["SMOOTH_EXTRACT"] > 0 and classified_counts["PLANAR"] == 0 and classified_counts["CYLINDER"] == 0:
                    actual_mode = "SMOOTH_EXTRACT"
                else:
                    actual_mode = "HYBRID"

            # 统一执行法向健壮对齐与反转控制（覆盖所有模式）
            _align_helper_normals_to_target(
                bm_helper=bm_helper,
                bm_target=bm,
                selected_faces=selected_faces,
                flip_normal=self.flip_normal,
            )

            # 5. 顶点组计算（支持向外扩展 grow_steps 与线性软羽化衰减 Falloff）
            vert_weights = {v.index: 1.0 for v in base_verts}
            if self.grow_steps > 0:
                current_shell = set(base_verts)
                visited_verts = set(base_verts)
                for step in range(1, self.grow_steps + 1):
                    next_shell = set()
                    for v in current_shell:
                        for e in v.link_edges:
                            other = e.other_vert(v)
                            if other not in visited_verts:
                                next_shell.add(other)
                                visited_verts.add(other)
                    w = max(0.1, 1.0 - (step / (self.grow_steps + 1.0)))
                    for v in next_shell:
                        vert_weights[v.index] = w
                    current_shell = next_shell

            base_vert_indices = {v.index for v in base_verts}
            vert_indices = list(vert_weights.keys())

            # 同步并暂时切换至 OBJECT 模式安全配置顶点组与修改器
            bmesh.update_edit_mesh(me)
            bpy.ops.object.mode_set(mode="OBJECT")

            # 5.5 处理叠加模式 (Stack Mode)
            existing_m8_mods = [
                m for m in obj.modifiers 
                if m.type == "DATA_TRANSFER" and m.name.startswith(MODIFIER_PREFIX)
            ]

            if self.stack_mode == "APPLY_PREVIOUS" and existing_m8_mods:
                # 固化前序：将物体上已存的所有 M8 修改器全部一键烘焙并清理
                for m in list(obj.modifiers):
                    if m.type == "DATA_TRANSFER" and m.name.startswith(MODIFIER_PREFIX):
                        h_obj = m.object
                        vg_name_old = m.vertex_group
                        try:
                            bpy.ops.object.modifier_apply(modifier=m.name)
                        except Exception as e:
                            logger.debug(f"Failed to apply previous modifier {m.name}: {e}")
                        if h_obj:
                            me_h = h_obj.data
                            try:
                                bpy.data.objects.remove(h_obj, do_unlink=True)
                                if me_h and me_h.users == 0:
                                    bpy.data.meshes.remove(me_h)
                            except Exception:
                                pass
                        if vg_name_old:
                            vg_old = obj.vertex_groups.get(vg_name_old)
                            if vg_old:
                                try:
                                    obj.vertex_groups.remove(vg_old)
                                except Exception:
                                    pass
                existing_m8_mods = []

            # 智能判定：是原地更新现有修改器，还是新建独立修改器进行多层叠加
            target_mod = None
            if self.stack_mode == "AUTO_STACK":
                # 自动检测：以核心基础选区 base_vert_indices 为基准，若与某已有 M8 修改器的顶点组存在高重合度 (>= 70%)，视为同一区域换算法/调参，覆盖更新
                for m in reversed(existing_m8_mods):
                    if m.vertex_group:
                        vg_test = obj.vertex_groups.get(m.vertex_group)
                        if vg_test:
                            in_count = 0
                            for vid in base_vert_indices:
                                try:
                                    if vg_test.weight(vid) > 0.0:
                                        in_count += 1
                                except Exception:
                                    pass
                            if (in_count / max(1, len(base_vert_indices))) >= 0.7:
                                target_mod = m
                                break
            elif self.stack_mode == "REPLACE":
                same_mode_mods = [m for m in existing_m8_mods if actual_mode in m.name]
                target_mod = same_mode_mods[-1] if same_mode_mods else (existing_m8_mods[-1] if existing_m8_mods else None)

            # 确定修改器、顶点组与辅助物体的名称
            if target_mod:
                # 若更新已有修改器且模式发生了改变，重命名以保持语义与断言一致
                ideal_mod_name = f"{MODIFIER_PREFIX}_{actual_mode}"
                if ideal_mod_name != target_mod.name:
                    if ideal_mod_name in obj.modifiers and obj.modifiers[ideal_mod_name] != target_mod:
                        idx = 2
                        while f"{ideal_mod_name}_{idx}" in obj.modifiers:
                            idx += 1
                        target_mod.name = f"{ideal_mod_name}_{idx}"
                    else:
                        target_mod.name = ideal_mod_name

                mod_name = target_mod.name
                vg_name = f"{VG_PREFIX}_{actual_mode.capitalize()}"
                if target_mod.vertex_group:
                    vg_old = obj.vertex_groups.get(target_mod.vertex_group)
                    if vg_old and vg_old.name != vg_name:
                        if vg_name in obj.vertex_groups and obj.vertex_groups[vg_name] != vg_old:
                            vg_old.name = f"{vg_name}_old"
                        vg_old.name = vg_name
                helper_obj_name = f"_M8_Helper_{obj.name}_{actual_mode}"
                if target_mod.object and target_mod.object.name != helper_obj_name:
                    if helper_obj_name in bpy.data.objects and bpy.data.objects[helper_obj_name] != target_mod.object:
                        target_mod.object.name = f"{helper_obj_name}_old"
                    target_mod.object.name = helper_obj_name
            else:
                base_mod_name = f"{MODIFIER_PREFIX}_{actual_mode}"
                base_vg_name = f"{VG_PREFIX}_{actual_mode.capitalize()}"
                base_helper_name = f"_M8_Helper_{obj.name}_{actual_mode}"

                existing_mod_names = {m.name for m in obj.modifiers}
                if base_mod_name not in existing_mod_names:
                    mod_name = base_mod_name
                    vg_name = base_vg_name
                    helper_obj_name = base_helper_name
                else:
                    idx = 2
                    while True:
                        cand_mod = f"{base_mod_name}_{idx}"
                        if cand_mod not in existing_mod_names:
                            mod_name = cand_mod
                            vg_name = f"{base_vg_name}_{idx}"
                            helper_obj_name = f"{base_helper_name}_{idx}"
                            break
                        idx += 1

            # 6. 顶点组创建与权重赋值（支持线性羽化衰减梯度）
            vg = obj.vertex_groups.get(vg_name)
            if not vg:
                vg = obj.vertex_groups.new(name=vg_name)
            else:
                try:
                    vg.remove(list(range(len(obj.data.vertices))))
                except Exception:
                    pass

            for vid, weight in vert_weights.items():
                vg.add([vid], weight, "REPLACE")

            # 7. 创建或更新辅助物体
            helper_col = _get_or_create_helper_collection(context.scene)
            helper_obj = bpy.data.objects.get(helper_obj_name)

            if not helper_obj:
                helper_me = bpy.data.meshes.new(name=f"{helper_obj_name}_Mesh")
                bm_helper.to_mesh(helper_me)
                helper_me.update()

                helper_obj = bpy.data.objects.new(name=helper_obj_name, object_data=helper_me)
                helper_col.objects.link(helper_obj)
            else:
                helper_me = helper_obj.data
                bm_helper.to_mesh(helper_me)
                helper_me.update()
        finally:
            if bm_helper:
                try:
                    bm_helper.free()
                except Exception:
                    pass

        helper_obj.matrix_world = obj.matrix_world.copy()
        helper_obj.display_type = "WIRE"
        helper_obj.hide_render = True
        helper_obj.hide_viewport = not self.show_helper

        # 镜像修改器自动同步：若原物体存在生效的 MIRROR 修改器，同步给辅助体以支持对称模型双向映射
        for m in obj.modifiers:
            if m.type == "MIRROR" and m.show_viewport:
                h_mirror = helper_obj.modifiers.get(m.name)
                if not h_mirror:
                    h_mirror = helper_obj.modifiers.new(name=m.name, type="MIRROR")
                h_mirror.use_axis = m.use_axis[:]
                h_mirror.use_bisect_axis = m.use_bisect_axis[:]
                h_mirror.use_bisect_flip_axis = m.use_bisect_flip_axis[:]
                h_mirror.mirror_object = m.mirror_object
                if hasattr(m, "mirror_offset"):
                    h_mirror.mirror_offset = m.mirror_offset

        helper_col.hide_render = True
        helper_col.hide_viewport = not self.show_helper
        vl = getattr(context, "view_layer", None)
        if vl:
            _hide_collection_in_view_layer(vl, HELPER_COLLECTION_NAME, hide=(not self.show_helper))

        # 8. 数据传递修改器 (DATA_TRANSFER)
        mod = obj.modifiers.get(mod_name)
        if not mod:
            mod = obj.modifiers.new(name=mod_name, type="DATA_TRANSFER")

        mod.object = helper_obj
        mod.use_loop_data = True
        mod.data_types_loops = {"CUSTOM_NORMAL"}
        mod.loop_mapping = "POLYINTERP_NEAREST"
        mod.vertex_group = vg.name

        # 修改器堆栈防御：确保 DATA_TRANSFER 位于任何 WEIGHTED_NORMAL 修改器之后，防止传递法向被无差别抹除
        weighted_mods = [m for m in obj.modifiers if m.type == "WEIGHTED_NORMAL"]
        if weighted_mods and hasattr(obj.modifiers, "move"):
            try:
                last_wn_idx = max(obj.modifiers.find(m.name) for m in weighted_mods)
                curr_idx = obj.modifiers.find(mod.name)
                if curr_idx < last_wn_idx:
                    obj.modifiers.move(curr_idx, last_wn_idx)
            except Exception as e:
                logger.debug(f"Modifier move after WEIGHTED_NORMAL fallback: {e}")

        # 仅针对受法向传递影响的多边形设置平滑着色，100% 杜绝污染未选中的硬表面垂直立面/平直侧面 (Zero Shading Bleed)
        affected_vert_set = set(vert_indices)
        for poly in obj.data.polygons:
            if poly.index in selected_face_indices:
                poly.use_smooth = True
            elif self.grow_steps > 0 and all(vid in affected_vert_set for vid in poly.vertices):
                poly.use_smooth = True

        # 9. 烘焙应用与清理 (Apply & Clean)
        if self.apply_and_clean:
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
                self.report({"INFO"}, _T("法向已烘焙至网格，辅助体已清理"))
            except Exception as e:
                self.report({"WARNING"}, f"{_T('修改器应用失败')}: {e}")

            try:
                bpy.data.objects.remove(helper_obj, do_unlink=True)
                if helper_me.users == 0:
                    bpy.data.meshes.remove(helper_me)
            except Exception:
                pass
            if vg:
                try:
                    obj.vertex_groups.remove(vg)
                except Exception:
                    pass
            # 空集合自动回收销毁 (零残留管理)
            if helper_col and len(helper_col.objects) == 0:
                try:
                    bpy.data.collections.remove(helper_col)
                except Exception:
                    pass
        else:
            total_m8_count = len([m for m in obj.modifiers if m.type == "DATA_TRANSFER" and m.name.startswith(MODIFIER_PREFIX)])
            if total_m8_count > 1:
                self.report({"INFO"}, f"{_T('法向传递修改器已生效')} ({_T('叠加')} #{total_m8_count} - {mod_name}): {actual_mode} ({len(vert_indices)} {_T('点')})")
            else:
                self.report({"INFO"}, f"{_T('法向传递修改器已生效')}: {actual_mode} ({len(vert_indices)} {_T('点')})")

        # 确保安全切回原始网格对象的 EDIT 模式，杜绝活动物体漂移至辅助体
        context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}


class M8_OT_ApplyNormalTransfer(bpy.types.Operator):
    bl_idname = "m8.apply_normal_transfer"
    bl_label = _T("应用法向传递修改器")
    bl_description = _T("将当前物体上的所有 M8 法向传递修改器烘焙应用到网格，并自动清理多余的辅助体与顶点组")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            return False
        return any(
            m.type == "DATA_TRANSFER" and m.name.startswith(MODIFIER_PREFIX)
            for m in obj.modifiers
        )

    def execute(self, context):
        obj = context.active_object or context.edit_object
        prev_mode = context.mode

        if prev_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.objects.active = obj
        obj.select_set(True)

        applied_count = 0
        helpers_to_remove = set()
        vgs_to_remove = set()

        for mod in list(obj.modifiers):
            if mod.type == "DATA_TRANSFER" and mod.name.startswith(MODIFIER_PREFIX):
                if mod.object:
                    helpers_to_remove.add(mod.object)
                if mod.vertex_group and mod.vertex_group.startswith(VG_PREFIX):
                    vgs_to_remove.add(mod.vertex_group)
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    applied_count += 1
                except Exception as e:
                    logger.debug(f"Failed to apply {mod.name}: {e}")

        # 额外扫描并清理可能孤立残留的同名物体专属辅助体
        helper_prefix = f"_M8_Helper_{obj.name}_"
        helper_col = bpy.data.collections.get(HELPER_COLLECTION_NAME)
        if helper_col:
            for h_cand in list(helper_col.objects):
                if h_cand.name.startswith(helper_prefix):
                    helpers_to_remove.add(h_cand)

        for h_obj in helpers_to_remove:
            me = h_obj.data
            try:
                bpy.data.objects.remove(h_obj, do_unlink=True)
                if me and me.users == 0:
                    bpy.data.meshes.remove(me)
            except Exception:
                pass

        for vg_name in vgs_to_remove:
            vg = obj.vertex_groups.get(vg_name)
            if vg:
                obj.vertex_groups.remove(vg)

        # 空集合自动回收销毁 (零残留管理)
        helper_col = bpy.data.collections.get(HELPER_COLLECTION_NAME)
        if helper_col and len(helper_col.objects) == 0:
            try:
                bpy.data.collections.remove(helper_col)
            except Exception:
                pass

        if prev_mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")

        self.report({"INFO"}, f"{_T('已成功应用并清理')} {applied_count} {_T('个法向修改器')}")
        return {"FINISHED"}


class M8_OT_ClearNormalTransfer(bpy.types.Operator):
    bl_idname = "m8.clear_normal_transfer"
    bl_label = _T("清理法向传递修改器")
    bl_description = _T("移除当前物体上的所有 M8 法向传递修改器，并删除相关辅助体")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            return False
        return any(
            m.type == "DATA_TRANSFER" and m.name.startswith(MODIFIER_PREFIX)
            for m in obj.modifiers
        )

    def execute(self, context):
        obj = context.active_object or context.edit_object
        cleared_count = 0
        helpers_to_remove = set()
        vgs_to_remove = set()

        for mod in list(obj.modifiers):
            if mod.type == "DATA_TRANSFER" and mod.name.startswith(MODIFIER_PREFIX):
                if mod.object:
                    helpers_to_remove.add(mod.object)
                if mod.vertex_group and mod.vertex_group.startswith(VG_PREFIX):
                    vgs_to_remove.add(mod.vertex_group)
                obj.modifiers.remove(mod)
                cleared_count += 1

        # 额外扫描并清理可能孤立残留的同名物体专属辅助体
        helper_prefix = f"_M8_Helper_{obj.name}_"
        helper_col = bpy.data.collections.get(HELPER_COLLECTION_NAME)
        if helper_col:
            for h_cand in list(helper_col.objects):
                if h_cand.name.startswith(helper_prefix):
                    helpers_to_remove.add(h_cand)

        for h_obj in helpers_to_remove:
            me = h_obj.data
            try:
                bpy.data.objects.remove(h_obj, do_unlink=True)
                if me and me.users == 0:
                    bpy.data.meshes.remove(me)
            except Exception:
                pass

        for vg_name in vgs_to_remove:
            vg = obj.vertex_groups.get(vg_name)
            if vg:
                obj.vertex_groups.remove(vg)

        # 空集合自动回收销毁 (零残留管理)
        if helper_col and len(helper_col.objects) == 0:
            try:
                bpy.data.collections.remove(helper_col)
            except Exception:
                pass

        self.report({"INFO"}, f"{_T('已清理')} {cleared_count} {_T('个法向修改器与辅助体')}")
        return {"FINISHED"}


class M8_OT_FlipNormalTransfer(bpy.types.Operator):
    bl_idname = "m8.flip_normal_transfer"
    bl_label = _T("反转法向传递")
    bl_description = _T("快速反转当前物体上 M8 法向传递辅助体的法线朝向")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            return False
        return any(
            m.type == "DATA_TRANSFER" and m.name.startswith(MODIFIER_PREFIX) and m.object
            for m in obj.modifiers
        )

    def execute(self, context):
        obj = context.active_object or context.edit_object
        flipped_count = 0
        prev_mode = context.mode

        for mod in obj.modifiers:
            if mod.type == "DATA_TRANSFER" and mod.name.startswith(MODIFIER_PREFIX) and mod.object:
                h_obj = mod.object
                if h_obj.data and hasattr(h_obj.data, "polygons"):
                    # 如果辅助体处于编辑模式，先切换为对象模式
                    if h_obj.mode == "EDIT":
                        bpy.ops.object.mode_set(mode="OBJECT")
                    bm = bmesh.new()
                    bm.from_mesh(h_obj.data)
                    for f in bm.faces:
                        f.normal_flip()
                    bm.to_mesh(h_obj.data)
                    h_obj.data.update()
                    bm.free()
                    flipped_count += 1

        obj.data.update()
        if prev_mode == "EDIT_MESH" and context.mode != "EDIT_MESH":
            context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")

        self.report({"INFO"}, f"{_T('已反转')} {flipped_count} {_T('个辅助体的法向朝向')}")
        return {"FINISHED"}


class M8_OT_ClearCustomNormals(bpy.types.Operator):
    bl_idname = "m8.clear_custom_normals"
    bl_label = _T("重置自定义法向")
    bl_description = _T("清除当前物体的自定义分割法向数据，在编辑模式与对象模式下均可即时恢复网格默认着色")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        prev_mode = context.mode

        if prev_mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="OBJECT")

        # 1. 优先使用 Blender 官方 API 清除自定义分割法向
        try:
            if hasattr(obj.data, "has_custom_normals") and obj.data.has_custom_normals:
                obj.data.normals_split_custom_set([])
            obj.data.update()
        except Exception as e:
            logger.debug(f"Direct custom normal clear: {e}")

        # 2. 调用底层通用操作符确保在所有 Blender 版本下彻底清空
        context.view_layer.objects.active = obj
        try:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        except Exception:
            pass

        if prev_mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")

        self.report({"INFO"}, _T("已重置自定义法向"))
        return {"FINISHED"}


