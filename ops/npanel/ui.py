"""
M8 N-Panel Manager: UI Presentation Layer
包含：宽屏三栏全景管理看板 (Kanban View)、3D 视图顶栏入口、首选项设置面板
"""
import bpy
from . import core
from ...utils.i18n import _T


class M8_UL_NPanelCategoryList(bpy.types.UIList):
    """大分类列表控件"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False, icon="COLLECTION_COLOR_02")
            row.label(text=f"({len(item.tabs)})")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=item.name)


class M8_OT_NPanelOpenManager(bpy.types.Operator):
    """打开 N 侧边栏全景管理器看板"""
    bl_idname = "m8.npanel_open_manager"
    bl_label = _T("N 侧栏子标签管理器")
    bl_description = _T("打开可视化侧边栏分类管理面板，随心编排大分类与子标签")
    bl_options = {"REGISTER", "INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=720)

    def execute(self, context):
        core.apply_organization(context)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            layout.label(text=_T("未初始化侧边栏设置"), icon="ERROR")
            return

        # 1. 顶部全局控制条
        top_box = layout.box()
        top_row = top_box.row(align=True)
        top_row.prop(settings, "enabled", text=_T("启用侧栏整理"), toggle=True, icon="CHECKMARK")
        top_row.separator()
        top_row.prop(settings, "hide_unassigned", text=_T("隐藏未分配标签"), toggle=True, icon="HIDE_OFF")
        top_row.separator()
        top_row.prop(settings, "workspace_auto_switch", text=_T("工作区自适应联动"), toggle=True, icon="WORKSPACE")

        layout.separator(factor=0.5)

        # 2. 三栏宽屏全景看板 (Kanban Layout)
        main_split = layout.split(factor=0.33)

        # -----------------------------
        # 左栏：主分类列表
        # -----------------------------
        left_col = main_split.column()
        left_box = left_col.box()
        left_header = left_box.row(align=True)
        left_header.label(text=_T("主分类列表"), icon="OUTLINER_COLLECTION")
        left_header.operator("m8.npanel_add_category", text="", icon="ADD")

        left_box.template_list(
            "M8_UL_NPanelCategoryList",
            "",
            settings,
            "categories",
            settings,
            "category_index",
            rows=8
        )

        cat_ops_row = left_box.row(align=True)
        op_up = cat_ops_row.operator("m8.npanel_move_category", text="", icon="TRIA_UP")
        op_up.direction = "UP"
        op_down = cat_ops_row.operator("m8.npanel_move_category", text="", icon="TRIA_DOWN")
        op_down.direction = "DOWN"
        cat_ops_row.separator()
        if settings.categories:
            del_op = cat_ops_row.operator("m8.npanel_remove_category", text=_T("删除分类"), icon="TRASH")
            del_op.category_index = settings.category_index

        # -----------------------------
        # 中栏：当前分类包含的子标签
        # -----------------------------
        right_split = main_split.split(factor=0.5)
        mid_col = right_split.column()
        mid_box = mid_col.box()

        cur_cat = None
        if 0 <= settings.category_index < len(settings.categories):
            cur_cat = settings.categories[settings.category_index]

        mid_header = mid_box.row(align=True)
        cat_title = cur_cat.name if cur_cat else _T("未选择分类")
        mid_header.label(text=f"{_T('包含子标签')}: {cat_title}", icon="WINDOW")

        if cur_cat:
            if not cur_cat.tabs:
                mid_box.label(text=_T("（暂无子标签，请从右侧点击 + 添加）"), icon="INFO")
            else:
                for tab in cur_cat.tabs:
                    tab_row = mid_box.row(align=True)
                    tab_row.label(text=tab.name, icon="RESTRICT_VIEW_OFF" if not tab.is_active else "RESTRICT_VIEW_ON")
                    rem_op = tab_row.operator("m8.npanel_remove_tab_from_category", text="", icon="PANEL_CLOSE")
                    rem_op.category_name = cur_cat.name
                    rem_op.tab_name = tab.name
        else:
            mid_box.label(text=_T("请在左侧选择或新建一个主分类"), icon="INFO")

        # -----------------------------
        # 右栏：待整理可用标签池
        # -----------------------------
        right_col = right_split.column()
        right_box = right_col.box()
        right_header = right_box.row(align=True)
        right_header.label(text=_T("可用标签池"), icon="LAYER_USED")

        # 搜索过滤输入框
        right_box.prop(settings, "search_query", text="", icon="VIEWZOOM")

        all_tabs, _ = core.scan_all_tabs("VIEW_3D")
        cat_tabs_set = set()
        if cur_cat:
            cat_tabs_set = {t.name for t in cur_cat.tabs}

        search_q = settings.search_query.strip().lower()

        pool_col = right_box.column(align=True)
        added_count = 0
        for t in all_tabs:
            if t in cat_tabs_set:
                continue
            if search_q and search_q not in t.lower():
                continue
            pool_row = pool_col.row(align=True)
            pool_row.label(text=t)
            if cur_cat:
                add_op = pool_row.operator("m8.npanel_add_tab_to_category", text="", icon="ADD")
                add_op.tab_name = t
            added_count += 1
            if added_count >= 15:
                pool_col.label(text=_T("...（更多标签请输入关键字搜索）"))
                break

        if added_count == 0:
            pool_col.label(text=_T("暂无待分配标签"), icon="CHECKMARK")

        # 3. 底部操作快捷工具条
        layout.separator(factor=0.5)
        bot_row = layout.row(align=True)
        bot_row.scale_y = 1.25
        bot_row.operator("m8.npanel_smart_auto_group", text=_T("⚡ 智能一键归档"), icon="AUTO")
        bot_row.operator("m8.npanel_restore_default", text=_T("🔄 恢复默认侧栏"), icon="RECOVER_LAST")
        bot_row.operator("m8.npanel_apply", text=_T("✔ 立即应用"), icon="CHECKMARK")


def draw_view3d_header(self, context):
    """3D 视图顶部工具栏右侧常驻图标"""
    layout = self.layout
    settings = getattr(context.scene, "m8_npanel", None)
    icon = "WORKSPACE" if (settings and settings.enabled) else "WINDOW"
    layout.operator("m8.npanel_open_manager", text="", icon=icon)


def draw_npanel_prefs_settings(prefs, layout, context):
    """在 M8 首选项中绘制侧栏管理器配置"""
    settings = getattr(context.scene, "m8_npanel", None) if context and hasattr(context, "scene") else None

    box = layout.box()
    box.label(text=_T("N 侧栏子标签与分类管理器"), icon="RESTRICT_VIEW_OFF")
    row = box.row()
    row.scale_y = 1.2
    row.operator("m8.npanel_open_manager", text=_T("打开侧栏全景管理器"), icon="WINDOW")
    row.operator("m8.npanel_smart_auto_group", text=_T("⚡ 一键智能归档"), icon="AUTO")
    row.operator("m8.npanel_restore_default", text=_T("🔄 恢复默认侧栏"), icon="RECOVER_LAST")

    if settings:
        sub_box = box.box()
        sub_box.prop(settings, "enabled", text=_T("启用侧边栏整理"))
        sub_box.prop(settings, "hide_unassigned", text=_T("隐藏未分配的残留标签"))
        sub_box.prop(settings, "workspace_auto_switch", text=_T("根据工作区自动切换分类"))
        sub_box.prop(settings, "max_tabs_per_row", text=_T("每行最多按钮数"))
        sub_box.prop(settings, "excluded_tabs", text=_T("排除标签白名单"))


UI_CLASSES = (
    M8_UL_NPanelCategoryList,
    M8_OT_NPanelOpenManager,
)
