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
SNAPSHOT_ATTR_NAME = "_M8_Normal_Snapshot"
SNAPSHOT_INFO_KEY = "_m8_normal_snapshot_info"
STASH_COLLECTION_NAME = "_M8_Normal_Stashes"
STASH_OBJ_PREFIX = "_M8_Stash_"
STASH_PROP_KEY = "_m8_normal_stash_name"
ALL_M8_NORMAL_MOD_PREFIXES = (MODIFIER_PREFIX, "M8_StashTransfer", "M8_TargetTransfer")
ALL_M8_NORMAL_VG_PREFIXES = (VG_PREFIX, "VG_M8_StashTransfer", "VG_M8_TargetTransfer")


def _extract_mesh_corner_normals(me):
    """跨 Blender 版本统一提取网格的面拐法向列表 [(nx, ny, nz), ...]"""
    total_corners = len(me.loops)
    if total_corners == 0:
        return []
    if hasattr(me, "corner_normals") and len(me.corner_normals) == total_corners:
        flat = [0.0] * (total_corners * 3)
        me.corner_normals.foreach_get("vector", flat)
        return [(flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2]) for i in range(total_corners)]
    else:
        if hasattr(me, "calc_normals_split"):
            try:
                me.calc_normals_split()
            except Exception:
                pass
        return [tuple(l.normal) for l in me.loops]


def _ensure_single_user_mesh(obj):
    """确保物体网格为单用户数据，防止 modifier_apply 抛出 Modifiers cannot be applied to multi-user data"""
    if obj and obj.type == "MESH" and obj.data and obj.data.users > 1:
        obj.data = obj.data.copy()


def _save_mesh_normal_snapshot(context, obj, silent=False):
    """将物体当前的最终计算法向（含修改器效果与已烘焙自定义法向）完整快照记录在网格原生属性中"""
    if not obj or obj.type != "MESH":
        return False, "无效的网格物体"

    prev_mode = context.mode
    if prev_mode == "EDIT_MESH":
        obj.update_from_editmode()
        bpy.ops.object.mode_set(mode="OBJECT")
    elif prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    context.view_layer.objects.active = obj
    obj.select_set(True)

    try:
        me = obj.data
        eval_normals = None
        try:
            dg = context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(dg)
            if eval_obj and eval_obj.data and len(eval_obj.data.loops) == len(me.loops):
                eval_normals = _extract_mesh_corner_normals(eval_obj.data)
        except Exception as e:
            logger.debug(f"Snapshot evaluated mesh fallback: {e}")

        if not eval_normals or len(eval_normals) != len(me.loops):
            eval_normals = _extract_mesh_corner_normals(me)

        if not eval_normals or len(eval_normals) != len(me.loops):
            return False, "无法提取当前网格的面拐法向数据"

        # 在 OBJECT 模式下获取或创建面拐属性 (此时 len(attr.data) == len(me.loops))
        attr = me.attributes.get(SNAPSHOT_ATTR_NAME)
        if not attr:
            attr = me.attributes.new(name=SNAPSHOT_ATTR_NAME, type="FLOAT_VECTOR", domain="CORNER")

        # 防御校验：确保属性数据长度与面拐数匹配，避免残留脏数据
        if len(attr.data) != len(me.loops):
            me.attributes.remove(attr)
            attr = me.attributes.new(name=SNAPSHOT_ATTR_NAME, type="FLOAT_VECTOR", domain="CORNER")

        flat = [comp for norm in eval_normals for comp in norm]
        attr.data.foreach_set("vector", flat)

        import time
        poly_smooth = [bool(p.use_smooth) for p in me.polygons]
        obj[SNAPSHOT_INFO_KEY] = {
            "timestamp": time.time(),
            "loop_count": len(me.loops),
            "poly_count": len(me.polygons),
            "vert_count": len(me.vertices),
            "poly_smooth": poly_smooth,
        }

        if not silent:
            logger.info(f"M8 Normal Snapshot saved for {obj.name}: {len(eval_normals)} corner normals.")
        return True, f"已成功保存 {len(eval_normals)} 个面拐法向快照"

    finally:
        if prev_mode == "EDIT_MESH":
            context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
        elif prev_mode != "OBJECT" and context.mode != prev_mode:
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except Exception:
                pass


def _restore_mesh_normal_snapshot(context, obj):
    """从网格快照属性中 100% 恢复自定义分割法向与多边形着色状态"""
    if not obj or obj.type != "MESH":
        return False, "无效的网格物体"

    prev_mode = context.mode
    if prev_mode == "EDIT_MESH":
        obj.update_from_editmode()
        bpy.ops.object.mode_set(mode="OBJECT")
    elif prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    context.view_layer.objects.active = obj
    obj.select_set(True)

    try:
        me = obj.data
        attr = me.attributes.get(SNAPSHOT_ATTR_NAME)
        if not attr:
            return False, "当前物体未保存任何法向快照"

        if len(attr.data) != len(me.loops):
            return False, f"网格拓扑已变更（当前面拐: {len(me.loops)}, 快照面拐: {len(attr.data)}），无法直接还原"

        # 1. 优先恢复多边形原始平滑/平直着色状态 (确保立面 Flat 与曲面 Smooth 各得其所)
        info = obj.get(SNAPSHOT_INFO_KEY, {})
        poly_smooth = info.get("poly_smooth")
        if poly_smooth and len(poly_smooth) == len(me.polygons):
            for poly, is_sm in zip(me.polygons, poly_smooth):
                poly.use_smooth = is_sm
        else:
            for poly in me.polygons:
                poly.use_smooth = True

        total_corners = len(me.loops)
        flat = [0.0] * (total_corners * 3)
        attr.data.foreach_get("vector", flat)
        loop_normals = [
            (flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2])
            for i in range(total_corners)
        ]

        try:
            me.normals_split_custom_set(loop_normals)
            me.update()
        except Exception as e:
            return False, f"恢复法向失败: {e}"

        return True, f"已成功恢复 {total_corners} 个面拐的自定义法向快照"

    finally:
        if prev_mode == "EDIT_MESH":
            context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
        elif prev_mode != "OBJECT" and context.mode != prev_mode:
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except Exception:
                pass


