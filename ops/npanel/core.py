"""
M8 N-Panel Manager: Core Engine
实现面板递归扫描、隐藏挂载黑魔法 (Parenting Hack)、增量差异重新注册与置顶子标签生成器。
"""
import bpy
import inspect
import uuid
from typing import Dict, List, Optional, Set, Tuple, Type
from .state import PanelStateManager
from . import classifier
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


def get_panel_root(panel: Type[bpy.types.Panel]) -> Type[bpy.types.Panel]:
    """递归追溯面板的根父级（顶层面板）"""
    curr = panel
    visited = set()
    while curr and curr not in visited:
        visited.add(curr)
        parent_id = getattr(curr, "bl_parent_id", None)
        if not parent_id or parent_id.startswith("M8_PT_HiddenPanel"):
            return curr
        parent_cls = getattr(bpy.types, parent_id, None)
        if not parent_cls:
            return curr
        curr = parent_cls
    return curr


def get_panel_original_tab(panel: Type[bpy.types.Panel]) -> str:
    """获取面板的原始标签名称（若为子面板，向上递归继承根面板标签，并规范化同源别名）"""
    if PanelStateManager.has_snapshot(panel):
        cat = PanelStateManager.get_original_category(panel)
        if cat:
            return classifier.resolve_canonical_tab(cat)

    root = get_panel_root(panel)
    if root and root is not panel:
        if PanelStateManager.has_snapshot(root):
            root_cat = PanelStateManager.get_original_category(root)
            if root_cat:
                return classifier.resolve_canonical_tab(root_cat)
        root_cat = getattr(root, "bl_category", None)
        if root_cat:
            return classifier.resolve_canonical_tab(root_cat)

    cat = getattr(panel, "bl_category", None)
    if cat:
        return classifier.resolve_canonical_tab(cat)
    return "Misc"


def is_valid_user_panel(panel: Type[bpy.types.Panel], space_type: str = "VIEW_3D") -> bool:
    """过滤判定是否为合法的待整理侧边栏面板（严格排除系统原生与未注册残留）"""
    if getattr(panel, "bl_space_type", None) != space_type:
        return False
    if getattr(panel, "bl_region_type", None) != "UI":
        return False

    # 忽略自身的隐藏面板与动态置顶面板
    idname = get_panel_idname(panel)
    name = getattr(panel, "__name__", "")
    if (name.startswith("M8_PT_HiddenPanel") or name.startswith("M8_PT_SubTabs") or
        idname.startswith("M8_PT_HiddenPanel") or idname.startswith("M8_PT_SubTabs")):
        return False

    # 忽略未注册或基础类（在 Blender 注册后必有 bl_rna，且在 bpy.types 中可通过 bl_idname 或 __name__ 查询）
    if "bl_rna" not in panel.__dict__:
        return False
    if not hasattr(bpy.types, idname) and not hasattr(bpy.types, name):
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
    """扫描所有有效的第三方侧边栏标签名称及其对应模块（严格排除系统原生标签并规范化同源别名）"""
    panels = scan_panels(space_type)
    tabs_set: Set[str] = set()
    tab_modules: Dict[str, str] = {}

    for p in panels:
        orig_tab = get_panel_original_tab(p)
        if not orig_tab or orig_tab in ("M8_HIDDEN", "NSUBHIDE"):
            continue
        canon_tab = classifier.resolve_canonical_tab(orig_tab)
        # 排除系统原生与保留标签
        if classifier.is_system_excluded(orig_tab) or classifier.is_system_excluded(canon_tab):
            continue

        tabs_set.add(canon_tab)
        if canon_tab not in tab_modules:
            tab_modules[canon_tab] = get_panel_module(p)

    sorted_tabs = sorted(list(tabs_set), key=lambda s: s.lower())
    return sorted_tabs, tab_modules


def get_panel_idname(panel: Type[bpy.types.Panel]) -> str:
    """获取面板的注册 ID 名称（优先 bl_idname，其次 __name__）"""
    return getattr(panel, "bl_idname", None) or getattr(panel, "__name__", "")


