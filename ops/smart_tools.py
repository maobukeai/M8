import bpy
import bmesh
from mathutils import Vector
from ..utils import edit_mesh


def _get_region_rv3d(context):
    return edit_mesh.get_region_rv3d(context)


def _closest_vert_2d(obj, region, rv3d, mouse_xy, verts):
    return edit_mesh.closest_vert_2d(obj, region, rv3d, mouse_xy, verts)


def _weld_to_target(bm, verts, target):
    return edit_mesh.weld_to_target(bm, verts, target)


def _pointmerge_to_co(bm, verts, co):
    return edit_mesh.pointmerge_to_co(bm, verts, co)


def _last_selected_vert(bm, selected_set):
    return edit_mesh.last_selected_vert(bm, selected_set)


def _avg_co(verts):
    return edit_mesh.avg_co(verts)


def _edge_components(edges):
    return edit_mesh.edge_components(edges)


def _face_islands(selected_faces):
    return edit_mesh.face_islands(selected_faces)


def _ordered_path_from_edges(edges):
    return edit_mesh.ordered_path_from_edges(edges)


def _selected_edges_from_vertex_selection(bm):
    return edit_mesh.selected_edges_from_vertex_selection(bm)


def _selected_edges_any(bm):
    return edit_mesh.selected_edges_any(bm)


def _get_addon_prefs():
    return edit_mesh.get_addon_prefs(__package__)


def _ensure_bevel_modifier(obj, name):
    return edit_mesh.ensure_bevel_modifier(obj, name)


def _set_edge_bevel_weight(bm, edges, weight):
    return edit_mesh.set_edge_bevel_weight(bm, edges, weight)