def _clear_mesh_normal_snapshot(context, obj):
    """清除当前物体上的法向快照属性与历史元数据"""
    if not obj or obj.type != "MESH":
        return False, "无效的网格物体"

    prev_mode = context.mode
    if prev_mode == "EDIT_MESH":
        obj.update_from_editmode()
        bpy.ops.object.mode_set(mode="OBJECT")
    elif prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    context.view_layer.objects.active = obj
    obj.select_set(True)

    try:
        me = obj.data
        attr = me.attributes.get(SNAPSHOT_ATTR_NAME)
        if attr:
            me.attributes.remove(attr)
        if SNAPSHOT_INFO_KEY in obj:
            del obj[SNAPSHOT_INFO_KEY]
        return True, "已成功清除法向快照历史"

    finally:
        if prev_mode == "EDIT_MESH":
            context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
        elif prev_mode != "OBJECT" and context.mode != prev_mode:
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except Exception:
                pass


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


def _get_or_create_stash_collection(scene):
    """获取或创建专门收纳几何暂存体 (Stash) 的隐藏集合，默认在视口与大纲中静默隐藏"""
    col = bpy.data.collections.get(STASH_COLLECTION_NAME)
    if not col:
        col = bpy.data.collections.new(STASH_COLLECTION_NAME)
        scene.collection.children.link(col)
    col.hide_viewport = True
    col.hide_render = True
    vl = getattr(bpy.context, "view_layer", None)
    if vl:
        _hide_collection_in_view_layer(vl, STASH_COLLECTION_NAME, hide=True)
    return col


def _get_geometry_stash(obj):
    """获取与当前物体关联的几何暂存体对象"""
    if not obj or obj.type != "MESH":
        return None
    stash_name = obj.get(STASH_PROP_KEY)
    if stash_name:
        stash_obj = bpy.data.objects.get(stash_name)
        if stash_obj and stash_obj.type == "MESH":
            return stash_obj
    default_name = f"{STASH_OBJ_PREFIX}{obj.name}"
    stash_obj = bpy.data.objects.get(default_name)
    if stash_obj and stash_obj.type == "MESH":
        return stash_obj
    return None


def _create_geometry_stash(context, obj):
    """
    在破坏性布尔/倒角/拓扑改动前，将当前网格的纯净几何与计算法向完整克隆并暂存在隐藏集合中。
    无论后续拓扑如何被破坏，均可通过数据传递跨拓扑投影恢复完美曲率法向 (MESHmachine Stash 范式)。
    """
    if not obj or obj.type != "MESH":
        return None, "无效的网格物体"

    prev_mode = context.mode
    if prev_mode == "EDIT_MESH":
        obj.update_from_editmode()
        bpy.ops.object.mode_set(mode="OBJECT")
    elif prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    context.view_layer.objects.active = obj
    obj.select_set(True)

    try:
        # 清理已有同名旧暂存体
        old_stash = _get_geometry_stash(obj)
        if old_stash:
            old_me = old_stash.data
            bpy.data.objects.remove(old_stash, do_unlink=True)
            if old_me and old_me.users == 0:
                bpy.data.meshes.remove(old_me)

        # 评估网格，获取当前物体最终状态（含修改器效果与平滑着色）
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        stash_me = bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True, depsgraph=depsgraph)
        stash_name = f"{STASH_OBJ_PREFIX}{obj.name}"
        stash_me.name = f"{stash_name}_Mesh"

        stash_obj = bpy.data.objects.new(stash_name, stash_me)
        stash_obj.matrix_world = obj.matrix_world.copy()
        stash_obj.hide_viewport = True
        stash_obj.hide_render = True

        stash_col = _get_or_create_stash_collection(context.scene)
        stash_col.objects.link(stash_obj)

        obj[STASH_PROP_KEY] = stash_obj.name

        return stash_obj, f"已成功暂存当前几何体: {stash_obj.name} ({len(stash_me.polygons)} 面)"
    finally:
        if prev_mode == "EDIT_MESH":
            context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
        elif prev_mode != "OBJECT" and context.mode != prev_mode:
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except Exception:
                pass


def _clear_geometry_stash(context, obj):
    """彻底清除指定物体的几何暂存体与关联数据块"""
    if not obj or obj.type != "MESH":
        return False, "无效的网格物体"

    stash_obj = _get_geometry_stash(obj)
    if not stash_obj:
        if STASH_PROP_KEY in obj:
            del obj[STASH_PROP_KEY]
        return False, "未找到关联的几何暂存体"

    stash_me = stash_obj.data
    try:
        bpy.data.objects.remove(stash_obj, do_unlink=True)
        if stash_me and stash_me.users == 0:
            bpy.data.meshes.remove(stash_me)
    except Exception as e:
        logger.debug(f"Clear geometry stash fallback: {e}")

    if STASH_PROP_KEY in obj:
        del obj[STASH_PROP_KEY]

    # 空集合自动回收
    col = bpy.data.collections.get(STASH_COLLECTION_NAME)
    if col and len(col.objects) == 0:
        try:
            bpy.data.collections.remove(col)
        except Exception:
            pass

    return True, "已清除几何暂存体"


