"""
M8 N-Panel Manager: Smart Auto-Group Classifier
内置智能指纹识别引擎，自动分析已安装的第三方插件面板并智能归档到大分类。
"""
from typing import Dict, List, Optional, Set
from ...utils.i18n import _T

# 系统或默认排除的标签（绝不归档）
SYSTEM_EXCLUDED_TABS: Set[str] = {
    "item", "tool", "view", "edit", "nsubhide", "m8_hidden"
}

# 预设大分类及其特征指纹词库（按优先级匹配）
SMART_CATEGORIES_DEF = [
    {
        "id": "MODELING",
        "name": _T("🔨 建模雕刻"),
        "keywords": [
            "hops", "hardops", "boxcutter", "mesh", "curve", "bool", "bevel",
            "sculpt", "loop", "quad", "retopo", "subd", "carver", "extrude",
            "poly", "surface", "modifier", "speedflow", "machin3", "fluent",
            "speedret", "mira", "bsurface", "edge", "vertex", "jmesh",
            "deform", "boolean", "cablerator", "pipe", "wire", "symmetry"
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
            "rig", "arp", "auto-rig", "bone", "pose", "anim", "character",
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
            "m8", "tool", "origin", "align", "measure", "clean", "check",
            "inspect", "pie", "helper", "shortcut", "quick", "screencast",
            "history", "preset"
        ]
    },
]


def is_system_excluded(tab_name: str) -> bool:
    """检查是否属于系统原生或应忽略的标签"""
    clean_name = (tab_name or "").strip().lower()
    return clean_name in SYSTEM_EXCLUDED_TABS


def classify_tab(tab_name: str, module_name: str = "") -> str:
    """
    智能分析标签归属大分类
    综合考虑标签名称 (tab_name) 与模块包名 (module_name)
    """
    target_str = f"{tab_name} {module_name}".lower()

    for cat in SMART_CATEGORIES_DEF:
        for kw in cat["keywords"]:
            # 单词或子串匹配
            if kw in target_str:
                return cat["name"]

    return _T("📦 其它扩展")


def auto_group_tabs(tabs: List[str], tab_modules: Optional[Dict[str, str]] = None) -> Dict[str, List[str]]:
    """
    对给定的所有标签列表进行全量智能归类
    返回: { 分类名: [子标签1, 子标签2, ...] }
    """
    tab_modules = tab_modules or {}
    grouped: Dict[str, List[str]] = {}

    for tab in tabs:
        if is_system_excluded(tab):
            continue
        mod = tab_modules.get(tab, "")
        cat_name = classify_tab(tab, mod)
        if cat_name not in grouped:
            grouped[cat_name] = []
        if tab not in grouped[cat_name]:
            grouped[cat_name].append(tab)

    return grouped