class M8_OT_SmartVert(bpy.types.Operator):
    bl_idname = "m8.smart_vert"
    bl_label = "M8 智能顶点"
    bl_options = {"REGISTER", "UNDO"}

    merge_mode: bpy.props.EnumProperty(
        name="合并模式",
        items=[
            ("AUTO", "自动", ""),
            ("ACTIVE", "活动点", ""),
            ("LAST", "最后选中", ""),
            ("MOUSE", "鼠标最近", ""),
            ("CENTER", "中心点", ""),
            ("PROJECT", "投影合并", ""),
        ],
        default="AUTO",
    )
    
    project_axis: bpy.props.EnumProperty(
        name="投影轴",
        items=[
            ("X", "X 轴", ""),
            ("Y", "Y 轴", ""),
            ("Z", "Z 轴", ""),
            ("VIEW", "视图", ""),
        ],
        default="Z",
    )
    
    project_target: bpy.props.EnumProperty(
        name="对齐目标",
        items=[
            ("ACTIVE", "活动点", ""),
            ("CENTER", "中心点", ""),
            ("CURSOR", "游标", ""),
        ],
        default="ACTIVE",
    )

    _mouse_xy = None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        # 使用 column_flow 让选项自动排布，避免下拉
        col = layout.column()
        col.prop(self, "merge_mode", expand=True)
        
        if self.merge_mode == "PROJECT":
            box = layout.box()
            row = box.row()
            row.prop(self, "project_axis", expand=True)
            row = box.row()
            row.prop(self, "project_target", expand=True)

    def invoke(self, context, event):
        self._mouse_xy = (event.mouse_region_x, event.mouse_region_y)
        return self.execute(context)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        obj = context.edit_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        bm.select_flush(False)

        region, rv3d = _get_region_rv3d(context)
        select_mode = context.tool_settings.mesh_select_mode
        
        # 投影合并逻辑
        if self.merge_mode == "PROJECT":
            verts = [v for v in bm.verts if v.select]
            if not verts:
                return {"CANCELLED"}
                
            active = bm.select_history.active
            target_v = None
            if isinstance(active, bmesh.types.BMVert) and active.select:
                target_v = active
            else:
                # 如果没有活动点，尝试找最后选中的点
                target_v = _last_selected_vert(bm, set(verts))
                
            if not target_v:
                # 依然没有，使用鼠标最近点
                target_v = _closest_vert_2d(obj, region, rv3d, self._mouse_xy, verts)
            
            if not target_v:
                return {"CANCELLED"}
                
            # 执行投影
            target_co = None
            if self.project_target == "ACTIVE":
                target_co = target_v.co.copy()
            elif self.project_target == "CENTER":
                target_co = _avg_co(verts)
            elif self.project_target == "CURSOR":
                target_co = obj.matrix_world.inverted() @ context.scene.cursor.location
            
            if target_co is None:
                return {"CANCELLED"}
            
            # 使用列表以便在循环中修改
            verts_to_project = [v for v in verts if v != target_v or self.project_target != "ACTIVE"]
            
            if self.project_axis == "VIEW" and region and rv3d:
                # 视图投影：将点移动到 target 在视图平面的投影线上
                view_mat = rv3d.view_matrix
                view_inv = view_mat.inverted()
                
                # target 在视图空间的位置
                target_view = view_mat @ (obj.matrix_world @ target_co)
                
                for v in verts_to_project:
                    # v 在视图空间的位置
                    v_view = view_mat @ (obj.matrix_world @ v.co)
                    # 保持 v 的深度 (Z)，但 X, Y 与 target 相同
                    v_view.x = target_view.x
                    v_view.y = target_view.y
                    
                    # 转换回局部空间
                    v.co = obj.matrix_world.inverted() @ (view_inv @ v_view)
            else:
                for v in verts_to_project:
                    if self.project_axis == "X":
                        v.co.x = target_co.x
                    elif self.project_axis == "Y":
                        v.co.y = target_co.y
                    elif self.project_axis == "Z":
                        v.co.z = target_co.z
                        
            # 投影后执行焊接 (Merge)
            bmesh.ops.remove_doubles(bm, verts=verts, dist=0.0001)
            bmesh.update_edit_mesh(me, destructive=True)
            return {"FINISHED"}

        if select_mode[0]:
            selected_verts = [v for v in bm.verts if v.select]
            if not selected_verts:
                return {"CANCELLED"}
            if len(selected_verts) == 1:
                bpy.ops.mesh.bevel("INVOKE_DEFAULT", affect='VERTICES')
                return {"FINISHED"}

            target = None
            active = bm.select_history.active
            selected_set = set(selected_verts)

            if self.merge_mode == "CENTER":
                co = _avg_co(selected_verts)
                if co is None:
                    return {"CANCELLED"}
                _pointmerge_to_co(bm, selected_verts, co)
                bmesh.update_edit_mesh(me, destructive=True)
                return {"FINISHED"}

            if self.merge_mode in {"ACTIVE", "AUTO"} and isinstance(active, bmesh.types.BMVert) and active.select:
                target = active
            if self.merge_mode == "LAST":
                target = _last_selected_vert(bm, selected_set) or target
            if self.merge_mode in {"MOUSE", "AUTO"} and target is None:
                target = _closest_vert_2d(obj, region, rv3d, self._mouse_xy, selected_verts) or selected_verts[-1]
            if self.merge_mode == "ACTIVE" and target is None:
                target = active if isinstance(active, bmesh.types.BMVert) else None
            if target is None:
                target = selected_verts[-1]

            _weld_to_target(bm, selected_verts, target)
            bmesh.update_edit_mesh(me, destructive=True)
            return {"FINISHED"}

        if select_mode[1]:
            selected_edges = [e for e in bm.edges if e.select]
            if not selected_edges:
                return {"CANCELLED"}
            for _, comp_verts in _edge_components(selected_edges):
                if self.merge_mode == "CENTER":
                    co = _avg_co(comp_verts)
                    if co is None:
                        continue
                    _pointmerge_to_co(bm, comp_verts, co)
                else:
                    target = None
                    active = bm.select_history.active
                    selected_set = set(comp_verts)
                    if self.merge_mode in {"ACTIVE", "AUTO"} and isinstance(active, bmesh.types.BMVert) and active.select and active in selected_set:
                        target = active
                    if self.merge_mode == "LAST":
                        target = _last_selected_vert(bm, selected_set) or target
                    if self.merge_mode in {"MOUSE", "AUTO"} and target is None:
                        target = _closest_vert_2d(obj, region, rv3d, self._mouse_xy, comp_verts) or (comp_verts[-1] if comp_verts else None)
                    if target is None and comp_verts:
                        target = comp_verts[-1]
                    _weld_to_target(bm, comp_verts, target)
            bmesh.update_edit_mesh(me, destructive=True)
            return {"FINISHED"}

        if select_mode[2]:
            selected_faces = [f for f in bm.faces if f.select]
            if not selected_faces:
                return {"CANCELLED"}
            for _, comp_verts in _face_islands(selected_faces):
                if self.merge_mode == "CENTER":
                    co = _avg_co(comp_verts)
                    if co is None:
                        continue
                    _pointmerge_to_co(bm, comp_verts, co)
                else:
                    target = None
                    active = bm.select_history.active
                    selected_set = set(comp_verts)
                    if self.merge_mode in {"ACTIVE", "AUTO"} and isinstance(active, bmesh.types.BMVert) and active.select and active in selected_set:
                        target = active
                    if self.merge_mode == "LAST":
                        target = _last_selected_vert(bm, selected_set) or target
                    if self.merge_mode in {"MOUSE", "AUTO"} and target is None:
                        target = _closest_vert_2d(obj, region, rv3d, self._mouse_xy, comp_verts) or (comp_verts[-1] if comp_verts else None)
                    if target is None and comp_verts:
                        target = comp_verts[-1]
                    _weld_to_target(bm, comp_verts, target)
            bmesh.update_edit_mesh(me, destructive=True)
            return {"FINISHED"}

        return {"CANCELLED"}