def _apply_normal_transfer_from_source(
    context,
    target_obj,
    source_obj,
    selected_only=True,
    mapping="POLYINTERP_NEAREST",
    apply_and_clean=False,
    mod_prefix="M8_Transfer",
):
    """
    从源几何体 (source_obj) 跨拓扑投射法向至目标物体 (target_obj)。
    支持编辑模式局部面选区与整物体全量投射。
    """
    if not target_obj or target_obj.type != "MESH":
        return False, "无效的目标网格物体"
    if not source_obj or source_obj.type != "MESH":
        return False, "请指定有效的参考网格物体"

    prev_mode = context.mode
    selected_verts = []
    selected_faces = []

    if prev_mode == "EDIT_MESH":
        target_obj.update_from_editmode()
        bm = bmesh.from_edit_mesh(target_obj.data)
        selected_faces = [f.index for f in bm.faces if f.select]
        selected_verts = [v.index for v in bm.verts if v.select]
        if not selected_faces and not selected_verts:
            # 若未选择任何面/点，自动退化为全物体投射
            selected_only = False
        bpy.ops.object.mode_set(mode="OBJECT")
    elif prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    context.view_layer.objects.active = target_obj
    target_obj.select_set(True)

    try:
        vg = None
        if selected_only and (selected_verts or selected_faces):
            vg_name = f"VG_{mod_prefix}_{source_obj.name[:10]}"
            vg = target_obj.vertex_groups.get(vg_name)
            if not vg:
                vg = target_obj.vertex_groups.new(name=vg_name)
            else:
                try:
                    vg.remove(list(range(len(target_obj.data.vertices))))
                except Exception:
                    pass

            v_indices = set(selected_verts)
            for p_idx in selected_faces:
                p = target_obj.data.polygons[p_idx]
                v_indices.update(p.vertices)

            for vid in v_indices:
                vg.add([vid], 1.0, "REPLACE")

        mod_name = f"{mod_prefix}_{source_obj.name[:12]}"
        mod = target_obj.modifiers.get(mod_name)
        if not mod:
            mod = target_obj.modifiers.new(name=mod_name, type="DATA_TRANSFER")

        mod.object = source_obj
        mod.use_loop_data = True
        mod.data_types_loops = {"CUSTOM_NORMAL"}
        mod.loop_mapping = mapping
        if vg:
            mod.vertex_group = vg.name

        # 确保 DATA_TRANSFER 位于 WEIGHTED_NORMAL 之后，防止传递法向被覆盖
        weighted_mods = [m for m in target_obj.modifiers if m.type == "WEIGHTED_NORMAL"]
        if weighted_mods and hasattr(target_obj.modifiers, "move"):
            try:
                last_wn_idx = max(target_obj.modifiers.find(m.name) for m in weighted_mods)
                curr_idx = target_obj.modifiers.find(mod.name)
                if curr_idx < last_wn_idx:
                    target_obj.modifiers.move(curr_idx, last_wn_idx)
            except Exception as e:
                logger.debug(f"Modifier move after WEIGHTED_NORMAL fallback: {e}")

        # 仅将受影响的多边形标记为 smooth，杜绝污染平直侧面
        if selected_faces:
            for p_idx in selected_faces:
                target_obj.data.polygons[p_idx].use_smooth = True
        elif not selected_only:
            for poly in target_obj.data.polygons:
                poly.use_smooth = True

        if apply_and_clean:
            try:
                _ensure_single_user_mesh(target_obj)
                bpy.ops.object.modifier_apply(modifier=mod.name)
                # 自动快照备份
                try:
                    _save_mesh_normal_snapshot(context, target_obj, silent=True)
                except Exception:
                    pass
                if vg:
                    try:
                        target_obj.vertex_groups.remove(vg)
                    except Exception:
                        pass
                return True, f"已成功将 {source_obj.name} 的法向烘焙至网格"
            except Exception as e:
                return False, f"修改器应用失败: {e}"
        else:
            return True, f"法向传递修改器已就绪: 来源 [{source_obj.name}] ➔ 算法 [{mapping}]"

    finally:
        if prev_mode == "EDIT_MESH":
            context.view_layer.objects.active = target_obj
            target_obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
        elif prev_mode != "OBJECT" and context.mode != prev_mode:
            try:
                bpy.ops.object.mode_set(mode=prev_mode)
            except Exception:
                pass


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
    if bm_target and selected_faces:
        try:
            target_verts_co = [v.co for v in bm_target.verts]
            target_polys = [[v.index for v in f.verts] for f in selected_faces]
            bvh = BVHTree.FromPolygons(target_verts_co, target_polys)
        except Exception:
            bvh = None

    bm_helper.verts.ensure_lookup_table()
    bm_helper.faces.ensure_lookup_table()
    bm_helper.normal_update()

    for v in bm_helper.verts:
        out_norm = None
        if bvh:
            loc, norm, idx, dist = bvh.find_nearest(v.co)
            if loc is not None and norm is not None and norm.length > 1e-4:
                out_norm = norm.normalized()
                if auto_wrap_outside:
                    disp = v.co - loc
                    signed_dist = disp.dot(out_norm)
                    if signed_dist < 0.0:
                        # 强力纠偏：推至原模型外侧微量安全边界 (至少处于表面偏外 0.0005m)
                        v.co = loc + out_norm * 0.0005

        if abs(cage_offset) > 1e-6:
            # 优先使用原模型表面绝对朝外的外法向进行 Cage 外推，杜绝辅助体面法向反转导致的向内穿模
            push_dir = out_norm
            if push_dir is None or push_dir.length < 1e-4:
                push_dir = v.normal if v.normal.length > 1e-4 else sum((f.normal for f in v.link_faces), Vector())
            if push_dir and push_dir.length > 1e-4:
                v.co += push_dir.normalized() * cage_offset

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
            box_cyl.prop(self, "cylinder_segments", text=_T("圆柱分段数"))
            box_cyl.prop(self, "axis_override", text=_T("圆柱中轴方向"))
            box_cyl.prop(self, "cylinder_cap_mode", text=_T("端盖闭合"))
            box_cyl.prop(self, "cylinder_arc_mode", text=_T("弧度范围"))

        if self.mode in ("AUTO", "SMOOTH_EXTRACT"):
            box_smooth = layout.box()
            box_smooth.label(text=_T("提取与四边面平滑"), icon="MOD_SMOOTH")
            box_smooth.prop(self, "extract_clean_mode", text=_T("提取净化模式"))
            if self.extract_clean_mode in ("AUTO", "BRIDGE"):
                box_smooth.prop(self, "profile_cuts", text=_T("剖面中间分段"))
            if self.extract_clean_mode in ("AUTO", "DISSOLVE"):
                box_smooth.prop(self, "dissolve_angle", text=_T("融解角度阈值"))
            box_smooth.prop(self, "smooth_iterations", text=_T("平滑迭代次数"))

            box_quad = box_smooth.box()
            box_quad.prop(self, "quad_remesh", text=_T("重置为四边面"), icon="MESH_GRID")
            if self.quad_remesh:
                box_quad.prop(self, "quad_subdiv", text=_T("四边面细分层级"))
                box_quad.prop(self, "snap_to_surface", text=_T("贴合原曲面"))
                box_quad.prop(self, "quad_smooth_factor", text=_T("曲面光顺度"))

            box_cage = box_smooth.box()
            box_cage.label(text=_T("外壳包裹与防内缩 (Cage)"), icon="OUTLINER_OB_SURFACE")
            box_cage.prop(self, "cage_offset", text=_T("向外包裹偏移"))
            box_cage.prop(self, "auto_wrap_outside", text=_T("防内缩外壳保护"))

        layout.separator()
        layout.prop(self, "grow_steps", text=_T("扩展选区 (圈数)"))

        row = layout.row()
        row.prop(self, "flip_normal", text=_T("反转法向"), icon="ARROW_LEFTRIGHT")
        row.prop(self, "show_helper", text=_T("显示辅助体"), icon="HIDE_OFF" if self.show_helper else "HIDE_ON")

        box_stack = layout.box()
        box_stack.prop(self, "stack_mode", text=_T("叠加模式"), icon="DUPLICATE")

        box = layout.box()
        box.alert = bool(self.apply_and_clean)
        box.prop(self, "apply_and_clean", text=_T("立即烘焙并清理"), icon="CHECKMARK")

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
                _ensure_single_user_mesh(obj)
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
                _ensure_single_user_mesh(obj)
                bpy.ops.object.modifier_apply(modifier=mod.name)
                # 自动快照备份：在修改器烘焙应用完成后，自动静默记录法向快照，提供随时可逆的后悔药保障
                try:
                    _save_mesh_normal_snapshot(context, obj, silent=True)
                except Exception as e:
                    logger.debug(f"Auto-snapshot on apply_and_clean fallback: {e}")
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
            m.type == "DATA_TRANSFER" and m.name.startswith(ALL_M8_NORMAL_MOD_PREFIXES)
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

        _ensure_single_user_mesh(obj)

        for mod in list(obj.modifiers):
            if mod.type == "DATA_TRANSFER" and mod.name.startswith(ALL_M8_NORMAL_MOD_PREFIXES):
                # 仅回收 M8 专属辅助体，严禁误删用户场景中的高模参考物体或暂存体
                if mod.object and mod.object.name.startswith("_M8_Helper_"):
                    helpers_to_remove.add(mod.object)
                if mod.vertex_group and mod.vertex_group.startswith(ALL_M8_NORMAL_VG_PREFIXES):
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

        # 自动快照备份：在修改器烘焙应用完成后，自动静默记录法向快照，提供随时可逆的后悔药保障
        try:
            _save_mesh_normal_snapshot(context, obj, silent=True)
        except Exception as e:
            logger.debug(f"Auto-snapshot on apply fallback: {e}")

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
            m.type == "DATA_TRANSFER" and m.name.startswith(ALL_M8_NORMAL_MOD_PREFIXES)
            for m in obj.modifiers
        )

    def execute(self, context):
        obj = context.active_object or context.edit_object
        cleared_count = 0
        helpers_to_remove = set()
        vgs_to_remove = set()

        for mod in list(obj.modifiers):
            if mod.type == "DATA_TRANSFER" and mod.name.startswith(ALL_M8_NORMAL_MOD_PREFIXES):
                # 仅回收 M8 专属辅助体，严禁误删用户场景中的高模参考物体或暂存体
                if mod.object and mod.object.name.startswith("_M8_Helper_"):
                    helpers_to_remove.add(mod.object)
                if mod.vertex_group and mod.vertex_group.startswith(ALL_M8_NORMAL_VG_PREFIXES):
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
    bl_label = _T("反转法向")
    bl_description = _T("反转当前物体上 M8 辅助体的法向朝向，或直接将选中区域的自定义分割法向取反")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, _T("无效的网格物体"))
            return {"CANCELLED"}

        prev_mode = context.mode
        helper_mods = [
            m for m in obj.modifiers
            if m.type == "DATA_TRANSFER"
            and m.name.startswith(ALL_M8_NORMAL_MOD_PREFIXES)
            and m.object
            and m.object.name.startswith("_M8_Helper_")
        ]

        if helper_mods:
            flipped_count = 0
            for mod in helper_mods:
                h_obj = mod.object
                if h_obj and h_obj.data and hasattr(h_obj.data, "polygons"):
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

        # 模式 2：直接反转选区或网格的自定义法向向量 (Invert Custom Normals)
        selected_verts = set()
        selected_faces = set()
        if prev_mode == "EDIT_MESH":
            obj.update_from_editmode()
            bm = bmesh.from_edit_mesh(obj.data)
            selected_verts = {v.index for v in bm.verts if v.select}
            selected_faces = {f.index for f in bm.faces if f.select}
            bpy.ops.object.mode_set(mode="OBJECT")
        elif prev_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        context.view_layer.objects.active = obj
        obj.select_set(True)

        try:
            me = obj.data
            total_corners = len(me.loops)
            if total_corners == 0:
                self.report({"WARNING"}, _T("网格没有面拐数据"))
                return {"CANCELLED"}

            curr_normals = _extract_mesh_corner_normals(me)
            new_normals = list(curr_normals)

            affected_vert_set = set()
            if selected_verts or selected_faces:
                affected_vert_set.update(selected_verts)
                for f_idx in selected_faces:
                    affected_vert_set.update(me.polygons[f_idx].vertices)
            else:
                affected_vert_set = set(range(len(me.vertices)))

            for l_idx, loop in enumerate(me.loops):
                if loop.vertex_index in affected_vert_set:
                    cn = curr_normals[l_idx]
                    new_normals[l_idx] = (-cn[0], -cn[1], -cn[2])

            _ensure_single_user_mesh(obj)
            me = obj.data

            for poly in me.polygons:
                if any(v in affected_vert_set for v in poly.vertices):
                    poly.use_smooth = True

            me.normals_split_custom_set(new_normals)
            me.update()

            try:
                _save_mesh_normal_snapshot(context, obj, silent=True)
            except Exception:
                pass

            self.report({"INFO"}, f"{_T('已反转')} {len(affected_vert_set)} {_T('个顶点的自定义法向')}")
            return {"FINISHED"}
        finally:
            if prev_mode == "EDIT_MESH":
                context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
            elif prev_mode != "OBJECT" and context.mode != prev_mode:
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass



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


