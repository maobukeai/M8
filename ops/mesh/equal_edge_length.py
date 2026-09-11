import bmesh
import bpy
import mathutils
from bpy.props import EnumProperty, FloatProperty, BoolProperty, IntProperty

from ...utils import get_operator_bl_idname
from ...utils.i18n import _T


def make_edges_equal_length(bm, selected_edges, target_length, iterations=40, keep_endpoints=False):
    """
    调整选中边的长度为 target_length。
    支持独立单边、简单开链折线、闭合环线以及分支拓扑。
    """
    if not selected_edges or target_length <= 1e-6:
        return

    from collections import defaultdict
    vert_to_edges = defaultdict(list)
    for e in selected_edges:
        vert_to_edges[e.verts[0]].append(e)
        vert_to_edges[e.verts[1]].append(e)

    unvisited_edges = set(selected_edges)
    components = []

    while unvisited_edges:
        start_edge = next(iter(unvisited_edges))
        unvisited_edges.remove(start_edge)
        comp = [start_edge]
        queue = [start_edge]
        visited_in_comp = {start_edge}

        while queue:
            curr_e = queue.pop(0)
            for v in curr_e.verts:
                for nxt_e in vert_to_edges[v]:
                    if nxt_e in unvisited_edges and nxt_e not in visited_in_comp:
                        visited_in_comp.add(nxt_e)
                        unvisited_edges.remove(nxt_e)
                        queue.append(nxt_e)
                        comp.append(nxt_e)
        components.append(comp)

    for comp in components:
        # 1. 独立单边 (快速几何缩放，保持中心对称)
        if len(comp) == 1:
            e = comp[0]
            v0, v1 = e.verts[0], e.verts[1]
            diff = v1.co - v0.co
            cur_len = diff.length
            if cur_len > 1e-7:
                mid = (v0.co + v1.co) * 0.5
                norm = diff / cur_len
                v0.co = mid - norm * (target_length * 0.5)
                v1.co = mid + norm * (target_length * 0.5)
            continue

        comp_verts = list(set(v for e in comp for v in e.verts))
        comp_degrees = {v: sum(1 for e in comp if v in e.verts) for v in comp_verts}
        is_open_chain = (
            max(comp_degrees.values()) == 2 and
            sum(1 for d in comp_degrees.values() if d == 1) == 2 and
            len(comp) == len(comp_verts) - 1
        )

        # 2. 简单直线开链 (共线连续段精确解析求解)
        if is_open_chain:
            start_v = next(v for v, d in comp_degrees.items() if d == 1)
            ordered_verts = [start_v]
            curr_v = start_v
            visited_e = set()
            while len(ordered_verts) < len(comp_verts):
                next_e = next(e for e in vert_to_edges[curr_v] if e in comp and e not in visited_e)
                visited_e.add(next_e)
                curr_v = next_e.verts[0] if next_e.verts[1] == curr_v else next_e.verts[1]
                ordered_verts.append(curr_v)

            v_start = ordered_verts[0].co
            v_end = ordered_verts[-1].co
            chain_vec = v_end - v_start
            is_straight = True
            if chain_vec.length > 1e-6:
                for v in ordered_verts[1:-1]:
                    proj, _ = mathutils.geometry.intersect_point_line(v.co, v_start, v_end)
                    if (v.co - proj).length > 1e-4:
                        is_straight = False
                        break
            else:
                is_straight = False

            if is_straight:
                k = len(ordered_verts) - 1
                if keep_endpoints:
                    step = chain_vec / k
                    for i in range(1, k):
                        ordered_verts[i].co = v_start + step * i
                else:
                    mid = (v_start + v_end) * 0.5
                    norm_dir = chain_vec.normalized()
                    total_len = k * target_length
                    new_start = mid - norm_dir * (total_len * 0.5)
                    step = norm_dir * target_length
                    for i in range(k + 1):
                        ordered_verts[i].co = new_start + step * i
                continue

        # 3. 闭合环线、曲线段以及分支网络 (基于位置约束动力学 PBD 松弛算法)
        fixed_verts = set()
        if is_open_chain and keep_endpoints:
            for v, d in comp_degrees.items():
                if d == 1:
                    fixed_verts.add(v)

        for _ in range(iterations):
            deltas = {v: mathutils.Vector((0, 0, 0)) for v in comp_verts}
            counts = {v: 0 for v in comp_verts}
            for e in comp:
                v0, v1 = e.verts[0], e.verts[1]
                diff = v1.co - v0.co
                cur_len = diff.length
                if cur_len > 1e-7:
                    err = cur_len - target_length
                    norm = diff / cur_len
                    if v0 not in fixed_verts and v1 not in fixed_verts:
                        deltas[v0] += norm * (err * 0.5)
                        deltas[v1] -= norm * (err * 0.5)
                        counts[v0] += 1
                        counts[v1] += 1
                    elif v0 not in fixed_verts:
                        deltas[v0] += norm * err
                        counts[v0] += 1
                    elif v1 not in fixed_verts:
                        deltas[v1] -= norm * err
                        counts[v1] += 1

            max_delta = 0.0
            for v in comp_verts:
                if counts[v] > 0:
                    d = (deltas[v] / counts[v]) * 0.9
                    v.co += d
                    max_delta = max(max_delta, d.length)
            if max_delta < 1e-6:
                break