class M8_OT_SmartEdge(bpy.types.Operator):
    bl_idname = "m8.smart_edge"
    bl_label = "M8 智能边"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name="模式",
        items=[
            ("SELECT", "选择区域 (Edge to Face)", "将闭合边环转换为面选择"),
            ("SHARPS", "锐边 (Sharps)", "标记或清除锐边"),
            ("BRIDGE", "桥接 (Bridge)", "桥接两个边环"),
            ("FILL", "填充 (Fill)", "填充闭合区域 (Grid Fill / F)"),
        ],
        default="SELECT",
    )

    # Select Mode Options
    select_bigger: bpy.props.BoolProperty(name="反转选择 (Select Bigger)", default=False)
    
    # Sharps Options
    sharps_action: bpy.props.EnumProperty(
        name="锐边操作",
        items=[
            ("TOGGLE", "切换 (Toggle)", ""),
            ("MARK", "标记 (Mark)", ""),
            ("CLEAR", "清除 (Clear)", ""),
        ],
        default="TOGGLE",
    )
    
    # Modifier/Bevel Options (Simplified)
    use_chamfer: bpy.props.BoolProperty(name="使用倒角修改器", default=False)
    width: bpy.props.FloatProperty(name="宽度", default=0.01, min=0.0)
    segments: bpy.props.IntProperty(name="段数", default=3, min=1)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        layout.prop(self, "mode", expand=True)
        
        if self.mode == "SELECT":
            layout.prop(self, "select_bigger")
            layout.label(text="选择闭合边环以转换为面", icon="INFO")
            
        elif self.mode == "SHARPS":
            layout.prop(self, "sharps_action", expand=True)
            
        elif self.mode == "BRIDGE":
            layout.label(text="选择两个边环进行桥接", icon="INFO")
            
        elif self.mode == "FILL":
            layout.label(text="选择闭合边进行填充", icon="INFO")

    def invoke(self, context, event):
        # 尝试从偏好设置读取默认模式
        prefs = _get_addon_prefs()
        if prefs and hasattr(prefs, "smart_edge_mode"):
            # 简单的映射，如果之前保存了偏好
            pass
            
        if context.mode == "EDIT_MESH":
            return self.execute(context)
        return {"CANCELLED"}

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        
        obj = context.edit_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        select_mode = context.tool_settings.mesh_select_mode

        # --- 顶点模式 (保留基础功能) ---
        if select_mode[0]:
            verts = [v for v in bm.verts if v.select]
            if len(verts) <= 1:
                bpy.ops.mesh.knife_tool("INVOKE_DEFAULT")
            else:
                try:
                    bpy.ops.mesh.vert_connect_path()
                except RuntimeError:
                    bpy.ops.mesh.edge_face_add()
            return {"FINISHED"}

        # --- 面模式 (保留基础功能) ---
        if select_mode[2]:
            faces = [f for f in bm.faces if f.select]
            if not faces:
                bpy.ops.mesh.loopcut_slide("INVOKE_DEFAULT")
            else:
                bpy.ops.mesh.region_to_loop()
            return {"FINISHED"}

        # --- 边模式 (核心重构) ---
        if select_mode[1]:
            edges = [e for e in bm.edges if e.select]
            
            # 1. 无选择 -> 环切
            if not edges:
                bpy.ops.mesh.loopcut_slide("INVOKE_DEFAULT")
                return {"FINISHED"}

            # 2. 根据模式执行
            if self.mode == "SELECT":
                # 核心需求：Edge to Face (Loop to Region)
                try:
                    bpy.ops.mesh.loop_to_region(select_bigger=self.select_bigger)
                    # 检查是否成功切换到了面模式并选择了面
                    if context.tool_settings.mesh_select_mode[2]:
                        return {"FINISHED"}
                except Exception as e:
                    self.report({'WARNING'}, f"无法转换为面选择: {e}")
                    return {"CANCELLED"}
            
            elif self.mode == "SHARPS":
                if self.sharps_action == "MARK":
                    bpy.ops.mesh.mark_sharp(clear=False)
                elif self.sharps_action == "CLEAR":
                    bpy.ops.mesh.mark_sharp(clear=True)
                else:
                    # Toggle
                    has_smooth = any(not e.smooth for e in edges) # sharp edges are !smooth? No, sharp is a flag.
                    # Blender API: mark_sharp(clear=True/False)
                    # Use standard toggle logic
                    bpy.ops.mesh.mark_sharp(clear=False) # 先简单处理，或者检查现有状态
                return {"FINISHED"}

            elif self.mode == "BRIDGE":
                try:
                    bpy.ops.mesh.bridge_edge_loops()
                except Exception as e:
                    self.report({'WARNING'}, "桥接失败")
                return {"FINISHED"}

            elif self.mode == "FILL":
                try:
                    bpy.ops.mesh.fill_grid()
                except Exception:
                    try:
                        bpy.ops.mesh.edge_face_add()
                    except Exception:
                        self.report({'WARNING'}, "填充失败")
                return {"FINISHED"}
            
            # 默认回退：如果是 SELECT 模式但失败了，可能是因为没闭合，
            # 用户可能想要智能判断，但用户明确要求 "默认应该选择边范围"
            # 所以这里不再做过多的自动回退，以免产生 "删除另一半" (Knife Project) 的误解。
            
        return {"FINISHED"}


