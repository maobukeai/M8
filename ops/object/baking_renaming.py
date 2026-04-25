import bpy
import math
import mathutils
import difflib
from bpy.props import BoolProperty, FloatProperty, StringProperty, EnumProperty, IntProperty
from bpy.types import Panel, Operator
from ...utils.logger import get_logger

logger = get_logger()

# --- 0. 本地化翻译字典 (Localization) ---

TRANSLATIONS = {
    # --- UI Labels ---
    "panel_title": {"CN": "拓扑智能重命名 Max", "EN": "Bake Smart Renamer Max"},
    "global_settings": {"CN": "全局设置", "EN": "Global Settings"},
    "selection": {"CN": "范围", "EN": "Scope"},
    "tolerance": {"CN": "容差(高级)", "EN": "Tolerance(Adv)"},
    "prefix": {"CN": "前缀", "EN": "Prefix"},
    "start_index": {"CN": "序号", "EN": "Start ID"},
    "auto_collection": {"CN": "自动放入集合", "EN": "Auto Move to Collection"},
    "manual_tools": {"CN": "1. 手动命名工具", "EN": "1. Manual Naming"},
    "smart_tools": {"CN": "2. 智能重构 (多维特征聚类)", "EN": "2. Smart Batch (Multi-modal Cluster)"},
    "smart_desc": {"CN": "体积相交 -> 智能拆分 -> 名称纠错", "EN": "AABB IoU -> Smart Split -> String Match"},
    "classic_tools": {"CN": "3. 传统匹配 (保留基准名)", "EN": "3. Classic Match (Keep Base)"},
    "author": {"CN": "作者: 猫布可爱 | V3.0", "EN": "Author: MaobuKawaii | V3.0"},
    
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
    if not hasattr(context.scene, "m8") or not hasattr(context.scene.m8, "bake_renamer"):
        return TRANSLATIONS.get(key, {}).get("CN", key)
    lang = context.scene.m8.bake_renamer.language
    return TRANSLATIONS.get(key, {}).get(lang, key)

# --- 核心算法工具 (Smart Multi-modal Matching) ---

def get_bbox_center(obj):
    if obj.type != 'MESH': return None
    mw = obj.matrix_world
    corners = [mw @ mathutils.Vector(corner) for corner in obj.bound_box]
    center = sum(corners, mathutils.Vector()) / 8.0
    return center

def get_aabb(obj):
    """获取世界坐标下的轴对齐包围盒 (AABB) 的 Min 和 Max"""
    mw = obj.matrix_world
    corners = [mw @ mathutils.Vector(corner) for corner in obj.bound_box]
    min_vec = mathutils.Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    max_vec = mathutils.Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return min_vec, max_vec

def get_aabb_volume(min_v, max_v):
    dim = max_v - min_v
    return max(1e-8, dim.x * dim.y * dim.z)

def aabb_intersection_volume(min1, max1, min2, max2):
    """计算两个 AABB 的相交体积"""
    min_inter = mathutils.Vector((max(min1.x, min2.x), max(min1.y, min2.y), max(min1.z, min2.z)))
    max_inter = mathutils.Vector((min(max1.x, max2.x), min(max1.y, max2.y), min(max1.z, max2.z)))
    dim = max_inter - min_inter
    if dim.x <= 0 or dim.y <= 0 or dim.z <= 0:
        return 0.0
    return dim.x * dim.y * dim.z

def calculate_iou(min1, max1, min2, max2):
    """计算 Intersection over Union (IoU) 相交比例"""
    v1 = get_aabb_volume(min1, max1)
    v2 = get_aabb_volume(min2, max2)
    inter = aabb_intersection_volume(min1, max1, min2, max2)
    union = v1 + v2 - inter
    return inter / max(1e-8, union)

def get_face_count(obj):
    if not hasattr(obj.data, "polygons"): return 0
    return len(obj.data.polygons)

def get_name_similarity(name1, name2):
    """计算两个名字的文本相似度 (去除后缀后)"""
    clean1 = name1.lower().replace("_low", "").replace("_high", "").replace("_hp", "").replace("_lp", "")
    clean2 = name2.lower().replace("_low", "").replace("_high", "").replace("_hp", "").replace("_lp", "")
    # Remove numbers to match base names like Gun_Barrel_001
    clean1 = ''.join([i for i in clean1 if not i.isdigit()]).strip('_')
    clean2 = ''.join([i for i in clean2 if not i.isdigit()]).strip('_')
    if not clean1 or not clean2:
        return 0.0
    return difflib.SequenceMatcher(None, clean1, clean2).ratio()

def pair_score(low, high):
    """
    融合：距离惩罚 + 尺寸差异惩罚 + 面数惩罚 - 名字相似度奖励 (越小越好)
    """
    obj_size = max(1e-8, low['dims'].length)
    pos_dist = (low['center'] - high['center']).length
    dist_penalty = (pos_dist / obj_size) * 5.0

    size_delta = (low['dims'] - high['dims']).length / obj_size
    
    face_ratio = max(1.0, high['faces'] / max(1, low['faces']))
    face_penalty = abs(math.log(face_ratio)) * 0.1

    name_bonus = get_name_similarity(low['obj'].name, high['obj'].name) * 5.0

    return dist_penalty + (size_delta * 2.0) + face_penalty - name_bonus

def move_to_collection(obj, coll_name):
    if coll_name in bpy.data.collections:
        target_coll = bpy.data.collections[coll_name]
    else:
        target_coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(target_coll)
    
    if obj.name not in target_coll.objects:
        target_coll.objects.link(obj)
    
    for coll in obj.users_collection:
        if coll != target_coll:
            coll.objects.unlink(obj)

# --- 1. 手动命名工具 ---

class BM_OT_SetLow(Operator):
    bl_idname = "bakematcher.set_low"
    bl_label = "Set Low (_low)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = context.selected_objects
        if not objs: return {'FINISHED'}
        
        props = context.scene.m8.bake_renamer
        prefix = props.prefix
        idx = props.start_index
        auto_coll = props.auto_collection
        
        for o in objs:
            o.name = f"{prefix}_{str(idx).zfill(3)}_low"
            if auto_coll:
                move_to_collection(o, f"{prefix}_Low")
            idx += 1
        
        props.start_index = idx
        self.report({"INFO"}, "Set to Low")
        return {'FINISHED'}

class BM_OT_SetHigh(Operator):
    bl_idname = "bakematcher.set_high"
    bl_label = "Set High (_high)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = context.selected_objects
        if not objs: return {'FINISHED'}
        
        props = context.scene.m8.bake_renamer
        prefix = props.prefix
        idx = props.start_index
        auto_coll = props.auto_collection
        
        for o in objs:
            o.name = f"{prefix}_{str(idx).zfill(3)}_high"
            if auto_coll:
                move_to_collection(o, f"{prefix}_High")
            idx += 1
        
        props.start_index = idx
        self.report({"INFO"}, "Set to High")
        return {'FINISHED'}

# --- 2. 智能重构 ---

class BM_OT_BatchRenumber(Operator):
    bl_idname = "bakematcher.batch_renumber"
    bl_label = "Smart Match (AABB & String)"
    bl_description = "AABB Clustering -> Face Ratio & String Match -> Rename"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.m8.bake_renamer
        threshold = props.distance
        prefix = props.prefix
        start_index = props.start_index
        auto_coll = props.auto_collection

        if props.selection_scope == 'VISIBLE':
            objs = [o for o in context.view_layer.objects if o.visible_get() and o.type == 'MESH']
        else:
            objs = [o for o in context.selected_objects if o.type == 'MESH']

        if len(objs) < 2:
            self.report({"ERROR"}, "Too few objects")
            return {'FINISHED'}

        data_pool = []
        for o in objs:
            min_v, max_v = get_aabb(o)
            center = (min_v + max_v) / 2.0
            data_pool.append({
                'obj': o,
                'center': center,
                'min': min_v,
                'max': max_v,
                'dims': o.dimensions.copy(),
                'faces': get_face_count(o),
            })

        # 1. 构建邻接表 (IoU > 0.05 or Distance < threshold)
        n = len(data_pool)
        adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                iou = calculate_iou(data_pool[i]['min'], data_pool[i]['max'], data_pool[j]['min'], data_pool[j]['max'])
                dist = (data_pool[i]['center'] - data_pool[j]['center']).length
                # Highly overlapping or very close
                if iou > 0.05 or dist <= threshold:
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
        
        # 3. 处理每个分组 (K-Means 1D / 断层拆分)
        for group in raw_groups:
            if len(group) < 2:
                groups.append(group)
                continue
                
            group.sort(key=lambda x: x['faces'])
            
            # Find largest gap in faces, biased by string similarity
            max_split_score = -9999
            split_idx = 1
            for k in range(len(group) - 1):
                f1 = max(1, group[k]['faces'])
                f2 = max(1, group[k+1]['faces'])
                ratio = f2 / f1
                
                # Check string similarity between components across the split
                name_sim = get_name_similarity(group[k]['obj'].name, group[k+1]['obj'].name)
                
                # If they share names heavily, they probably ARE a pair, so this split is good
                split_score = ratio + name_sim * 2.0
                if split_score > max_split_score:
                    max_split_score = split_score
                    split_idx = k + 1
            
            # Even a small ratio is acceptable if string similarity is high
            lows = group[:split_idx]
            highs = group[split_idx:]

            candidates = []
            for low in lows:
                for high in highs:
                    score = pair_score(low, high)
                    # Relax strict pairing to allow smart matching to correct BBox shifts
                    if score < 5.0: # Arbitrary high threshold
                        candidates.append((score, low, high))

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

        # Renaming Process
        import time
        timestamp = int(time.time())
        temp_count = 0
        
        for group in groups:
            if len(group) < 2: continue
            for item in group:
                item['obj'].name = f"__M8_TEMP_{timestamp}_{temp_count}__"
                temp_count += 1

        renamed_pairs = 0
        
        for group in groups:
            if len(group) < 2:
                continue

            group.sort(key=lambda x: x['faces'])
            low_data = group[0]
            high_datas = group[1:]

            while True:
                base_name_check = f"{prefix}_{str(start_index).zfill(3)}"
                conflict = False
                if f"{base_name_check}_low" in bpy.data.objects or f"{base_name_check}_high" in bpy.data.objects:
                    conflict = True
                
                if not conflict:
                    break
                start_index += 1

            base_name = f"{prefix}_{str(start_index).zfill(3)}"
            low_data['obj'].name = f"{base_name}_low"
            if auto_coll: move_to_collection(low_data['obj'], f"{prefix}_Low")
            
            for idx, h_data in enumerate(high_datas):
                suffix = "" if idx == 0 else f".{str(idx).zfill(3)}"
                h_data['obj'].name = f"{base_name}_high{suffix}"
                if auto_coll: move_to_collection(h_data['obj'], f"{prefix}_High")
            
            start_index += 1
            renamed_pairs += 1

        props.start_index = start_index
        self.report({"INFO"}, f"Done! Processed {renamed_pairs} pairs.")
        return {'FINISHED'}

# --- 3. 传统匹配 ---

class BM_OT_ClassicMatch(Operator):
    bl_idname = "bakematcher.classic_match"
    bl_label = "Classic Match"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.m8.bake_renamer
        threshold = props.distance
        
        if props.selection_scope == 'VISIBLE':
            all_objs = [o for o in context.view_layer.objects if o.visible_get() and o.type == 'MESH']
        else:
            all_objs = [o for o in context.selected_objects if o.type == 'MESH']

        if props.match_order == 'LOW':
            src_suffix, tgt_suffix = "_low", "_high"
        else:
            src_suffix, tgt_suffix = "_high", "_low"

        sources = [o for o in all_objs if o.name.endswith(src_suffix)]
        targets = [o for o in all_objs if not o.name.endswith(src_suffix)]

        count = 0
        for src in sources:
            src_center = get_bbox_center(src)
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

        self.report({"INFO"}, f"Classic match updated {count} pairs.")
        return {'FINISHED'}

# --- 辅助工具 ---

class BM_OT_DetectConflicts(Operator):
    bl_idname = "bakematcher.detect_conflicts"
    bl_label = "Detect Conflicts"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        threshold = context.scene.m8.bake_renamer.distance
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
            self.report({"WARNING"}, f"Found {len(conflicts)} overlaps")
        else:
            self.report({"INFO"}, "No overlaps found")
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
        props = context.scene.m8.bake_renamer
        prefix = props.prefix
        idx = 1
        for o in context.selected_objects:
            o.name = f"{prefix}_{str(idx).zfill(3)}"
            idx += 1
        return {'FINISHED'}

# --- UI 界面布局 ---

class BAKEMATCHER_PT_Main(Panel):
    bl_idname = "BAKEMATCHER_PT_Main"
    bl_label = "智能烘焙重命名"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "m8"
    bl_order = 20
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        if not hasattr(context.scene, "m8") or not hasattr(context.scene.m8, "bake_renamer"):
            layout.label(text="Loading settings...")
            return
            
        props = context.scene.m8.bake_renamer

        row = layout.row()
        row.prop(props, "language", expand=True)
        layout.separator()

        box = layout.box()
        box.label(text=T(context, "global_settings"), icon="PREFERENCES")
        col = box.column(align=True)
        col.prop(props, 'selection_scope', text=T(context, "selection"))
        
        row = box.row()
        row.prop(props, 'prefix', text=T(context, "prefix"))
        row.prop(props, 'start_index', text=T(context, "start_index"))
        
        row = box.row()
        row.prop(props, 'auto_collection', text=T(context, "auto_collection"))

        box_manual = layout.box()
        box_manual.label(text=T(context, "manual_tools"), icon="BRUSH_DATA")
        row = box_manual.row(align=True)
        row.scale_y = 1.2
        row.operator(BM_OT_SetLow.bl_idname, text=T(context, "btn_set_low"), icon="MESH_CUBE")
        row.operator(BM_OT_SetHigh.bl_idname, text=T(context, "btn_set_high"), icon="META_CUBE")

        box_auto = layout.box()
        col = box_auto.column()
        col.label(text=T(context, "smart_tools"), icon="MODIFIER")
        col.label(text=T(context, "smart_desc"), icon="INFO")
        
        row = col.row()
        row.scale_y = 2.0
        icon_name = "LIGHTPROBE_SPHERE" if hasattr(bpy.types, "LightProbe") else "MESH_ICOSPHERE"
        row.operator(BM_OT_BatchRenumber.bl_idname, text=T(context, "btn_smart_match"), icon=icon_name)

        box_old = layout.box()
        col = box_old.column()
        col.label(text=T(context, "classic_tools"), icon="LINKED")
        row = col.row(align=True)
        row.prop(props, 'match_order', expand=True)
        # Put tolerance in classic match section since it strictly uses distance
        col.prop(props, 'distance', text=T(context, "tolerance"))
        col.operator(BM_OT_ClassicMatch.bl_idname, text=T(context, "btn_classic_match"), icon="LINK_BLEND")
        
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
    # Removed global Scene properties, they are now encapsulated in M8_BakeRenamer_Props 
    # which is registered inside property/state.py
    pass

def unregister():
    pass
