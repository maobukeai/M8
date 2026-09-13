"""
M8 N-Panel Manager: Interactive Operators
包含：子标签增量瞬切、一键智能自动归类、一键无痕复原、分类管理操作符
"""
import bpy
from . import classifier
from . import core
from .state import PanelStateManager
from ...utils.i18n import _T


def _tag_redraw_safely(context):
    if context and getattr(context, "area", None):
        try:
            context.area.tag_redraw()
        except Exception:
            pass


class M8_OT_NPanelSwitchTab(bpy.types.Operator):
    """切换或多选当前分类下的子标签"""
    bl_idname = "m8.npanel_switch_tab"
    bl_label = _T("切换子标签")
    bl_description = _T("切换显示此子标签对应的面板（按住 Shift 可多选同时显示）")
    bl_options = {"REGISTER", "INTERNAL"}

    category_name: bpy.props.StringProperty()
    tab_name: bpy.props.StringProperty()

    def invoke(self, context, event):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        cat = None
        for c in settings.categories:
            if c.name == self.category_name:
                cat = c
                break
        if not cat:
            return {"CANCELLED"}

        is_shift = bool(event.shift)

        for tab in cat.tabs:
            if tab.name == self.tab_name:
                if is_shift:
                    tab.is_active = not tab.is_active
                else:
                    tab.is_active = True
            else:
                if not is_shift:
                    tab.is_active = False

        core.apply_organization(context)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelSmartAutoGroup(bpy.types.Operator):
    """⚡ 一键智能自动归类所有第三方侧边栏标签"""
    bl_idname = "m8.npanel_smart_auto_group"
    bl_label = _T("智能一键归档")
    bl_description = _T("扫描当前安装的所有第三方插件，基于特征指纹库自动分类收纳（3秒极速整理）")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        # 扫描现有所有标签
        all_tabs, tab_modules = core.scan_all_tabs("VIEW_3D")
        if not all_tabs:
            self.report({"WARNING"}, _T("未扫描到有效的第三方侧边栏标签"))
            return {"CANCELLED"}

        # 智能归档计算
        grouped = classifier.auto_group_tabs(all_tabs, tab_modules)
        if not grouped:
            self.report({"WARNING"}, _T("所有标签均在排除列表中，未产生新分类"))
            return {"CANCELLED"}

        # 清空重构现有分类数据
        settings.categories.clear()
        total_tabs = 0

        for cat_name, subtabs in grouped.items():
            cat = settings.categories.add()
            cat.name = cat_name
            cat.is_expanded = True
            for i, tab_name in enumerate(subtabs):
                tab_item = cat.tabs.add()
                tab_item.name = tab_name
                tab_item.is_active = (i == 0)  # 默认激活第一个子标签
                total_tabs += 1

        settings.enabled = True
        core.apply_organization(context)
        _tag_redraw_safely(context)

        msg = f"{_T('已成功将')} {total_tabs} {_T('个标签智能归纳为')} {len(grouped)} {_T('个大分类！')}"
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class M8_OT_NPanelRestoreDefault(bpy.types.Operator):
    """🔄 一键无痕还原原生侧边栏"""
    bl_idname = "m8.npanel_restore_default"
    bl_label = _T("恢复默认侧栏")
    bl_description = _T("完全清除分类与隐藏劫持，瞬间将侧边栏 100% 还原至 Blender 原生状态（无需重启）")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if settings:
            settings.enabled = False

        PanelStateManager.restore_all()
        _tag_redraw_safely(context)
        self.report({"INFO"}, _T("已 0 延迟无痕恢复 Blender 原生侧边栏状态！"))
        return {"FINISHED"}


class M8_OT_NPanelApply(bpy.types.Operator):
    """应用并刷新侧边栏配置"""
    bl_idname = "m8.npanel_apply"
    bl_label = _T("应用设置")
    bl_description = _T("重新应用侧边栏子标签布局与分类状态")
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        core.apply_organization(context)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelAddCategory(bpy.types.Operator):
    """新建大分类"""
    bl_idname = "m8.npanel_add_category"
    bl_label = _T("新建分类")
    bl_description = _T("新建一个侧边栏主分类")
    bl_options = {"REGISTER", "UNDO"}

    category_name: bpy.props.StringProperty(
        name=_T("分类名称"),
        default=_T("📁 自定义分类")
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}
        name = self.category_name.strip()
        if not name:
            self.report({"ERROR"}, _T("分类名称不能为空！"))
            return {"CANCELLED"}

        cat = settings.categories.add()
        cat.name = name
        settings.category_index = len(settings.categories) - 1

        if settings.enabled:
            core.apply_organization(context)
        return {"FINISHED"}


