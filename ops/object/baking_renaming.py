import bpy
import math
import mathutils
from bpy.props import BoolProperty, FloatProperty, StringProperty, EnumProperty, IntProperty
from bpy.types import Panel, Operator

# --- 0. 本地化翻译字典 (Localization) ---

TRANSLATIONS = {
    # --- UI Labels ---
    "panel_title": {"CN": "拓扑智能重命名 Max", "EN": "Bake Smart Renamer Max"},
    "global_settings": {"CN": "全局设置", "EN": "Global Settings"},
    "selection": {"CN": "范围", "EN": "Scope"},
    "tolerance": {"CN": "容差", "EN": "Tolerance"},
    "prefix": {"CN": "前缀", "EN": "Prefix"},
    "start_index": {"CN": "序号", "EN": "Start ID"},
    "auto_collection": {"CN": "自动放入集合", "EN": "Auto Move to Collection"},
    "manual_tools": {"CN": "1. 手动命名工具", "EN": "1. Manual Naming"},
    "smart_tools": {"CN": "2. 智能重构 (图论聚类)", "EN": "2. Smart Batch (Graph Cluster)"},
    "smart_desc": {"CN": "位置聚类 -> 面数判定(智能拆分) -> 重命名", "EN": "Graph Cluster -> Face Check(Smart Split) -> Rename"},
    "classic_tools": {"CN": "3. 传统匹配 (保留基准名)", "EN": "3. Classic Match (Keep Base)"},
    "author": {"CN": "作者: 猫布可爱 | V2.2", "EN": "Author: MaobuKawaii | V2.2"},
    
    # --- Buttons ---
    "btn_set_low": {"CN": "设为 Low", "EN": "Set Low"},
    "btn_set_high": {"CN": "设为 High", "EN": "Set High"},
    "btn_smart_match": {"CN": "一键智能配对", "EN": "Auto Smart Match"},
    "btn_classic_match": {"CN": "执行传统匹配", "EN": "Run Classic Match"},
    "btn_conflict": {"CN": "查重叠", "EN": "Check Overlap"},
    "btn_origin": {"CN": "原点居中", "EN": "Center Origin"},
    "btn_reset": {"CN": "重置名", "EN": "Reset Names"},
    
    # --- Selection Options ---
    "sel_selected": {"CN": "仅选中", "EN": "Selected"},
    "sel_visible": {"CN": "所有可见", "EN": "Visible"},
    
    # --- Order Options ---
    "order_low": {"CN": "找Low改High", "EN": "Find Low -> Ren High"},
    "order_high": {"CN": "找High改Low", "EN": "Find High -> Ren Low"},
}

def T(context, key):
    """根据当前场景语言设置返回对应文本"""
    lang = context.scene.Language_BakeMatcher
    return TRANSLATIONS.get(key, {}).get(lang, key)

# --- 核心算法工具 ---

def get_bbox_center(obj):
    """获取物体世界坐标下的边界框几何中心"""
    if obj.type != 'MESH': return None
    mw = obj.matrix_world
    corners = [mw @ mathutils.Vector(corner) for corner in obj.bound_box]
    center = sum(corners, mathutils.Vector()) / 8.0
    return center

def get_face_count(obj):
    """获取面数 (Polygons)，用于精准判断高低模"""
    if not hasattr(obj.data, "polygons"): return 0
    return len(obj.data.polygons)

def _safe_axis_ratio(a, b):
    aa = max(1e-8, float(a))
    bb = max(1e-8, float(b))
    r1 = aa / bb
    r2 = bb / aa
    return max(r1, r2)

def pair_score(low, high, threshold):
    pos_dist = (low['center'] - high['center']).length
    low_diag = max(1e-8, low['dims'].length)
    size_delta = (low['dims'] - high['dims']).length / low_diag
    face_ratio = max(1.0, high['faces'] / max(1, low['faces']))
    return (pos_dist / max(1e-8, threshold)) + size_delta * 2.0 + abs(math.log(face_ratio)) * 0.15

def is_strict_pair(low, high, threshold):
    pos_dist = (low['center'] - high['center']).length
    if pos_dist > threshold * 1.5:
        return False
    x_ratio = _safe_axis_ratio(low['dims'].x, high['dims'].x)
    y_ratio = _safe_axis_ratio(low['dims'].y, high['dims'].y)
    z_ratio = _safe_axis_ratio(low['dims'].z, high['dims'].z)
    if max(x_ratio, y_ratio, z_ratio) > 1.35:
        return False
    low_vol = max(1e-8, low['dims'].x * low['dims'].y * low['dims'].z)
    high_vol = max(1e-8, high['dims'].x * high['dims'].y * high['dims'].z)
    vol_ratio = max(low_vol / high_vol, high_vol / low_vol)
    if vol_ratio > 1.6:
        return False
    if high['faces'] < low['faces']:
        return False
    return True

