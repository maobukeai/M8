"""
M8 N-Panel Manager: Data Structures & PropertyGroups
"""
import bpy
from ...utils.i18n import _T


class M8_NPanelTabItem(bpy.types.PropertyGroup):
    """单个子标签项"""
    name: bpy.props.StringProperty(
        name="Tab Name",
        description="原始侧边栏标签名称",
        default=""
    )
    is_active: bpy.props.BoolProperty(
        name="Active",
        description="是否为当前展开显示的子标签",
        default=False
    )
    is_selected: bpy.props.BoolProperty(
        name="Selected",
        description="在管理界面中是否被选中",
        default=False
    )


class M8_NPanelCategoryItem(bpy.types.PropertyGroup):
    """大分类项（例如：建模、材质）"""
    name: bpy.props.StringProperty(
        name="Category Name",
        description="大分类名称",
        default="新分类"
    )
    is_expanded: bpy.props.BoolProperty(
        name="Expanded",
        description="管理界面中是否展开详情",
        default=True
    )
    tabs: bpy.props.CollectionProperty(
        type=M8_NPanelTabItem,
        name="Sub Tabs"
    )
    tab_index: bpy.props.IntProperty(
        name="Active Tab Index",
        default=0
    )
    active_tab_name: bpy.props.StringProperty(
        name="Active Tab Name",
        default=""
    )


class M8_NPanelWorkspaceItem(bpy.types.PropertyGroup):
    """工作区与分类关联预设"""
    workspace_pattern: bpy.props.StringProperty(
        name="Workspace Pattern",
        description="工作区匹配通配符，如 *Model*, *Shading*",
        default="*"
    )
    target_category: bpy.props.StringProperty(
        name="Target Category",
        description="匹配时自动激活的大分类名称",
        default=""
    )


class M8_NPanelSettings(bpy.types.PropertyGroup):
    """侧边栏管理器全局设置数据"""
    enabled: bpy.props.BoolProperty(
        name=_T("启用侧栏管理器"),
        description=_T("开启后将聚合整理 N 侧边栏为二级子标签分类"),
        default=False
    )
    hide_unassigned: bpy.props.BoolProperty(
        name=_T("隐藏未分配标签"),
        description=_T("将未加入任何分类的第三方残留标签隐藏，保持侧边栏极度清爽"),
        default=False
    )
    excluded_tabs: bpy.props.StringProperty(
        name=_T("排除标签"),
        description=_T("不进行接管的标签白名单，逗号分隔"),
        default="Item, Tool, View"
    )
    max_tabs_per_row: bpy.props.IntProperty(
        name=_T("每行最多按钮数"),
        description=_T("置顶子标签面板中每行最多排布的子标签按钮数量"),
        default=4,
        min=1,
        max=8
    )
    workspace_auto_switch: bpy.props.BoolProperty(
        name=_T("跟随工作区自动切换分类"),
        description=_T("切换 Blender 工作区时自动激活对应的分类"),
        default=True
    )
    categories: bpy.props.CollectionProperty(
        type=M8_NPanelCategoryItem,
        name="Categories"
    )
    category_index: bpy.props.IntProperty(
        name="Category Index",
        default=0
    )
    workspace_items: bpy.props.CollectionProperty(
        type=M8_NPanelWorkspaceItem,
        name="Workspace Mappings"
    )
    search_query: bpy.props.StringProperty(
        name=_T("搜索标签"),
        description=_T("在待分配标签池中搜索过滤"),
        default=""
    )


classes = (
    M8_NPanelTabItem,
    M8_NPanelCategoryItem,
    M8_NPanelWorkspaceItem,
    M8_NPanelSettings,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass
    # 挂载到 Scene 上便于界面与操作符直接双向绑定访问
    bpy.types.Scene.m8_npanel = bpy.props.PointerProperty(type=M8_NPanelSettings)


def unregister():
    if hasattr(bpy.types.Scene, "m8_npanel"):
        del bpy.types.Scene.m8_npanel
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
