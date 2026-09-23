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
    """获取面板的原始标签名称（若为子面板，向上递归继承根面板标签，严格排除大分类名称污染）"""
    def _is_clean(c: Optional[str]) -> bool:
        return bool(c and c not in ("M8_HIDDEN", "NSUBHIDE", "Misc") and not classifier.is_category_tab_name(c))

    # 0. 优先从类对象永久固化属性中读取
    pinned = getattr(panel, "_m8_original_category", None)
    if _is_clean(pinned):
        return classifier.resolve_canonical_tab(pinned)

    # 1. 检查面板自身快照
    if PanelStateManager.has_snapshot(panel):
        cat = PanelStateManager.get_original_category(panel)
        if _is_clean(cat):
            return classifier.resolve_canonical_tab(cat)

    # 2. 向上递归追溯根面板
    root = get_panel_root(panel)
    if root and root is not panel:
        root_pinned = getattr(root, "_m8_original_category", None)
        if _is_clean(root_pinned):
            return classifier.resolve_canonical_tab(root_pinned)
        if PanelStateManager.has_snapshot(root):
            root_cat = PanelStateManager.get_original_category(root)
            if _is_clean(root_cat):
                return classifier.resolve_canonical_tab(root_cat)
        root_cat = getattr(root, "bl_category", None)
        if _is_clean(root_cat):
            return classifier.resolve_canonical_tab(root_cat)

    # 3. 检查当前内存属性
    cat = getattr(panel, "bl_category", None)
    if _is_clean(cat):
        return classifier.resolve_canonical_tab(cat)

    # 4. 兜底：若内存已脏或被分类篡改，从类定义源码中提取真实原始分类
    from . import state
    src_cat, _ = state.get_source_attributes(panel)
    if _is_clean(src_cat):
        return classifier.resolve_canonical_tab(src_cat)

    # 5. 若子面板源码无 bl_category，提取根父级源码中的真实分类
    if root and root is not panel:
        root_src_cat, _ = state.get_source_attributes(root)
        if _is_clean(root_src_cat):
            return classifier.resolve_canonical_tab(root_src_cat)

    return "Misc"


def is_valid_user_panel(panel: Type[bpy.types.Panel], space_type: str = "VIEW_3D", visited: Optional[Set[Type[bpy.types.Panel]]] = None) -> bool:
    """过滤判定是否为合法的待整理侧边栏面板（严格排除系统原生与未注册残留，支持子面板自动继承父级 space_type）"""
    # 忽略自身的隐藏面板与动态置顶面板
    idname = get_panel_idname(panel)
    name = getattr(panel, "__name__", "")
    if (name.startswith("M8_PT_HiddenPanel") or name.startswith("M8_PT_SubTabs") or
        idname.startswith("M8_PT_HiddenPanel") or idname.startswith("M8_PT_SubTabs")):
        return False

    # 忽略 M8 自身的任何业务面板（M8 面板保持独立原生状态，绝不自我接管）
    mod = get_panel_module(panel)
    if mod.endswith(".M8") or mod == "M8" or "bl_ext.user_default.M8" in mod:
        return False

    # 忽略未注册或基础类（在 Blender 注册后必有 bl_rna，且在 bpy.types 中可通过 bl_idname 或 __name__ 查询）
    if "bl_rna" not in panel.__dict__:
        return False
    if not hasattr(bpy.types, idname) and not hasattr(bpy.types, name):
        return False

    # 核心继承规则（对齐 n_panel_sub_tabs）:
    # 若存在 bl_parent_id 且非 M8 隐藏宿主，说明是嵌套子面板；
    # Blender 引擎完全允许子面板省略自身 bl_space_type 与 bl_region_type（自动继承自父级）。
    # 递归向上验证其真实父面板是否属于目标 space_type 与 UI 区域！
    curr_parent = getattr(panel, "bl_parent_id", None)
    if curr_parent and not curr_parent.startswith("M8_PT_HiddenPanel"):
        if visited is None:
            visited = set()
        if panel in visited:
            return False
        visited.add(panel)
        parent_cls = getattr(bpy.types, curr_parent, None)
        if parent_cls and parent_cls is not panel:
            return is_valid_user_panel(parent_cls, space_type, visited)

    if getattr(panel, "bl_space_type", None) != space_type:
        return False
    if getattr(panel, "bl_region_type", None) != "UI":
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


