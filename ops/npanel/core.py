"""
M8 N-Panel Manager: Core Engine
实现面板递归扫描、隐藏挂载黑魔法 (Parenting Hack)、增量差异重新注册与置顶子标签生成器。
"""
import bpy
import inspect
import uuid
from typing import Dict, List, Optional, Set, Tuple, Type
from .state import PanelStateManager
from ...utils.i18n import _T

# 隐藏面板 ID 映射表
HIDDEN_PANEL_IDS = {
    "VIEW_3D": "M8_PT_HiddenPanelView3D",
    "IMAGE_EDITOR": "M8_PT_HiddenPanelImageEditor",
    "NODE_EDITOR": "M8_PT_HiddenPanelNodeEditor",
}


# -------------------------------------------------------------------------
# 1. 永不显示的宿主隐藏面板（核心黑科技：作为父级隐藏所有挂载的子面板）
# -------------------------------------------------------------------------
class M8_PT_HiddenPanelView3D(bpy.types.Panel):
    bl_idname = "M8_PT_HiddenPanelView3D"
    bl_label = "M8 Hidden Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "M8_HIDDEN"

    @classmethod
    def poll(cls, context):
        return False

    def draw(self, context):
        pass


class M8_PT_HiddenPanelImageEditor(bpy.types.Panel):
    bl_idname = "M8_PT_HiddenPanelImageEditor"
    bl_label = "M8 Hidden Panel"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "M8_HIDDEN"

    @classmethod
    def poll(cls, context):
        return False

    def draw(self, context):
        pass


class M8_PT_HiddenPanelNodeEditor(bpy.types.Panel):
    bl_idname = "M8_PT_HiddenPanelNodeEditor"
    bl_label = "M8 Hidden Panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "M8_HIDDEN"

    @classmethod
    def poll(cls, context):
        return False

    def draw(self, context):
        pass


CORE_PANEL_CLASSES = (
    M8_PT_HiddenPanelView3D,
    M8_PT_HiddenPanelImageEditor,
    M8_PT_HiddenPanelNodeEditor,
)


# -------------------------------------------------------------------------
# 2. 面板信息提取与扫描机制
# -------------------------------------------------------------------------
def get_panel_module(panel: Type[bpy.types.Panel]) -> str:
    """提取面板归属模块名称，适配 Blender 4.2+ 扩展架构"""
    try:
        mod = inspect.getmodule(panel)
        if not mod:
            return ""
        name = mod.__name__
        if name.startswith("bl_ext."):
            # 扩展架构: bl_ext.user_default.addon_name
            parts = name.split(".")
            return ".".join(parts[:3])
        elif name.startswith("bl_ui."):
            return "bl_ui"
        else:
            return name.split(".")[0]
    except Exception:
        return ""


def get_panel_original_tab(panel: Type[bpy.types.Panel]) -> str:
    """获取面板的原始标签名称"""
    if PanelStateManager.has_snapshot(panel):
        return PanelStateManager.get_original_category(panel)
    return getattr(panel, "bl_category", "Misc")


def is_valid_user_panel(panel: Type[bpy.types.Panel], space_type: str = "VIEW_3D") -> bool:
    """过滤判定是否为合法的待整理侧边栏面板"""
    if getattr(panel, "bl_space_type", None) != space_type:
        return False
    if getattr(panel, "bl_region_type", None) != "UI":
        return False
    # 忽略自身的隐藏面板与动态置顶面板
    if panel.__name__.startswith("M8_PT_HiddenPanel") or panel.__name__.startswith("M8_PT_SubTabs"):
        return False
    # 忽略未注册或基础类
    if "bl_rna" not in panel.__dict__:
        return False
    if not hasattr(bpy.types, panel.__name__):
        return False
    # 忽略失去模块的残留面板
    try:
        if not inspect.getmodule(panel):
            return False
    except Exception:
        return False
    return True


def scan_panels(space_type: str = "VIEW_3D") -> List[Type[bpy.types.Panel]]:
    """递归扫描 Blender 内存中所有注册的侧边栏面板"""
    matched: List[Type[bpy.types.Panel]] = []

    def _walk(cls):
        for sub in cls.__subclasses__():
            if is_valid_user_panel(sub, space_type):
                matched.append(sub)
            _walk(sub)

    _walk(bpy.types.Panel)
    return matched


def scan_all_tabs(space_type: str = "VIEW_3D") -> Tuple[List[str], Dict[str, str]]:
    """扫描所有有效的侧边栏标签名称及其对应模块"""
    panels = scan_panels(space_type)
    tabs_set: Set[str] = set()
    tab_modules: Dict[str, str] = {}

    for p in panels:
        orig_tab = get_panel_original_tab(p)
        if orig_tab and orig_tab not in ("M8_HIDDEN", "NSUBHIDE"):
            tabs_set.add(orig_tab)
            if orig_tab not in tab_modules:
                tab_modules[orig_tab] = get_panel_module(p)

    sorted_tabs = sorted(list(tabs_set), key=lambda s: s.lower())
    return sorted_tabs, tab_modules


