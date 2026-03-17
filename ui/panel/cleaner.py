import bpy
from ...utils.i18n import _T

def _get_addon_prefs(context):
    root_pkg = (__package__ or "").split(".")[0]
    addon = context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

class VIEW3D_PT_M8_CleanUp(bpy.types.Panel):
    bl_label = ""
    bl_idname = "VIEW3D_PT_m8_clean_up"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm8'
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return False

    def draw_header(self, context):
        self.layout.label(text=_T("清理"))

    def draw(self, context):
        layout = self.layout

        if not (context.active_object and context.active_object.type == 'MESH' and context.mode == 'EDIT_MESH'):
            layout.label(text=_T("Please enter Edit Mode"), icon='INFO')
            layout.enabled = False

        if not hasattr(context.scene, 'm8_clean_props'):
            layout.label(text=_T("Properties not registered"), icon='ERROR')
            return

        props = context.scene.m8_clean_props
        prefs = _get_addon_prefs(context)

        # Initialization logic moved out of draw to prevent "Writing to ID classes" error
        # Properties will use their default values defined in M8_Clean_Props


        row = layout.row(align=True)
        op = row.operator("m8.clean_up", text=_T("清理"), icon="BRUSH_DATA")
        op.merge_distance = float(props.cleanup_merge_distance)
        op.affect = str(props.cleanup_affect)
        op.do_merge_by_distance = bool(props.cleanup_do_merge_by_distance)
        op.do_dissolve_degenerate = bool(props.cleanup_do_dissolve_degenerate)
        op.degenerate_dist = float(props.cleanup_degenerate_dist)
        op.do_limited_dissolve = bool(props.cleanup_do_limited_dissolve)
        op.limited_dissolve_angle = float(props.cleanup_limited_dissolve_angle)
        op.do_make_planar = bool(props.cleanup_do_make_planar)
        op.planar_iterations = int(props.cleanup_planar_iterations)
        op.do_delete_interior_faces = bool(props.cleanup_do_delete_interior_faces)
        op.do_delete_loose = bool(props.cleanup_do_delete_loose)
        op.do_delete_loose_edges = bool(props.cleanup_do_delete_loose)
        op.do_delete_loose_verts = bool(props.cleanup_do_delete_loose)
        op.do_recalc_normals = bool(props.cleanup_do_recalc_normals)

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(props, "cleanup_do_merge_by_distance", text=_T("重复"))
        row.prop(props, "cleanup_do_dissolve_degenerate", text=_T("退化"))
        sub = row.row(align=True)
        sub.enabled = bool(props.cleanup_do_merge_by_distance)
        sub.prop(props, "cleanup_merge_distance", text="")

        row = col.row(align=True)
        row.prop(props, "cleanup_do_delete_loose", text=_T("松散"))
        row.prop(props, "cleanup_do_limited_dissolve", text=_T("冗余"))
        sub = row.row(align=True)
        sub.enabled = bool(props.cleanup_do_limited_dissolve)
        sub.prop(props, "cleanup_limited_dissolve_angle", text="")

        ts = getattr(context, "tool_settings", None)
        if ts and getattr(ts, "mesh_select_mode", None):
            row = col.row(align=True)
            row.prop(ts, "mesh_select_mode", index=0, toggle=True, text=_T("顶点"))
            row.prop(ts, "mesh_select_mode", index=1, toggle=True, text=_T("边"))
            row.prop(ts, "mesh_select_mode", index=2, toggle=True, text=_T("面"))

        row = col.row(align=True)
        row.prop(props, "cleanup_do_recalc_normals", text=_T("重新计算法线"))
        row.operator("mesh.flip_normals", text=_T("翻转"))

        row = col.row(align=True)
        row.prop(props, "cleanup_do_select_tools", text=_T("选择"))
        row.operator("view3d.view_selected", text=_T("查看所选"))

        row = col.row(align=True)
        row.enabled = bool(props.cleanup_do_select_tools)
        row.operator("mesh.select_non_manifold", text=_T("非流形"))
        row.operator("mesh.select_non_planar", text=_T("非平面"))
        op = row.operator("mesh.select_face_by_sides", text=_T("三角面"))
        op.number = 3
        op.type = "EQUAL"
        op.extend = False
        op = row.operator("mesh.select_face_by_sides", text=_T("N边面"))
        op.number = 4
        op.type = "GREATER"
        op.extend = False

        box = layout.box()
        box.prop(props, "cleanup_show_advanced", toggle=True)
        if props.cleanup_show_advanced:
            box.prop(props, "cleanup_affect", expand=True)

            row = box.row(align=True)
            row.prop(props, "cleanup_do_dissolve_degenerate")
            sub = row.row(align=True)
            sub.enabled = bool(props.cleanup_do_dissolve_degenerate)
            sub.prop(props, "cleanup_degenerate_dist", text="")

            row = box.row(align=True)
            row.prop(props, "cleanup_do_make_planar")
            sub = row.row(align=True)
            sub.enabled = bool(props.cleanup_do_make_planar)
            sub.prop(props, "cleanup_planar_iterations", text="")

            box.prop(props, "cleanup_do_delete_interior_faces")

            row = box.row(align=True)
            row.label(text=_T("非平面角度"))
            row.prop(props, "cleanup_non_planar_angle", text="")