def is_panel_root_declaration(p: Type[bpy.types.Panel]) -> bool:
    """判定面板在原始声明中是否为顶层根面板（非嵌套子面板，哪怕当前处于受控隐藏挂载状态）"""
    if PanelStateManager.has_snapshot(p):
        orig_parent = PanelStateManager.get_original_parent_id(p)
        if orig_parent and not orig_parent.startswith("M8_PT_HiddenPanel"):
            return False
        return True

    from . import state
    _, src_parent = state.get_source_attributes(p)
    if src_parent:
        return False

    curr_parent = getattr(p, "bl_parent_id", None)
    return not curr_parent or curr_parent.startswith("M8_PT_HiddenPanel")


def scan_all_tabs(space_type: str = "VIEW_3D") -> Tuple[List[str], Dict[str, str]]:
    """扫描所有有效的第三方侧边栏标签名称及其对应模块（严格排除系统原生标签并规范化同源别名）"""
    panels = scan_panels(space_type)
    tabs_set: Set[str] = set()
    tab_modules: Dict[str, str] = {}

    # 关键机制：侧边栏标签完全由顶层根面板 (Root Panel) 声明！
    # 嵌套子面板 (bl_parent_id 存在) 嵌套在父级内部，绝不能独立引入伪标签。
    root_panels = [p for p in panels if is_panel_root_declaration(p)]

    for p in root_panels:
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


def get_space_context_override(space_type: str = "VIEW_3D") -> dict:
    """
    为指定编辑器类型构建精准的 Context Override 字典，解决弹窗或非主视口环境下 poll(context) 缺乏 space_data 的问题
    """
    try:
        wm = getattr(bpy.context, "window_manager", None)
        if not wm or not wm.windows:
            return {}
        win = wm.windows[0]
        screen = win.screen
        for area in screen.areas:
            if area.type == space_type:
                ui_reg = None
                for reg in area.regions:
                    if reg.type == 'UI':
                        ui_reg = reg
                        break
                return {
                    "window": win,
                    "screen": screen,
                    "area": area,
                    "space_data": area.spaces.active,
                    "region": ui_reg
                }
    except Exception:
        pass
    return {}


def is_panel_live_in_context(panel: Type[bpy.types.Panel], context: Optional[bpy.types.Context] = None) -> bool:
    """
    检测面板在当前上下文（视口模式、选中项、激活状态）下是否处于物理渲染/可见状态。
    结合 bl_region_type、bl_context 与 poll(context) 多重裁决。
    自动通过 Context Override 注入真实的视口 Space/Region，确保在弹窗环境下 100% 准确评估。
    """
    if getattr(panel, "bl_region_type", None) != "UI":
        return False

    sp_type = getattr(panel, "bl_space_type", "VIEW_3D")
    need_override = False
    if context is None:
        context = getattr(bpy, "context", None)
        need_override = True
    elif isinstance(context, getattr(bpy.types, "Context", type(None))):
        if not getattr(context, "space_data", None) or getattr(context.space_data, "type", "") != sp_type:
            need_override = True

    ov = get_space_context_override(sp_type) if need_override else {}

    def _eval(ctx):
        # 1. 模式限制 (bl_context) 检查
        bl_ctx = getattr(panel, "bl_context", None)
        if bl_ctx:
            mode = getattr(ctx, "mode", "OBJECT")
            clean_ctx = bl_ctx.lstrip(".").lower()
            mode_map = {
                "objectmode": ["OBJECT"],
                "mesh_edit": ["EDIT_MESH"],
                "curve_edit": ["EDIT_CURVE"],
                "armature_edit": ["EDIT_ARMATURE"],
                "posemode": ["POSE"],
                "sculpt": ["SCULPT"],
                "sculpt_mode": ["SCULPT"],
                "curves_sculpt": ["SCULPT_CURVES"],
                "weightpaint": ["PAINT_WEIGHT"],
                "paint_weight": ["PAINT_WEIGHT"],
                "vertexpaint": ["PAINT_VERTEX"],
                "paint_vertex": ["PAINT_VERTEX"],
                "imagepaint": ["PAINT_TEXTURE"],
                "paint_texture": ["PAINT_TEXTURE"],
                "particlemode": ["PARTICLE_EDIT"],
                "particle": ["PARTICLE_EDIT"],
                "grease_pencil_paint": ["PAINT_GPENCIL"],
                "grease_pencil_sculpt": ["SCULPT_GPENCIL"],
                "greasepencil_vertex": ["VERTEX_GPENCIL"],
                "greasepencil_weight": ["WEIGHT_GPENCIL"],
            }
            allowed = mode_map.get(clean_ctx, [clean_ctx])
            if mode not in allowed:
                return False

        # 2. poll(context) 检查
        poll_fn = getattr(panel, "poll", None)
        if poll_fn:
            try:
                if not poll_fn(ctx):
                    return False
            except Exception:
                return False

        # 3. 渲染引擎限制 (COMPAT_ENGINES) 检查（严格对齐 Blender C 引擎 ED_panel_type_poll）
        compat = getattr(panel, "COMPAT_ENGINES", None)
        if compat:
            scene = getattr(ctx, "scene", None)
            if scene and hasattr(scene, "render"):
                curr_engine = getattr(scene.render, "engine", "")
                if curr_engine and curr_engine not in compat:
                    return False

        return True

    if ov:
        try:
            with bpy.context.temp_override(**ov):
                return _eval(bpy.context)
        except Exception:
            return _eval(context or getattr(bpy, "context", None))
    else:
        return _eval(context or getattr(bpy, "context", None))