def move_to_collection(obj, coll_name):
    """将物体移动到指定名称的集合，若不存在则创建"""
    # 获取或创建集合
    if coll_name in bpy.data.collections:
        target_coll = bpy.data.collections[coll_name]
    else:
        target_coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(target_coll)
    
    # 如果已经在目标集合中，不需要再次link，但仍需清理其他集合
    if obj.name not in target_coll.objects:
        target_coll.objects.link(obj)
    
    # 从旧集合移除（只保留在新集合中）
    for coll in obj.users_collection:
        if coll != target_coll:
            coll.objects.unlink(obj)

# --- 1. 手动命名工具 ---

class BM_OT_SetLow(Operator):
    bl_idname = "bakematcher.set_low"
    bl_label = "Set Low (_low)" # 内部名称保持英文通用
    bl_description = "Manually rename selected objects to _low / 手动设为 _low"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = context.selected_objects
        if not objs: return {'FINISHED'}
        
        prefix = context.scene.Name_BakeMatcher
        idx = context.scene.NameStartIndex_BakeMatcher
        auto_coll = context.scene.AutoCollection_BakeMatcher
        
        for o in objs:
            o.name = f"{prefix}_{str(idx).zfill(3)}_low"
            if auto_coll:
                move_to_collection(o, f"{prefix}_Low")
            idx += 1
        
        self.report({"INFO"}, "Set to Low / 已设为 Low")
        return {'FINISHED'}

class BM_OT_SetHigh(Operator):
    bl_idname = "bakematcher.set_high"
    bl_label = "Set High (_high)"
    bl_description = "Manually rename selected objects to _high / 手动设为 _high"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = context.selected_objects
        if not objs: return {'FINISHED'}
        
        prefix = context.scene.Name_BakeMatcher
        idx = context.scene.NameStartIndex_BakeMatcher
        auto_coll = context.scene.AutoCollection_BakeMatcher
        
        for o in objs:
            o.name = f"{prefix}_{str(idx).zfill(3)}_high"
            if auto_coll:
                move_to_collection(o, f"{prefix}_High")
            idx += 1
        
        self.report({"INFO"}, "Set to High / 已设为 High")
        return {'FINISHED'}

# --- 2. 智能重构 ---

