import bpy
from ..utils.logger import get_logger
from ..utils.i18n import _T
from ..utils.adapter import get_adapter_blender_icon as _ICON


def _on_language_changed():
    """Re-register translations when the addon language preference changes."""
    try:
        from ..translations import register_translations
        register_translations()
    except Exception:
        pass
    try:
        from ..src import translate as mp7_translate
        mp7_translate.unregister()
        mp7_translate.register()
    except Exception:
        pass


def _on_auto_error_report_changed(self, context):
    """Record explicit consent before allowing automated error uploads."""
    if self.auto_error_report:
        self.error_report_consent_version = 1


from .keymap_constants import *
from .keymap_helpers import (
    _get_addon_prefs,
    _ensure_pie_keymap_priority,
    _on_prefs_update,
    _on_autoorigin_update,
    _on_autopack_update,
    _switch_editor_items,
    _active_tab_items,
    _smart_face_action_items,
    _clean_up_affect_items,
    _switch_mode_tab_behavior_items,
    _screencast_align_items,
    _screencast_operator_label_mode_items,
    _screencast_stack_direction_items,
    _screencast_mouse_display_items,
    _addon_language_items,
    _smart_edge_mode_items,
    _group_tool_empty_type_items,
    _switch_mode_target_items,
    _switch_bone_mode_target_items,
    _delete_pie_items,
    _unity_fbx_apply_scale_options_items,
    _origin_default_operator_types_items,
    _moving_view_type_items,
    _find_subdivision_keymap_items,
    _find_pie_keymap_item,
    _find_switch_mode_keymap_items,
    _find_quick_delete_keymap_items,
    _find_delete_pie_keymap_items,
    _find_edge_property_pie_keymap_items,
    _find_align_pie_keymap_items,
    _find_shading_pie_keymap_items,
    _find_save_pie_keymap_items,
    _find_switch_editor_pie_keymap_items,
    _find_rename_keymap_items,
    _find_mirror_keymap_items,
    _find_group_tool_keymap_items,
    _find_double_click_select_group_keymap_items,
    _find_smart_pie_keymap_items,
    _find_toggle_area_keymap_items,
    _find_fast_loop_keymap_items,
    restore_tracked_conflicts,
)

class M8_MP7_MockDrawProperty(bpy.types.PropertyGroup):
    enable_name_translation: bpy.props.BoolProperty(name="Enable Name Translation", default=True)

def _on_transform_update(self, context):
    self.navigation_tab = "TRANSFORM"
    _on_prefs_update(self, context)

def _on_switch_mode_update(self, context):
    self.navigation_tab = "SWITCH_MODE"
    _on_prefs_update(self, context)

def _on_quick_delete_update(self, context):
    self.navigation_tab = "DELETE"
    _on_prefs_update(self, context)

def _on_delete_pie_update(self, context):
    self.navigation_tab = "DELETE"
    _on_prefs_update(self, context)

def _on_edge_property_update(self, context):
    self.navigation_tab = "EDGE_PROPERTY"
    _on_prefs_update(self, context)

def _on_align_update(self, context):
    self.navigation_tab = "ALIGN"
    _on_prefs_update(self, context)

def _on_shading_update(self, context):
    self.navigation_tab = "SHADING"
    _on_prefs_update(self, context)

def _on_save_update(self, context):
    self.navigation_tab = "SAVE"
    _on_prefs_update(self, context)

def _on_mirror_update(self, context):
    self.navigation_tab = "MIRROR"
    _on_prefs_update(self, context)

def _on_group_tool_update(self, context):
    self.navigation_tab = "GROUP"
    _on_prefs_update(self, context)

def _on_smart_pie_update(self, context):
    self.navigation_tab = "SMART_PIE"
    _on_prefs_update(self, context)

def _on_toggle_area_update(self, context):
    self.navigation_tab = "TOGGLE_AREA"
    _on_prefs_update(self, context)

def _on_switch_editor_update(self, context):
    self.navigation_tab = "SWITCH_EDITOR"
    _on_prefs_update(self, context)

def _on_subdivision_update(self, context):
    self.navigation_tab = "SUBDIVISION"
    _on_prefs_update(self, context)

def _on_rename_update(self, context):
    self.navigation_tab = "RENAME"
    _on_prefs_update(self, context)

class M8_OT_Dummy(bpy.types.Operator):
    bl_idname = "m8.dummy"
    bl_label = _T("未开发")
    bl_description = _T("该功能暂时未开发")
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}