class M8_OT_SmartFace(bpy.types.Operator):
    bl_idname = "m8.smart_face"
    bl_label = "M8 智能面"
    bl_options = {"REGISTER", "UNDO"}

    face_action: bpy.props.EnumProperty(
        name="操作",
        items=[
            ("SEPARATE", "分离", ""),
            ("DUPLICATE", "复制", ""),
            ("DISSOLVE", "溶解", ""),
            ("EXTRACT", "提取", ""),
        ],
        default="SEPARATE",
    )
    focus_mode: bpy.props.BoolProperty(name="聚焦模式", default=False)
    stay_on_original: bpy.props.BoolProperty(name="停留在原始对象", default=False)
    dissolve_use_verts: bpy.props.BoolProperty(name="溶解顶点", default=True)
    extract_offset: bpy.props.FloatProperty(name="提取距离", default=0.01)
    keep_original: bpy.props.BoolProperty(name="保留原始面", default=True)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        layout.prop(self, "face_action", expand=True)
        
        if self.face_action == "EXTRACT":
            layout.prop(self, "extract_offset")
            layout.prop(self, "keep_original")
        elif self.face_action == "DISSOLVE":
            layout.prop(self, "dissolve_use_verts")
        
        box = layout.box()
        box.prop(self, "focus_mode")
        box.prop(self, "stay_on_original")

    def invoke(self, context, event):
        prefs = _get_addon_prefs()
        if prefs:
            try:
                self.focus_mode = bool(getattr(prefs, "smart_face_focus_mode", self.focus_mode))
                self.stay_on_original = bool(getattr(prefs, "smart_face_stay_on_original", self.stay_on_original))
                if not self.is_property_set("face_action"):
                    self.face_action = str(getattr(prefs, "smart_face_action", self.face_action))
            except Exception:
                pass
        return self.execute(context)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        obj = context.edit_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        select_mode = context.tool_settings.mesh_select_mode

        if select_mode[0]:
            verts = [v for v in bm.verts if v.select]
            if 1 <= len(verts) <= 2:
                bpy.ops.mesh.edge_face_add()
                return {"FINISHED"}
            if len(verts) >= 3:
                bpy.ops.mesh.fill()
                return {"FINISHED"}
            return {"CANCELLED"}

        if select_mode[2]:
            faces = [f for f in bm.faces if f.select]
            if not faces:
                return {"CANCELLED"}

            prefs = _get_addon_prefs()
            focus_mode = bool(self.focus_mode)
            stay_on_original = bool(self.stay_on_original)
            if prefs:
                try:
                    prefs.smart_face_focus_mode = focus_mode
                    prefs.smart_face_stay_on_original = stay_on_original
                    prefs.smart_face_action = str(self.face_action)
                except Exception:
                    pass

            original_obj = context.active_object
            if self.face_action == "DISSOLVE":
                bmesh.ops.dissolve_faces(bm, faces=faces, use_verts=bool(self.dissolve_use_verts))
                bmesh.update_edit_mesh(me, destructive=True)
                return {"FINISHED"}

            if self.face_action == "DUPLICATE":
                res = bmesh.ops.duplicate(bm, geom=faces)
                dup_faces = [g for g in res.get("geom", []) if isinstance(g, bmesh.types.BMFace)]
                for f in faces:
                    f.select = False
                for f in dup_faces:
                    f.select = True
                bmesh.update_edit_mesh(me, destructive=True)
                bpy.ops.mesh.separate(type="SELECTED")
            elif self.face_action == "EXTRACT":
                # 1. Duplicate faces
                res_dup = bmesh.ops.duplicate(bm, geom=faces)
                dup_faces = [g for g in res_dup["geom"] if isinstance(g, bmesh.types.BMFace)]
                
                # 2. Extrude the duplicated faces
                # bmesh.ops.extrude_face_region returns the new geometry (sides, new faces, etc.)
                # If we extrude, we get a solid block.
                res_ext = bmesh.ops.extrude_face_region(bm, geom=dup_faces)
                
                # Gather new geometry from extrusion
                verts_ext = [g for g in res_ext["geom"] if isinstance(g, bmesh.types.BMVert)]
                faces_ext = [g for g in res_ext["geom"] if isinstance(g, bmesh.types.BMFace)]
                
                # The extrusion result contains the "side" faces and the "top" faces (which are the original dup_faces transformed?)
                # Actually, extrude_face_region keeps the original faces as the "base" and creates new "top" faces?
                # No, typically it extrudes the selection.
                
                # To ensure good normal calculation for Shrink/Fatten (Alt+S), we should select ALL the new geometry
                # (top, bottom, sides) and let Blender calculate the vertex normals.
                # However, usually we only want to move the "top" faces to create thickness,
                # or use Solidify logic which moves vertices along vertex normals.
                
                # Let's try to select everything we created (duplicate + extrude)
                all_new_geom = set(dup_faces) | set(faces_ext)
                all_new_verts = set()
                for f in all_new_geom:
                    all_new_verts.update(f.verts)
                    
                # Deselect everything first
                for v in bm.verts: v.select = False
                for e in bm.edges: e.select = False
                for f in bm.faces: f.select = False
                
                # Select the new shell
                for f in all_new_geom:
                    f.select = True
                    
                # Recalculate normals to be sure
                bmesh.ops.recalc_face_normals(bm, faces=list(all_new_geom))
                
                bmesh.update_edit_mesh(me, destructive=True)
                
                # 4. Use Shrink/Fatten (Alt+S)
                # Shrink/Fatten works by moving vertices along their averaged normal.
                # Since we have a closed volume (or at least a shell), this should give thickness.
                try:
                    bpy.ops.transform.shrink_fatten(value=self.extract_offset)
                except Exception:
                    pass
                
                # 删除原始面（如果未勾选保留）
                if not self.keep_original:
                    bmesh.ops.delete(bm, geom=faces, context="FACES")
                    bmesh.update_edit_mesh(me, destructive=True)
                
                # 5. Separate
                bpy.ops.mesh.separate(type="SELECTED")
            else:
                bpy.ops.mesh.separate(type="SELECTED")

            if stay_on_original and original_obj and original_obj.name in context.view_layer.objects:
                try:
                    context.view_layer.objects.active = original_obj
                except Exception:
                    pass

            if focus_mode:
                try:
                    bpy.ops.view3d.localview("INVOKE_DEFAULT")
                except Exception:
                    pass

            return {"FINISHED"}

        return {"CANCELLED"}