def is_tab_live(tab_name: str, context: Optional[bpy.types.Context] = None, space_type: str = "VIEW_3D") -> bool:
    """
    检测指定标签在当前视口模式下是否物理渲染（只要该标签下有任意一个顶层根面板处于活跃可见状态即为可见）
    Blender 侧边栏标签渲染完全由根面板驱动，子面板绝不可能单独唤醒侧边栏标签。
    """
    canon = classifier.resolve_canonical_tab(tab_name)
    panels = scan_panels(space_type)
    root_panels = [p for p in panels if is_panel_root_declaration(p)]
    for p in root_panels:
        p_tab = classifier.resolve_canonical_tab(get_panel_original_tab(p))
        if p_tab == canon:
            if is_panel_live_in_context(p, context):
                return True
    return False


_ADDON_TITLE_CACHE: Dict[str, str] = {}


def get_tab_origin_badge(tab_name: str, space_type: str = "VIEW_3D") -> Tuple[str, bool]:
    """
    分析指定标签的真实插件来源与工作模式特征。
    返回: (badge_text, is_addon)
    例如: ("Bool Tool / LoopTools · 仅编辑模式", True)
          ("HardOps 内置模块", True)
          ("Rigify · 需骨骼/姿态模式", True)
          ("Blender 原生系统", False)
    """
    global _ADDON_TITLE_CACHE
    if not _ADDON_TITLE_CACHE:
        try:
            import addon_utils
            for mod in addon_utils.modules():
                m_name = getattr(mod, "__name__", "")
                info = addon_utils.module_bl_info(mod)
                title = info.get("name", m_name)
                _ADDON_TITLE_CACHE[m_name] = title
        except Exception:
            pass

    canon = classifier.resolve_canonical_tab(tab_name)
    panels = scan_panels(space_type)
    mods: Set[str] = set()
    contexts: Set[str] = set()

    for p in panels:
        p_tab = classifier.resolve_canonical_tab(get_panel_original_tab(p))
        if p_tab == canon:
            mod = get_panel_module(p)
            if mod:
                mods.add(mod)
            bl_ctx = getattr(p, "bl_context", None)
            if bl_ctx:
                contexts.add(bl_ctx)

    # 1. 常见知名插件与内置子模块特异性指纹
    clean_orig = (tab_name or "").strip().lower()
    if canon == "Hardflow" or clean_orig in ("hardflow", "hard_flow"):
        return _T("HardOps 内置模块"), True
    if canon == "HardOps" or clean_orig in ("hardops", "hops"):
        return _T("HardOps"), True
    if canon.lower() == "rigify" or clean_orig == "rigify":
        return _T("Rigify · 需骨骼/姿态模式"), True
    if canon == "Edit" or clean_orig in ("edit", "编辑"):
        return _T("Bool Tool / LoopTools"), True

    # 2. 系统原生基础标签（即使有第三方插件向其注入了辅助面板，标签主体仍属于系统原生）
    native_system_tabs = {"Item", "Tool", "View", "Animation", "Display"}
    if canon in native_system_tabs or not mods or mods == {"bl_ui"}:
        addon_mods = [m for m in mods if m != "bl_ui"]
        if addon_mods:
            return _T("Blender 原生系统 · 含扩展"), False
        return _T("Blender 原生系统"), False

    # 3. 提取插件友好展示名
    addon_names: List[str] = []
    for m in sorted(list(mods)):
        if m == "bl_ui":
            continue
        friendly = _ADDON_TITLE_CACHE.get(m, "")
        if not friendly:
            clean = m.split(".")[-1]
            friendly = clean.replace("_", " ").title()
        if friendly not in addon_names:
            addon_names.append(friendly)

    ctx_suffix = ""
    if "mesh_edit" in contexts and len(contexts) == 1:
        ctx_suffix = f" · {_T('仅编辑模式')}"
    elif "posemode" in contexts and len(contexts) == 1:
        ctx_suffix = f" · {_T('仅姿态模式')}"
    elif "armature_edit" in contexts and len(contexts) == 1:
        ctx_suffix = f" · {_T('仅骨骼编辑模式')}"

    addon_str = "/".join(addon_names[:2]) if addon_names else _T("第三方扩展")
    return f"{addon_str}{ctx_suffix}", True


