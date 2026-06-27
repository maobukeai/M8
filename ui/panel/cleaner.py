import bpy
from ...utils.i18n import _T

def _get_addon_prefs(context):
    root_pkg = ".".join(__package__.split(".")[:3]) if (__package__ or "").startswith("bl_ext") else (__package__ or "").split(".")[0]
    addon = context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

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
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.clean
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
