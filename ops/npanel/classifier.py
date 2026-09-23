"""
M8 N-Panel Manager: Smart Auto-Group Classifier
内置智能指纹识别引擎，自动分析已安装的第三方插件面板并智能归档到大分类。
"""
from typing import Dict, List, Optional, Set
from ...utils.i18n import _T

# 系统内部隐藏与标记专用标签（绝不向用户展示或归档）
SYSTEM_EXCLUDED_TABS: Set[str] = {
    "nsubhide", "m8_hidden", "misc", "杂项", "m8"
}

# 原生基础标签的中英双向对照与友好展示名
NATIVE_TAB_DISPLAY_MAP: Dict[str, str] = {
    "Item": _T("条目 (Item)"),
    "Tool": _T("工具 (Tool)"),
    "View": _T("视图 (View)"),
    "Animation": _T("动画 (Animation)"),
    "Edit": _T("编辑 (Edit)"),
    "Display": _T("显示 (Display)"),
}

NATIVE_TAB_SHORT_ZH: Dict[str, str] = {
    "Item": "条目",
    "Tool": "工具",
    "View": "视图",
    "Animation": "动画",
    "Edit": "编辑",
    "Display": "显示",
}

# 复杂插件附生碎片标签与主插件标签同源映射表（包含原生中英标签别名对齐）
TAB_CANONICAL_MAP: Dict[str, str] = {
    "hops": "HardOps",
    "hardflow": "HardOps",
    "hard_flow": "HardOps",
    "条目": "Item",
    "item": "Item",
    "工具": "Tool",
    "tool": "Tool",
    "视图": "View",
    "view": "View",
    "动画": "Animation",
    "animation": "Animation",
    "编辑": "Edit",
    "edit": "Edit",
    "显示": "Display",
    "display": "Display",
}


def resolve_canonical_tab(tab_name: str) -> str:
    """将附生碎片标签（如 hops）及中英复合标签规范化为对应主标签"""
    clean = (tab_name or "").strip()
    # 支持形如 "视图 (View)" -> "View"
    if "(" in clean and clean.endswith(")"):
        inner = clean[clean.rfind("(") + 1:-1].strip()
        if inner.lower() in TAB_CANONICAL_MAP:
            return TAB_CANONICAL_MAP[inner.lower()]
        prefix = clean[:clean.find("(")].strip()
        if prefix.lower() in TAB_CANONICAL_MAP:
            return TAB_CANONICAL_MAP[prefix.lower()]
    return TAB_CANONICAL_MAP.get(clean.lower(), clean)


def get_tab_display_label(tab_name: str) -> str:
    """获取在 UI 标签池中展示给用户看的友好本地化/双语名称"""
    canon = resolve_canonical_tab(tab_name)
    return NATIVE_TAB_DISPLAY_MAP.get(canon, tab_name)


def get_tab_button_label(tab_name: str) -> str:
    """获取置顶子标签切换条按钮上的精简显示文本"""
    canon = resolve_canonical_tab(tab_name)
    try:
        from ...utils.i18n import get_addon_language
        if get_addon_language() != "EN" and canon in NATIVE_TAB_SHORT_ZH:
            return NATIVE_TAB_SHORT_ZH[canon]
    except Exception:
        pass
    return tab_name

# 预设大分类及其特征指纹词库（按优先级匹配）
SMART_CATEGORIES_DEF = [
    {
        "id": "MODELING",
        "name": _T("🔨 建模雕刻"),
        "keywords": [
            "hops", "hardops", "boxcutter", "hardflow", "bqr", "mesh", "curve", "bool", "bevel",
            "sculpt", "loop", "quad", "retopo", "subd", "carver", "extrude",
            "poly", "surface", "modifier", "speedflow", "machin3", "fluent",
            "speedret", "mira", "bsurface", "edge", "vertex", "jmesh",
            "deform", "boolean", "cablerator", "pipe", "wire", "symmetry",
            "edit", "编辑"
        ]
    },
    {
        "id": "SHADING",
        "name": _T("🎨 材质着色"),
        "keywords": [
            "material", "mat", "shader", "texture", "uv", "bake", "paint",
            "color", "pbr", "sanctus", "decal", "smudge", "grunge", "palette",
            "substance", "node", "unfold", "unwrap", "pack", "texel"
        ]
    },
    {
        "id": "LIGHTING",
        "name": _T("💡 灯光渲染"),
        "keywords": [
            "light", "render", "camera", "lux", "octane", "cycles", "eevee",
            "photographer", "cam", "hdr", "world", "exposure", "bloom",
            "gobo", "viewport", "compositor"
        ]
    },
    {
        "id": "RIGGING",
        "name": _T("🦴 装配动画"),
        "keywords": [
            "rig", "rigify", "arp", "auto-rig", "bone", "pose", "anim", "animation", "动画", "character",
            "motion", "face", "wiggle", "timeline", "driver", "nla", "spring",
            "ik", "fk", "mocap", "retarget"
        ]
    },
    {
        "id": "ASSETS",
        "name": _T("🌿 资产管线"),
        "keywords": [
            "asset", "scatter", "botaniq", "flora", "grass", "tree", "library",
            "export", "import", "fbx", "obj", "sync", "g-scatter", "geoscatter",
            "bagapie", "kitbash", "blenderkit"
        ]
    },
    {
        "id": "TOOLS",
        "name": _T("⚡ 实用工具"),
        "keywords": [
            "m8", "tool", "工具", "view", "视图", "origin", "align", "measure", "clean", "check",
            "inspect", "pie", "helper", "shortcut", "quick", "screencast",
            "history", "preset"
        ]
    },
]