def get_panel_idname(panel: Type[bpy.types.Panel]) -> str:
    """获取面板的注册 ID 名称（优先 bl_idname，其次 __name__）"""
    return getattr(panel, "bl_idname", None) or getattr(panel, "__name__", "")


# -------------------------------------------------------------------------
# 2.1 官方推荐根面板黄金显示顺序与特殊插件首选项同步
# -------------------------------------------------------------------------
HARD_OPS_PANELS_ORDER_REFERENCE = [
    'HOPS_PT_Button',
    'HOPS_PT_material_hops',
    'HARDFLOW_PT_display_miscs',
    'HARDFLOW_PT_display_smartshapes',
    'HARDFLOW_PT_display_modifiers',
    'HOPS_PT_settings',
    'HARDFLOW_PT_settings'
]

BOX_CUTTER_PANELS_ORDER_REFERENCE = [
    'BC_PT_help_npanel',
    'BC_PT_mode',
    'BC_PT_shape',
    'BC_PT_set_origin',
    'BC_PT_operation',
    'BC_PT_surface',
    'BC_PT_snap',
    'BC_PT_settings'
]


def sort_by_order_reference(panels: List[Type[bpy.types.Panel]], order_reference: List[str]) -> List[Type[bpy.types.Panel]]:
    """按官方推荐参考顺序对面板列表重排"""
    sorted_panels = []
    panels_copy = list(panels)
    for idna in order_reference:
        for p in panels_copy[:]:
            if get_panel_idname(p) == idna or getattr(p, "__name__", "") == idna:
                sorted_panels.append(p)
                panels_copy.remove(p)
                break
    sorted_panels.extend(panels_copy)
    return sorted_panels


def normalize_bl_order(panels: List[Type[bpy.types.Panel]]):
    """
    规范化面板 bl_order，保证所有第三方面板的 bl_order >= 1，
    从而确保 bl_order=0 的 M8 动态置顶子标签条（M8_PT_SubTabs）永远在最顶部！
    使用原始快照 bl_order 计算幂等偏移量，彻底杜绝多次调用导致的 order 无限漂移！
    """
    all_names = {get_panel_idname(p) for p in panels if get_panel_idname(p)} | {getattr(p, "__name__", "") for p in panels if getattr(p, "__name__", "")}
    min_order = None
    for p in panels:
        pid = getattr(p, "bl_parent_id", None)
        if not pid or pid not in all_names or pid.startswith("M8_PT_HiddenPanel"):
            orig = PanelStateManager.get_original_order(p) if PanelStateManager.has_snapshot(p) else getattr(p, "bl_order", 0)
            if min_order is None or orig < min_order:
                min_order = orig
    if min_order is None:
        min_order = 0
    # 确保根面板的最小 order >= 1（若 min_order <= 0，整体向右偏移 1 - min_order）
    shift = max(0, 1 - min_order)
    for p in panels:
        orig = PanelStateManager.get_original_order(p) if PanelStateManager.has_snapshot(p) else getattr(p, "bl_order", 0)
        try:
            p.bl_order = orig + shift
        except Exception:
            pass


