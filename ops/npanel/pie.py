"""
M8 N-Panel Sub-Tab Right-Click Context Menu Hook
Provides:
Sub-tab Right-Click Context Menu hook: quick rename, reset name, remove, or open manager.
"""
import bpy
from ...utils.i18n import _T
from . import classifier


def draw_subtab_button_context_menu(self, context):
    """右键置顶药丸按钮时注入便捷操作菜单项"""
    btn_op = getattr(context, "button_operator", None)
    if not btn_op:
        return

    # 检查是否为 M8 子标签切换操作符
    op_id = getattr(btn_op, "bl_idname", "") or getattr(getattr(btn_op, "bl_rna", None), "identifier", "")
    if not ("npanel_switch_tab" in op_id.lower() or "M8_OT_NPanelSwitchTab" in type(btn_op).__name__):
        return

    props = getattr(btn_op, "properties", btn_op)
    tab_name = getattr(props, "tab_name", "") or getattr(btn_op, "tab_name", "") or (props.get("tab_name", "") if hasattr(props, "get") else "")
    cat_name = getattr(props, "category_name", "") or getattr(btn_op, "category_name", "") or (props.get("category_name", "") if hasattr(props, "get") else "")
    space_type = getattr(props, "space_type", "") or getattr(btn_op, "space_type", "") or (props.get("space_type", "") if hasattr(props, "get") else "") or "VIEW_3D"

    if not tab_name:
        return

    layout = self.layout
    layout.separator()
    layout.label(text=f"M8 · {classifier.get_tab_display_label(tab_name)}")

    # 1. 快速重命名
    ren_op = layout.operator("m8.npanel_quick_rename_tab", text=_T("快速重命名..."), icon="GREASEPENCIL")
    ren_op.category_name = cat_name
    ren_op.tab_name = tab_name
    ren_op.space_type = space_type

    # 2. 恢复默认名称
    rst_op = layout.operator("m8.npanel_reset_tab_name", text=_T("恢复默认名称"), icon="BACK")
    rst_op.category_name = cat_name
    rst_op.tab_name = tab_name
    rst_op.space_type = space_type

    # 3. 从此分类移出
    rem_op = layout.operator("m8.npanel_remove_tab_from_category", text=_T("从此分类移出"), icon="PANEL_CLOSE")
    rem_op.category_name = cat_name
    rem_op.tab_name = tab_name
    rem_op.space_type = space_type

    # 4. 打开全景管理器
    mgr_op = layout.operator("m8.npanel_open_manager", text=_T("打开全景管理器..."), icon="PREFERENCES")
    mgr_op.space_type = space_type


def register():
    try:
        # 强化防重：清理可能残留的历史右键菜单钩子，防止多重注册
        menu_cls = getattr(bpy.types, "UI_MT_button_context_menu", None)
        if menu_cls:
            draw_fn = getattr(menu_cls, "draw", None)
            old_funcs = [f for f in getattr(draw_fn, "_draw_funcs", []) if getattr(f, "__name__", "") == "draw_subtab_button_context_menu"]
            for of in old_funcs:
                try:
                    menu_cls.remove(of)
                except Exception:
                    pass
            menu_cls.append(draw_subtab_button_context_menu)
    except Exception as e:
        print(f"[M8 NPanel] Warning registering button context menu hook: {e}")


def unregister():
    try:
        bpy.types.UI_MT_button_context_menu.remove(draw_subtab_button_context_menu)
    except Exception:
        pass