class VIEW3D_PT_M8_MeshCleaner(bpy.types.Panel):
    """M8 Mesh Cleaner Panel"""
    bl_label = ""
    bl_idname = "VIEW3D_PT_m8_mesh_cleaner"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm8'
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return True

    def draw_header(self, context):
        self.layout.label(text=_T("网格清理"))

    def draw(self, context):
        layout = self.layout
        
        # Check if we are in Edit Mode
        if not (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH'):
            layout.label(text=_T("Please enter Edit Mode"), icon='INFO')
            layout.enabled = False
        
        # Use our new property group if available, otherwise fallback might be needed but we expect it to be registered
        if hasattr(context.scene, 'm8_clean_props'):
            props = context.scene.m8_clean_props
        else:
            layout.label(text=_T("Properties not registered"), icon='ERROR')
            return

        # Toggle Advanced Settings
        layout.prop(props, "show_advanced", icon='SETTINGS', toggle=True)
        layout.separator()

        # -------------------------------------------------------------------
        # Circular Loop Cleaner Section
        # -------------------------------------------------------------------
        box = layout.box()
        box.label(text=_T("循环边清理"), icon='MESH_CIRCLE')
        
        # Main cleaning buttons
        row = box.row(align=True)
        row.operator("mesh.m8_simple_edge_loop_cleaner", 
                    text=_T("清理循环边"), 
                    icon='MESH_CIRCLE')
        
        row.operator("mesh.m8_smart_edge_loop_cleaner", 
                    text=_T("智能清理"), 
                    icon='MESH_ICOSPHERE')
        
        if props.show_advanced:
            # Advanced Filter Settings
            col = box.column(align=True)
            col.label(text=_T("高级过滤设置:"))
            col.prop(props, "flat_threshold_min", slider=True)
            col.prop(props, "flat_threshold_max", slider=True)
            
            # Settings
            col = box.column(align=True)
            col.label(text=_T("通用设置:"))
            col.prop(props, "use_checker_deselect")
            col.prop(props, "auto_dissolve")
        
        # Tools
        sub_box = box.box()
        sub_box.label(text=_T("辅助工具"), icon='TOOL_SETTINGS')
        
        row = sub_box.row(align=True)
        row.operator("mesh.m8_checker_deselect",
                    text=_T("间隔减选"),
                    icon='SELECT_INTERSECT')
        row.operator("mesh.m8_mark_sharp_edges",
                    text=_T("标记锐边"),
                    icon='LINCURVE')
        
        row = sub_box.row(align=True)
        row.operator("mesh.m8_auto_unsubdivide",
                    text=_T("自动反细分"),
                    icon='MOD_DECIM')
        row.operator("mesh.m8_decimate_selected",
                    text=_T("精简"),
                    icon='MOD_DECIM')
        
        row = sub_box.row(align=True)
        row.operator("mesh.m8_dissolve_selected_edges",
                    text=_T("融并边"),
                    icon='X')

        # -------------------------------------------------------------------
        # Auto Unbevel Section
        # -------------------------------------------------------------------
        box = layout.box()
        box.label(text=_T("反倒角工具"), icon='MESH_DATA')
        
        if props.show_advanced:
            col = box.column(align=True)
            col.prop(props, "similarity_threshold", text=_T("相似阈值"))
            row = col.row(align=True)
            row.prop(props, "mark_sharp_similar", text=_T("锐边(相似)"))
            row.prop(props, "mark_sharp_selected", text=_T("锐边(选中)"))
        
        row = box.row(align=True)
        row.operator("mesh.m8_select_short_edges", text=_T("选择短边"), icon='RESTRICT_SELECT_OFF')
        row.operator("mesh.m8_unbevel_selected", text=_T("反倒角选中"), icon='X')
        
        box.operator("mesh.m8_auto_unbevel_similar", text=_T("反倒角相似项"), icon='MOD_WIREFRAME')

        # -------------------------------------------------------------------
        # Flat Loop Cleaner Section
        # -------------------------------------------------------------------
        box = layout.box()
        box.label(text=_T("平坦边清理"), icon="MOD_DECIM")

        col = box.column(align=True)
        col.operator("mesh.m8_flat_loop_cleaner", icon="MOD_DECIM", text=_T("选择平坦循环边"))
        col.operator("mesh.m8_dissolve_selected_edges", icon="X", text=_T("融并选中的边"))

        if props.show_advanced:
            # Select Similar Loops Section
            layout.separator()
            box2 = layout.box()
            box2.label(text=_T("相似/打平工具"), icon="FACESEL")

            col2 = box2.column(align=True)
            col2.operator("mesh.m8_select_similar_loops", icon="FACESEL", text=_T("选择相似循环边"))
            col2.operator("mesh.m8_flatten_loops", icon="MESH_PLANE", text=_T("打平选中项"))