def sync_special_addon_preferences(tab_name: str, target_category: str):
    """
    当切换或启用 HardOps / BoxCutter 标签时，同步更新其插件内部首选项中的分类位置属性，
    彻底杜绝其插件内部 update 回调将 bl_category 还原重置导致的面板丢失问题。
    """
    canon = classifier.resolve_canonical_tab(tab_name).lower()
    clean = (tab_name or "").strip().lower()
    try:
        # 1. HardOps 偏好设置同步
        if canon == "hardops" or clean in ("hardops", "hops", "hardflow"):
            for name, addon_obj in bpy.context.preferences.addons.items():
                if "hardops" in name.lower() or name.lower() == "hops":
                    prefs = getattr(addon_obj, "preferences", None)
                    if prefs and hasattr(prefs, "ui") and hasattr(prefs.ui, "Hops_panel_location"):
                        if prefs.ui.Hops_panel_location != target_category:
                            prefs.ui.Hops_panel_location = target_category
                    break

        # 2. BoxCutter 偏好设置同步
        elif canon == "boxcutter" or clean in ("boxcutter", "bc"):
            for name, addon_obj in bpy.context.preferences.addons.items():
                if "boxcutter" in name.lower():
                    prefs = getattr(addon_obj, "preferences", None)
                    if prefs and hasattr(prefs, "display") and hasattr(prefs.display, "tab"):
                        if prefs.display.tab != target_category:
                            prefs.display.tab = target_category
                    break
    except Exception:
        pass