class M8_OT_CleanUp(bpy.types.Operator):
    bl_idname = "m8.clean_up"
    bl_label = "M8 清理 (Clean Up)"
    bl_options = {"REGISTER", "UNDO"}

    merge_distance: bpy.props.FloatProperty(name="合并距离", default=0.0001, min=0.0)
    affect: bpy.props.EnumProperty(
        name="影响范围",
        items=[
            ("ALL", "全部", ""),
            ("SELECTED", "仅选中", ""),
        ],
        default="ALL",
    )
    do_merge_by_distance: bpy.props.BoolProperty(name="合并重复点", default=True)
    do_dissolve_degenerate: bpy.props.BoolProperty(name="溶解退化几何", default=True)
    degenerate_dist: bpy.props.FloatProperty(name="退化阈值", default=0.00001, min=0.0)
    do_delete_loose_edges: bpy.props.BoolProperty(name="删除孤立边", default=True)
    do_delete_loose_verts: bpy.props.BoolProperty(name="删除孤立点", default=True)
    do_recalc_normals: bpy.props.BoolProperty(name="重算法线", default=False)
    
    do_limited_dissolve: bpy.props.BoolProperty(name="有限溶解", default=False)
    limited_dissolve_angle: bpy.props.FloatProperty(name="角度", default=0.0872665, min=0.0, max=3.14159, subtype="ANGLE")
    
    do_make_planar: bpy.props.BoolProperty(name="平坦化面", default=False)
    planar_iterations: bpy.props.IntProperty(name="迭代", default=1, min=1, max=10)
    
    do_delete_interior_faces: bpy.props.BoolProperty(name="删除内部面 (非流形)", default=False)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        layout.prop(self, "affect", expand=True)
        layout.prop(self, "merge_distance")
        
        box = layout.box()
        box.label(text="Clean Options", icon="BRUSH_DATA")
        
        col = box.column(align=True)
        col.prop(self, "do_merge_by_distance")
        
        row = col.row()
        row.prop(self, "do_dissolve_degenerate")
        if self.do_dissolve_degenerate:
            row.prop(self, "degenerate_dist", text="")
            
        row = col.row()
        row.prop(self, "do_limited_dissolve")
        if self.do_limited_dissolve:
            row.prop(self, "limited_dissolve_angle", text="")
            
        row = col.row()
        row.prop(self, "do_make_planar")
        if self.do_make_planar:
            row.prop(self, "planar_iterations", text="")
            
        col.prop(self, "do_delete_interior_faces")
        col.prop(self, "do_delete_loose_edges")
        col.prop(self, "do_delete_loose_verts")
        col.prop(self, "do_recalc_normals")

    def invoke(self, context, event):
        prefs = _get_addon_prefs()
        if prefs:
            try:
                if hasattr(prefs, "clean_up_merge_distance") and not self.is_property_set("merge_distance"):
                    self.merge_distance = float(getattr(prefs, "clean_up_merge_distance", self.merge_distance))
                if hasattr(prefs, "clean_up_affect") and not self.is_property_set("affect"):
                    self.affect = str(getattr(prefs, "clean_up_affect", self.affect))
                if hasattr(prefs, "clean_up_degenerate_dist") and not self.is_property_set("degenerate_dist"):
                    self.degenerate_dist = float(getattr(prefs, "clean_up_degenerate_dist", self.degenerate_dist))
                if hasattr(prefs, "clean_up_recalc_normals") and not self.is_property_set("do_recalc_normals"):
                    self.do_recalc_normals = bool(getattr(prefs, "clean_up_recalc_normals", self.do_recalc_normals))
                if hasattr(prefs, "clean_up_limited_dissolve") and not self.is_property_set("do_limited_dissolve"):
                    self.do_limited_dissolve = bool(getattr(prefs, "clean_up_limited_dissolve", self.do_limited_dissolve))
                if hasattr(prefs, "clean_up_limited_dissolve_angle") and not self.is_property_set("limited_dissolve_angle"):
                    self.limited_dissolve_angle = float(getattr(prefs, "clean_up_limited_dissolve_angle", self.limited_dissolve_angle))
                if hasattr(prefs, "clean_up_make_planar") and not self.is_property_set("do_make_planar"):
                    self.do_make_planar = bool(getattr(prefs, "clean_up_make_planar", self.do_make_planar))
                if hasattr(prefs, "clean_up_delete_interior_faces") and not self.is_property_set("do_delete_interior_faces"):
                    self.do_delete_interior_faces = bool(getattr(prefs, "clean_up_delete_interior_faces", self.do_delete_interior_faces))
            except Exception:
                pass
        return self.execute(context)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}

        prefs = _get_addon_prefs()
        merge_distance = float(self.merge_distance)
        if prefs:
            try:
                if hasattr(prefs, "clean_up_merge_distance"):
                    prefs.clean_up_merge_distance = merge_distance
                if hasattr(prefs, "clean_up_affect"):
                    prefs.clean_up_affect = str(self.affect)
                if hasattr(prefs, "clean_up_degenerate_dist"):
                    prefs.clean_up_degenerate_dist = float(self.degenerate_dist)
                if hasattr(prefs, "clean_up_recalc_normals"):
                    prefs.clean_up_recalc_normals = bool(self.do_recalc_normals)
                if hasattr(prefs, "clean_up_limited_dissolve"):
                    prefs.clean_up_limited_dissolve = bool(self.do_limited_dissolve)
                if hasattr(prefs, "clean_up_limited_dissolve_angle"):
                    prefs.clean_up_limited_dissolve_angle = float(self.limited_dissolve_angle)
                if hasattr(prefs, "clean_up_make_planar"):
                    prefs.clean_up_make_planar = bool(self.do_make_planar)
                if hasattr(prefs, "clean_up_delete_interior_faces"):
                    prefs.clean_up_delete_interior_faces = bool(self.do_delete_interior_faces)
            except Exception:
                pass

        objs = []
        for o in getattr(context, "objects_in_mode_unique_data", []) or []:
            if getattr(o, "type", "") == "MESH":
                objs.append(o)
        if not objs:
            obj = context.edit_object
            if obj and obj.type == "MESH":
                objs = [obj]

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            
            # Record initial counts for report
            init_v_count = len(bm.verts)
            
            # Helper to get target geometry dynamically
            def get_target(what):
                if self.affect == 'SELECTED':
                    if what == 'VERTS':
                        return [v for v in bm.verts if v.select]
                    elif what == 'EDGES':
                        return [e for e in bm.edges if e.select]
                    elif what == 'FACES':
                        return [f for f in bm.faces if f.select]
                else:
                    if what == 'VERTS':
                        return list(bm.verts)
                    elif what == 'EDGES':
                        return list(bm.edges)
                    elif what == 'FACES':
                        return list(bm.faces)
                return []

            if self.do_merge_by_distance:
                verts = get_target('VERTS')
                if verts:
                    bmesh.ops.remove_doubles(bm, verts=verts, dist=merge_distance)
                    bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()

            if self.do_dissolve_degenerate:
                try:
                    edges = get_target('EDGES')
                    bmesh.ops.dissolve_degenerate(bm, dist=float(self.degenerate_dist), edges=edges)
                    bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()
                except Exception:
                    pass
            
            if self.do_limited_dissolve:
                try:
                    target_edges = get_target('EDGES')
                    target_verts = get_target('VERTS')
                    bmesh.ops.dissolve_limit(bm, angle_limit=float(self.limited_dissolve_angle), use_dissolve_boundaries=True, edges=target_edges, verts=target_verts)
                    bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()
                except Exception:
                    pass
            
            if self.do_make_planar:
                try:
                    target_faces = get_target('FACES')
                    bmesh.ops.planar_faces(bm, faces=target_faces, iterations=int(self.planar_iterations), factor=1.0)
                    bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()
                except Exception:
                    pass
            
            if self.do_delete_interior_faces:
                try:
                    # Simple heuristic: edges with > 2 faces
                    target_edges = get_target('EDGES')
                    interior_edges = [e for e in target_edges if len(e.link_faces) > 2]
                    if interior_edges:
                        bmesh.ops.delete(bm, geom=interior_edges, context="EDGES")
                        bm.verts.ensure_lookup_table()
                        bm.edges.ensure_lookup_table()
                        bm.faces.ensure_lookup_table()
                except Exception:
                    pass

            if self.do_delete_loose_edges:
                edges = get_target('EDGES')
                loose_edges = [e for e in edges if len(e.link_faces) == 0]
                if loose_edges:
                    bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
                    bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()

            if self.do_delete_loose_verts:
                verts = get_target('VERTS')
                loose_verts = [v for v in verts if len(v.link_edges) == 0]
                if loose_verts:
                    bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
                    bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()

            if self.do_recalc_normals:
                faces = get_target('FACES')
                if faces:
                    try:
                        bmesh.ops.recalc_face_normals(bm, faces=faces)
                    except Exception:
                        pass

            bmesh.update_edit_mesh(obj.data, destructive=True)
            
            # Report
            count_v = init_v_count - len(bm.verts)
            if count_v > 0:
                self.report({'INFO'}, f"Cleaned up {count_v} vertices")

        return {"FINISHED"}