class M8_OT_SaveNormalSnapshot(bpy.types.Operator):
    bl_idname = "m8.save_normal_snapshot"
    bl_label = _T("保存法向快照")
    bl_description = _T("将当前物体的最终法向完整记录为快照并保存在网格中，随工程文件永久保存，支持随时恢复")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        success, msg = _save_mesh_normal_snapshot(context, obj, silent=False)
        if success:
            self.report({"INFO"}, _T(msg))
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T(msg))
            return {"CANCELLED"}


class M8_OT_RestoreNormalSnapshot(bpy.types.Operator):
    bl_idname = "m8.restore_normal_snapshot"
    bl_label = _T("还原法向快照")
    bl_description = _T("从网格快照中 100% 还原自定义法向，即使已应用修改器、重置法向或重新打开文件均可一键恢复")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            return False
        return SNAPSHOT_ATTR_NAME in obj.data.attributes

    def execute(self, context):
        obj = context.active_object or context.edit_object
        success, msg = _restore_mesh_normal_snapshot(context, obj)
        if success:
            self.report({"INFO"}, _T(msg))
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T(msg))
            return {"CANCELLED"}


class M8_OT_ClearNormalSnapshot(bpy.types.Operator):
    bl_idname = "m8.clear_normal_snapshot"
    bl_label = _T("清除法向快照")
    bl_description = _T("清除当前物体上保存的法向历史快照数据与属性")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            return False
        return SNAPSHOT_ATTR_NAME in obj.data.attributes

    def execute(self, context):
        obj = context.active_object or context.edit_object
        success, msg = _clear_mesh_normal_snapshot(context, obj)
        if success:
            self.report({"INFO"}, _T(msg))
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T(msg))
            return {"CANCELLED"}