def sort_panels_by_generation(
    panels: List[Type[bpy.types.Panel]],
    target_parents: Optional[Dict[Type[bpy.types.Panel], Optional[str]]] = None
) -> List[Type[bpy.types.Panel]]:
    """
    按父子继承代数对面板进行拓扑分代排序：
    Gen 0 (根面板) -> Gen 1 (子面板) -> Gen 2 (孙面板) ...
    当指定 target_parents 时，基于目标注册父级进行正向拓扑排序（确保父级先注册）；
    未指定时基于当前 bl_parent_id 排序（用于安全逆序注销）。
    """
    if not panels:
        return []

    unique_panels = list(dict.fromkeys(panels))
    all_names = {get_panel_idname(p) for p in unique_panels if get_panel_idname(p)} | {getattr(p, "__name__", "") for p in unique_panels if getattr(p, "__name__", "")}

    def get_pid(p):
        if target_parents is not None and p in target_parents:
            return target_parents[p]
        return getattr(p, "bl_parent_id", None)

    sorted_result: List[Type[bpy.types.Panel]] = []

    # 提取根面板（无父级或其父级不在此次待更新列表中）
    current_gen = []
    for p in unique_panels:
        pid = get_pid(p)
        if not pid or pid not in all_names or pid.startswith("M8_PT_HiddenPanel"):
            current_gen.append(p)

    # 对根面板按官方黄金顺序（HardOps / BoxCutter）进行优先重排
    all_root_names = {get_panel_idname(p) for p in current_gen} | {getattr(p, "__name__", "") for p in current_gen}
    if any(k in all_root_names for k in HARD_OPS_PANELS_ORDER_REFERENCE) and any(k in all_root_names for k in BOX_CUTTER_PANELS_ORDER_REFERENCE):
        current_gen = sort_by_order_reference(current_gen, HARD_OPS_PANELS_ORDER_REFERENCE + BOX_CUTTER_PANELS_ORDER_REFERENCE)
    elif any(k in all_root_names for k in HARD_OPS_PANELS_ORDER_REFERENCE):
        current_gen = sort_by_order_reference(current_gen, HARD_OPS_PANELS_ORDER_REFERENCE)
    elif any(k in all_root_names for k in BOX_CUTTER_PANELS_ORDER_REFERENCE):
        current_gen = sort_by_order_reference(current_gen, BOX_CUTTER_PANELS_ORDER_REFERENCE)

    sorted_result.extend(current_gen)

    # 逐代向下推导子孙面板（基于累计已就绪父级集合）
    all_sorted_names = {get_panel_idname(p) for p in current_gen if get_panel_idname(p)} | {getattr(p, "__name__", "") for p in current_gen if getattr(p, "__name__", "")}
    while len(sorted_result) < len(unique_panels):
        next_gen = [
            p for p in unique_panels
            if p not in sorted_result and get_pid(p) in all_sorted_names
        ]
        if not next_gen:
            remaining = [p for p in unique_panels if p not in sorted_result]
            sorted_result.extend(remaining)
            break
        sorted_result.extend(next_gen)
        all_sorted_names |= {get_panel_idname(p) for p in next_gen if get_panel_idname(p)} | {getattr(p, "__name__", "") for p in next_gen if getattr(p, "__name__", "")}

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

        # 体验优化：若当前激活的子标签在当前视口模式下处于休眠状态（如 Rigify 需骨骼/姿态模式，LoopTools 需编辑模式），
        # 在子标签栏底部展示温和提示，彻底消除用户关于“分类后插件内容未显示/不见了”的疑惑！
        active_tab_obj = next((t for t in tabs_list if t.is_active), None)
        if active_tab_obj and not is_tab_live(active_tab_obj.name, context, space_type=space_type):
            badge_text, _ = get_tab_origin_badge(active_tab_obj.name, space_type=space_type)
            disp_name = classifier.get_tab_display_label(active_tab_obj.name)
            sub_box = layout.box()
            sub_box.scale_y = 0.8
            sub_row = sub_box.row(align=True)
            sub_row.label(
                text=_T("提示: [%s] 当前模式休眠 (%s)") % (disp_name, badge_text),
                icon="INFO"
            )

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

        # 2. 梳理分类与标签映射表（建立全别名双向不区分大小写索引）
        active_tabs: Dict[str, str] = {}
        active_tabs_lower: Dict[str, str] = {}
        hidden_tabs: Set[str] = set()
        hidden_tabs_lower: Set[str] = set()
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

                # 同步收集该主标签名下所有的同源附生别名（如 HardOps -> hops, hardflow）
                all_aliases = {tab.name, canon_name}
                for alias_k, alias_v in classifier.TAB_CANONICAL_MAP.items():
                    if alias_v.lower() == canon_name.lower() or alias_v.lower() == tab.name.lower():
                        all_aliases.add(alias_k)

                if tab.is_active:
                    for a in all_aliases:
                        active_tabs[a] = cat.name
                        active_tabs_lower[a.lower()] = cat.name
                else:
                    for a in all_aliases:
                        hidden_tabs.add(a)
                        hidden_tabs_lower.add(a.lower())

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

            is_root = is_panel_root_declaration(panel)

            is_active_tab = (
                canon_tab in active_tabs or
                orig_tab in active_tabs or
                canon_tab.lower() in active_tabs_lower or
                orig_tab.lower() in active_tabs_lower
            )

            is_hidden_tab = (
                canon_tab in hidden_tabs or
                orig_tab in hidden_tabs or
                canon_tab.lower() in hidden_tabs_lower or
                orig_tab.lower() in hidden_tabs_lower
            )

            # 判定目标 category 与 parent_id
            # 核心机制（借鉴 n_panel_sub_tabs）：
            # 1. 子面板 (Subpanel) 绝对不改变 bl_parent_id！始终保留指向真实父级的原始 parent_id；
            # 2. 只有顶层根面板 (Root Panel) 在需要隐藏时挂载至 hidden_parent_id，激活时 delattr 清除 bl_parent_id；
            # 3. 根面板隐藏时，Blender 引擎会自动递归隐藏挂载在其下的所有子孙面板。
            if is_active_tab:
                target_cat = (
                    active_tabs.get(canon_tab) or
                    active_tabs.get(orig_tab) or
                    active_tabs_lower.get(canon_tab.lower()) or
                    active_tabs_lower.get(orig_tab.lower())
                )
                desired_cat = target_cat
                if is_root:
                    desired_parent = None
                    # 同步 HardOps / BoxCutter 插件内部偏好设置，防止内部回调弹出重置
                    sync_special_addon_preferences(canon_tab, target_cat)
                    sync_special_addon_preferences(orig_tab, target_cat)
                else:
                    clean_parent = orig_parent
                    if not clean_parent or clean_parent.startswith("M8_PT_HiddenPanel"):
                        from . import state
                        _, src_parent = state.get_source_attributes(panel)
                        clean_parent = src_parent
                    desired_parent = clean_parent

            elif is_hidden_tab:
                desired_cat = orig_cat or "M8_HIDDEN"
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
                    desired_cat = orig_cat or "M8_HIDDEN"
                    if is_root:
                        desired_parent = hidden_parent_id
                    else:
                        desired_parent = orig_parent
                else:
                    desired_cat = orig_cat
                    desired_parent = orig_parent

            curr_cat = getattr(panel, "bl_category", None)
            curr_parent = getattr(panel, "bl_parent_id", None)

            desired_states[panel] = (desired_cat, desired_parent)
            if curr_cat != desired_cat or curr_parent != desired_parent:
                panels_to_update.append(panel)

        if not panels_to_update:
            return

        # 核心级联闭包机制（对齐 n_panel_sub_tabs）：
        # 在 Blender C++ UI 架构中，若父级面板注销并重新注册，其 C 结构体的 children 链表被完全重置；
        # 若子面板不在父级重新注册后联动重新注册，Blender 将丢失挂载指针，导致子面板内容消失/空白；
        # 因此，只要父级面板进入待更新队列，其所有子孙级面板（递归所有后代）必须联动加入更新队列！
        # 且必须按分代正序（父级先注册，子级后注册）重新挂载。
        all_by_id = {get_panel_idname(p): p for p in panels if get_panel_idname(p)}
        all_by_name = {getattr(p, "__name__", ""): p for p in panels if getattr(p, "__name__", "")}

        child_map: Dict[Type[bpy.types.Panel], List[Type[bpy.types.Panel]]] = {}
        parent_map: Dict[Type[bpy.types.Panel], Type[bpy.types.Panel]] = {}

        for p in panels:
            pid = getattr(p, "bl_parent_id", None)
            if pid and not pid.startswith("M8_PT_HiddenPanel"):
                p_parent = all_by_id.get(pid) or all_by_name.get(pid)
                if p_parent:
                    parent_map[p] = p_parent
                    child_map.setdefault(p_parent, []).append(p)

        update_set = set(panels_to_update)
        queue = list(panels_to_update)
        while queue:
            curr = queue.pop(0)
            # 向下级联扩散至所有子孙级
            for child in child_map.get(curr, []):
                if child not in update_set:
                    update_set.add(child)
                    queue.append(child)
                    panels_to_update.append(child)
                    # 确保子面板目标状态同步更新
                    if child not in desired_states or desired_states[child][1] != getattr(child, "bl_parent_id", None):
                        c_snap = PanelStateManager.record(child)
                        c_clean_parent = c_snap.original_parent_id
                        if not c_clean_parent or c_clean_parent.startswith("M8_PT_HiddenPanel"):
                            from . import state
                            _, src_p = state.get_source_attributes(child)
                            c_clean_parent = src_p
                        p_desired_cat = desired_states.get(curr, (None, None))[0]
                        desired_states[child] = (p_desired_cat or getattr(child, "bl_category", None), c_clean_parent)
            # 向上级联扩散至父级
            if curr in parent_map:
                p_parent = parent_map[curr]
                if p_parent not in update_set:
                    update_set.add(p_parent)
                    queue.append(p_parent)
                    panels_to_update.append(p_parent)

        # 4. 分代拓扑排序，保证安全注销与注册
        # 逆序注销（基于当前 bl_parent_id 逆序：子面板先注销，父面板后注销）
        current_sorted = sort_panels_by_generation(panels_to_update)
        for panel in reversed(current_sorted):
            idname = get_panel_idname(panel)
            if getattr(panel, "is_registered", False) or hasattr(bpy.types, idname) or hasattr(bpy.types, getattr(panel, "__name__", "")):
                try:
                    bpy.utils.unregister_class(panel)
                except Exception:
                    pass

        # 规范化 bl_order 确保所有第三方面板在 M8 动态置顶标题栏下方（bl_order >= 1）
        normalize_bl_order(panels_to_update)

        # 顺序应用属性修改并注册（基于目标 desired_parent 正序：父面板先注册，子面板后注册）
        target_parents = {p: desired_states[p][1] for p in panels_to_update}
        target_sorted = sort_panels_by_generation(panels_to_update, target_parents=target_parents)

        failed_panels = []
        for panel in target_sorted:
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
                failed_panels.append(panel)

        # 多轮拓扑补救重试机制：持续重试直至全部成功或收敛
        while failed_panels:
            remaining_failed = []
            registered_any = False
            for panel in failed_panels:
                try:
                    bpy.utils.register_class(panel)
                    registered_any = True
                except Exception:
                    remaining_failed.append(panel)
            if not registered_any or len(remaining_failed) == len(failed_panels):
                for p in remaining_failed:
                    print(f"[M8 NPanel] Warning: Unable to re-register panel {p.__name__}")
                break
            failed_panels = remaining_failed

    finally:
        PanelStateManager.is_updating = False