class M8_OT_SmartMergeCenter(bpy.types.Operator):
    bl_idname = "m8.smart_merge_center"
    bl_label = "M8 中心合并"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.EnumProperty(
        name="目标",
        items=[
            ("CENTER", "中心点", ""),
            ("CURSOR", "游标", ""),
        ],
        default="CENTER",
    )

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        obj = context.edit_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}
        bm = bmesh.from_edit_mesh(obj.data)
        select_mode = context.tool_settings.mesh_select_mode
        verts = []
        if select_mode[0]:
            verts = [v for v in bm.verts if v.select]
        elif select_mode[1]:
            edges = [e for e in bm.edges if e.select]
            for e in edges:
                verts.extend(e.verts)
            verts = list({v for v in verts})
        elif select_mode[2]:
            faces = [f for f in bm.faces if f.select]
            for f in faces:
                verts.extend(f.verts)
            verts = list({v for v in verts})
        if not verts:
            return {"CANCELLED"}
        if self.target == "CURSOR":
            co = obj.matrix_world.inverted() @ context.scene.cursor.location
        else:
            co = _avg_co(verts)
            if co is None:
                return {"CANCELLED"}
        _pointmerge_to_co(bm, verts, co)
        bmesh.update_edit_mesh(obj.data, destructive=True)
        return {"FINISHED"}