class SIZE_TOOL_Preferences(bpy.types.AddonPreferences):
    bl_idname = ".".join(__package__.split(".")[:3]) if (__package__ or "").startswith("bl_ext") else (__package__ or "").split(".")[0]

    addon_language: bpy.props.EnumProperty(
        name=_T("界面语言"),
        items=_addon_language_items,
        default=0,
        update=lambda self, context: _on_language_changed(),
    )

    auto_error_report: bpy.props.BoolProperty(
        name=_T("自动发送错误报告"),
        description=_T("当插件运行出错时自动上报Traceback到服务器以利于后续修复"),
        default=False,
        update=_on_auto_error_report_changed,
    )
    error_report_consent_version: bpy.props.IntProperty(default=0, options={'HIDDEN'})
    auto_check_updates: bpy.props.BoolProperty(
        name=_T("自动检查更新"),
        description=_T("启动后自动连接更新服务器检查新版本"),
        default=True,
    )

    backup_suffix: bpy.props.StringProperty(name=_T("备用盒后缀"), default="_Backup")
    backup_collection_name: bpy.props.StringProperty(name=_T("备用盒集合名"), default="SizeTool_Backups")
    default_padding: bpy.props.FloatProperty(name=_T("默认 Padding"), default=0.0, min=0.0, unit='LENGTH')
    archive_default_bake: bpy.props.BoolProperty(name=_T("备用盒默认烘焙"), default=False)
    enable_transform_pie: bpy.props.BoolProperty(name=_T("启用变换辅助饼菜单"), default=True, update=_on_transform_update)
    activate_switch_mode: bpy.props.BoolProperty(name=_T("启用模式切换(Tab)"), default=True, update=_on_switch_mode_update)
    activate_quick_delete: bpy.props.BoolProperty(name=_T("快速删除(无确认)"), default=True, update=_on_quick_delete_update)
    activate_delete_pie: bpy.props.BoolProperty(name=_T("启用删除饼菜单(Edit)"), default=True, update=_on_delete_pie_update)
    activate_align_pie: bpy.props.BoolProperty(name=_T("启用对齐饼菜单 (Alt+A)"), default=True, update=_on_align_update)
    activate_shading_pie: bpy.props.BoolProperty(name=_T("启用着色饼菜单 (Z)"), default=True, update=_on_shading_update)
    activate_save_pie: bpy.props.BoolProperty(name=_T("启用保存饼菜单 (Ctrl+S)"), default=True, update=_on_save_update)
    activate_advanced_rename: bpy.props.BoolProperty(name=_T("启用高级重命名 (F2)"), default=True, update=_on_rename_update)
    activate_mirror: bpy.props.BoolProperty(name=_T("启用镜像 (Shift+Alt+X)"), default=True, update=_on_mirror_update)
    activate_group_tool: bpy.props.BoolProperty(name=_T("启用打组 (Ctrl+G)"), default=True, update=_on_group_tool_update)
    activate_smart_pie: bpy.props.BoolProperty(name=_T("启用智能饼菜单 (1)"), default=True, update=_on_smart_pie_update)

    activate_switch_editor_pie: bpy.props.BoolProperty(name=_T("启用切换窗口饼菜单 (F12)"), default=True, update=_on_switch_editor_update)
    ui_show_switch_editor_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(切换窗口)"), default=False)
    activate_subdivision_shortcuts: bpy.props.BoolProperty(name=_T("启用细分快捷键 (Ctrl+0..4)"), default=True, update=_on_subdivision_update)
    ui_show_subdivision_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(细分级别)"), default=False)
    switch_editor_pie_left: bpy.props.EnumProperty(name=_T("左"), items=_switch_editor_items, default=4)
    switch_editor_pie_right: bpy.props.EnumProperty(name=_T("右"), items=_switch_editor_items, default=24)
    switch_editor_pie_bottom: bpy.props.EnumProperty(name=_T("下"), items=_switch_editor_items, default=3)
    switch_editor_pie_top: bpy.props.EnumProperty(name=_T("上"), items=_switch_editor_items, default=1)
    switch_editor_pie_top_left: bpy.props.EnumProperty(name=_T("左上"), items=_switch_editor_items, default=3)
    switch_editor_pie_top_right: bpy.props.EnumProperty(name=_T("右上"), items=_switch_editor_items, default=7)
    switch_editor_pie_bottom_left: bpy.props.EnumProperty(name=_T("左下"), items=_switch_editor_items, default=6)
    switch_editor_pie_bottom_right: bpy.props.EnumProperty(name=_T("右下"), items=_switch_editor_items, default=13)

    
    # --- Toggle Area ---
    activate_toggle_area: bpy.props.BoolProperty(name=_T("启用区域切换 (T)"), default=True, update=_on_toggle_area_update)
    toggle_area_close_range: bpy.props.FloatProperty(name=_T("关闭范围 (%)"), default=30.0, min=0.0, max=100.0, description=_T("以区域宽/高的百分比表示与边界的接近度"))
    toggle_area_prefer_left_right: bpy.props.BoolProperty(name=_T("首选左/右切换"), default=True, description=_T("在使用 Close Range 确定是否切换另一对之前，首选左/右切换，而不是 下/上"))
    toggle_area_asset_shelf: bpy.props.BoolProperty(name=_T("切换资产架"), default=True, description=_T("如果可用，则切换“资产工具架”而不是“浏览器”"))
    toggle_area_asset_browser_top: bpy.props.BoolProperty(name=_T("切换资产浏览器到顶部"), default=True)
    toggle_area_asset_browser_bottom: bpy.props.BoolProperty(name=_T("切换资产浏览器到底部"), default=True)
    toggle_area_split_factor: bpy.props.FloatProperty(name=_T("分割比例"), default=0.25, min=0.1, max=0.8, description=_T("切换出的资产浏览器占区域高度的比例"))
    toggle_area_wrap_mouse: bpy.props.BoolProperty(name=_T("鼠标跟随"), default=False, description=_T("将鼠标包围到资源浏览器边框"))
    ui_show_toggle_area_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Toggle Area)"), default=False)

    ui_show_smart_pie_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(智能饼菜单)"), default=False)
    smart_edge_mode: bpy.props.EnumProperty(
        name=_T("Smart Edge 模式"),
        items=_smart_edge_mode_items,
        default=0,
    )
    smart_face_focus_mode: bpy.props.BoolProperty(name=_T("Smart Face: 聚焦模式"), default=False)
    smart_face_stay_on_original: bpy.props.BoolProperty(name=_T("Smart Face: 停留在原始对象"), default=False)
    smart_face_action: bpy.props.EnumProperty(
        name=_T("Smart Face 默认动作"),
        items=_smart_face_action_items,
        default=0,
    )
    clean_up_merge_distance: bpy.props.FloatProperty(name=_T("合并距离"), default=0.0001, min=0.0)
    clean_up_affect: bpy.props.EnumProperty(
        name=_T("影响范围"),
        items=_clean_up_affect_items,
        default=0,
    )
    clean_up_do_merge_by_distance: bpy.props.BoolProperty(name=_T("合并重复点"), default=False)
    clean_up_do_dissolve_degenerate: bpy.props.BoolProperty(name=_T("溶解退化几何"), default=True)
    clean_up_degenerate_dist: bpy.props.FloatProperty(name=_T("退化阈值"), default=0.00001, min=0.0)
    clean_up_do_limited_dissolve: bpy.props.BoolProperty(name=_T("有限溶解"), default=True)
    clean_up_limited_dissolve_angle: bpy.props.FloatProperty(name=_T("有限溶解角度"), default=0.0872665, min=0.0, max=3.14159, subtype="ANGLE")
    clean_up_do_make_planar: bpy.props.BoolProperty(name=_T("平坦化面"), default=False)
    clean_up_planar_iterations: bpy.props.IntProperty(name=_T("平坦化迭代"), default=1, min=1, max=10)
    clean_up_do_delete_interior_faces: bpy.props.BoolProperty(name=_T("删除内部面"), default=False)
    clean_up_do_delete_loose_edges: bpy.props.BoolProperty(name=_T("删除孤立边"), default=True)
    clean_up_do_delete_loose_verts: bpy.props.BoolProperty(name=_T("删除孤立点"), default=True)
    clean_up_recalc_normals: bpy.props.BoolProperty(name=_T("重算法线"), default=False)
    has_migrated_clean_up_defaults: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    activate_double_click_select_group: bpy.props.BoolProperty(name=_T("双击选择组"), default=False, update=_on_prefs_update)
    group_tool_radius: bpy.props.FloatProperty(name=_T("组半径"), default=1.0, min=0.1, unit='LENGTH')
    group_tool_empty_type: bpy.props.EnumProperty(
        name=_T("空物体类型"),
        items=_group_tool_empty_type_items,
        default=5,
    )
    group_tool_hide_empty: bpy.props.BoolProperty(name=_T("隐藏组空物体"), default=False, description=_T("创建组时自动隐藏组父物体"))
    activate_restart_blender: bpy.props.BoolProperty(name=_T("启用重启 Blender 按钮"), default=True)

    active_tab: bpy.props.EnumProperty(
        name="Tab",
        items=_active_tab_items,
        default=0,
    )

    navigation_tab: bpy.props.EnumProperty(
        name="Navigation",
        items=[
            ("TRANSFORM", _T("变换"), "Transform Pie"),
            ("SWITCH_MODE", _T("切换模式"), "Switch Mode"),
            ("DELETE", _T("删除"), "Delete Tools"),
            ("EDGE_PROPERTY", _T("边属性"), "Edge Property"),
            ("ALIGN", _T("对齐"), "Align Pie"),
            ("SHADING", _T("着色"), "Shading Pie"),
            ("SAVE", _T("保存"), "Save Pie"),
            ("RENAME", _T("重命名"), "Advanced Rename"),
            ("MIRROR", _T("镜像"), "Mirror Tool"),
            ("GROUP", _T("打组"), "Group Tool"),
            ("SMART_PIE", _T("智能饼菜单"), "Smart Pie (1)"),
            ("TOGGLE_AREA", _T("区域切换"), "Toggle Area (T)"),
            ("SWITCH_EDITOR", _T("切换窗口"), "Switch Editor Pie (F12)"),
            ("SUBDIVISION", _T("细分级别"), "Subdivision Set"),
            ("FAST_LOOP", _T("快速循环切刀"), "Fast Loop Cut"),
            ("SCREENCAST", _T("按键显示"), "Screencast"),
            ("OTHER", _T("其它设置"), "Other Settings"),
            ("ABOUT", _T("关于"), "About"),
        ],
        default="TRANSFORM",
    )

    ui_show_all_settings: bpy.props.BoolProperty(name=_T("显示全部"), default=False)
    show_diagnostics_panels: bpy.props.BoolProperty(name=_T("显示诊断/场景审计面板"), default=False)

    fbx_export_unity_preset: bpy.props.BoolProperty(name=_T("FBX 导出使用 Unity 预设"), default=True)
    unity_fbx_use_selection: bpy.props.BoolProperty(name=_T("Unity FBX: 仅导出选择"), default=True)
    unity_fbx_global_scale: bpy.props.FloatProperty(name=_T("Unity FBX: 全局缩放"), default=100.0, min=0.001, max=1000.0)
    unity_fbx_apply_unit_scale: bpy.props.BoolProperty(name=_T("Unity FBX: 应用单位"), default=True)
    unity_fbx_apply_scale_options: bpy.props.EnumProperty(
        name="Unity FBX: Apply Scalings",
        items=_unity_fbx_apply_scale_options_items,
        default=3,
    )
    unity_fbx_use_triangles: bpy.props.BoolProperty(name=_T("Unity FBX: 三角化"), default=True)
    unity_fbx_use_tspace: bpy.props.BoolProperty(name=_T("Unity FBX: 导出切线"), default=True)
    unity_fbx_bake_anim: bpy.props.BoolProperty(name=_T("Unity FBX: 导出动画"), default=False)
    unity_fbx_export_dir: bpy.props.StringProperty(name=_T("Unity FBX: 导出目录"), default="", subtype="DIR_PATH")
    unity_fbx_use_blend_dir: bpy.props.BoolProperty(name=_T("Unity FBX: 使用 .blend 同目录"), default=True)
    unity_fbx_open_folder_after_export: bpy.props.BoolProperty(name=_T("Unity FBX: 导出后打开文件夹"), default=False)
    unity_fbx_reveal_after_export: bpy.props.BoolProperty(name=_T("Unity FBX: 导出后定位文件"), default=True)
    ui_show_unity_fbx_advanced: bpy.props.BoolProperty(name=_T("Unity FBX: 高级"), default=False)

    auto_pack_resources_on_save: bpy.props.BoolProperty(name=_T("保存时自动打包资源"), default=False, update=_on_autopack_update)
    auto_purge_unused_materials_on_save: bpy.props.BoolProperty(name=_T("保存时自动清除孤立数据"), default=False, update=_on_autopack_update)
    incremental_save_prefix: bpy.props.StringProperty(
        name=_T("增量保存版本前缀"),
        description=_T("增量保存时使用的版本前缀，例如 '_v' 会生成 filename_v1.blend、filename_v2.blend"),
        default="_v",
    )

    auto_new_object_origin_bottom: bpy.props.BoolProperty(name=_T("新建物体默认原点到底部"), default=False, update=_on_autoorigin_update)
    auto_new_object_snap_to_floor: bpy.props.BoolProperty(name=_T("新建物体自动落地 (Z=0)"), default=False, update=_on_autoorigin_update)
    auto_exclusive_shift_s_on_startup: bpy.props.BoolProperty(name=_T("启动时自动独占所有快捷键"), default=False)
    auto_exclusive_shift_s_include_user: bpy.props.BoolProperty(name=_T("同时处理用户键位冲突"), default=True)

    # --- MP7Tools Integration Properties ---
    init: bpy.props.BoolProperty(name="Init", default=True, options={"SKIP_SAVE"})
    panel_name: bpy.props.StringProperty(name="Panel Name", default="M8")
    
    # MP7 Hub/Gizmo Settings
    hub_text_color: bpy.props.FloatVectorProperty(name=_T("文本颜色"), subtype='COLOR', default=(1, 1, 1, 1), size=4)
    hub_3d_color: bpy.props.FloatVectorProperty(name=_T("轴向颜色"), subtype='COLOR', default=(0.2, 0.6, 1, 0.8), size=4)
    hub_area_color: bpy.props.FloatVectorProperty(name=_T("区域颜色"), subtype='COLOR', default=(0.2, 0.6, 1, 0.2), size=4)
    hub_line_width: bpy.props.IntProperty(name=_T("线宽"), default=2, min=1, max=10)
    hub_vert_size: bpy.props.IntProperty(name=_T("点大小"), default=6, min=1, max=20)
    hub_matrix_line_width: bpy.props.IntProperty(name=_T("轴线宽"), default=3, min=1, max=10)
    hub_scale: bpy.props.FloatProperty(name=_T("Gizmo 缩放"), default=0.35, min=0.1, max=5.0)
    hub_fps: bpy.props.FloatProperty(name="FPS", default=60.0)

    # Mirror Preview Properties
    mirror_show_preview: bpy.props.BoolProperty(name=_T("显示网格预览"), default=False, description=_T("在操作时显示镜像后的网格预览（可能会影响性能）"))
    mirror_preview_vert_size: bpy.props.IntProperty(name=_T("预览点大小"), default=6, min=1, max=20)
    mirror_preview_edge_width: bpy.props.IntProperty(name=_T("预览线宽"), default=2, min=1, max=10)
    mirror_preview_max_edge_count: bpy.props.IntProperty(name=_T("最大边数优化"), default=10000, description=_T("当物体边数超过此值时简化预览以提高性能"))
    mirror_preview_optimize: bpy.props.BoolProperty(name=_T("强制简化预览"), default=False)
    mirror_preview_alpha: bpy.props.FloatProperty(name=_T("预览透明度"), default=0.5, min=0.0, max=1.0)
    mirror_preview_edge_color: bpy.props.FloatVectorProperty(name=_T("预览线颜色"), subtype='COLOR', default=(0.2, 0.8, 1.0, 1.0), size=4)

    mirror_use_mouse_pos: bpy.props.BoolProperty(name=_T("Gizmo 跟随鼠标"), default=True, description=_T("启动时 Gizmo 出现在鼠标位置，而非物体原点"))
    mirror_auto_confirm: bpy.props.BoolProperty(name=_T("松开即确认"), default=True, description=_T("松开快捷键时自动执行镜像，无需点击左键"))
    mirror_sensitivity: bpy.props.FloatProperty(name=_T("感应灵敏度"), default=2.0, min=0.1, max=5.0, description=_T("Gizmo 触发距离的缩放系数"))
    mirror_use_fixed_scale: bpy.props.BoolProperty(name=_T("使用固定大小"), default=False, description=_T("Gizmo 使用固定大小，不随视图缩放变化"))
    mirror_fixed_scale_value: bpy.props.FloatProperty(name=_T("固定大小值"), default=1.0, min=0.01, max=1000.0)

    activate_face_groups: bpy.props.BoolProperty(name=_T("启用面组"), default=True)
    origin_default_operator_types: bpy.props.EnumProperty(
        name="Default Origin Operator",
        description="Shift Add Selection",
        options={"ENUM_FLAG"},
        items=[
            ("ROTATE", "Rotate", ""),
            ("LOCATION", "Location", ""),
        ],
        default={"ROTATE", "LOCATION"},
    )
    moving_view_type: bpy.props.EnumProperty(
        default=2,
        name="Moving View Type",
        items=_moving_view_type_items
    )
    draw_property: bpy.props.PointerProperty(type=M8_MP7_MockDrawProperty)

    ui_show_tab_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Tab)"), default=False)
    ui_show_shift_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Shift+S)"), default=False)
    ui_show_switch_mode_mapping: bpy.props.BoolProperty(name=_T("显示方向映射"), default=False)
    ui_show_shift_s_advanced: bpy.props.BoolProperty(name=_T("显示高级(Shift+S)"), default=False)
    ui_show_other_settings: bpy.props.BoolProperty(name=_T("显示其它设置"), default=False)
    ui_show_delete_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Delete)"), default=False)
    ui_show_delete_mapping: bpy.props.BoolProperty(name=_T("显示方向映射(Delete)"), default=False)
    ui_show_align_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Align)"), default=False)
    ui_show_align_advanced: bpy.props.BoolProperty(name=_T("显示高级(Align)"), default=False)
    ui_show_shading_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Shading)"), default=False)
    ui_show_save_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Save)"), default=False)
    ui_show_save_advanced: bpy.props.BoolProperty(name=_T("显示高级(Save)"), default=False)

    ui_show_section_switch_mode: bpy.props.BoolProperty(name=_T("切换模式 (Tab)"), default=False)
    ui_show_section_transform_pie: bpy.props.BoolProperty(name=_T("变换辅助 (Shift+S)"), default=False)
    ui_show_section_delete: bpy.props.BoolProperty(name=_T("删除 (X)"), default=False)
    ui_show_section_align_pie: bpy.props.BoolProperty(name=_T("对齐 (Alt+A)"), default=False)
    ui_show_section_shading_pie: bpy.props.BoolProperty(name=_T("着色 (Z)"), default=False)
    ui_show_section_save_pie: bpy.props.BoolProperty(name=_T("保存 (Ctrl+S)"), default=False)
    ui_show_section_rename: bpy.props.BoolProperty(name=_T("重命名 (F2)"), default=False)
    ui_show_section_mirror: bpy.props.BoolProperty(name=_T("镜像 (Shift+Alt+X)"), default=False)
    ui_show_section_other: bpy.props.BoolProperty(name=_T("其它设置"), default=False)
    ui_show_section_screencast: bpy.props.BoolProperty(name=_T("Screencast (投射)"), default=False)

    # --- Edge Property Properties ---
    activate_edge_property_pie: bpy.props.BoolProperty(name=_T("启用 Edge Property Pie"), default=True, update=_on_edge_property_update)
    ui_show_edge_property_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Edge Property)"), default=False)
    ui_show_edge_property_advanced: bpy.props.BoolProperty(name=_T("显示高级(Edge Property)"), default=False)

    # --- Mirror Properties ---
    ui_show_mirror_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Mirror)"), default=False)
    ui_show_mirror_advanced: bpy.props.BoolProperty(name=_T("显示高级(Mirror)"), default=False)
    ui_show_group_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Group)"), default=False)
    ui_show_group_advanced: bpy.props.BoolProperty(name=_T("显示高级(Group)"), default=False)

    # --- Additional UI toggle properties ---
    ui_show_shading_advanced: bpy.props.BoolProperty(name=_T("高级(Shading)"), default=False)
    ui_show_smart_pie_advanced: bpy.props.BoolProperty(name=_T("高级(SmartPie)"), default=False)
    ui_show_toggle_area_advanced: bpy.props.BoolProperty(name=_T("高级(ToggleArea)"), default=False)
    ui_show_switch_editor_advanced: bpy.props.BoolProperty(name=_T("映射(SwitchEditor)"), default=False)
    ui_show_subdivision_advanced: bpy.props.BoolProperty(name=_T("高级(Subdivision)"), default=False)
    ui_show_rename_keymap: bpy.props.BoolProperty(name=_T("快捷键(Rename)"), default=False)

    # --- Fast Loop Properties ---
    activate_fast_loop: bpy.props.BoolProperty(name=_T("启用快速循环切刀"), default=True, update=_on_prefs_update)
    fast_loop_segments: bpy.props.IntProperty(name=_T("默认段数 (Cuts)"), default=1, min=1, max=100)
    fast_loop_vertex_mode: bpy.props.BoolProperty(name=_T("默认顶点模式"), default=False)
    fast_loop_guide_mode: bpy.props.BoolProperty(name=_T("默认引导模式"), default=False)
    fast_loop_snap_divisions: bpy.props.IntProperty(name=_T("吸附等分数"), default=4, min=1, max=100)
    fast_loop_use_even: bpy.props.BoolProperty(name=_T("默认等距模式"), default=False)
    fast_loop_flipped: bpy.props.BoolProperty(name=_T("默认反转方向"), default=False)
    fast_loop_mirrored: bpy.props.BoolProperty(name=_T("默认对称镜像"), default=False)
    fast_loop_perpendicular: bpy.props.BoolProperty(name=_T("默认法向投影"), default=False)
    fast_loop_use_curvature: bpy.props.BoolProperty(name=_T("默认曲率平滑"), default=False)
    fast_loop_enable_edge_flow: bpy.props.BoolProperty(
        name=_T("默认启用 EdgeFlow"),
        description=_T("启动工具时默认开启 EdgeFlow 模式（左键点击直接平滑切线）"),
        default=False
    )
    fast_loop_reproject_uv_after_edge_flow: bpy.props.BoolProperty(
        name=_T("EdgeFlow 后重投影 UV"),
        description=_T("按 EdgeFlow 后的新环线长度重新插值 UV，并保留 UV 缝。关闭可保留旧版 UV 行为。"),
        default=True
    )
    fast_loop_keep_selection: bpy.props.BoolProperty(
        name=_T("保持选择 (S键)"),
        description=_T("加线后保持新线和原有选择均处于选中状态。此选项会被记忆，下次打开工具时继承。"),
        default=False
    )
    # EdgeFlow parameters (mirroring the original Fast-Loop set_flow options)
    fast_loop_tension: bpy.props.IntProperty(
        name=_T("Tension"),
        description=_T("EdgeFlow 张力。默认 180，正值越大越贴近曲面，负值将弄到反面。"),
        default=180, min=-500, max=500
    )
    fast_loop_iterations: bpy.props.IntProperty(
        name=_T("Iterations"),
        description=_T("EdgeFlow 平滑迭代次数"),
        default=1, min=1, max=32
    )
    fast_loop_min_angle: bpy.props.IntProperty(
        name=_T("Min Angle"),
        description=_T("EdgeFlow 最小转角阈値（度），小于此角度的边不平滑"),
        default=0, min=0, max=180
    )
    ui_show_fast_loop_keymap: bpy.props.BoolProperty(name=_T("显示快捷键详情(Fast Loop)"), default=False)

    # --- Screencast Properties ---
    def _on_screencast_enabled_update(self, context):
        self.navigation_tab = "SCREENCAST"
        try:
            from ..ops.misc.screencast import M8_OT_InternalScreencast
            if self.screencast_enabled != M8_OT_InternalScreencast._running:
                found = False
                for win in context.window_manager.windows:
                    for area in win.screen.areas:
                        if area.type == 'VIEW_3D':
                            with context.temp_override(window=win, area=area):
                                bpy.ops.m8.internal_screencast('INVOKE_DEFAULT')
                            found = True
                            break
                    if found: break
                
                if not found:
                    bpy.ops.m8.internal_screencast('INVOKE_DEFAULT')
        except Exception:
            pass

    screencast_enabled: bpy.props.BoolProperty(
        name=_T("启用 Screencast"),
        default=True,
        description=_T("启用/禁用屏幕投射功能"),
        update=_on_screencast_enabled_update
    )
    screencast_font_size: bpy.props.IntProperty(name=_T("字体大小"), default=20, min=8, max=100)
    screencast_color: bpy.props.FloatVectorProperty(name=_T("文字颜色"), subtype='COLOR', default=(1, 1, 1, 1), size=4, min=0, max=1)
    screencast_bg_color: bpy.props.FloatVectorProperty(name=_T("背景颜色"), subtype='COLOR', default=(0.1, 0.1, 0.1, 0.2), size=4, min=0, max=1)
    screencast_offset_x: bpy.props.IntProperty(name=_T("X 偏移"), default=50)
    screencast_offset_y: bpy.props.IntProperty(name=_T("Y 偏移"), default=50)
    screencast_align: bpy.props.EnumProperty(
        name=_T("对齐"),
        items=_screencast_align_items,
        default=0
    )
    screencast_history_count: bpy.props.IntProperty(name=_T("显示行数"), default=5, min=1, max=20)
    screencast_timeout: bpy.props.FloatProperty(name=_T("消失延迟 (秒)"), default=2.0, min=0.1, max=10.0)
    screencast_show_shadow: bpy.props.BoolProperty(name=_T("文字阴影"), default=True)
    screencast_shadow_color: bpy.props.FloatVectorProperty(name=_T("阴影颜色"), subtype='COLOR', default=(0, 0, 0, 0.7), size=4, min=0, max=1)
    screencast_show_box: bpy.props.BoolProperty(name=_T("显示背景框"), default=True)
    screencast_box_radius: bpy.props.IntProperty(name=_T("背景框圆角"), default=20, min=0, max=50)
    screencast_box_padding: bpy.props.IntProperty(name=_T("背景框边距"), default=10, min=2, max=40)
    screencast_bg_image: bpy.props.StringProperty(name=_T("背景图片"), subtype='FILE_PATH', description=_T("可选作为背景框替代的自定义图片文件"))
    screencast_bg_image_alpha: bpy.props.FloatProperty(name=_T("背景图片透明度"), default=1.0, min=0.0, max=1.0)
    screencast_mouse_display: bpy.props.EnumProperty(
        name=_T("鼠标显示方式"),
        items=_screencast_mouse_display_items,
        default=0
    )
    screencast_mouse_size: bpy.props.IntProperty(
        name=_T("鼠标图标大小"),
        default=30,
        min=10,
        max=300,
        description=_T("设置鼠标显示图标的尺寸")
    )
    screencast_show_ripples: bpy.props.BoolProperty(name=_T("启用点击涟漪"), default=True, description=_T("鼠标点击时在光标位置显示扩散圆环动画"))
    screencast_ripple_color: bpy.props.FloatVectorProperty(name=_T("涟漪颜色"), subtype='COLOR', default=(0.0, 0.6, 1.0, 0.8), size=4, min=0, max=1)
    screencast_font_filepath: bpy.props.StringProperty(name=_T("自定义字体路径"), subtype='FILE_PATH', description=_T("可选加载外部字体（TTF/OTF）文件代替内置默认字体"))
    screencast_show_mouse: bpy.props.BoolProperty(name=_T("显示鼠标图形"), default=True, description=_T("常驻显示矢量鼠标指示图标"))
    screencast_show_last_operator: bpy.props.BoolProperty(name=_T("显示最后操作"), default=True, description=_T("在界面顶部显示刚调用的操作"))
    screencast_operator_label_mode: bpy.props.EnumProperty(
        name=_T("操作名称语言"),
        items=_screencast_operator_label_mode_items,
        default=0
    )
    screencast_stack_direction: bpy.props.EnumProperty(
        name=_T("堆叠方向"),
        items=_screencast_stack_direction_items,
        default=0
    )
    screencast_layout_mode: bpy.props.EnumProperty(
        name=_T("排版模式"),
        items=[
            ("SIDE", _T("并排"), _T("鼠标在左侧，文字在右侧")),
            ("ABOVE", _T("文字在上方"), _T("文字显示在鼠标图标的上方")),
            ("BELOW", _T("文字在下方"), _T("文字显示在鼠标图标的下方")),
        ],
        default="SIDE"
    )
    screencast_use_custom_mouse: bpy.props.BoolProperty(name=_T("使用自定义鼠标贴图"), default=False)
    screencast_mouse_img_base: bpy.props.StringProperty(name=_T("基础鼠标贴图"), subtype='FILE_PATH')
    screencast_mouse_img_lmouse: bpy.props.StringProperty(name=_T("左键按压贴图"), subtype='FILE_PATH')
    screencast_mouse_img_rmouse: bpy.props.StringProperty(name=_T("右键按压贴图"), subtype='FILE_PATH')
    screencast_mouse_img_mmouse: bpy.props.StringProperty(name=_T("中键按压贴图"), subtype='FILE_PATH')

    # --- Mode Switching Properties ---
    switch_mode_up: bpy.props.EnumProperty(items=_switch_mode_target_items, name="Up", default=3)
    switch_mode_down: bpy.props.EnumProperty(items=_switch_mode_target_items, name="Down", default=1)
    switch_mode_left: bpy.props.EnumProperty(items=_switch_mode_target_items, name="Left", default=0)
    switch_mode_right: bpy.props.EnumProperty(items=_switch_mode_target_items, name="Right", default=2)

    switch_bone_mode_up: bpy.props.EnumProperty(items=_switch_bone_mode_target_items, name="Up", default=0)
    switch_bone_mode_down: bpy.props.EnumProperty(items=_switch_bone_mode_target_items, name="Down", default=4)
    switch_bone_mode_left: bpy.props.EnumProperty(items=_switch_bone_mode_target_items, name="Left", default=1)
    switch_bone_mode_right: bpy.props.EnumProperty(items=_switch_bone_mode_target_items, name="Right", default=2)

    # --- Delete Pie Properties ---
    delete_pie_left: bpy.props.EnumProperty(items=_delete_pie_items, name="Left", default=0)
    delete_pie_right: bpy.props.EnumProperty(items=_delete_pie_items, name="Right", default=2)
    delete_pie_down: bpy.props.EnumProperty(items=_delete_pie_items, name="Down", default=1)
    delete_pie_up: bpy.props.EnumProperty(items=_delete_pie_items, name="Up", default=11)
    delete_pie_top_left: bpy.props.EnumProperty(items=_delete_pie_items, name="Top-Left", default=6)
    delete_pie_top_right: bpy.props.EnumProperty(items=_delete_pie_items, name="Top-Right", default=7)
    delete_pie_bottom_left: bpy.props.EnumProperty(items=_delete_pie_items, name="Bottom-Left", default=8)
    delete_pie_bottom_right: bpy.props.EnumProperty(items=_delete_pie_items, name="Bottom-Right", default=9)
    has_migrated_delete_pie: bpy.props.BoolProperty(default=False, options={'HIDDEN'})


    switch_mode_smart_focus: bpy.props.BoolProperty(
        name="Smart Focus",
        description="If the object cannot switch modes, it will focus on the object",
        default=True
    )

    switch_mode_double_click_edit_switch: bpy.props.BoolProperty(
        name=_T("双击切换编辑对象"),
        description=_T("网格编辑模式下，双击其他物体切换到其编辑模式"),
        default=True,
        update=_on_prefs_update,
    )

    switch_mode_double_click_edge_loop_ring: bpy.props.BoolProperty(
        name=_T("双击边循环选择"),
        description=_T("网格编辑模式下，双击边自动选择循环边(Edge Loop)，Shift 可加选"),
        default=True,
        update=_on_prefs_update,
    )

    switch_mode_tab_behavior: bpy.props.EnumProperty(
        name=_T("Tab 行为"),
        items=_switch_mode_tab_behavior_items,
        default=0,
        update=_on_prefs_update,
    )
    switch_mode_hold_ms: bpy.props.IntProperty(
        name=_T("长按阈值(ms)"),
        default=220,
        min=80,
        max=1000,
        update=_on_prefs_update,
    )

    def draw_switch_mode_basic(self, layout):
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "switch_mode_smart_focus", text=_T("智能聚焦"))
        layout.prop(self, "switch_mode_double_click_edit_switch", text=_T("双击切换编辑对象"))
        sub = layout.column()
        sub.enabled = self.switch_mode_double_click_edit_switch
        sub.prop(self, "switch_mode_double_click_edge_loop_ring", text=_T("双击边循环选择"))
        layout.prop(self, "switch_mode_tab_behavior", text=_T("Tab 行为"))
        sub = layout.column()
        sub.enabled = self.switch_mode_tab_behavior == "TAP_HOLD"
        sub.prop(self, "switch_mode_hold_ms", text=_T("长按阈值(ms)"))

    def draw_switch_mode_mapping(self, layout):
        layout.use_property_split = True
        layout.use_property_decorate = False

        draw_data = {1: "up", 3: "left", 5: "right", 7: "down"}
        box_a = layout.box()
        box_a.label(text=_T("3D 视图"), icon="VIEW3D")
        box_b = layout.box()
        box_b.label(text=_T("骨骼"), icon="ARMATURE_DATA")

        for i in range(3):
            row_a = box_a.row(align=True)
            row_b = box_b.row(align=True)
            for j in range(3):
                index = i * 3 + j
                direction = draw_data.get(index)
                if direction:
                    row_a.prop(self, f"switch_mode_{direction}", text="")
                    row_b.prop(self, f"switch_bone_mode_{direction}", text="")
                else:
                    row_a.label(text="")
                    row_b.label(text="")

    def draw_delete_mapping(self, layout):
        layout.use_property_split = False
        layout.use_property_decorate = False
        
        mapping = {
            0: "delete_pie_top_left", 1: "delete_pie_up", 2: "delete_pie_top_right",
            3: "delete_pie_left",                     5: "delete_pie_right",
            6: "delete_pie_bottom_left", 7: "delete_pie_down", 8: "delete_pie_bottom_right"
        }

        box = layout.box()
        box.label(text=_T("网格编辑模式 (Edit Mesh)"), icon="EDITMODE_HLT")
        grid_col = box.column()

        for i in range(3):
            if i > 0:
                grid_col.separator(factor=4.0)
            
            row = grid_col.row()
            split = row.split(factor=0.2)
            col1 = split.column()
            split = split.split(factor=0.25)
            split.column() # Gap
            split = split.split(factor=0.333)
            col2 = split.column()
            split = split.split(factor=0.5)
            split.column() # Gap
            col3 = split.column()
            
            cols = [col1, col2, col3]
            
            for j in range(3):
                idx = i * 3 + j
                prop_name = mapping.get(idx)
                if prop_name:
                    cols[j].prop(self, prop_name, text="")
                else:
                    cols[j].label(text="")

    def draw_about_settings(self, layout):
        col = layout.column(align=True)
        
        # Logo / Title
        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.scale_y = 1.5
        row.label(text=_T("M8 全能工具箱"), icon=_ICON("TOPBAR"))
        
        col.separator()
        
        # Settings Box (Language & Error Telemetry)
        box = col.box()
        row = box.row(align=True)
        row.alignment = 'CENTER'
        row.label(text=_T("界面语言"), icon=_ICON("WORLD"))
        row.prop(self, "addon_language", expand=True)
        
        row_telemetry = box.row(align=True)
        row_telemetry.alignment = 'CENTER'
        row_telemetry.prop(self, "auto_error_report")
        row_telemetry.prop(self, "auto_check_updates")
        if self.auto_error_report:
            row_telemetry.operator("m8.trigger_test_error", text=_T("测试报错上报"), icon='ERROR')
        
        col.separator()
        
        # Info Grid
        box = col.box()
        grid = box.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True)
        
        grid.label(text=_T("作者:") + " " + _T("猫步可爱"))
        grid.label(text=_T("微信:") + " LiLan-8")
        
        # Version from bl_info
        from ..utils.network import get_addon_version, version_tuple_to_str
        cur_ver = version_tuple_to_str(get_addon_version())
        grid.label(text=_T("版本:") + f" {cur_ver}")
        
        # Draw dynamic update status if checked or checking
        wm = bpy.context.window_manager
        m8 = getattr(wm, "m8", None)
        if m8 and m8.update_status != "idle":
            status_box = col.box()
            status_row = status_box.row(align=True)
            status_row.alignment = 'CENTER'
            if m8.update_status == "checking":
                status_row.label(text=_T("正在检测更新..."), icon="FILE_REFRESH")
            elif m8.update_status == "available":
                status_row.label(text=f"{_T('检测到新版本')}: v{m8.update_version}!", icon="ERROR")
                op_dl = status_row.operator("wm.url_open", text=_T("前往下载"), icon="IMPORT")
                op_dl.url = m8.update_download_url
            elif m8.update_status == "latest":
                status_row.label(text=_T("已经是最新版本"), icon="CHECKMARK")
            elif m8.update_status == "error":
                status_row.label(text=_T("连接失败，请检查网络"), icon="CANCEL")
        
        col.separator()
        
        # Links
        row1 = col.row(align=True)
        row1.scale_y = 1.3
        op = row1.operator("wm.url_open", text=_T("官网社区"), icon="WORLD")
        op.url = "https://mao.591595.xyz/"
        
        op = row1.operator("wm.url_open", text=_T("GitHub 链接"), icon="FILE_SCRIPT")
        op.url = "https://github.com/maobukeai/M8"
        
        row2 = col.row(align=True)
        row2.scale_y = 1.3
        row2.operator("m8.check_update", text=_T("检测更新"), icon="FILE_REFRESH")
        row2.operator("m8.submit_feedback", text=_T("提交反馈"), icon="QUESTION")
        
        col.separator()
        
        # QR Codes
        try:
            from ..src import icons as mp7_icons
            pcoll = mp7_icons.previews_icons
            if pcoll:
                qr_box = col.box()
                row = qr_box.row()
                
                # 左侧：联系二维码
                col1 = row.column(align=True)
                col1.alignment = 'CENTER'
                col1.label(text=_T("联系作者"))
                if "wechat_code" in pcoll:
                    col1.template_icon(icon_value=pcoll["wechat_code"].icon_id, scale=8.0)
                else:
                    col1.label(text=_T("图片未找到"), icon=_ICON("ERROR"))
                    col1.label(text=_T("请放入") + " wechat_code.png")
                
                # 右侧：捐款码
                col2 = row.column(align=True)
                col2.alignment = 'CENTER'
                col2.label(text=_T("赞赏支持"))
                if "donate_code" in pcoll:
                    col2.template_icon(icon_value=pcoll["donate_code"].icon_id, scale=8.0)
                else:
                    col2.label(text=_T("图片未找到"), icon=_ICON("ERROR"))
                    col2.label(text=_T("请放入") + " donate_code.png")
        except Exception:
            pass
            
        col.separator()
        
        # Description
        box = col.box()
        box.label(text=_T("功能简介:"), icon=_ICON("INFO"))
        col_desc = box.column(align=True)
        row = col_desc.row()
        row.label(text=_T("在复杂的 3D 建模项目中，效率就是生命。"), icon=_ICON("FORWARD"))
        row = col_desc.row()
        row.label(text=_T("M8 不仅仅是一个工具箱，它是你工作流中的润滑剂。"), icon=_ICON("FORWARD"))
        
        box.separator()
        
        # Features List
        box.label(text=_T("核心模块:"), icon=_ICON("MODIFIER"))
        
        split = box.split(factor=0.5)
        col1 = split.column(align=True)
        col2 = split.column(align=True)
        
        # Left Column
        col1.label(text=_T("变换辅助 (Shift+S): 原点与游标控制"), icon=_ICON("PIVOT_CURSOR"))
        col1.label(text=_T("模式切换 (Tab): 智能多模式切换"), icon=_ICON("FILE_REFRESH"))
        col1.label(text=_T("智能删除 (X): 智能判断无需确认"), icon=_ICON("TRASH"))
        col1.label(text=_T("对齐工具 (Alt+A): 物体与元素对齐"), icon=_ICON("ALIGN_CENTER"))
        col1.label(text=_T("视图着色 (Z): 快速切换显示模式"), icon=_ICON("SHADING_RENDERED"))
        
        # Right Column
        col2.label(text=_T("保存导出 (Ctrl+S): 自动打包及导出"), icon=_ICON("FILE_TICK"))
        col2.label(text=_T("批量命名 (F2): 变量/正则/预览"), icon=_ICON("FONT_DATA"))
        col2.label(text=_T("智能饼菜单 (1): 点/线/面/清理/路径"), icon=_ICON("VIEW3D"))
        col2.label(text=_T("区域切换 (T): 侧栏及资产浏览器"), icon=_ICON("FULLSCREEN_ENTER"))
        col2.label(text=_T("按键显示: 实时按键操作反馈"), icon=_ICON("WINDOW"))

    def draw(self, context):
        layout = self.layout
        try:
            required = ("active_tab", "navigation_tab", "enable_transform_pie", "activate_switch_mode")
            missing = [k for k in required if k not in self.bl_rna.properties]
        except Exception:
            missing = ["active_tab", "navigation_tab"]
        if missing:
            box = layout.box()
            box.label(text=_T("偏好项未完成注册：请重新启用插件或重启 Blender"), icon=_ICON("ERROR"))
            box.label(text=_T("常见原因：升级后未重启；或 Blender\\4.4/5.0 同时存在多个 M8，实际加载的不是当前文件。"), icon=_ICON("INFO"))
            return
        active_tab = getattr(self, "active_tab", "GENERAL")
        
        row = layout.row(align=True)
        if "active_tab" in self.bl_rna.properties:
            row.prop(self, "active_tab", expand=True)
        layout.separator()

        try:
            if active_tab == "GENERAL":
                self.draw_general(context)
            else:
                self.draw_about_settings(layout)
        except Exception:
            box = layout.box()
            box.label(text=_T("偏好设置界面绘制失败，请打开系统控制台查看报错。"), icon=_ICON("ERROR"))

    def _draw_sidebar_button(self, layout, icon, text, item_value):
        row = layout.row(align=True)
        row.scale_y = 1.25
        
        prop_map = {
            "TRANSFORM": "enable_transform_pie",
            "SWITCH_MODE": "activate_switch_mode",
            "DELETE": "activate_quick_delete",
            "EDGE_PROPERTY": "activate_edge_property_pie",
            "ALIGN": "activate_align_pie",
            "SHADING": "activate_shading_pie",
            "MIRROR": "activate_mirror",
            "GROUP": "activate_group_tool",
            "SAVE": "activate_save_pie",
            "SMART_PIE": "activate_smart_pie",
            "TOGGLE_AREA": "activate_toggle_area",
            "SWITCH_EDITOR": "activate_switch_editor_pie",
            "SUBDIVISION": "activate_subdivision_shortcuts",
            "FAST_LOOP": "activate_fast_loop",
            "RENAME": "activate_advanced_rename",
            "SCREENCAST": "screencast_enabled",
        }
        
        feature_prop_name = prop_map.get(item_value, None)
        nav_tab = getattr(self, "navigation_tab", "TRANSFORM")
        
        if "navigation_tab" in self.bl_rna.properties:
            row_split = row.split(factor=0.75, align=True)
            if feature_prop_name and feature_prop_name in self.bl_rna.properties:
                row_split.prop_enum(self, "navigation_tab", item_value, text=_T(text))
                row_split.prop(self, feature_prop_name, text="", icon=_ICON(icon), toggle=True)
            else:
                row_split.prop_enum(self, "navigation_tab", item_value, text=_T(text))
                row_split.prop_enum(self, "navigation_tab", item_value, text="", icon=_ICON(icon))
        else:
            row.label(text=_T(text), icon=_ICON(icon))

    def _get_tab_description(self, key=None):
        key = key or getattr(self, "navigation_tab", "TRANSFORM")
        desc = {
            "TRANSFORM": (_T("变换辅助"), _T("Shift+S 增强版，包含原点调整、游标控制及变换操作")),
            "SWITCH_MODE": (_T("模式切换"), _T("Tab 智能切换，支持物体、编辑、骨骼及UV模式的快速切换")),
            "DELETE": (_T("智能删除"), _T("X/Del 键增强，根据选区智能判断删除元素，无需弹窗确认")),
            "EDGE_PROPERTY": (_T("边属性"), _T("Shift+E 增强，支持快速设置 Crease, Bevel Weight, Seam, Sharp 等")),
            "ALIGN": (_T("对齐工具"), _T("Alt+A 增强版，提供物体、网格、UV的对齐与分布功能")),
            "SHADING": (_T("视图着色"), _T("Z 键增强，快速切换透视、线框、实体及渲染预览模式")),
            "SAVE": (_T("保存导出"), _T("Ctrl+S 增强，支持自动打包资源、清理材质及 Unity FBX 导出预设")),
            "RENAME": (_T("批量命名"), _T("F2 增强，支持变量($N $T)、正则替换、序号生成及预览")),
            "MIRROR": (_T("镜像工具"), _T("Shift+Alt+X，提供直观的轴向滑动选择镜像功能")),
            "SMART_PIE": (_T("智能饼菜单"), _T("编辑模式下 1/2/3 的智能建模操作合集（顶点/边/面/清理/路径等）")),
            "TOGGLE_AREA": (_T("区域切换"), _T("T 键切换 Toolbar/Sidebar 及 Asset Browser/Shelf")),
            "SWITCH_EDITOR": (_T("切换窗口"), _T("配置 F12 切换窗口饼菜单映射")),
            "SUBDIVISION": (_T("细分级别"), _T("物体模式下 Ctrl+1/2/3/4 设置细分级别，Ctrl+0 清零细分级别")),
            "FAST_LOOP": (_T("快速循环切刀"), _T("编辑模式下 Ctrl+Shift+E 交互式添加循环边或顶点，支持吸附、等距、对称、法向等高级控制")),

            "SCREENCAST": (_T("按键显示"), _T("实时在视口显示键盘鼠标操作，支持自定义外观")),
            "OTHER": (_T("系统设置"), _T("包含备份设置、新建物体默认行为等全局选项")),
            "ABOUT": (_T("关于"), _T("关于 M8 工具箱")),
        }
        return desc.get(key, ("", ""))

    def draw_general(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        icon_map = {
            "TRANSFORM": "PIVOT_CURSOR",
            "SWITCH_MODE": "FILE_REFRESH",
            "DELETE": "TRASH",
            "EDGE_PROPERTY": "EDGESEL",
            "ALIGN": "ALIGN_CENTER",
            "SHADING": "SHADING_RENDERED",
            "SAVE": "FILE_TICK",
            "RENAME": "FONT_DATA",
            "MIRROR": "MOD_MIRROR",
            "GROUP": "EMPTY_AXIS",
            "SMART_PIE": "VIEW3D",
            "TOGGLE_AREA": "FULLSCREEN_ENTER",
            "SWITCH_EDITOR": "WINDOW",
            "SUBDIVISION": "MOD_SUBSURF",
            "FAST_LOOP": "EDGESEL",

            "SCREENCAST": "WINDOW",
            "OTHER": "PREFERENCES",
            "ABOUT": "INFO",
        }

        split = layout.split(factor=0.12)

        col = split.column(align=True)
        col.use_property_split = False
        nav_box = col.box()
        nav_box.use_property_split = False
        col_nav = nav_box.column(align=True)
        col_nav.use_property_split = False

        col_nav.label(text=_T("核心功能"), icon="MODIFIER")
        self._draw_sidebar_button(col_nav, "PIVOT_CURSOR", _T("变换辅助 (Shift+S)"), "TRANSFORM")
        self._draw_sidebar_button(col_nav, "FILE_REFRESH", _T("模式切换 (Tab)"), "SWITCH_MODE")
        self._draw_sidebar_button(col_nav, "TRASH", _T("删除 (X)"), "DELETE")
        self._draw_sidebar_button(col_nav, "EDGESEL", _T("边属性 (Shift+E)"), "EDGE_PROPERTY")
        self._draw_sidebar_button(col_nav, "ALIGN_CENTER", _T("对齐 (Alt+A)"), "ALIGN")
        self._draw_sidebar_button(col_nav, "SHADING_RENDERED", _T("着色 (Z)"), "SHADING")
        self._draw_sidebar_button(col_nav, "MOD_MIRROR", _T("镜像 (Shift+Alt+X)"), "MIRROR")
        self._draw_sidebar_button(col_nav, "EMPTY_AXIS", _T("打组 (Ctrl+G)"), "GROUP")
        self._draw_sidebar_button(col_nav, "FILE_TICK", _T("保存 (Ctrl+S)"), "SAVE")
        self._draw_sidebar_button(col_nav, "VIEW3D", _T("智能饼菜单 (1)"), "SMART_PIE")
        self._draw_sidebar_button(col_nav, "FULLSCREEN_ENTER", _T("区域切换 (T)"), "TOGGLE_AREA")
        self._draw_sidebar_button(col_nav, "WINDOW", _T("切换窗口 (F12)"), "SWITCH_EDITOR")
        self._draw_sidebar_button(col_nav, "MOD_SUBSURF", _T("细分级别 (Ctrl+0..4)"), "SUBDIVISION")
        self._draw_sidebar_button(col_nav, "EDGESEL", _T("快速循环切刀 (Ctrl+Shift+E)"), "FAST_LOOP")

        col_nav.separator()
        col_nav.label(text=_T("实用工具"), icon="TOOL_SETTINGS")
        self._draw_sidebar_button(col_nav, "FONT_DATA", _T("重命名 (F2)"), "RENAME")
        self._draw_sidebar_button(col_nav, "WINDOW", _T("按键显示"), "SCREENCAST")

        col_nav.separator()
        col_nav.label(text=_T("设置"), icon="PREFERENCES")
        self._draw_sidebar_button(col_nav, "PREFERENCES", _T("其它设置"), "OTHER")
        self._draw_sidebar_button(col_nav, "INFO", _T("关于"), "ABOUT")
        col_nav.separator()
        if "ui_show_all_settings" in self.bl_rna.properties:
            row = col_nav.row(align=True)
            row.scale_y = 1.25
            row_split = row.split(factor=0.75, align=True)
            row_split.prop(self, "ui_show_all_settings", text=_T("显示全部"), toggle=True)
            row_split.prop(self, "ui_show_all_settings", text="", toggle=True, icon=_ICON("ALIGN_JUSTIFY"))

        col = split.column()

        header_box = col.box()
        header_row = header_box.row(align=True)
        header_row.alignment = "LEFT"
        
        show_all = getattr(self, "ui_show_all_settings", False)
        nav_tab = getattr(self, "navigation_tab", "TRANSFORM")
        
        if show_all:
            header_row.label(text=_T("全部设置"), icon="PREFERENCES")
        else:
            title, desc = self._get_tab_description(nav_tab)
            header_row.label(text=title, icon=_ICON(icon_map.get(nav_tab, "INFO")))
        if "ui_show_all_settings" in self.bl_rna.properties:
            header_row.prop(self, "ui_show_all_settings", text=_T("显示全部"), toggle=True, icon=_ICON("ALIGN_JUSTIFY"))

        desc_row = header_box.row(align=True)
        desc_row.alignment = "LEFT"
        if show_all:
            desc_row.label(text=_T("按模块分区显示全部偏好设置"))
        else:
            desc_row.label(text=desc)

        col.separator()

        if show_all:
            ordered = [
                "TRANSFORM",
                "SWITCH_MODE",
                "DELETE",
                "EDGE_PROPERTY",
                "ALIGN",
                "SHADING",
                "SAVE",
                "RENAME",
                "MIRROR",
                "GROUP",
                "SMART_PIE",
                "TOGGLE_AREA",
                "SWITCH_EDITOR",
                "SUBDIVISION",
                "FAST_LOOP",
                "SCREENCAST",
                "OTHER",
                "ABOUT",
            ]
            for key in ordered:
                section = col.box()
                row = section.row(align=True)
                row.prop_enum(self, "navigation_tab", key, text=self._get_tab_description(key)[0], icon=_ICON(icon_map.get(key, "DOT")))
                sub = section.column()
                if key == "TRANSFORM":
                    self.draw_transform_settings(sub)
                elif key == "SWITCH_MODE":
                    self.draw_switch_mode_settings(sub)
                elif key == "DELETE":
                    self.draw_delete_settings(sub)
                elif key == "EDGE_PROPERTY":
                    self.draw_edge_property_settings(sub)
                elif key == "ALIGN":
                    self.draw_align_settings(sub)
                elif key == "SHADING":
                    self.draw_shading_settings(sub)
                elif key == "SAVE":
                    self.draw_save_settings(sub)
                elif key == "RENAME":
                    self.draw_rename_settings(sub)
                elif key == "MIRROR":
                    self.draw_mirror_settings(sub)
                elif key == "GROUP":
                    self.draw_group_settings(sub)
                elif key == "SMART_PIE":
                    self.draw_smart_pie_settings(sub)
                elif key == "TOGGLE_AREA":
                    self.draw_toggle_area_settings(sub)
                elif key == "SWITCH_EDITOR":
                    self.draw_switch_editor_settings(sub)
                elif key == "SUBDIVISION":
                    self.draw_subdivision_settings(sub)
                elif key == "FAST_LOOP":
                    self.draw_fast_loop_settings(sub)
                elif key == "SCREENCAST":
                    self.draw_screencast_settings(sub)
                elif key == "OTHER":
                    self.draw_other_settings(sub)
                elif key == "ABOUT":
                    self.draw_about_settings(sub)
        else:
            box = col.box()
            if nav_tab == "TRANSFORM":
                self.draw_transform_settings(box)
            elif nav_tab == "SWITCH_MODE":
                self.draw_switch_mode_settings(box)
            elif nav_tab == "DELETE":
                self.draw_delete_settings(box)
            elif nav_tab == "EDGE_PROPERTY":
                self.draw_edge_property_settings(box)
            elif nav_tab == "ALIGN":
                self.draw_align_settings(box)
            elif nav_tab == "SHADING":
                self.draw_shading_settings(box)
            elif nav_tab == "SAVE":
                self.draw_save_settings(box)
            elif nav_tab == "RENAME":
                self.draw_rename_settings(box)
            elif nav_tab == "MIRROR":
                self.draw_mirror_settings(box)
            elif nav_tab == "GROUP":
                self.draw_group_settings(box)
            elif nav_tab == "SMART_PIE":
                self.draw_smart_pie_settings(box)
            elif nav_tab == "TOGGLE_AREA":
                self.draw_toggle_area_settings(box)
            elif nav_tab == "SWITCH_EDITOR":
                self.draw_switch_editor_settings(box)
            elif nav_tab == "SUBDIVISION":
                self.draw_subdivision_settings(box)
            elif nav_tab == "FAST_LOOP":
                self.draw_fast_loop_settings(box)
            elif nav_tab == "SCREENCAST":
                self.draw_screencast_settings(box)
            elif nav_tab == "OTHER":
                self.draw_other_settings(box)
            elif nav_tab == "ABOUT":
                self.draw_about_settings(box)

    
    def draw_switch_editor_settings(self, layout):
        col = layout.column()
        if "activate_switch_editor_pie" in self.bl_rna.properties:
            col.prop(self, "activate_switch_editor_pie", text=_T("启用切换窗口饼菜单(F12)"))
        
        if getattr(self, "activate_switch_editor_pie", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_switch_editor_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_editor_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_switch_editor_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_editor_advanced", text=_T("映射"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_switch_editor_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            
            if getattr(self, "ui_show_switch_editor_keymap", False):
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    items = _find_switch_editor_pie_keymap_items()
                    if not items:
                        sub_col.label(text=_T("未找到 F12 绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in items:
                            row = sub_col.row(align=True)
                            row.label(text=km.name, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass

            if getattr(self, "ui_show_switch_editor_advanced", False):
                box = col.box()
                box.label(text=_T("映射"), icon="KEYINGSET")
                
                grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
                
                col1 = grid.column()
                col1.prop(self, "switch_editor_pie_left")
                col1.prop(self, "switch_editor_pie_right")
                col1.prop(self, "switch_editor_pie_bottom")
                col1.prop(self, "switch_editor_pie_top")
                
                col2 = grid.column()
                col2.prop(self, "switch_editor_pie_top_left")
                col2.prop(self, "switch_editor_pie_top_right")
                col2.prop(self, "switch_editor_pie_bottom_left")
                col2.prop(self, "switch_editor_pie_bottom_right")
    
    def draw_subdivision_settings(self, layout):
        col = layout.column()
        if "activate_subdivision_shortcuts" in self.bl_rna.properties:
            col.prop(self, "activate_subdivision_shortcuts")

        activate_shortcuts = getattr(self, "activate_subdivision_shortcuts", False)
        
        if activate_shortcuts:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.operator("size_tool.force_subdivision_priority", text=_T("置顶"), icon="SORT_ASC")
            if "ui_show_subdivision_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_subdivision_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_subdivision_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_subdivision_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            
            if getattr(self, "ui_show_subdivision_advanced", False):
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_subdivision_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_subdivision_conflicts", text=_T("恢复冲突"))

            show_keymap = getattr(self, "ui_show_subdivision_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    subdiv_items = _find_subdivision_keymap_items()
                    
                    if not subdiv_items:
                        sub_col.label(text=_T("未找到细分级别绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in subdiv_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass

    def draw_fast_loop_settings(self, layout):
        col = layout.column()
        if "activate_fast_loop" in self.bl_rna.properties:
            col.prop(self, "activate_fast_loop")

        activate_fl = getattr(self, "activate_fast_loop", False)
        
        if activate_fl:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_fast_loop_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_fast_loop_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()

            box = col.box()
            box.label(text=_T("默认启动属性 (Default Launch Settings)"), icon="TOOL_SETTINGS")
            
            flow = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=False, align=True)
            flow.prop(self, "fast_loop_segments")
            flow.prop(self, "fast_loop_snap_divisions")
            flow.prop(self, "fast_loop_vertex_mode")
            flow.prop(self, "fast_loop_guide_mode")
            flow.prop(self, "fast_loop_use_even")
            flow.prop(self, "fast_loop_flipped")
            flow.prop(self, "fast_loop_mirrored")
            flow.prop(self, "fast_loop_perpendicular")
            flow.prop(self, "fast_loop_use_curvature")
            flow.prop(self, "fast_loop_enable_edge_flow")
            flow.prop(self, "fast_loop_reproject_uv_after_edge_flow")

            # EdgeFlow params sub-box
            ef_box = box.box()
            ef_col = ef_box.column(align=True)
            ef_col.label(text="EdgeFlow 参数 (Shift+左键 / EdgeFlow 开启时生效)", icon="MOD_SMOOTH")
            ef_row = ef_col.row(align=True)
            ef_row.prop(self, "fast_loop_tension")
            ef_row.prop(self, "fast_loop_iterations")
            ef_row.prop(self, "fast_loop_min_angle")

            col.separator(factor=0.5)

            # Persistent behavior settings (saved immediately on toggle, remembered across sessions)
            box2 = col.box()
            box2.label(text=_T("持久行为设置 (Persistent Behavior)"), icon="LOCKED")
            row2 = box2.row(align=True)
            row2.prop(self, "fast_loop_keep_selection", toggle=True, icon="RESTRICT_SELECT_OFF")

            show_keymap = getattr(self, "ui_show_fast_loop_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    fl_items = _find_fast_loop_keymap_items()
                    
                    if not fl_items:
                        sub_col.label(text=_T("未找到快速循环切刀绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in fl_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass

    def draw_switch_mode_settings(self, layout):
        col = layout.column()
        if "activate_switch_mode" in self.bl_rna.properties:
            col.prop(self, "activate_switch_mode", text=_T("启用模式切换(Tab)"))

        if getattr(self, "activate_switch_mode", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_tab_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_tab_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_switch_mode_mapping" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_mode_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_switch_mode_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_switch_mode_prefs", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            self.draw_switch_mode_basic(col)

            if getattr(self, "ui_show_tab_keymap", False):
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    items = _find_switch_mode_keymap_items()
                    if not items:
                        sub_col.label(text=_T("未找到 Tab 绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in items:
                            row = sub_col.row(align=True)
                            row.label(text=km.name, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass

            if getattr(self, "ui_show_switch_mode_mapping", False):
                self.draw_switch_mode_mapping(col)

    def draw_transform_settings(self, layout):
        col = layout.column()
        
        if "enable_transform_pie" in self.bl_rna.properties:
            col.prop(self, "enable_transform_pie", text=_T("启用变换辅助饼菜单"))

        enable_pie = getattr(self, "enable_transform_pie", False)
        
        if enable_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_shift_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shift_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_shift_s_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_shift_s_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_transform_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("size_tool.reset_transform_pie_keymap", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            
            show_keymap = getattr(self, "ui_show_shift_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    kc, km, kmi = _find_pie_keymap_item()
                    if kc and km and kmi:
                        rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                    else:
                        sub_col.label(text=_T("未找到 Shift+S 绑定"), icon="INFO")
                except Exception:
                    pass

            show_advanced = getattr(self, "ui_show_shift_s_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_transform_pie_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_shift_s_conflicts", text=_T("恢复冲突"))
                if "auto_exclusive_shift_s_on_startup" in self.bl_rna.properties:
                    sub_col.prop(self, "auto_exclusive_shift_s_on_startup", text=_T("启动时自动独占所有快捷键"))
                if "auto_exclusive_shift_s_include_user" in self.bl_rna.properties:
                    sub_col.prop(self, "auto_exclusive_shift_s_include_user", text=_T("同时处理用户键位冲突"))

    def draw_delete_settings(self, layout):
        col = layout.column()
        col.prop(self, "activate_quick_delete", text=_T("快速删除 (Object)"))
        col.prop(self, "activate_delete_pie", text=_T("饼菜单 (Edit)"))

        if self.activate_quick_delete or self.activate_delete_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_delete_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.prop(self, "ui_show_delete_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_delete_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            if self.ui_show_delete_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    quick_items = _find_quick_delete_keymap_items()
                    pie_items = _find_delete_pie_keymap_items()
                    
                    if not quick_items and not pie_items:
                        sub_col.label(text=_T("未找到删除相关绑定"), icon="INFO")
                    
                    if quick_items:
                        sub_col.label(text=_T("快速删除 (Object):"))
                        for kc, km, kmi in quick_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                            
                    if pie_items:
                        sub_col.label(text=_T("饼菜单 (Edit Mesh):"))
                        for kc, km, kmi in pie_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)

                except Exception:
                    pass

            if self.ui_show_delete_mapping and self.activate_delete_pie:
                self.draw_delete_mapping(col)

    def draw_edge_property_settings(self, layout):
        col = layout.column()
        if "activate_edge_property_pie" in self.bl_rna.properties:
            col.prop(self, "activate_edge_property_pie", text=_T("启用 Shift+E"))

        activate_pie = getattr(self, "activate_edge_property_pie", False)
        
        if activate_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_edge_property_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_edge_property_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_edge_property_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_edge_property_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_edge_property_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            show_keymap = getattr(self, "ui_show_edge_property_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    items = _find_edge_property_pie_keymap_items()
                    
                    if not items:
                        sub_col.label(text=_T("未找到 Edge Property 绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in items:
                            row_km = sub_col.row(align=True)
                            row_km.label(text=km.name, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row_km, 0)
                except Exception:
                    pass

            show_advanced = getattr(self, "ui_show_edge_property_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_edge_property_pie_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_shift_e_conflicts", text=_T("恢复冲突"))

    def draw_align_settings(self, layout):
        col = layout.column()
        if "activate_align_pie" in self.bl_rna.properties:
            col.prop(self, "activate_align_pie")

        activate_pie = getattr(self, "activate_align_pie", False)
        
        if activate_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_align_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_align_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_align_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_align_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_align_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            show_keymap = getattr(self, "ui_show_align_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    align_items = _find_align_pie_keymap_items()
                    
                    if not align_items:
                        sub_col.label(text=_T("未找到对齐相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in align_items:
                            row_km = sub_col.row(align=True)
                            mode_label = km.name
                            if mode_label == "3D View Generic": mode_label = _T("3D 视图通用")
                            elif mode_label == "Object Mode": mode_label = _T("物体模式")
                            elif mode_label == "Mesh": mode_label = _T("网格编辑")
                            elif mode_label == "UV Editor": mode_label = _T("UV 编辑器")
                            
                            row_km.label(text=mode_label, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row_km, 0)
                except Exception:
                    pass
            
            show_advanced = getattr(self, "ui_show_align_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_align_pie_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_alt_a_conflicts", text=_T("恢复冲突"))

    def draw_shading_settings(self, layout):
        col = layout.column()
        if "activate_shading_pie" in self.bl_rna.properties:
            col.prop(self, "activate_shading_pie")

        activate_pie = getattr(self, "activate_shading_pie", False)
        
        if activate_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_shading_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shading_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_shading_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_shading_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_shading_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            if getattr(self, "ui_show_shading_advanced", False):
                sub_col = col.column()
                sub_col.label(text=_T("该模块暂无内置的快捷键冲突配置"), icon="INFO")
            show_keymap = getattr(self, "ui_show_shading_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    shading_items = _find_shading_pie_keymap_items()
                    
                    if not shading_items:
                        sub_col.label(text=_T("未找到着色相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in shading_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass

    def draw_save_settings(self, layout):
        col = layout.column()
        if "activate_save_pie" in self.bl_rna.properties:
            col.prop(self, "activate_save_pie", text=_T("启用保存饼菜单 (Ctrl+S)"))

        activate_pie = getattr(self, "activate_save_pie", False)

        box_auto = col.box()
        box_auto.label(text=_T("常规自动化"), icon="FILE_BLEND")
        if "auto_pack_resources_on_save" in self.bl_rna.properties:
            box_auto.prop(self, "auto_pack_resources_on_save", text=_T("保存时自动打包资源"))
        if "auto_purge_unused_materials_on_save" in self.bl_rna.properties:
            box_auto.prop(self, "auto_purge_unused_materials_on_save", text=_T("保存时自动清除孤立数据"))
        if "incremental_save_prefix" in self.bl_rna.properties:
            row = box_auto.row(align=True)
            row.use_property_split = True
            row.use_property_decorate = False
            row.prop(self, "incremental_save_prefix", text=_T("增量保存版本前缀"))
        
        if activate_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_save_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_save_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_save_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_save_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_save_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            
            box_fbx = col.box()
            box_fbx.label(text=_T("FBX 导出预设"), icon="EXPORT")
            if "fbx_export_unity_preset" in self.bl_rna.properties:
                box_fbx.prop(self, "fbx_export_unity_preset", text=_T("启用 Unity 标准预设"))
            
            fbx_preset = getattr(self, "fbx_export_unity_preset", False)
            
            sub = box_fbx.column()
            sub.enabled = bool(fbx_preset)
            sub.operator("m8.reset_unity_fbx_preset", text=_T("重置为 Unity 推荐设置"), icon="FILE_REFRESH")
            if "unity_fbx_use_blend_dir" in self.bl_rna.properties:
                sub.prop(self, "unity_fbx_use_blend_dir", text=_T("使用 .blend 同目录"))
            row = sub.row(align=True)
            row.enabled = not bool(self.unity_fbx_use_blend_dir)
            row.prop(self, "unity_fbx_export_dir", text=_T("导出目录"))
            sub.prop(self, "unity_fbx_reveal_after_export", text=_T("导出后定位文件"))
            
            sub.prop(self, "ui_show_unity_fbx_advanced", text=_T("展开高级选项"), toggle=True, icon="PREFERENCES")
            if self.ui_show_unity_fbx_advanced:
                adv_box = sub.box()
                adv_box.prop(self, "unity_fbx_use_selection", text=_T("仅导出选择"))
                adv_box.prop(self, "unity_fbx_global_scale", text=_T("全局缩放"))
                adv_box.prop(self, "unity_fbx_apply_unit_scale", text=_T("应用单位"))
                adv_box.prop(self, "unity_fbx_apply_scale_options", text=_T("应用缩放方式"))
                adv_box.prop(self, "unity_fbx_use_triangles", text=_T("三角化"))
                adv_box.prop(self, "unity_fbx_use_tspace", text=_T("导出切线"))
                adv_box.prop(self, "unity_fbx_bake_anim", text=_T("导出动画"))
                adv_box.prop(self, "unity_fbx_open_folder_after_export", text=_T("导出后打开文件夹"))

            if self.ui_show_save_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    save_items = _find_save_pie_keymap_items()
                    
                    if not save_items:
                        sub_col.label(text=_T("未找到保存相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in save_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass

            if self.ui_show_save_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_save_pie_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_ctrl_s_conflicts", text=_T("恢复冲突"))

    def draw_rename_settings(self, layout):
        col = layout.column()
        col.prop(self, "activate_advanced_rename", text=_T("启用高级重命名 (F2)"))

        if getattr(self, "activate_advanced_rename", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_rename_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_rename_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.operator("size_tool.force_rename_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()

            if getattr(self, "ui_show_rename_keymap", False):
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    rename_items = _find_rename_keymap_items()
                    
                    if not rename_items:
                        sub_col.label(text=_T("未找到重命名相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in rename_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass

    def draw_mirror_settings(self, layout):
        col = layout.column()
        if "activate_mirror" in self.bl_rna.properties:
            col.prop(self, "activate_mirror", text=_T("启用镜像 (Shift+Alt+X)"))

        activate_mirror = getattr(self, "activate_mirror", False)
        
        if activate_mirror:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_mirror_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_mirror_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_mirror_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_mirror_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_mirror_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            box = col.box()
            box.label(text=_T("外观设置:"), icon="BRUSH_DATA")
            row = box.row()
            if "hub_scale" in self.bl_rna.properties:
                row.prop(self, "hub_scale", text=_T("Gizmo 缩放"))
            
            row = box.row()
            if "hub_3d_color" in self.bl_rna.properties:
                row.prop(self, "hub_3d_color", text=_T("轴向颜色"))
            if "hub_area_color" in self.bl_rna.properties:
                row.prop(self, "hub_area_color", text=_T("区域颜色"))
            if "hub_text_color" in self.bl_rna.properties:
                row.prop(self, "hub_text_color", text=_T("文本颜色"))
            
            row = box.row()
            if "hub_line_width" in self.bl_rna.properties:
                row.prop(self, "hub_line_width", text=_T("线宽"))
            if "hub_matrix_line_width" in self.bl_rna.properties:
                row.prop(self, "hub_matrix_line_width", text=_T("轴线宽"))

            box.label(text=_T("预览设置:"), icon="SHADING_WIREFRAME")
            row = box.row()
            row.prop(self, "mirror_show_preview", text=_T("显示网格预览"))
            
            if self.mirror_show_preview:
                row = box.row()
                row.prop(self, "mirror_preview_vert_size", text=_T("预览点大小"))
                row.prop(self, "mirror_preview_edge_width", text=_T("预览线宽"))
                row = box.row()
                row.prop(self, "mirror_preview_edge_color", text=_T("预览线颜色"))
                row.prop(self, "mirror_preview_alpha", text=_T("预览透明度"))
                row = box.row()
                row.prop(self, "mirror_preview_max_edge_count", text=_T("最大边数优化"))
                row.prop(self, "mirror_preview_optimize", text=_T("强制简化预览"))
            
            row = box.row()
            row.prop(self, "mirror_use_mouse_pos", text=_T("Gizmo 跟随鼠标"))
            row.prop(self, "mirror_auto_confirm", text=_T("松开即确认"))
            
            row = box.row()
            row.prop(self, "mirror_sensitivity", text=_T("感应灵敏度"))
            
            row = box.row()
            row.prop(self, "mirror_use_fixed_scale", text=_T("使用固定大小"))
            sub = row.row()
            sub.enabled = self.mirror_use_fixed_scale
            sub.prop(self, "mirror_fixed_scale_value", text=_T("固定大小值"))

            if self.ui_show_mirror_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    mirror_items = _find_mirror_keymap_items()
                    
                    if not mirror_items:
                        sub_col.label(text=_T("未找到镜像相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in mirror_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass
            
            if self.ui_show_mirror_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_mirror_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_shift_alt_x_conflicts", text=_T("恢复冲突"))

    def draw_group_settings(self, layout):
        col = layout.column()
        if "activate_group_tool" in self.bl_rna.properties:
            col.prop(self, "activate_group_tool", text=_T("启用打组 (Ctrl+G)"))

        if getattr(self, "activate_group_tool", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_group_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_group_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_group_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_group_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_group_tool_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            box_group = col.box()
            box_group.label(text=_T("工具设置"), icon="TOOL_SETTINGS")
            box_group.prop(self, "activate_double_click_select_group", text=_T("双击选择组"))
            box_group.prop(self, "group_tool_radius", text=_T("组半径"))
            box_group.prop(self, "group_tool_empty_type", text=_T("空物体类型"))
            box_group.prop(self, "group_tool_hide_empty", text=_T("隐藏组空物体"))

            if getattr(self, "ui_show_group_keymap", False):
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    group_items = _find_group_tool_keymap_items()
                    double_click_items = _find_double_click_select_group_keymap_items()
                    
                    if not group_items and not double_click_items:
                        sub_col.label(text=_T("未找到打组相关绑定"), icon="INFO")
                    
                    if group_items:
                        sub_col.label(text=_T("打组 (Ctrl+G):"))
                        for kc, km, kmi in group_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                    
                    if double_click_items:
                        sub_col.label(text=_T("双击选择组:"))
                        for kc, km, kmi in double_click_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass
            
            if getattr(self, "ui_show_group_advanced", False):
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_group_tool_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_ctrl_g_conflicts", text=_T("恢复冲突"))

    def draw_smart_pie_settings(self, layout):
        col = layout.column()
        col.prop(self, "activate_smart_pie", text=_T("启用智能饼菜单 (1)"))
        
        if self.activate_smart_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_smart_pie_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_smart_pie_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_smart_pie_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_smart_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            if getattr(self, "ui_show_smart_pie_advanced", False):
                sub_col = col.column()
                sub_col.label(text=_T("该模块暂无内置的快捷键冲突配置"), icon="INFO")

        sub = col.column()
        sub.enabled = bool(self.activate_smart_pie)
        sub.prop(self, "smart_edge_mode", text=_T("Smart Edge 模式"))
        sub.prop(self, "smart_face_action", text=_T("Smart Face 默认动作"))
        sub.prop(self, "smart_face_focus_mode", text=_T("Smart Face: 聚焦模式"))
        sub.prop(self, "smart_face_stay_on_original", text=_T("Smart Face: 停留在原始对象"))

        box = sub.box()
        box.label(text=_T("清理默认设置"), icon="BRUSH_DATA")
        
        row = box.row()
        row.prop(self, "clean_up_affect", text=_T("影响范围"))
        row.prop(self, "clean_up_merge_distance", text=_T("合并距离"))
        
        box.separator()
        
        split = box.split(factor=0.55)
        
        # Left Column
        col = split.column(align=True)
        col.label(text=_T("优化处理:"))
        col.prop(self, "clean_up_do_merge_by_distance", text=_T("合并重复点"))
        
        row = col.row(align=True)
        row.prop(self, "clean_up_do_dissolve_degenerate", text=_T("溶解退化几何"))
        sub_row = row.row()
        sub_row.enabled = self.clean_up_do_dissolve_degenerate
        sub_row.prop(self, "clean_up_degenerate_dist", text="")
        
        row = col.row(align=True)
        row.prop(self, "clean_up_do_limited_dissolve", text=_T("有限溶解"))
        sub_row = row.row()
        sub_row.enabled = self.clean_up_do_limited_dissolve
        sub_row.prop(self, "clean_up_limited_dissolve_angle", text="")
        
        row = col.row(align=True)
        row.prop(self, "clean_up_do_make_planar", text=_T("平坦化面"))
        sub_row = row.row()
        sub_row.enabled = self.clean_up_do_make_planar
        sub_row.prop(self, "clean_up_planar_iterations", text="")

        # Right Column
        col = split.column(align=True)
        col.label(text=_T("清理选项:"))
        col.prop(self, "clean_up_do_delete_loose_verts", text=_T("删除孤立点"))
        col.prop(self, "clean_up_do_delete_loose_edges", text=_T("删除孤立边"))
        col.prop(self, "clean_up_do_delete_interior_faces", text=_T("删除内部面"))
        col.separator()
        col.prop(self, "clean_up_recalc_normals", toggle=True, text=_T("重算法线"))

        if self.ui_show_smart_pie_keymap:
            try:
                import rna_keymap_ui
                items = _find_smart_pie_keymap_items()
                if not items:
                    sub.label(text=_T("未找到智能饼菜单相关绑定"), icon="INFO")
                else:
                    for kc, km, kmi in items:
                        rna_keymap_ui.draw_kmi([], kc, km, kmi, sub, 0)
            except Exception:
                pass
        
    def draw_toggle_area_settings(self, layout):
        col = layout.column()
        col.prop(self, "activate_toggle_area", text=_T("启用区域切换 (T)"))
        
        if self.activate_toggle_area:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_toggle_area_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_toggle_area_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_toggle_area_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_toggle_area_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            if getattr(self, "ui_show_toggle_area_advanced", False):
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_toggle_area_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_toggle_area_conflicts", text=_T("恢复冲突"))
            box_toggle = col.box()

            box_toggle.label(text=_T("交互逻辑"), icon="MOUSE_LMB")
            box_toggle.prop(self, "toggle_area_close_range", text=_T("关闭范围 (%)"))
            box_toggle.prop(self, "toggle_area_prefer_left_right", text=_T("首选左/右切换"))
            box_toggle.prop(self, "toggle_area_wrap_mouse", text=_T("鼠标跟随"))
            
            box = col.box()
            box.label(text=_T("资产浏览器/资产架 (3D 视图)"), icon="ASSET_MANAGER")
            box.prop(self, "toggle_area_asset_shelf", text=_T("切换资产架"))
            box.prop(self, "toggle_area_asset_browser_top", text=_T("切换资产浏览器到顶部"))
            box.prop(self, "toggle_area_asset_browser_bottom", text=_T("切换资产浏览器到底部"))
            box.prop(self, "toggle_area_split_factor", text=_T("分割比例"))

            if self.ui_show_toggle_area_keymap:
                try:
                    import rna_keymap_ui
                    
                    def _find_toggle_area_keymap_items_local():
                        wm = bpy.context.window_manager if bpy.context else None
                        kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
                        if not kc: return []
                        items = []
                        for keymap_name, _ in TOGGLE_AREA_KEYMAP_BINDINGS:
                            km = kc.keymaps.get(keymap_name)
                            if km:
                                for kmi in km.keymap_items:
                                    if kmi.idname == TOGGLE_AREA_OP_ID:
                                        items.append((kc, km, kmi))
                        return items

                    items = _find_toggle_area_keymap_items_local()
                    if not items:
                        col.label(text=_T("未找到相关绑定"), icon="INFO")
                    else:
                        sub = col.column()
                        for kc, km, kmi in items:
                            row = sub.row(align=True)
                            row.label(text=km.name, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass

    def draw_screencast_settings(self, layout):
        col = layout.column()
        col.prop(self, "screencast_enabled", text=_T("启用 Screencast (按键显示)"))
        
        col = col.column()
        col.enabled = self.screencast_enabled
        
        # 1. 显示元素 (Display Elements)
        box = col.box()
        box.label(text=_T("显示内容 (Display Elements)"), icon=_ICON("MOUSE_MOVE"))
        box.prop(self, "screencast_mouse_display", text=_T("鼠标显示方式"))
        if self.screencast_mouse_display != 'NONE':
            box.prop(self, "screencast_mouse_size", text=_T("鼠标图标大小"))
        box.prop(self, "screencast_show_last_operator", text=_T("显示最后操作名称"))
        if self.screencast_show_last_operator:
            box.prop(self, "screencast_operator_label_mode", text=_T("操作语言"))

        # 2. 位置与对齐 (Position & Alignment)
        box = col.box()
        box.label(text=_T("位置与对齐 (Position)"), icon=_ICON("RESTRICT_VIEW_OFF"))
        box.prop(self, "screencast_align", text=_T("对齐位置"))
        box.prop(self, "screencast_stack_direction", text=_T("堆叠方向"))
        box.prop(self, "screencast_layout_mode", text=_T("排版模式"))
        row = box.row(align=True)
        row.prop(self, "screencast_offset_x", text=_T("X 偏移"))
        row.prop(self, "screencast_offset_y", text=_T("Y 偏移"))

        # 3. 字体与阴影 (Font & Shadow)
        box = col.box()
        box.label(text=_T("字体与阴影 (Font & Shadow)"), icon=_ICON("FONT_DATA"))
        box.prop(self, "screencast_font_size", text=_T("字体大小"))
        box.prop(self, "screencast_color", text=_T("文字颜色"))
        box.prop(self, "screencast_show_shadow", text=_T("启用阴影"))
        if self.screencast_show_shadow:
            box.prop(self, "screencast_shadow_color", text=_T("阴影颜色"))
        box.prop(self, "screencast_font_filepath", text=_T("自定义字体文件"))

        # 4. 背景框设置 (Background Box)
        box = col.box()
        box.label(text=_T("背景框设置 (Background)"), icon=_ICON("MODIFIER"))
        box.prop(self, "screencast_show_box", text=_T("显示背景框"))
        if self.screencast_show_box:
            box.prop(self, "screencast_bg_color", text=_T("背景颜色"))
            row = box.row(align=True)
            row.prop(self, "screencast_box_radius", text=_T("圆角半径"))
            row.prop(self, "screencast_box_padding", text=_T("边距大小"))
            box.prop(self, "screencast_bg_image", text=_T("背景图片"))
            if self.screencast_bg_image:
                box.prop(self, "screencast_bg_image_alpha", text=_T("图片透明度"))

        # 5. 特效设置 (Effects)
        box = col.box()
        box.label(text=_T("特效设置 (Effects)"), icon=_ICON("PARTICLES"))
        box.prop(self, "screencast_show_ripples", text=_T("启用点击涟漪"))
        if self.screencast_show_ripples:
            box.prop(self, "screencast_ripple_color", text=_T("涟漪颜色"))

        # 6. 时间与历史 (Timing & History)
        box = col.box()
        box.label(text=_T("时间与历史 (Timing & History)"), icon=_ICON("TIME"))
        row = box.row(align=True)
        row.prop(self, "screencast_history_count", text=_T("最多显示行"))
        row.prop(self, "screencast_timeout", text=_T("显示时长(秒)"))

        # 7. 自定义贴图 (Custom Mouse Image)
        box = col.box()
        box.label(text=_T("自定义鼠标贴图 (Custom Mouse Image)"), icon=_ICON("FILE_IMAGE"))
        box.prop(self, "screencast_use_custom_mouse", text=_T("使用自定义贴图"))
        if self.screencast_use_custom_mouse:
            row = box.row(align=True)
            
            col_b = row.column()
            col_b.label(text=_T("基础鼠标"))
            col_b.prop(self, "screencast_mouse_img_base", text="")
            
            col_l = row.column()
            col_l.label(text=_T("左键按压"))
            col_l.prop(self, "screencast_mouse_img_lmouse", text="")
            
            col_r = row.column()
            col_r.label(text=_T("右键按压"))
            col_r.prop(self, "screencast_mouse_img_rmouse", text="")
            
            col_m = row.column()
            col_m.label(text=_T("中键按压"))
            col_m.prop(self, "screencast_mouse_img_mmouse", text="")

    def draw_other_settings(self, layout):
        col = layout.column()
        
        box = col.box()
        box.label(text=_T("全局快捷键管理:"), icon="KEYINGSET")
        row = box.row(align=True)
        row.scale_y = 1.2
        row.operator("size_tool.exclusive_all_hotkeys", text=_T("一键独占所有快捷键 (禁用冲突)"))
        row.operator("size_tool.restore_all_conflicts", text=_T("一键恢复所有冲突"))
        box.prop(self, "auto_exclusive_shift_s_on_startup", text=_T("启动时自动独占所有快捷键"))
        
        col.separator()
        col.prop(self, "activate_restart_blender", text=_T("在顶部菜单栏显示重启 Blender 按钮"))
        if "show_diagnostics_panels" in self.bl_rna.properties:
            col.prop(self, "show_diagnostics_panels", text=_T("显示诊断/场景审计面板"))
        col.separator()
        row = col.row(align=True)
        row.operator("m8.reset_prefs_ui", text=_T("重置界面设置"), icon="FILE_REFRESH")
        
        col.prop(self, "backup_suffix", text=_T("备用盒后缀"))
        col.prop(self, "backup_collection_name", text=_T("备用盒集合名"))
        col.prop(self, "default_padding", text=_T("默认 Padding"))
        col.prop(self, "archive_default_bake", text=_T("备用盒默认烘焙"))
        col.separator()
        col.prop(self, "auto_new_object_origin_bottom", text=_T("新建物体默认原点到底部"))
        sub = col.column()
        sub.enabled = self.auto_new_object_origin_bottom
        sub.prop(self, "auto_new_object_snap_to_floor", text=_T("新建物体自动落地 (Z=0)"))


# Re-expose properties and keymap registration/exclusive operators for registration.py and other files
from .keymap_helpers import _get_addon_prefs

from .keymap_exclusive import (
    SIZE_TOOL_OT_ResetTransformPieKeymap,
    SIZE_TOOL_OT_ForceTransformPiePriority,
    SIZE_TOOL_OT_ForceSwitchModePriority,
    SIZE_TOOL_OT_ForceAlignPiePriority,
    SIZE_TOOL_OT_ForceSavePiePriority,
    SIZE_TOOL_OT_ForceEdgePropertyPiePriority,
    SIZE_TOOL_OT_ForceMirrorPriority,
    SIZE_TOOL_OT_ForceGroupToolPriority,
    SIZE_TOOL_OT_ExclusiveTransformPieHotkey,
    SIZE_TOOL_OT_RestoreShiftSConflicts,
    SIZE_TOOL_OT_ExclusiveAlignPieHotkey,
    SIZE_TOOL_OT_RestoreAltAConflicts,
    SIZE_TOOL_OT_ExclusiveSavePieHotkey,
    SIZE_TOOL_OT_RestoreCtrlSConflicts,
    SIZE_TOOL_OT_ExclusiveEdgePropertyPieHotkey,
    SIZE_TOOL_OT_RestoreShiftEConflicts,
    SIZE_TOOL_OT_ExclusiveMirrorHotkey,
    SIZE_TOOL_OT_RestoreShiftAltXConflicts,
    SIZE_TOOL_OT_ExclusiveGroupToolHotkey,
    SIZE_TOOL_OT_RestoreCtrlGConflicts,
    SIZE_TOOL_OT_ForceDeletePiePriority,
    SIZE_TOOL_OT_ForceRenamePriority,
    SIZE_TOOL_OT_ForceShadingPiePriority,
    SIZE_TOOL_OT_ForceSmartPiePriority,
    SIZE_TOOL_OT_ForceSwitchEditorPriority,
    SIZE_TOOL_OT_ForceToggleAreaPriority,
    SIZE_TOOL_OT_ForceSubdivisionPriority,
    SIZE_TOOL_OT_ExclusiveAllHotkeys,
    SIZE_TOOL_OT_RestoreAllConflicts,
    SIZE_TOOL_OT_ExclusiveSubdivisionHotkey,
    SIZE_TOOL_OT_RestoreSubdivisionConflicts,
    SIZE_TOOL_OT_ExclusiveToggleAreaHotkey,
    SIZE_TOOL_OT_RestoreToggleAreaConflicts,
    M8_OT_ResetSwitchModePrefs,
    M8_OT_ResetPrefsUI,
)

from .keymap_manager import (
    register_keymaps,
    unregister_keymaps,
    update_keymaps,
)