class BM_OT_BatchRenumber(Operator):
    bl_idname = "bakematcher.batch_renumber"
    bl_label = "Smart Match (Face Count)"
    bl_description = "Group by location -> Check faces -> Rename / 按位置分组并按面数重命名"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        threshold = scn.Distance_BakeMatcher
        prefix = scn.Name_BakeMatcher
        start_index = scn.NameStartIndex_BakeMatcher
        auto_coll = scn.AutoCollection_BakeMatcher

        if scn.Selection_BakeMatcher == 'VISIBLE':
            objs = [o for o in context.view_layer.objects if o.visible_get() and o.type == 'MESH']
        else:
            objs = [o for o in context.selected_objects if o.type == 'MESH']

        if len(objs) < 2:
            self.report({"ERROR"}, "Too few objects / 物体太少")
            return {'FINISHED'}

        data_pool = []
        for o in objs:
            center = get_bbox_center(o)
            if center:
                data_pool.append({
                    'obj': o,
                    'center': center,
                    'dims': o.dimensions.copy(),
                    'faces': get_face_count(o),
                    'processed': False
                })

        # 1. 构建邻接表 (Adjacency List)
        n = len(data_pool)
        adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dist = (data_pool[i]['center'] - data_pool[j]['center']).length
                if dist <= threshold:
                    adj[i].append(j)
                    adj[j].append(i)
        
        # 2. 寻找连通分量 (Connected Components)
        visited = [False] * n
        raw_groups = []
        for i in range(n):
            if not visited[i]:
                component = []
                stack = [i]
                visited[i] = True
                while stack:
                    curr = stack.pop()
                    component.append(data_pool[curr])
                    for neighbor in adj[curr]:
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            stack.append(neighbor)
                raw_groups.append(component)

        groups = []
        
        # 3. 处理每个分组 (拆分与配对)
        for group in raw_groups:
            if len(group) < 2:
                groups.append(group)
                continue
                
            # 按面数排序
            group.sort(key=lambda x: x['faces'])
            
            # 寻找最大面数断层
            max_ratio = 0
            split_idx = 1
            for k in range(len(group) - 1):
                f1 = max(1, group[k]['faces'])
                f2 = max(1, group[k+1]['faces'])
                ratio = f2 / f1
                if ratio > max_ratio:
                    max_ratio = ratio
                    split_idx = k + 1
            
            if max_ratio > 1.5:
                lows = group[:split_idx]
                highs = group[split_idx:]

                candidates = []
                for low in lows:
                    for high in highs:
                        if is_strict_pair(low, high, threshold):
                            candidates.append((pair_score(low, high, threshold), low, high))

                candidates.sort(key=lambda x: x[0])
                used_lows = set()
                used_highs = set()

                for score, low, high in candidates:
                    low_id = id(low['obj'])
                    high_id = id(high['obj'])
                    if low_id in used_lows or high_id in used_highs:
                        continue
                    used_lows.add(low_id)
                    used_highs.add(high_id)
                    groups.append([low, high])

                for low in lows:
                    if id(low['obj']) not in used_lows:
                        groups.append([low])
                for high in highs:
                    if id(high['obj']) not in used_highs:
                        groups.append([high])
            else:
                groups.append(group)

        strict_groups = []
        for group in groups:
            if len(group) <= 2:
                strict_groups.append(group)
                continue
            group.sort(key=lambda x: x['faces'])
            low = group[0]
            highs = group[1:]
            valid = []
            for h in highs:
                if is_strict_pair(low, h, threshold):
                    valid.append((pair_score(low, h, threshold), h))
                else:
                    strict_groups.append([h])
            if valid:
                valid.sort(key=lambda x: x[0])
                strict_groups.append([low, valid[0][1]])
                for _, h in valid[1:]:
                    strict_groups.append([h])
            else:
                strict_groups.append([low])
                for h in highs:
                    strict_groups.append([h])
        groups = strict_groups

        import time
        timestamp = int(time.time())
        temp_count = 0
        
        for group in groups:
            if len(group) < 2: continue # 跳过无效组
            for item in group:
                item['obj'].name = f"__M8_TEMP_{timestamp}_{temp_count}__"
                temp_count += 1

        renamed_pairs = 0
        
        for group in groups:
            if len(group) < 2:
                print(f"Skipped isolated: {group[0]['obj'].name}")
                continue

            group.sort(key=lambda x: x['faces'])
            low_data = group[0]
            high_datas = group[1:]

            # 3. 寻找可用的 start_index (自动避让场景中已存在的物体)
            while True:
                base_name_check = f"{prefix}_{str(start_index).zfill(3)}"
                low_name_check = f"{base_name_check}_low"
                high_name_check = f"{base_name_check}_high"
                
                # 检查是否冲突 (因为待处理物体都已经改了临时名，所以只要存在就是外人)
                conflict = False
                if low_name_check in bpy.data.objects: conflict = True
                if high_name_check in bpy.data.objects: conflict = True
                
                if not conflict:
                    break
                start_index += 1

            base_name = f"{prefix}_{str(start_index).zfill(3)}"
            low_data['obj'].name = f"{base_name}_low"
            if auto_coll:
                move_to_collection(low_data['obj'], f"{prefix}_Low")
            
            if len(high_datas) == 1:
                high_datas[0]['obj'].name = f"{base_name}_high"
                if auto_coll:
                    move_to_collection(high_datas[0]['obj'], f"{prefix}_High")
            else:
                for idx, h_data in enumerate(high_datas):
                    suffix = "" if idx == 0 else f".{str(idx).zfill(3)}"
                    h_data['obj'].name = f"{base_name}_high{suffix}"
                    if auto_coll:
                        move_to_collection(h_data['obj'], f"{prefix}_High")
            
            start_index += 1
            renamed_pairs += 1

        self.report({"INFO"}, f"Done! Processed {renamed_pairs} pairs. / 完成！处理了 {renamed_pairs} 组")
        return {'FINISHED'}


# --- 3. 传统匹配 ---