class M8_OT_SmartPathsMerge(bpy.types.Operator):
    bl_idname = "m8.smart_paths_merge"
    bl_label = "M8 合并路径 (Merge Paths)"
    bl_options = {"REGISTER", "UNDO"}

    pairing: bpy.props.EnumProperty(
        name="配对",
        items=[
            ("AUTO", "自动", ""),
            ("INDEX", "顺序", ""),
            ("REVERSE", "反向", ""),
        ],
        default="AUTO",
    )

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.prop(self, "pairing", expand=True)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        obj = context.edit_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        edges = _selected_edges_any(bm)
        comps = _edge_components(edges)
        if len(comps) != 2:
            return {"CANCELLED"}

        path_a = _ordered_path_from_edges(comps[0][0])
        path_b = _ordered_path_from_edges(comps[1][0])
        if not path_a or not path_b:
            return {"CANCELLED"}

        n = min(len(path_a), len(path_b))
        if n < 2:
            return {"CANCELLED"}

        pairing = self.pairing
        if pairing == "AUTO":
            d_index = (path_a[0].co - path_b[0].co).length_squared + (path_a[-1].co - path_b[-1].co).length_squared
            d_rev = (path_a[0].co - path_b[-1].co).length_squared + (path_a[-1].co - path_b[0].co).length_squared
            pairing = "REVERSE" if d_rev < d_index else "INDEX"
        if pairing == "REVERSE":
            path_b = list(reversed(path_b))

        targetmap = {}
        for i in range(n):
            va = path_a[i]
            vb = path_b[i]
            mid = (va.co + vb.co) * 0.5
            va.co = mid
            targetmap[vb] = va
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
        bmesh.update_edit_mesh(obj.data, destructive=True)
        return {"FINISHED"}


class M8_OT_SmartPathsConnect(bpy.types.Operator):
    bl_idname = "m8.smart_paths_connect"
    bl_label = "M8 连接路径 (Connect Paths)"
    bl_options = {"REGISTER", "UNDO"}

    pairing: bpy.props.EnumProperty(
        name="配对",
        items=[
            ("AUTO", "自动", ""),
            ("INDEX", "顺序", ""),
            ("REVERSE", "反向", ""),
        ],
        default="AUTO",
    )

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.prop(self, "pairing", expand=True)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        obj = context.edit_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        edges = _selected_edges_any(bm)
        comps = _edge_components(edges)
        if len(comps) != 2:
            return {"CANCELLED"}

        path_a = _ordered_path_from_edges(comps[0][0])
        path_b = _ordered_path_from_edges(comps[1][0])
        if not path_a or not path_b:
            return {"CANCELLED"}

        n = min(len(path_a), len(path_b))
        if n < 2:
            return {"CANCELLED"}

        pairing = self.pairing
        if pairing == "AUTO":
            d_index = (path_a[0].co - path_b[0].co).length_squared + (path_a[-1].co - path_b[-1].co).length_squared
            d_rev = (path_a[0].co - path_b[-1].co).length_squared + (path_a[-1].co - path_b[0].co).length_squared
            pairing = "REVERSE" if d_rev < d_index else "INDEX"
        if pairing == "REVERSE":
            path_b = list(reversed(path_b))

        created = 0
        for i in range(n):
            v1 = path_a[i]
            v2 = path_b[i]
            try:
                bm.edges.new((v1, v2))
                created += 1
            except ValueError:
                pass

        if created:
            bmesh.update_edit_mesh(obj.data, destructive=True)
        return {"FINISHED"}


