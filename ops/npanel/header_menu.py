"""
M8 N-Panel Editor Header Menu Entry Hook
Mounts [ 🏁 ˅ ] entry button to the top menus of all supported editors:
VIEW3D, IMAGE_EDITOR, NODE_EDITOR, etc.
"""
import bpy
from . import icons
from ...utils.i18n import _T

EDITOR_MENU_HOOKS = [
    ("VIEW3D_MT_editor_menus", "VIEW_3D"),
    ("IMAGE_MT_editor_menus", "IMAGE_EDITOR"),
    ("NODE_MT_editor_menus", "NODE_EDITOR"),
    ("DOPESHEET_MT_editor_menus", "DOPESHEET_EDITOR"),
    ("SEQUENCER_MT_editor_menus", "SEQUENCE_EDITOR"),
]


class M8_MT_NPanelHeaderMenu(bpy.types.Menu):
    """M8 N 侧栏管理器顶部菜单项 [ 图标 ˅ ]"""
    bl_idname = "M8_MT_npanel_header_menu"
    bl_label = "M8 侧栏管理"

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, "m8_npanel", None)
        space_type = getattr(context.space_data, "type", "VIEW_3D") if hasattr(context, "space_data") and context.space_data else "VIEW_3D"

        # 1. 打开全景管理器
        op = layout.operator("m8.npanel_open_manager", text=_T("打开侧栏全景管理器..."), icon="WINDOW")
        op.space_type = space_type

        layout.separator()

        # 2. 核心快捷操作
        op = layout.operator("m8.npanel_smart_auto_group", text=_T("⚡ 一键智能归档"), icon="AUTO")
        op.space_type = space_type

        op = layout.operator("m8.npanel_restore_default", text=_T("🔄 恢复默认侧栏"), icon="RECOVER_LAST")
        op.space_type = space_type

        if settings:
            layout.separator()
            # 3. 核心开关
            layout.prop(settings, "enabled", text=_T("启用侧栏整理"))
            if space_type == "IMAGE_EDITOR":
                layout.prop(settings, "hide_unassigned_image_editor", text=_T("隐藏未分配标签"))
            elif space_type == "NODE_EDITOR":
                layout.prop(settings, "hide_unassigned_node_editor", text=_T("隐藏未分配标签"))
            else:
                layout.prop(settings, "hide_unassigned", text=_T("隐藏未分配标签"))
            layout.prop(settings, "show_subtabs_header", text=_T("显示分类面板标题栏"))
            layout.prop(settings, "workspace_auto_switch", text=_T("跟随工作区自动切换"))
            layout.prop(settings, "max_tabs_per_row", text=_T("每行按钮数"))

            layout.separator()
            layout.operator("m8.npanel_export_config", text=_T("导出侧栏配置..."), icon="EXPORT")
            layout.operator("m8.npanel_import_config", text=_T("导入侧栏配置..."), icon="IMPORT")


def _make_draw_func(space_type: str):
    def draw_menu(self, context: bpy.types.Context):
        layout = self.layout
        icon_id = icons.get_subtabs_icon_id()
        row = layout.row(align=True)
        if icon_id:
            op = row.operator("m8.npanel_open_manager", text="", icon_value=icon_id)
        else:
            op = row.operator("m8.npanel_open_manager", text="", icon="WINDOW")
        op.space_type = space_type
    return draw_menu


_HOOKED_FUNCS = {}


def register():
    icons.register()
    try:
        bpy.utils.register_class(M8_MT_NPanelHeaderMenu)
    except Exception as e:
        print(f"[M8 NPanel] Failed to register header menu: {e}")

    for menu_idname, space_type in EDITOR_MENU_HOOKS:
        menu_cls = getattr(bpy.types, menu_idname, None)
        if menu_cls:
            # 强化防重复：先清理可能遗留的本模块绘制钩子
            old_funcs = [f for f in getattr(getattr(menu_cls, "draw", None), "_draw_funcs", []) if getattr(f, "__module__", "") == __name__]
            for of in old_funcs:
                try:
                    menu_cls.remove(of)
                except Exception:
                    pass
            draw_func = _make_draw_func(space_type)
            _HOOKED_FUNCS[menu_idname] = draw_func
            try:
                menu_cls.append(draw_func)
            except Exception as e:
                print(f"[M8 NPanel] Warning appending menu to {menu_idname}: {e}")


def unregister():
    for menu_idname, space_type in EDITOR_MENU_HOOKS:
        menu_cls = getattr(bpy.types, menu_idname, None)
        draw_func = _HOOKED_FUNCS.pop(menu_idname, None)
        if menu_cls and draw_func:
            try:
                menu_cls.remove(draw_func)
            except Exception:
                pass

    try:
        bpy.utils.unregister_class(M8_MT_NPanelHeaderMenu)
    except Exception:
        pass

    icons.unregister()