class BM_OT_ClassicMatch(Operator):
    bl_idname = "bakematcher.classic_match"
    bl_label = "Classic Match"
    bl_description = "Match nearby objects based on existing names / 根据现有名字匹配附近物体"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        threshold = scn.Distance_BakeMatcher
        
        if scn.Selection_BakeMatcher == 'VISIBLE':
            all_objs = [o for o in context.view_layer.objects if o.visible_get() and o.type == 'MESH']
        else:
            all_objs = [o for o in context.selected_objects if o.type == 'MESH']

        if scn.Order_BakeMatcher == 'LOW':
            src_suffix, tgt_suffix = "_low", "_high"
        else:
            src_suffix, tgt_suffix = "_high", "_low"

        sources = [o for o in all_objs if o.name.endswith(src_suffix)]
        targets = [o for o in all_objs if not o.name.endswith(src_suffix)]

        count = 0
        for src in sources:
            src_center = get_bbox_center(src)
            best_dist = threshold
            candidates = []
            
            for tgt in targets:
                if tgt.parent and "Empty" not in tgt.parent.name: continue
                tgt_center = get_bbox_center(tgt)
                if not tgt_center: continue
                
                dist = (src_center - tgt_center).length
                if dist <= threshold:
                    candidates.append((dist, tgt))
            
            if candidates:
                base_name = src.name.replace(src_suffix, "")
                candidates.sort(key=lambda x: x[0])
                
                for idx, (d, t) in enumerate(candidates):
                    suffix = "" if idx == 0 else f".{str(idx).zfill(3)}"
                    t.name = f"{base_name}{tgt_suffix}{suffix}"
                count += 1

        self.report({"INFO"}, f"Classic match updated {count} pairs. / 传统匹配更新了 {count} 组")
        return {'FINISHED'}

# --- 辅助工具 ---

class BM_OT_DetectConflicts(Operator):
    bl_idname = "bakematcher.detect_conflicts"
    bl_label = "Detect Conflicts"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        threshold = context.scene.Distance_BakeMatcher
        objs = context.selected_objects
        centers = [(o, get_bbox_center(o)) for o in objs if o.type == 'MESH']
        conflicts = set()
        for i in range(len(centers)):
            for j in range(i+1, len(centers)):
                if (centers[i][1] - centers[j][1]).length <= threshold:
                    conflicts.add(centers[i][0])
                    conflicts.add(centers[j][0])
        if conflicts:
            bpy.ops.object.select_all(action='DESELECT')
            for o in conflicts: o.select_set(True)
            self.report({"WARNING"}, f"Found {len(conflicts)} overlaps / 发现 {len(conflicts)} 个重叠")
        else:
            self.report({"INFO"}, "No overlaps found / 无重叠")
        return {'FINISHED'}

class BM_OT_OriginToBounds(Operator):
    bl_idname = "bakematcher.origin_to_bounds"
    bl_label = "Origin to Bounds"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        if context.selected_objects:
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        return {'FINISHED'}

class BM_OT_ResetNames(Operator):
    bl_idname = "bakematcher.reset_names"
    bl_label = "Reset Names"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        prefix = context.scene.Name_BakeMatcher
        idx = 1
        for o in context.selected_objects:
            o.name = f"{prefix}_{str(idx).zfill(3)}"
            idx += 1
        return {'FINISHED'}

# --- UI 界面布局 ---