def sort_panels_by_generation(panels: List[Type[bpy.types.Panel]]) -> List[Type[bpy.types.Panel]]:
    """
    按父子继承代数对面板进行拓扑分代排序：
    Gen 0 (根面板) -> Gen 1 (子面板) -> Gen 2 (孙面板) ...
    确保 register 时父级必定先于子级注册；unregister 时逆序操作。
    """
    if not panels:
        return []

    unique_panels = list(dict.fromkeys(panels))
    all_names = {get_panel_idname(p) for p in unique_panels if get_panel_idname(p)}

    sorted_result: List[Type[bpy.types.Panel]] = []

    # 提取根面板（无父级或其父级不在此次待更新列表中）
    current_gen = []
    for p in unique_panels:
        pid = getattr(p, "bl_parent_id", None)
        if not pid or pid not in all_names or pid.startswith("M8_PT_HiddenPanel"):
            current_gen.append(p)

    sorted_result.extend(current_gen)

    # 逐代向下推导子孙面板
    prev_gen_names = {get_panel_idname(p) for p in current_gen if get_panel_idname(p)}
    while len(sorted_result) < len(unique_panels):
        next_gen = [
            p for p in unique_panels
            if p not in sorted_result and getattr(p, "bl_parent_id", None) in prev_gen_names
        ]
        if not next_gen:
            # 存在外部依赖或非闭环依赖，安全追加剩余面板
            remaining = [p for p in unique_panels if p not in sorted_result]
            sorted_result.extend(remaining)
            break
        sorted_result.extend(next_gen)
        prev_gen_names = {get_panel_idname(p) for p in next_gen if get_panel_idname(p)}

    return sorted_result