class M8_OT_CreateGeometryStash(bpy.types.Operator):
    bl_idname = "m8.create_geometry_stash"
    bl_label = _T("暂存几何体 (Stash)")
    bl_description = _T("在破坏性布尔/倒角前将干净几何体暂存至隐藏集合，以便后续跨拓扑100%还原完美曲率法向")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        stash_obj, msg = _create_geometry_stash(context, obj)
        if stash_obj:
            self.report({"INFO"}, _T(msg))
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T(msg))
            return {"CANCELLED"}


class M8_OT_TransferFromStash(bpy.types.Operator):
    bl_idname = "m8.transfer_from_stash"
    bl_label = _T("从暂存体恢复法向")
    bl_description = _T("利用数据传递修改器从暂存的几何体跨拓扑投射法向至当前网格")
    bl_options = {"REGISTER", "UNDO"}

    mapping: bpy.props.EnumProperty(
        name=_T("面拐映射算法"),
        items=[
            ("POLYINTERP_NEAREST", _T("最近多边形插值 (推荐)"), _T("跨拓扑最均匀保真")),
            ("NEAREST_POLYNOR", _T("最近多边形法向"), _T("匹配最近面的法向")),
            ("NEAREST_CORNER", _T("最近面拐点"), _T("匹配最近的角点")),
            ("TOPOLOGY", _T("拓扑匹配"), _T("点线面完全相同时 1:1 映射")),
        ],
        default="POLYINTERP_NEAREST",
    )

    selected_only: bpy.props.BoolProperty(
        name=_T("仅限选中区域"),
        description=_T("仅将法向投射至当前选中的面/顶点；未勾选则作用于整物体"),
        default=True,
    )

    apply_and_clean: bpy.props.BoolProperty(
        name=_T("直接烘焙并清理"),
        description=_T("立即应用修改器并清理临时顶点组，无需手动应用"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            return False
        return _get_geometry_stash(obj) is not None

    def execute(self, context):
        obj = context.active_object or context.edit_object
        stash_obj = _get_geometry_stash(obj)
        if not stash_obj:
            self.report({"WARNING"}, _T("未找到与当前物体关联的几何暂存体"))
            return {"CANCELLED"}

        success, msg = _apply_normal_transfer_from_source(
            context,
            target_obj=obj,
            source_obj=stash_obj,
            selected_only=self.selected_only,
            mapping=self.mapping,
            apply_and_clean=self.apply_and_clean,
            mod_prefix="M8_StashTransfer",
        )
        if success:
            self.report({"INFO"}, _T(msg))
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T(msg))
            return {"CANCELLED"}


class M8_OT_ClearGeometryStash(bpy.types.Operator):
    bl_idname = "m8.clear_geometry_stash"
    bl_label = _T("清除几何暂存")
    bl_description = _T("彻底清除当前物体关联的几何暂存体及数据块")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            return False
        return _get_geometry_stash(obj) is not None

    def execute(self, context):
        obj = context.active_object or context.edit_object
        success, msg = _clear_geometry_stash(context, obj)
        if success:
            self.report({"INFO"}, _T(msg))
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T(msg))
            return {"CANCELLED"}