SMART_CATEGORIES_IMAGE_EDITOR = [
    {
        "id": "UV",
        "name": _T("📐 UV 展平包装"),
        "keywords": [
            "uv", "unwrap", "pack", "island", "seam", "textool", "toolkit",
            "zen", "trimflow", "stitch", "texel", "layout", "pin", "relax"
        ]
    },
    {
        "id": "PAINT",
        "name": _T("🎨 图像绘制"),
        "keywords": [
            "paint", "draw", "brush", "color", "palette", "mask", "scope",
            "scopes", "mio3", "image", "图像", "canvas", "bake", "layer"
        ]
    },
    {
        "id": "TOOLS",
        "name": _T("⚡ 实用工具"),
        "keywords": ["tool", "工具", "view", "视图", "measure", "help"]
    }
]

SMART_CATEGORIES_NODE_EDITOR = [
    {
        "id": "ENHANCE",
        "name": _T("🌿 节点增强"),
        "keywords": [
            "wrangler", "peek", "preview", "connect", "align", "math",
            "search", "quick", "clean", "shader", "geo", "geometry"
        ]
    },
    {
        "id": "GROUPS",
        "name": _T("📦 节点组库"),
        "keywords": ["group", "library", "asset", "preset", "template", "组"]
    },
    {
        "id": "TOOLS",
        "name": _T("⚡ 选项与工具"),
        "keywords": ["options", "tool", "view", "node", "选项", "工具", "视图", "节点"]
    }
]


CATEGORY_EMOJI_PREFIXES = ('🔨', '🎨', '💡', '🦴', '🌿', '⚡', '📦', '📐', '🔧', '📁')

ALL_CATEGORY_NAMES: Set[str] = {
    # 3D 视图
    "🔨 建模雕刻", "🎨 材质着色", "💡 灯光渲染", "🦴 装配动画", "🌿 资产管线", "⚡ 实用工具", "📦 其它扩展",
    "建模雕刻", "材质着色", "灯光渲染", "装配动画", "资产管线", "实用工具", "其它扩展",
    # 图像与 UV
    "📐 UV 展平包装", "🎨 图像绘制",
    "UV 展平包装", "图像绘制",
    # 节点
    "🌿 节点增强", "📦 节点组库", "⚡ 选项与工具",
    "节点增强", "节点组库", "选项与工具",
}


def is_category_tab_name(name: str) -> bool:
    """判定给定名称是否为分类标题或带有分类 Emoji 前缀（绝不可被当作插件原始侧边栏标签）"""
    if not name:
        return False
    clean = str(name).strip()
    if any(clean.startswith(emoji) for emoji in CATEGORY_EMOJI_PREFIXES):
        return True
    if clean in ALL_CATEGORY_NAMES:
        return True
    return False


def is_system_excluded(tab_name: str) -> bool:
    """检查是否属于系统原生、内部隐藏或大分类标题"""
    if not tab_name:
        return True
    clean_name = str(tab_name).strip().lower()
    if clean_name in SYSTEM_EXCLUDED_TABS:
        return True
    if is_category_tab_name(tab_name):
        return True
    return False


import re


def classify_tab(tab_name: str, module_name: str = "", space_type: str = "VIEW_3D") -> str:
    """
    智能分析标签归属大分类
    综合考虑标签名称 (tab_name)、模块包名 (module_name) 与编辑器类型 (space_type)
    短词精准全词匹配，长词支持子串匹配，避免短词误伤
    """
    target_str = f"{tab_name} {module_name}".lower()
    words = set(re.findall(r'[a-zA-Z0-9_\u4e00-\u9fa5]+', target_str))

    if space_type == "IMAGE_EDITOR":
        defs = SMART_CATEGORIES_IMAGE_EDITOR
    elif space_type == "NODE_EDITOR":
        defs = SMART_CATEGORIES_NODE_EDITOR
    else:
        defs = SMART_CATEGORIES_DEF

    for cat in defs:
        for kw in cat["keywords"]:
            if len(kw) <= 3:
                if kw in words:
                    return cat["name"]
            else:
                if kw in target_str:
                    return cat["name"]

    return _T("📦 其它扩展")


AUTO_GROUP_EXCLUDED_TABS: Set[str] = {
    "item", "条目",
    "tool", "工具",
    "view", "视图",
    "animation", "动画",
    "display", "显示",
    "misc", "杂项",
    "m8",
}


def auto_group_tabs(tabs: List[str], tab_modules: Optional[Dict[str, str]] = None, space_type: str = "VIEW_3D") -> Dict[str, List[str]]:
    """
    对给定的所有标签列表进行全量智能归类
    返回: { 分类名: [子标签1, 子标签2, ...] }
    """
    tab_modules = tab_modules or {}
    grouped: Dict[str, List[str]] = {}

    for tab in tabs:
        if is_system_excluded(tab) or tab.lower() in AUTO_GROUP_EXCLUDED_TABS:
            continue
        canon_tab = resolve_canonical_tab(tab)
        mod = tab_modules.get(tab, "") or tab_modules.get(canon_tab, "")
        cat_name = classify_tab(canon_tab, mod, space_type=space_type)
        if cat_name not in grouped:
            grouped[cat_name] = []
        if canon_tab not in grouped[cat_name]:
            grouped[cat_name].append(canon_tab)

    return grouped