class M8_OT_NPanelRemoveCategory(bpy.types.Operator):
    """删除分类"""
    bl_idname = "m8.npanel_remove_category"
    bl_label = _T("删除分类")
    bl_description = _T("删除此分类及其下的所有子标签映射")
    bl_options = {"REGISTER", "UNDO"}

    category_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}
        if 0 <= self.category_index < len(settings.categories):
            settings.categories.remove(self.category_index)
            if settings.category_index >= len(settings.categories):
                settings.category_index = max(0, len(settings.categories) - 1)

            if settings.enabled:
                core.apply_organization(context)
            _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelMoveCategory(bpy.types.Operator):
    """调整分类上下顺序"""
    bl_idname = "m8.npanel_move_category"
    bl_label = _T("移动分类")
    bl_description = _T("调整分类在侧边栏的排列顺序")
    bl_options = {"REGISTER", "UNDO"}

    direction: bpy.props.EnumProperty(
        items=[("UP", "Up", ""), ("DOWN", "Down", "")],
        default="UP"
    )

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}
        idx = settings.category_index
        total = len(settings.categories)
        if self.direction == "UP" and idx > 0:
            settings.categories.move(idx, idx - 1)
            settings.category_index = idx - 1
        elif self.direction == "DOWN" and idx < total - 1:
            settings.categories.move(idx, idx + 1)
            settings.category_index = idx + 1

        if settings.enabled:
            core.apply_organization(context)
        return {"FINISHED"}


class M8_OT_NPanelAddTabToCategory(bpy.types.Operator):
    """将指定标签添加到当前分类"""
    bl_idname = "m8.npanel_add_tab_to_category"
    bl_label = _T("添加标签到分类")
    bl_description = _T("将此标签收纳到当前选中的主分类中")
    bl_options = {"REGISTER", "UNDO"}

    tab_name: bpy.props.StringProperty()

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings or not settings.categories:
            return {"CANCELLED"}

        cat_idx = settings.category_index
        if not (0 <= cat_idx < len(settings.categories)):
            return {"CANCELLED"}

        cat = settings.categories[cat_idx]

        # 检查是否已存在
        if any(t.name == self.tab_name for t in cat.tabs):
            return {"CANCELLED"}

        tab_item = cat.tabs.add()
        tab_item.name = self.tab_name
        tab_item.is_active = (len(cat.tabs) == 1)

        if settings.enabled:
            core.apply_organization(context)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelRemoveTabFromCategory(bpy.types.Operator):
    """从分类中移出子标签"""
    bl_idname = "m8.npanel_remove_tab_from_category"
    bl_label = _T("移出子标签")
    bl_description = _T("将此标签从当前分类中移除")
    bl_options = {"REGISTER", "UNDO"}

    category_name: bpy.props.StringProperty()
    tab_name: bpy.props.StringProperty()

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        cat = None
        for c in settings.categories:
            if c.name == self.category_name:
                cat = c
                break
        if not cat:
            return {"CANCELLED"}

        for i, t in enumerate(cat.tabs):
            if t.name == self.tab_name:
                cat.tabs.remove(i)
                break

        # 保证至少有一个子标签激活
        if cat.tabs and not any(t.is_active for t in cat.tabs):
            cat.tabs[0].is_active = True

        if settings.enabled:
            core.apply_organization(context)
        _tag_redraw_safely(context)
        return {"FINISHED"}


OPERATOR_CLASSES = (
    M8_OT_NPanelSwitchTab,
    M8_OT_NPanelSmartAutoGroup,
    M8_OT_NPanelRestoreDefault,
    M8_OT_NPanelApply,
    M8_OT_NPanelAddCategory,
    M8_OT_NPanelRemoveCategory,
    M8_OT_NPanelMoveCategory,
    M8_OT_NPanelAddTabToCategory,
    M8_OT_NPanelRemoveTabFromCategory,
)