class EqualEdgeLength(bpy.types.Operator):
    bl_idname = get_operator_bl_idname("equal_edge_length")
    bl_label = _T("等长边")
    bl_description = _T("将选中的边调整为相同长度（支持单边、连续边链和闭合环线）")
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(
        name=_T("目标长度"),
        description=_T("计算目标边长的方式"),
        items=[
            ('AVERAGE', _T("平均长度"), _T("使用所有选中边的平均长度作为目标")),
            ('ACTIVE', _T("活动边长"), _T("使用最后选中的活动边长度作为目标")),
            ('MAX', _T("最长边"), _T("使用选中边中最长的边长作为目标")),
            ('MIN', _T("最短边"), _T("使用选中边中最短的边长作为目标")),
            ('CUSTOM', _T("指定长度"), _T("手动指定具体数值长度")),
        ],
        default='AVERAGE',
    )

    target_length: FloatProperty(
        name=_T("长度"),
        description=_T("目标边长度"),
        default=1.0,
        min=0.0001,
        unit='LENGTH',
        precision=4,
    )

    keep_endpoints: BoolProperty(
        name=_T("保持端点固定"),
        description=_T("对于连续边链，保持两端顶点位置不变，仅均匀分布中间顶点"),
        default=False,
    )

    iterations: IntProperty(
        name=_T("平滑迭代"),
        description=_T("闭合环线和分支网络的松弛迭代次数"),
        default=40,
        min=1,
        max=200,
    )

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH":
            return False
        obj = context.object
        if not obj or obj.type != 'MESH':
            return False
        try:
            bm = bmesh.from_edit_mesh(obj.data)
            return any(e.select for e in bm.edges)
        except Exception:
            return False

    def invoke(self, context, event):
        obj = context.object
        if obj and obj.type == 'MESH':
            bm = bmesh.from_edit_mesh(obj.data)
            sel_edges = [e for e in bm.edges if e.select and not e.hide]
            if sel_edges:
                lengths = [e.calc_length() for e in sel_edges]
                self.target_length = sum(lengths) / len(lengths)
        return self.execute(context)

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, _T("当前没有激活的网格对象"))
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        selected_edges = [e for e in bm.edges if e.select and not e.hide]
        if not selected_edges:
            self.report({'WARNING'}, _T("请先选择至少一条边"))
            return {'CANCELLED'}

        lengths = [e.calc_length() for e in selected_edges]
        avg_len = sum(lengths) / len(lengths)
        min_len = min(lengths)
        max_len = max(lengths)

        active_edge = None
        if bm.select_history:
            elem = bm.select_history[-1]
            if isinstance(elem, bmesh.types.BMEdge) and elem.select and not elem.hide:
                active_edge = elem
        active_len = active_edge.calc_length() if active_edge else avg_len

        if self.mode == 'AVERAGE':
            effective_target = avg_len
        elif self.mode == 'ACTIVE':
            effective_target = active_len
        elif self.mode == 'MAX':
            effective_target = max_len
        elif self.mode == 'MIN':
            effective_target = min_len
        elif self.mode == 'CUSTOM':
            effective_target = self.target_length
        else:
            effective_target = avg_len

        make_edges_equal_length(
            bm,
            selected_edges,
            effective_target,
            iterations=self.iterations,
            keep_endpoints=self.keep_endpoints
        )

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"{_T('已等长化')} {len(selected_edges)} {_T('条边 (长度: ')}{effective_target:.4f}m)")
        return {'FINISHED'}