# -------------------------------------------------------------------------
# 3. 动态置顶子标签面板生成器 (Title Panel)
# -------------------------------------------------------------------------
def create_category_title_panel(category_name: str, space_type: str = "VIEW_3D") -> Type[bpy.types.Panel]:
    """为指定的大分类动态创建 bl_order=0 的置顶子标签切换条"""
    def draw_title(self, context: bpy.types.Context):
        layout = self.layout
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return

        cat = None
        for c in settings.categories:
            if c.name == category_name:
                cat = c
                break

        if not cat or len(cat.tabs) == 0:
            row = layout.row()
            row.label(text=_T("（此分类下暂无子标签）"), icon="INFO")
            row.operator("m8.npanel_open_manager", text="", icon="PREFERENCES")
            return

        # 主栏：子标签药丸按钮流 + 右侧管理小齿轮
        main_row = layout.row(align=True)
        
        # 子标签网格流
        cols = max(1, min(8, settings.max_tabs_per_row))
        grid = main_row.grid_flow(columns=cols, row_major=True, align=True)
        
        for tab in cat.tabs:
            op = grid.operator(
                "m8.npanel_switch_tab",
                text=tab.name,
                depress=tab.is_active
            )
            op.category_name = category_name
            op.tab_name = tab.name

        # 右侧独立设置快捷按钮
        main_row.separator(factor=0.5)
        gear_op = main_row.operator("m8.npanel_open_manager", text="", icon="PREFERENCES")

    panel_cls_name = f"M8_PT_SubTabs_{uuid.uuid4().hex[:8]}"
    title_panel = type(
        panel_cls_name,
        (bpy.types.Panel,),
        {
            "bl_idname": panel_cls_name,
            "bl_label": category_name,
            "bl_space_type": space_type,
            "bl_region_type": "UI",
            "bl_category": category_name,
            "bl_order": 0,
            "bl_options": {"DEFAULT_CLOSED"} if False else set(),
            "draw": draw_title,
        }
    )
    return title_panel


# -------------------------------------------------------------------------
# 4. 增量式差异刷新与应用引擎 (Differential Apply Engine)
# -------------------------------------------------------------------------
def apply_organization(context: bpy.types.Context, space_type: str = "VIEW_3D"):
    """
    核心调度器：根据当前设置增量更新面板与置顶条
    """
    settings = getattr(context.scene, "m8_npanel", None)
    if not settings:
        return

    # 若未启用，执行无痕还原
    if not settings.enabled:
        PanelStateManager.restore_all()
        return

    if PanelStateManager.is_updating:
        return
    PanelStateManager.is_updating = True

    try:
        PanelStateManager.is_active = True
        hidden_parent_id = HIDDEN_PANEL_IDS.get(space_type, "M8_PT_HiddenPanelView3D")

        # 1. 重建所有动态置顶子标签栏
        PanelStateManager.clear_title_panels()
        for cat in settings.categories:
            title_cls = create_category_title_panel(cat.name, space_type)
            bpy.utils.register_class(title_cls)
            PanelStateManager.register_title_panel(title_cls)

        # 2. 梳理分类与标签映射表
        # active_tabs: tab_name -> category_name (应该在大分类下显示的面板)
        # hidden_tabs: set of tab_names (应该被隐藏到 HiddenPanel 的面板)
        active_tabs: Dict[str, str] = {}
        hidden_tabs: Set[str] = set()
        categorized_tabs: Set[str] = set()

        for cat in settings.categories:
            has_active = any(t.is_active for t in cat.tabs)
            # 如果该分类下没有激活项且有标签，默认激活第一个
            if not has_active and len(cat.tabs) > 0:
                cat.tabs[0].is_active = True

            for tab in cat.tabs:
                categorized_tabs.add(tab.name)
                if tab.is_active:
                    active_tabs[tab.name] = cat.name
                else:
                    hidden_tabs.add(tab.name)

        # 白名单排除列表
        excluded_list = {x.strip().lower() for x in settings.excluded_tabs.split(",") if x.strip()}

        # 3. 扫描并增量更新面板
        panels = scan_panels(space_type)
        updated_count = 0

        for panel in panels:
            # 记录原始快照
            snapshot = PanelStateManager.record(panel)
            orig_tab = snapshot.original_category
            orig_parent = snapshot.original_parent_id

            # 如果属于排除白名单，保持原状
            if orig_tab.lower() in excluded_list:
                desired_cat = orig_tab
                desired_parent = orig_parent
            # 属于激活的子标签：挂载到对应大分类下
            elif orig_tab in active_tabs:
                desired_cat = active_tabs[orig_tab]
                desired_parent = orig_parent
            # 属于已归类但非激活状态的子标签：挂载到 HiddenPanel 隐藏
            elif orig_tab in hidden_tabs:
                desired_cat = orig_tab
                desired_parent = hidden_parent_id
            # 未归类的标签
            else:
                if settings.hide_unassigned:
                    desired_cat = orig_tab
                    desired_parent = hidden_parent_id
                else:
                    desired_cat = orig_tab
                    desired_parent = orig_parent

            # 差异比对：仅在发生实质变化时重新注册，大幅提升切换性能
            curr_cat = getattr(panel, "bl_category", None)
            curr_parent = getattr(panel, "bl_parent_id", None)

            if curr_cat != desired_cat or curr_parent != desired_parent:
                is_reg = hasattr(bpy.types, panel.__name__)
                if is_reg:
                    try:
                        bpy.utils.unregister_class(panel)
                    except Exception:
                        pass

                panel.bl_category = desired_cat
                if desired_parent:
                    panel.bl_parent_id = desired_parent
                elif hasattr(panel, "bl_parent_id"):
                    try:
                        delattr(panel, "bl_parent_id")
                    except Exception:
                        pass

                if is_reg:
                    try:
                        bpy.utils.register_class(panel)
                    except Exception:
                        pass
                updated_count += 1

    finally:
        PanelStateManager.is_updating = False