class M8_OT_SmartSlideExtend(bpy.types.Operator):
    bl_idname = "m8.smart_slide_extend"
    bl_label = "M8 滑动/延伸 (Slide/Extend)"
    bl_options = {"REGISTER", "UNDO"}

    slide_mode: bpy.props.EnumProperty(
        name="类型",
        items=[
            ("AUTO", "自动", ""),
            ("VERT", "顶点", ""),
            ("EDGE", "边", ""),
        ],
        default="AUTO",
    )

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.prop(self, "slide_mode", expand=True)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        select_mode = context.tool_settings.mesh_select_mode
        if self.slide_mode == "EDGE" or (self.slide_mode == "AUTO" and select_mode[1]):
            bpy.ops.transform.edge_slide("INVOKE_DEFAULT")
            return {"FINISHED"}
        bpy.ops.transform.vert_slide("INVOKE_DEFAULT")
        return {"FINISHED"}


class M8_OT_SmartToggleSharp(bpy.types.Operator):
    bl_idname = "m8.smart_toggle_sharp"
    bl_label = "M8 切换锐边 (Sharps)"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        name="操作",
        items=[
            ("TOGGLE", "切换", ""),
            ("MARK", "标记", ""),
            ("CLEAR", "清除", ""),
        ],
        default="TOGGLE",
    )

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.prop(self, "action", expand=True)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        obj = context.edit_object
        if not obj or obj.type != "MESH":
            return {"CANCELLED"}
        bm = bmesh.from_edit_mesh(obj.data)
        edges = [e for e in bm.edges if e.select]
        if not edges:
            return {"CANCELLED"}
        if self.action == "MARK":
            bpy.ops.mesh.mark_sharp(clear=False)
        elif self.action == "CLEAR":
            bpy.ops.mesh.mark_sharp(clear=True)
        else:
            if any(e.smooth for e in edges):
                bpy.ops.mesh.mark_sharp(clear=False)
            else:
                bpy.ops.mesh.mark_sharp(clear=True)
        return {"FINISHED"}


class M8_OT_SmartOffsetEdges(bpy.types.Operator):
    bl_idname = "m8.smart_offset_edges"
    bl_label = "M8 偏移边 (Offset Edges)"
    bl_options = {"REGISTER", "UNDO"}

    method: bpy.props.EnumProperty(
        name="方式",
        items=[
            ("AUTO", "自动", ""),
            ("OFFSET", "Offset Edge Loops", ""),
            ("BEVEL", "Bevel", ""),
        ],
        default="AUTO",
    )

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.prop(self, "method", expand=True)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            return {"CANCELLED"}
        if self.method == "BEVEL":
            bpy.ops.mesh.bevel("INVOKE_DEFAULT", offset_type="WIDTH", affect='EDGES')
            return {"FINISHED"}
        if self.method == "OFFSET":
            bpy.ops.mesh.offset_edge_loops_slide("INVOKE_DEFAULT")
            return {"FINISHED"}
        try:
            bpy.ops.mesh.offset_edge_loops_slide("INVOKE_DEFAULT")
        except Exception:
            bpy.ops.mesh.bevel("INVOKE_DEFAULT", offset_type="WIDTH", affect='EDGES')
        return {"FINISHED"}


class M8_OT_SmartEdgeToggleMode(bpy.types.Operator):
    bl_idname = "m8.smart_edge_toggle_mode"
    bl_label = "M8 切换 Smart Edge 模式"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name="模式",
        items=[
            ("SELECT", "选择区域 (Select)", "将闭合边环转换为面选择"),
            ("SHARPS", "锐边 (Sharps)", "标记或清除锐边"),
            ("BRIDGE", "桥接 (Bridge)", "桥接两个边环"),
            ("FILL", "填充 (Fill)", "填充闭合区域"),
        ],
        default="SELECT",
    )

    def invoke(self, context, event):
        prefs = _get_addon_prefs()
        if prefs and hasattr(prefs, "smart_edge_mode"):
            try:
                # Use string conversion to avoid enum errors if old prefs exist
                self.mode = str(getattr(prefs, "smart_edge_mode", self.mode))
            except Exception:
                pass
        return self.execute(context)

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not hasattr(prefs, "smart_edge_mode"):
            return {"CANCELLED"}
        try:
            cur = str(getattr(prefs, "smart_edge_mode", "SELECT"))
            modes = ["SELECT", "SHARPS", "BRIDGE", "FILL"]
            
            # Simple cycle logic
            if self.mode == cur:
                try:
                    idx = modes.index(cur)
                except ValueError:
                    idx = 0
                prefs.smart_edge_mode = modes[(idx + 1) % len(modes)]
            else:
                prefs.smart_edge_mode = self.mode
                
            # Report the new mode
            self.report({'INFO'}, f"Smart Edge Mode: {prefs.smart_edge_mode}")
        except Exception:
            pass
        return {"FINISHED"}


classes = (
    M8_OT_SmartVert,
    M8_OT_SmartEdge,
    M8_OT_SmartFace,
    M8_OT_CleanUp,
    M8_OT_SmartMergeCenter,
    M8_OT_SmartPathsMerge,
    M8_OT_SmartPathsConnect,
    M8_OT_SmartSlideExtend,
    M8_OT_SmartToggleSharp,
    M8_OT_SmartOffsetEdges,
    M8_OT_SmartEdgeToggleMode,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