# -------------------------------------------------------------------------
# 3. 动态置顶子标签面板生成器 (Title Panel)
# -------------------------------------------------------------------------
# -------------------------------------------------------------------------
# 3. 动态置顶子标签面板生成器 (Title Panel)
# -------------------------------------------------------------------------
def calculate_category_columns(num_tabs: int, max_setting: str) -> int:
    """
    智能自适应每行按钮数与排数算法：
    - 智能模式 (AUTO)：
      - 1 个子标签：1 列 (单行占满 100% 宽度)
      - 2 个子标签：2 列 (单行平分各 50% 宽度)
      - 3 个子标签：3 列 (单行平分各 33.3% 宽度)
      - 4 个子标签：2 列 (2x2 平衡方块排布，共 2 行)
      - 5 个子标签：3 列 (3 + 2 紧凑两排，共 2 行)
      - 6 个子标签：3 列 (3 + 3 完美对称两排，共 2 行，即“六个两排三行显示”)
      - > 6 个子标签（超过两行）：4 列显示，最多排布到 4 行 (上限 16 个标签)，超大时智能扩列
    - 手动模式 (1~8)：
      - 手动选择的值即为「最高每行按钮数」上限 M；
      - 自适应规则依然生效：当分类子标签数 N <= M 时，直接采用 N 列（自适应平分铺满整行，绝不留出右侧空白）；
      - 仅当分类子标签数 N > M 时，按 M 列进行分行排布，末行等宽对齐。
    """
    if num_tabs <= 0:
        return 1

    setting_str = str(max_setting).strip().upper()
    if setting_str == "AUTO":
        if num_tabs <= 3:
            return num_tabs
        elif num_tabs <= 6:
            return 2 if num_tabs == 4 else 3
        else:
            # 超过两行就是四排显示，最多到四行
            return 4 if num_tabs <= 16 else min(8, (num_tabs + 3) // 4)
    else:
        try:
            manual_max = max(1, min(8, int(setting_str)))
        except (ValueError, TypeError):
            manual_max = 4

        # 手动选择最高行按钮数，但是规则还是如此：
        # 少于上限时自适应平分铺满整行（如设为5但只有2个按钮时，以2列显示铺满）
        if num_tabs <= manual_max:
            return max(1, num_tabs)
        return manual_max


def create_category_title_panel(category_name: str, space_type: str = "VIEW_3D", show_header: bool = False) -> Type[bpy.types.Panel]:
    """为指定的大分类动态创建 bl_order=0 的置顶子标签切换条"""
    def draw_header(self, context: bpy.types.Context):
        layout = self.layout
        # 齿轮按钮移入面板标题栏 Header 最右侧，不占用任何子标签网格宽度
        op = layout.operator("m8.npanel_open_manager", text="", icon="PREFERENCES", emboss=False)
        op.space_type = space_type

    def draw_title(self, context: bpy.types.Context):
        layout = self.layout
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return

        categories = settings.get_categories(space_type)
        cat = None
        for c in categories:
            if c.name == category_name:
                cat = c
                break

        if not cat or len(cat.tabs) == 0:
            row = layout.row()
            row.label(text=_T("（此分类下暂无子标签）"), icon="INFO")
            op = row.operator("m8.npanel_open_manager", text="", icon="PREFERENCES")
            op.space_type = space_type
            return

        # 智能计算当前分类的列数排布（支持智能自适应与手动上限规则）
        tabs_list = list(cat.tabs)
        num_tabs = len(tabs_list)
        setting_val = getattr(settings, "max_tabs_per_row", "AUTO")
        cols = calculate_category_columns(num_tabs, setting_val)
        chunks = [tabs_list[i:i + cols] for i in range(0, num_tabs, cols)]

        col = layout.column(align=True)
        for chunk in chunks:
            row = col.row(align=True)
            if len(chunk) < cols:
                # 严格等宽对齐：利用 split 约束末行的按钮宽度与前几行保持绝对一致
                btn_container = row.split(factor=len(chunk) / cols, align=True)
            else:
                btn_container = row

            for tab in chunk:
                default_display = classifier.get_tab_display_label(tab.name)
                cust = getattr(tab, "custom_name", "").strip()
                btn_text = cust if (cust and cust != default_display) else classifier.get_tab_button_label(tab.name)
                op = btn_container.operator(
                    "m8.npanel_switch_tab",
                    text=btn_text,
                    depress=tab.is_active,
                    translate=False
                )
                op.category_name = category_name
                op.tab_name = tab.name
                op.space_type = space_type

    panel_cls_name = f"M8_PT_SubTabs_{space_type}_{uuid.uuid4().hex[:8]}"
    panel_dict = {
        "bl_idname": panel_cls_name,
        "bl_label": category_name if show_header else "",
        "bl_space_type": space_type,
        "bl_region_type": "UI",
        "bl_category": category_name,
        "bl_order": 0,
        "bl_options": set() if show_header else {'HIDE_HEADER'},
        "draw": draw_title,
    }
    if show_header:
        panel_dict["draw_header"] = draw_header

    title_panel = type(panel_cls_name, (bpy.types.Panel,), panel_dict)
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
    if not settings.is_space_enabled(space_type):
        PanelStateManager.restore_all()
        return

    if PanelStateManager.is_updating:
        return
    PanelStateManager.is_updating = True

    try:
        PanelStateManager.is_active = True
        hidden_parent_id = HIDDEN_PANEL_IDS.get(space_type, "M8_PT_HiddenPanelView3D")

        categories = settings.get_categories(space_type)

        # 1. 重建所有动态置顶子标签栏
        show_header = getattr(settings, "show_subtabs_header", False)
        PanelStateManager.clear_title_panels()
        for cat in categories:
            title_cls = create_category_title_panel(cat.name, space_type, show_header=show_header)
            bpy.utils.register_class(title_cls)
            PanelStateManager.register_title_panel(title_cls)

        # 2. 梳理分类与标签映射表
        active_tabs: Dict[str, str] = {}
        hidden_tabs: Set[str] = set()
        categorized_tabs: Set[str] = set()

        for cat in categories:
            has_active = any(t.is_active for t in cat.tabs)
            # 如果该分类下没有激活项且有标签，默认激活第一个
            if not has_active and len(cat.tabs) > 0:
                cat.tabs[0].is_active = True

            for tab in cat.tabs:
                canon_name = classifier.resolve_canonical_tab(tab.name)
                categorized_tabs.add(canon_name)
                categorized_tabs.add(tab.name)
                if tab.is_active:
                    active_tabs[canon_name] = cat.name
                    active_tabs[tab.name] = cat.name
                else:
                    hidden_tabs.add(canon_name)
                    hidden_tabs.add(tab.name)

        # 白名单排除列表与隐藏配置
        excluded_list = {x.strip().lower() for x in settings.get_excluded_tabs(space_type).split(",") if x.strip()}
        hide_unassigned = settings.get_hide_unassigned(space_type)

        # 3. 扫描并增量更新面板
        panels = scan_panels(space_type)
        panel_names = {get_panel_idname(p) for p in panels if get_panel_idname(p)}
        panels_to_update = []
        desired_states: Dict[Type[bpy.types.Panel], Tuple[Optional[str], Optional[str]]] = {}

        for panel in panels:
            # 记录原始快照
            snapshot = PanelStateManager.record(panel)
            orig_cat = snapshot.original_category
            orig_parent = snapshot.original_parent_id

            # 追溯其根面板
            root = get_panel_root(panel)
            if root and root is not panel:
                root_cat = PanelStateManager.get_original_category(root) if PanelStateManager.has_snapshot(root) else getattr(root, "bl_category", orig_cat)
            else:
                root_cat = orig_cat

            canon_tab = classifier.resolve_canonical_tab(root_cat or orig_cat)
            orig_tab = root_cat or orig_cat

            is_root = (panel is root) or (not orig_parent) or (orig_parent not in panel_names) or orig_parent.startswith("M8_PT_HiddenPanel")

            # 判定目标 category 与 parent_id
            # A. 用户已显式归入分类（最高优先级，即使包含在排除名单中也按用户意图接管）
            if canon_tab in active_tabs or orig_tab in active_tabs:
                target_cat = active_tabs.get(canon_tab) or active_tabs.get(orig_tab)
                desired_cat = target_cat
                # 顶层根面板恢复原父级（None），子面板保持原父级
                desired_parent = orig_parent

            elif canon_tab in hidden_tabs or orig_tab in hidden_tabs:
                desired_cat = "M8_HIDDEN"
                if is_root:
                    desired_parent = hidden_parent_id
                else:
                    desired_parent = orig_parent

            # B. 排除白名单或系统原生保留项（未加入任何分类时保持不动）
            elif (orig_tab.lower() in excluded_list or 
                  canon_tab.lower() in excluded_list or 
                  classifier.is_system_excluded(orig_tab) or 
                  classifier.is_system_excluded(canon_tab)):
                desired_cat = orig_cat
                desired_parent = orig_parent

            # C. 未分配的标签
            else:
                if hide_unassigned:
                    desired_cat = "M8_HIDDEN"
                    if is_root:
                        desired_parent = hidden_parent_id
                    else:
                        desired_parent = orig_parent
                else:
                    desired_cat = orig_cat
                    desired_parent = orig_parent

            curr_cat = getattr(panel, "bl_category", None)
            curr_parent = getattr(panel, "bl_parent_id", None)

            if curr_cat != desired_cat or curr_parent != desired_parent:
                panels_to_update.append(panel)
                desired_states[panel] = (desired_cat, desired_parent)

        if not panels_to_update:
            return

        # 4. 分代拓扑排序，保证安全注销与注册
        sorted_panels = sort_panels_by_generation(panels_to_update)

        # 逆序注销（子面板先注销，父面板后注销）
        for panel in reversed(sorted_panels):
            idname = get_panel_idname(panel)
            if getattr(panel, "is_registered", False) or hasattr(bpy.types, idname) or hasattr(bpy.types, getattr(panel, "__name__", "")):
                try:
                    bpy.utils.unregister_class(panel)
                except Exception:
                    pass

        # 顺序应用属性修改并注册（父面板先注册，子面板后注册）
        for panel in sorted_panels:
            desired_cat, desired_parent = desired_states[panel]
            if desired_cat:
                panel.bl_category = desired_cat
            elif hasattr(panel, "bl_category"):
                try:
                    delattr(panel, "bl_category")
                except Exception:
                    pass

            if desired_parent:
                panel.bl_parent_id = desired_parent
            elif hasattr(panel, "bl_parent_id"):
                try:
                    delattr(panel, "bl_parent_id")
                except Exception:
                    pass

            try:
                bpy.utils.register_class(panel)
            except Exception as e:
                print(f"[M8 NPanel] Error re-registering {panel.__name__}: {e}")

    finally:
        PanelStateManager.is_updating = False