class BAKEMATCHER_PT_Main(Panel):
    bl_idname = "BAKEMATCHER_PT_Main"
    bl_label = "智能烘焙重命名" # 静态标题，中英双语
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "m8" # 整合到 m8 标签页
    bl_order = 20 # 设置顺序

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        # --- 语言切换 ---
        row = layout.row()
        row.prop(scn, "Language_BakeMatcher", expand=True)
        layout.separator()

        # 全局参数
        box = layout.box()
        box.label(text=T(context, "global_settings"), icon="PREFERENCES")
        col = box.column(align=True)
        col.prop(scn, 'Selection_BakeMatcher', text=T(context, "selection"))
        col.prop(scn, 'Distance_BakeMatcher', text=T(context, "tolerance"))
        
        row = box.row()
        row.prop(scn, 'Name_BakeMatcher', text=T(context, "prefix"))
        row.prop(scn, 'NameStartIndex_BakeMatcher', text=T(context, "start_index"))
        
        row = box.row()
        row.prop(scn, 'AutoCollection_BakeMatcher', text=T(context, "auto_collection"))

        # 区域 1: 手动工具
        box_manual = layout.box()
        box_manual.label(text=T(context, "manual_tools"), icon="BRUSH_DATA")
        row = box_manual.row(align=True)
        row.scale_y = 1.2
        # 注意：这里使用 text=T(...) 来动态覆盖 Operator 的默认 label
        row.operator(BM_OT_SetLow.bl_idname, text=T(context, "btn_set_low"), icon="MESH_CUBE")
        row.operator(BM_OT_SetHigh.bl_idname, text=T(context, "btn_set_high"), icon="META_CUBE")

        # 区域 2: 智能重构
        box_auto = layout.box()
        col = box_auto.column()
        col.label(text=T(context, "smart_tools"), icon="MODIFIER")
        col.label(text=T(context, "smart_desc"), icon="INFO")
        
        # 大按钮
        row = col.row()
        row.scale_y = 2.0
        icon_name = "LIGHTPROBE_SPHERE" if hasattr(bpy.types, "LightProbe") else "MESH_ICOSPHERE"
        row.operator(BM_OT_BatchRenumber.bl_idname, text=T(context, "btn_smart_match"), icon=icon_name)

        # 区域 3: 传统工具
        box_old = layout.box()
        col = box_old.column()
        col.label(text=T(context, "classic_tools"), icon="LINKED")
        row = col.row(align=True)
        row.prop(scn, 'Order_BakeMatcher', expand=True)
        col.operator(BM_OT_ClassicMatch.bl_idname, text=T(context, "btn_classic_match"), icon="LINK_BLEND")
        
        # 辅助
        box_tool = layout.box()
        row = box_tool.row(align=True)
        row.operator(BM_OT_DetectConflicts.bl_idname, text=T(context, "btn_conflict"), icon="ERROR")
        row.operator(BM_OT_OriginToBounds.bl_idname, text=T(context, "btn_origin"), icon="PIVOT_BOUNDBOX")
        row.operator(BM_OT_ResetNames.bl_idname, text=T(context, "btn_reset"), icon="FILE_REFRESH")
        
        layout.label(text=T(context, "author"), icon="USER")

# --- 注册 ---

classes = (
    BM_OT_SetLow,
    BM_OT_SetHigh,
    BM_OT_BatchRenumber,
    BM_OT_ClassicMatch,
    BM_OT_DetectConflicts,
    BM_OT_OriginToBounds,
    BM_OT_ResetNames,
    BAKEMATCHER_PT_Main
)

def register():
    # 语言属性
    bpy.types.Scene.Language_BakeMatcher = EnumProperty(
        items=[('CN', '中文', ''), ('EN', 'English', '')],
        default='CN',
        description="Switch Interface Language"
    )

    # 动态更新 EnumProperty 的 items 实现翻译
    # 这里我们使用一个稍微投机取巧的方法：在 draw 里面动态传参
    # 所以这里的定义保留英文key，UI显示时由 text=T(...) 覆盖，
    # 但 EnumProperty 自身的 items 需要在这里定义
    
    bpy.types.Scene.Selection_BakeMatcher = EnumProperty(
        items=[('SELECTED', 'Selected', ''), ('VISIBLE', 'Visible', '')],
        default='SELECTED',
        # 注意：为了让下拉菜单也能翻译，我们可以在 update 或者 draw 时处理，
        # 但最简单的方法是保持简单的英文或双语，这里我选择简单的英文Key，
        # 实际上 Panel draw 里的 text=T(...) 无法直接覆盖 Prop 的下拉选项。
        # 如果需要下拉菜单也完全汉化，需要定义两个 Enum 或动态回调，比较复杂。
        # 为了代码稳定性，这里保留英文 ID，但 Label 已经在 Panel 里汉化。
        name="Selection Scope"
    )
    
    bpy.types.Scene.Order_BakeMatcher = EnumProperty(
        items=[('LOW', 'Low -> High', ''), ('HIGH', 'High -> Low', '')],
        default='LOW',
        name="Match Order"
    )
    
    bpy.types.Scene.Name_BakeMatcher = StringProperty(default="Bake")
    bpy.types.Scene.NameStartIndex_BakeMatcher = IntProperty(default=1, min=1)
    bpy.types.Scene.AutoCollection_BakeMatcher = BoolProperty(
        default=True,
        name="Auto Move to Collection",
        description="Automatically move objects to _Low/_High collections"
    )
    bpy.types.Scene.Distance_BakeMatcher = FloatProperty(
        default=0.01, min=0.0001, precision=4, description="Tolerance distance")

def unregister():
    del bpy.types.Scene.Language_BakeMatcher
    del bpy.types.Scene.Selection_BakeMatcher
    del bpy.types.Scene.Order_BakeMatcher
    del bpy.types.Scene.Name_BakeMatcher
    del bpy.types.Scene.NameStartIndex_BakeMatcher
    del bpy.types.Scene.AutoCollection_BakeMatcher
    del bpy.types.Scene.Distance_BakeMatcher