class M8_OT_TransferFromTarget(bpy.types.Operator):
    bl_idname = "m8.transfer_from_target"
    bl_label = _T("从目标物体吸取法向")
    bl_description = _T("从视口选中的另一个网格物体或指定目标参考体跨物体传递法向 (Normal Thief / Target Transfer 范式)")
    bl_options = {"REGISTER", "UNDO"}

    target_object_name: bpy.props.StringProperty(
        name=_T("目标参考物体"),
        description=_T("作为法向来源的参考物体名称（留空则自动选用视口中选中的其他网格物体）"),
        default="",
    )

    mapping: bpy.props.EnumProperty(
        name=_T("面拐映射算法"),
        items=[
            ("POLYINTERP_NEAREST", _T("最近多边形插值 (推荐)"), _T("跨拓扑最均匀保真")),
            ("NEAREST_POLYNOR", _T("最近多边形法向"), _T("匹配最近面的法向")),
            ("NEAREST_CORNER", _T("最近面拐点"), _T("匹配最近的角点")),
            ("TOPOLOGY", _T("拓扑匹配"), _T("点线面完全相同时 1:1 映射")),
        ],
        default="POLYINTERP_NEAREST",
    )

    selected_only: bpy.props.BoolProperty(
        name=_T("仅限选中区域"),
        description=_T("仅将法向投射至当前选中的面/顶点；未勾选则作用于整物体"),
        default=True,
    )

    apply_and_clean: bpy.props.BoolProperty(
        name=_T("直接烘焙并清理"),
        description=_T("立即应用修改器并清理临时顶点组"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def invoke(self, context, event):
        act_obj = context.active_object or context.edit_object
        if not self.target_object_name:
            candidates = [o for o in context.selected_objects if o != act_obj and o.type == "MESH"]
            if candidates:
                self.target_object_name = candidates[0].name
        return self.execute(context)

    def execute(self, context):
        act_obj = context.active_object or context.edit_object
        if not act_obj or act_obj.type != "MESH":
            self.report({"WARNING"}, _T("无效的目标网格物体"))
            return {"CANCELLED"}

        source_obj = None
        if self.target_object_name:
            source_obj = bpy.data.objects.get(self.target_object_name)

        if not source_obj or source_obj.type != "MESH":
            candidates = [o for o in context.selected_objects if o != act_obj and o.type == "MESH"]
            if candidates:
                source_obj = candidates[0]

        if not source_obj or source_obj.type != "MESH":
            self.report({"WARNING"}, _T("请在视口中同时选中参考高模物体，或在操作面板中指定目标参考物体"))
            return {"CANCELLED"}

        if source_obj == act_obj:
            self.report({"WARNING"}, _T("源参考物体不能与当前操作物体相同"))
            return {"CANCELLED"}

        success, msg = _apply_normal_transfer_from_source(
            context,
            target_obj=act_obj,
            source_obj=source_obj,
            selected_only=self.selected_only,
            mapping=self.mapping,
            apply_and_clean=self.apply_and_clean,
            mod_prefix="M8_TargetTransfer",
        )
        if success:
            self.report({"INFO"}, _T(msg))
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T(msg))
            return {"CANCELLED"}


class M8_OT_PointNormalsToCursor(bpy.types.Operator):
    bl_idname = "m8.point_normals_to_cursor"
    bl_label = _T("法向指向游标")
    bl_description = _T("将选中顶点/面拐的自定义法向对齐至 3D 游标（从游标发射或指向游标），常用于圆顶、圆弧面与植被树冠的高光平滑 (Abnormal 范式)")
    bl_options = {"REGISTER", "UNDO"}

    invert: bpy.props.BoolProperty(
        name=_T("反向指向"),
        description=_T("反转方向，使法向指向 3D 游标中心（适合内凹碗状/反射罩几何）"),
        default=False,
    )

    selected_only: bpy.props.BoolProperty(
        name=_T("仅限选中区域"),
        description=_T("仅调整当前选中的面或顶点；未勾选则作用于整个模型"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, _T("无效的网格物体"))
            return {"CANCELLED"}

        prev_mode = context.mode
        selected_verts = set()
        selected_faces = set()

        if prev_mode == "EDIT_MESH":
            obj.update_from_editmode()
            bm = bmesh.from_edit_mesh(obj.data)
            selected_verts = {v.index for v in bm.verts if v.select}
            selected_faces = {f.index for f in bm.faces if f.select}
            if not selected_verts and not selected_faces:
                self.selected_only = False
            bpy.ops.object.mode_set(mode="OBJECT")
        elif prev_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        context.view_layer.objects.active = obj
        obj.select_set(True)

        try:
            me = obj.data
            cursor_loc = context.scene.cursor.location
            mat_world = obj.matrix_world
            local_cursor = mat_world.inverted() @ cursor_loc

            total_corners = len(me.loops)
            if total_corners == 0:
                self.report({"WARNING"}, _T("网格没有面拐数据"))
                return {"CANCELLED"}

            # 提取现有法向作为基底
            curr_normals = _extract_mesh_corner_normals(me)
            new_normals = list(curr_normals)

            # 确定受影响顶点
            affected_vert_set = set()
            if self.selected_only and (selected_verts or selected_faces):
                affected_vert_set.update(selected_verts)
                for f_idx in selected_faces:
                    affected_vert_set.update(me.polygons[f_idx].vertices)
            else:
                affected_vert_set = set(range(len(me.vertices)))

            # 计算每个局部顶点的朝向向量
            vert_local_dirs = {}
            for vid in affected_vert_set:
                v = me.vertices[vid]
                diff = v.co - local_cursor
                if diff.length_squared < 1e-8:
                    diff = Vector((0, 0, 1))
                if self.invert:
                    diff = -diff
                vert_local_dirs[vid] = tuple(diff.normalized())

            # 赋给对应 loop
            for l_idx, loop in enumerate(me.loops):
                if loop.vertex_index in vert_local_dirs:
                    new_normals[l_idx] = vert_local_dirs[loop.vertex_index]

            # 确保单用户保护
            _ensure_single_user_mesh(obj)
            me = obj.data

            # 必须先标记受影响的多边形为 smooth，再写入分割法向，避免 use_smooth 冲刷重算法向
            for poly in me.polygons:
                if any(v in affected_vert_set for v in poly.vertices):
                    poly.use_smooth = True

            me.normals_split_custom_set(new_normals)
            me.update()

            # 自动备份快照
            try:
                _save_mesh_normal_snapshot(context, obj, silent=True)
            except Exception:
                pass

            self.report({"INFO"}, f"{_T('已将')} {len(affected_vert_set)} {_T('个顶点的法向对齐至 3D 游标')}")
            return {"FINISHED"}
        finally:
            if prev_mode == "EDIT_MESH":
                context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
            elif prev_mode != "OBJECT" and context.mode != prev_mode:
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass


class M8_OT_ToggleSplitNormals(bpy.types.Operator):
    bl_idname = "m8.toggle_split_normals"
    bl_label = _T("显示法向连线")
    bl_description = _T("切换 3D 视图中面拐分割法向线（Split Normals）的显隐，用于直观检查模型法向与光影平滑度")
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        v3d = None
        space = getattr(context, "space_data", None)
        if space and space.type == "VIEW_3D":
            v3d = space
        else:
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    v3d = area.spaces.active
                    break

        if v3d and hasattr(v3d, "overlay"):
            curr = v3d.overlay.show_split_normals
            v3d.overlay.show_split_normals = not curr
            state_str = _T("开启") if not curr else _T("关闭")
            self.report({"INFO"}, f"{_T('法向连线显示已')}{state_str}")
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, _T("未找到活动的 3D 视图"))
            return {"CANCELLED"}


class M8_OT_FlattenNormals(bpy.types.Operator):
    bl_idname = "m8.flatten_normals"
    bl_label = _T("选区法向拍平")
    bl_description = _T("将选中区域的面拐法向直接对齐至几何面法向，无需修改器即可瞬间消除硬表面开孔、凹槽周围的高光黑斑与波浪拉扯 (MESHmachine & Y.A.V.N.E. 范式)")
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name=_T("拍平模式"),
        items=[
            ("PER_FACE", _T("各面独立拍平"), _T("每个选中的多边形分别将其所有面拐法向对齐为其自身的几何面法向 (最适合复杂角度的多孔硬表面)")),
            ("AVERAGE", _T("选区平均平面"), _T("计算选中面的面积加权平均几何法向，并将所有选中面拐对齐至该统一平面")),
            ("ACTIVE", _T("对齐活动面"), _T("将所有选中面拐强制对齐至活动多边形 (Active Face) 的几何法向")),
        ],
        default="PER_FACE",
    )

    selected_only: bpy.props.BoolProperty(
        name=_T("仅限选中区域"),
        description=_T("仅处理当前选中的面或顶点；未勾选则作用于整个模型"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, _T("无效的网格物体"))
            return {"CANCELLED"}

        prev_mode = context.mode
        selected_faces = []
        selected_verts = set()
        active_face_idx = None

        if prev_mode == "EDIT_MESH":
            obj.update_from_editmode()
            bm = bmesh.from_edit_mesh(obj.data)
            selected_faces = [f.index for f in bm.faces if f.select]
            selected_verts = {v.index for v in bm.verts if v.select}
            if bm.faces.active and bm.faces.active.select:
                active_face_idx = bm.faces.active.index
            if not selected_faces and not selected_verts:
                self.selected_only = False
            bpy.ops.object.mode_set(mode="OBJECT")
        elif prev_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        context.view_layer.objects.active = obj
        obj.select_set(True)

        try:
            me = obj.data
            total_corners = len(me.loops)
            if total_corners == 0:
                self.report({"WARNING"}, _T("网格没有面拐数据"))
                return {"CANCELLED"}

            target_poly_indices = set()
            if self.selected_only and (selected_faces or selected_verts):
                target_poly_indices.update(selected_faces)
                for p in me.polygons:
                    if any(v in selected_verts for v in p.vertices):
                        target_poly_indices.add(p.index)
            else:
                target_poly_indices = set(range(len(me.polygons)))

            if not target_poly_indices:
                self.report({"WARNING"}, _T("未选中任何多边形"))
                return {"CANCELLED"}

            curr_normals = _extract_mesh_corner_normals(me)
            new_normals = list(curr_normals)

            # 模式 1: 对齐活动面
            if self.mode == "ACTIVE" and active_face_idx is not None and active_face_idx < len(me.polygons):
                act_norm = tuple(me.polygons[active_face_idx].normal.normalized())
                for p_idx in target_poly_indices:
                    poly = me.polygons[p_idx]
                    for l_idx in poly.loop_indices:
                        new_normals[l_idx] = act_norm
            # 模式 2: 选区面积加权平均平面
            elif self.mode == "AVERAGE":
                weighted_sum = Vector((0.0, 0.0, 0.0))
                for p_idx in target_poly_indices:
                    p = me.polygons[p_idx]
                    weighted_sum += p.normal * max(p.area, 1e-6)
                if weighted_sum.length_squared > 1e-8:
                    avg_norm = tuple(weighted_sum.normalized())
                else:
                    avg_norm = (0.0, 0.0, 1.0)
                for p_idx in target_poly_indices:
                    poly = me.polygons[p_idx]
                    for l_idx in poly.loop_indices:
                        new_normals[l_idx] = avg_norm
            # 模式 3: 各面独立按自身几何法向拍平 (PER_FACE)
            else:
                for p_idx in target_poly_indices:
                    poly = me.polygons[p_idx]
                    p_norm = poly.normal
                    if p_norm.length_squared > 1e-8:
                        fn = tuple(p_norm.normalized())
                    else:
                        fn = (0.0, 0.0, 1.0)
                    for l_idx in poly.loop_indices:
                        new_normals[l_idx] = fn

            _ensure_single_user_mesh(obj)
            me = obj.data

            for p_idx in target_poly_indices:
                me.polygons[p_idx].use_smooth = True

            me.normals_split_custom_set(new_normals)
            me.update()

            try:
                _save_mesh_normal_snapshot(context, obj, silent=True)
            except Exception:
                pass

            self.report({"INFO"}, f"{_T('已将')} {len(target_poly_indices)} {_T('个多边形法向原地拍平')}")
            return {"FINISHED"}
        finally:
            if prev_mode == "EDIT_MESH":
                context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
            elif prev_mode != "OBJECT" and context.mode != prev_mode:
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass


class M8_OT_AlignNormalsToAxis(bpy.types.Operator):
    bl_idname = "m8.align_normals_to_axis"
    bl_label = _T("法向轴向对齐")
    bl_description = _T("将选中区域的面拐法向绝对强制对齐到指定坐标轴向（如地台+Z、垂直墙面+X/+Y），彻底杜绝建筑与硬表面场景的接缝漏光 (Abnormal & Y.A.V.N.E. 范式)")
    bl_options = {"REGISTER", "UNDO"}

    axis: bpy.props.EnumProperty(
        name=_T("对齐轴向"),
        items=[
            ("POS_Z", "+Z", _T("对齐至向上轴向")),
            ("NEG_Z", "-Z", _T("对齐至向下轴向")),
            ("POS_X", "+X", _T("对齐至正X轴向")),
            ("NEG_X", "-X", _T("对齐至负X轴向")),
            ("POS_Y", "+Y", _T("对齐至正Y轴向")),
            ("NEG_Y", "-Y", _T("对齐至负Y轴向")),
        ],
        default="POS_Z",
    )

    space: bpy.props.EnumProperty(
        name=_T("坐标空间"),
        items=[
            ("WORLD", _T("世界空间"), _T("依据场景世界坐标系的绝对轴向对齐")),
            ("LOCAL", _T("局部空间"), _T("依据物体自身旋转与变换的局部轴向对齐")),
        ],
        default="WORLD",
    )

    selected_only: bpy.props.BoolProperty(
        name=_T("仅限选中区域"),
        description=_T("仅调整当前选中的面或顶点；未勾选则作用于整个模型"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, _T("无效的网格物体"))
            return {"CANCELLED"}

        prev_mode = context.mode
        selected_verts = set()
        selected_faces = set()

        if prev_mode == "EDIT_MESH":
            obj.update_from_editmode()
            bm = bmesh.from_edit_mesh(obj.data)
            selected_verts = {v.index for v in bm.verts if v.select}
            selected_faces = {f.index for f in bm.faces if f.select}
            if not selected_verts and not selected_faces:
                self.selected_only = False
            bpy.ops.object.mode_set(mode="OBJECT")
        elif prev_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        context.view_layer.objects.active = obj
        obj.select_set(True)

        try:
            me = obj.data
            total_corners = len(me.loops)
            if total_corners == 0:
                self.report({"WARNING"}, _T("网格没有面拐数据"))
                return {"CANCELLED"}

            axis_map = {
                "POS_Z": Vector((0.0, 0.0, 1.0)),
                "NEG_Z": Vector((0.0, 0.0, -1.0)),
                "POS_X": Vector((1.0, 0.0, 0.0)),
                "NEG_X": Vector((-1.0, 0.0, 0.0)),
                "POS_Y": Vector((0.0, 1.0, 0.0)),
                "NEG_Y": Vector((0.0, -1.0, 0.0)),
            }
            raw_axis = axis_map.get(self.axis, Vector((0.0, 0.0, 1.0)))

            if self.space == "WORLD":
                mat_world = obj.matrix_world
                try:
                    # 将世界法向变换至局部空间：局部法向 = (M^T @ n_world).normalized()
                    # 渲染器世界法向 = (M^-T @ n_local)，两者矩阵恰好完全互逆，在任意旋转与非均匀缩放下均能 100% 严格对齐世界坐标轴
                    target_dir = (mat_world.to_3x3().transposed() @ raw_axis).normalized()
                except Exception:
                    target_dir = raw_axis
            else:
                target_dir = raw_axis

            target_normal = tuple(target_dir)

            curr_normals = _extract_mesh_corner_normals(me)
            new_normals = list(curr_normals)

            affected_vert_set = set()
            if self.selected_only and (selected_verts or selected_faces):
                affected_vert_set.update(selected_verts)
                for f_idx in selected_faces:
                    affected_vert_set.update(me.polygons[f_idx].vertices)
            else:
                affected_vert_set = set(range(len(me.vertices)))

            for l_idx, loop in enumerate(me.loops):
                if loop.vertex_index in affected_vert_set:
                    new_normals[l_idx] = target_normal

            _ensure_single_user_mesh(obj)
            me = obj.data

            for poly in me.polygons:
                if any(v in affected_vert_set for v in poly.vertices):
                    poly.use_smooth = True

            me.normals_split_custom_set(new_normals)
            me.update()

            try:
                _save_mesh_normal_snapshot(context, obj, silent=True)
            except Exception:
                pass

            self.report({"INFO"}, f"{_T('已将法向对齐至')} {self.axis} ({self.space})")
            return {"FINISHED"}
        finally:
            if prev_mode == "EDIT_MESH":
                context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
            elif prev_mode != "OBJECT" and context.mode != prev_mode:
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass


class M8_OT_AverageNormals(bpy.types.Operator):
    bl_idname = "m8.average_normals"
    bl_label = _T("法向平均化")
    bl_description = _T("将选中顶点相连的所有面拐法向取加权平均并统一赋值，彻底消除拼合接缝、对称缝隙处的高光硬切线 (Abnormal 范式)")
    bl_options = {"REGISTER", "UNDO"}

    selected_only: bpy.props.BoolProperty(
        name=_T("仅限选中区域"),
        description=_T("仅平滑处理当前选中的顶点/面；未勾选则作用于整个模型"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object or context.edit_object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        obj = context.active_object or context.edit_object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, _T("无效的网格物体"))
            return {"CANCELLED"}

        prev_mode = context.mode
        selected_verts = set()
        selected_faces = set()

        if prev_mode == "EDIT_MESH":
            obj.update_from_editmode()
            bm = bmesh.from_edit_mesh(obj.data)
            selected_verts = {v.index for v in bm.verts if v.select}
            selected_faces = {f.index for f in bm.faces if f.select}
            if not selected_verts and not selected_faces:
                self.selected_only = False
            bpy.ops.object.mode_set(mode="OBJECT")
        elif prev_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        context.view_layer.objects.active = obj
        obj.select_set(True)

        try:
            me = obj.data
            total_corners = len(me.loops)
            if total_corners == 0:
                self.report({"WARNING"}, _T("网格没有面拐数据"))
                return {"CANCELLED"}

            curr_normals = _extract_mesh_corner_normals(me)
            new_normals = list(curr_normals)

            affected_vert_set = set()
            if self.selected_only and (selected_verts or selected_faces):
                affected_vert_set.update(selected_verts)
                for f_idx in selected_faces:
                    affected_vert_set.update(me.polygons[f_idx].vertices)
            else:
                affected_vert_set = set(range(len(me.vertices)))

            vert_to_loops = {}
            for l_idx, loop in enumerate(me.loops):
                vid = loop.vertex_index
                if vid in affected_vert_set:
                    if vid not in vert_to_loops:
                        vert_to_loops[vid] = []
                    vert_to_loops[vid].append(l_idx)

            for vid, l_indices in vert_to_loops.items():
                sum_vec = Vector((0.0, 0.0, 0.0))
                for li in l_indices:
                    sum_vec += Vector(curr_normals[li])
                if sum_vec.length_squared > 1e-8:
                    avg_n = tuple(sum_vec.normalized())
                else:
                    avg_n = (0.0, 0.0, 1.0)
                for li in l_indices:
                    new_normals[li] = avg_n

            _ensure_single_user_mesh(obj)
            me = obj.data

            for poly in me.polygons:
                if any(v in affected_vert_set for v in poly.vertices):
                    poly.use_smooth = True

            me.normals_split_custom_set(new_normals)
            me.update()

            try:
                _save_mesh_normal_snapshot(context, obj, silent=True)
            except Exception:
                pass

            self.report({"INFO"}, f"{_T('已完成')} {len(vert_to_loops)} {_T('个顶点的法向平均化平滑')}")
            return {"FINISHED"}
        finally:
            if prev_mode == "EDIT_MESH":
                context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
            elif prev_mode != "OBJECT" and context.mode != prev_mode:
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass






