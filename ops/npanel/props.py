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
    custom_name: bpy.props.StringProperty(
        name=_T("自定义名称"),
        description=_T("自定义子标签在侧边栏按钮上显示的文字（鼠标点击/双击即可直接重命名，留空恢复默认）"),
        default="",
        update=lambda self, context: getattr(self, "_on_custom_name_changed", lambda c: None)(context)
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

    def _on_custom_name_changed(self, context):
        if not self.custom_name.strip():
            try:
                from . import classifier
                self.custom_name = classifier.get_tab_display_label(self.name)
            except Exception:
                pass
        try:
            from . import backup, core
            backup.save_presets_to_disk(context)
            settings = getattr(context.scene, "m8_npanel", None) if context and hasattr(context, "scene") else None
            st = settings.active_space_type if settings else "VIEW_3D"
            if settings and settings.enabled:
                core.apply_organization(context, space_type=st)
        except Exception:
            pass
        if context and getattr(context, "area", None):
            try:
                context.area.tag_redraw()
            except Exception:
                pass
        elif context and getattr(context, "screen", None):
            try:
                for area in context.screen.areas:
                    area.tag_redraw()
            except Exception:
                pass


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
    icon: bpy.props.StringProperty(
        name="Category Icon",
        description="大分类矢量图标标识符（如 MOD_SOLIDIFY, SCULPTMODE_HLT, MATERIAL 等）",
        default="OUTLINER_COLLECTION"
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
        default=False,
        update=lambda self, context: getattr(self, "_on_enabled_changed", lambda c: None)(context)
    )
    active_space_type: bpy.props.EnumProperty(
        name=_T("当前编辑器"),
        description=_T("选择正在配置与管理的编辑器类型"),
        items=[
            ("VIEW_3D", _T("3D 视图"), _T("管理 3D 视图视口侧边栏插件 (如 HardOps, BoxCutter, DECALmachine)"), "VIEW3D", 0),
            ("IMAGE_EDITOR", _T("图像/UV 编辑器"), _T("管理 UV 与图像编辑器侧边栏插件 (如 UV Toolkit, Mio3, TexTools)"), "IMAGE", 1),
            ("NODE_EDITOR", _T("节点编辑器"), _T("管理着色器与几何节点侧边栏插件 (如 Node Wrangler, Node Peek)"), "NODETREE", 2),
        ],
        default="VIEW_3D",
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )

    # --- 3D 视图配置 (默认) ---
    hide_unassigned: bpy.props.BoolProperty(
        name=_T("隐藏未分配标签"),
        description=_T("将未加入任何分类的第三方残留标签隐藏，保持侧边栏极度清爽"),
        default=False,
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )
    excluded_tabs: bpy.props.StringProperty(
        name=_T("排除标签"),
        description=_T("不进行接管的标签白名单，逗号分隔"),
        default="",
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )
    categories: bpy.props.CollectionProperty(
        type=M8_NPanelCategoryItem,
        name="Categories"
    )
    category_index: bpy.props.IntProperty(
        name="Category Index",
        default=0
    )

    # --- 图像与 UV 编辑器配置 ---
    enabled_image_editor: bpy.props.BoolProperty(
        name=_T("启用图像编辑器整理"),
        default=True,
        update=lambda self, context: getattr(self, "_on_enabled_changed", lambda c: None)(context)
    )
    hide_unassigned_image_editor: bpy.props.BoolProperty(
        name=_T("隐藏图像编辑器未分配标签"),
        default=False,
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )
    excluded_tabs_image_editor: bpy.props.StringProperty(
        name=_T("排除标签 (图像编辑器)"),
        default="Image, Tool, View, 图像, 工具, 视图",
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )
    categories_image_editor: bpy.props.CollectionProperty(
        type=M8_NPanelCategoryItem,
        name="Image Editor Categories"
    )
    category_index_image_editor: bpy.props.IntProperty(
        name="Image Editor Category Index",
        default=0
    )

    # --- 节点编辑器配置 ---
    enabled_node_editor: bpy.props.BoolProperty(
        name=_T("启用节点编辑器整理"),
        default=True,
        update=lambda self, context: getattr(self, "_on_enabled_changed", lambda c: None)(context)
    )
    hide_unassigned_node_editor: bpy.props.BoolProperty(
        name=_T("隐藏节点编辑器未分配标签"),
        default=False,
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )
    excluded_tabs_node_editor: bpy.props.StringProperty(
        name=_T("排除标签 (节点编辑器)"),
        default="Node, Tool, View, Options, 节点, 工具, 视图, 选项",
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )
    categories_node_editor: bpy.props.CollectionProperty(
        type=M8_NPanelCategoryItem,
        name="Node Editor Categories"
    )
    category_index_node_editor: bpy.props.IntProperty(
        name="Node Editor Category Index",
        default=0
    )

    max_tabs_per_row: bpy.props.EnumProperty(
        name=_T("每行按钮数"),
        description=_T("置顶子标签按钮的每行排布规则：智能自适应（推荐）或手动指定最高每行按钮数"),
        items=[
            ("AUTO", _T("智能自适应"), _T("智能计算最佳每行排布：1~3个铺满一行，4~6个分两排，超过两排四列显示，最高四行")),
            ("1", "1", _T("每行最高 1 个按钮")),
            ("2", "2", _T("每行最高 2 个按钮")),
            ("3", "3", _T("每行最高 3 个按钮")),
            ("4", "4", _T("每行最高 4 个按钮")),
            ("5", "5", _T("每行最高 5 个按钮")),
            ("6", "6", _T("每行最高 6 个按钮")),
            ("7", "7", _T("每行最高 7 个按钮")),
            ("8", "8", _T("每行最高 8 个按钮")),
        ],
        default="AUTO",
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
    )
    workspace_auto_switch: bpy.props.BoolProperty(
        name=_T("跟随工作区自动切换分类"),
        description=_T("切换 Blender 工作区时自动激活对应的分类"),
        default=True
    )
    show_subtabs_header: bpy.props.BoolProperty(
        name=_T("显示分类标题栏"),
        description=_T("是否在侧边栏子标签切换面板顶部显示标题与折叠栏（关闭后隐藏标题栏，界面更紧凑清爽）"),
        default=False,
        update=lambda self, context: getattr(self, "_update_subtabs_header", lambda c: None)(context)
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
    filter_unassigned_only: bpy.props.BoolProperty(
        name=_T("仅看未归类"),
        description=_T("在可用标签池中仅显示未加入任何分类的独立标签"),
        default=False
    )
    filter_live_only: bpy.props.BoolProperty(
        name=_T("仅当前可见"),
        description=_T("在可用标签池中仅显示当前视口模式下正在渲染的可见标签（过滤掉休眠标签）"),
        default=True
    )
    filter_addons_only: bpy.props.BoolProperty(
        name=_T("仅第三方插件"),
        description=_T("在可用标签池中仅显示第三方插件标签，隐藏 Blender 原生系统基础标签（条目/工具/视图/动画）"),
        default=True
    )

    def get_categories(self, space_type: str = ""):
        st = space_type or self.active_space_type
        if st == "IMAGE_EDITOR":
            return self.categories_image_editor
        elif st == "NODE_EDITOR":
            return self.categories_node_editor
        return self.categories

    def get_category_index(self, space_type: str = "") -> int:
        st = space_type or self.active_space_type
        if st == "IMAGE_EDITOR":
            return self.category_index_image_editor
        elif st == "NODE_EDITOR":
            return self.category_index_node_editor
        return self.category_index

    def set_category_index(self, val: int, space_type: str = ""):
        st = space_type or self.active_space_type
        if st == "IMAGE_EDITOR":
            self.category_index_image_editor = val
        elif st == "NODE_EDITOR":
            self.category_index_node_editor = val
        else:
            self.category_index = val

    def get_excluded_tabs(self, space_type: str = "") -> str:
        st = space_type or self.active_space_type
        if st == "IMAGE_EDITOR":
            return self.excluded_tabs_image_editor
        elif st == "NODE_EDITOR":
            return self.excluded_tabs_node_editor
        return self.excluded_tabs

    def get_hide_unassigned(self, space_type: str = "") -> bool:
        st = space_type or self.active_space_type
        if st == "IMAGE_EDITOR":
            return self.hide_unassigned_image_editor
        elif st == "NODE_EDITOR":
            return self.hide_unassigned_node_editor
        return self.hide_unassigned

    def is_space_enabled(self, space_type: str = "") -> bool:
        if not self.enabled:
            return False
        st = space_type or self.active_space_type
        if st == "IMAGE_EDITOR":
            return self.enabled_image_editor
        elif st == "NODE_EDITOR":
            return self.enabled_node_editor
        return self.enabled

    def _on_enabled_changed(self, context):
        try:
            from . import backup, core
            from .state import PanelStateManager
            backup.save_presets_to_disk(context)
            st = self.active_space_type
            if not self.is_space_enabled(st):
                # 关闭整理时，立即 0 延迟无痕还原原生侧边栏，清理所有动态药丸面板
                PanelStateManager.restore_all()
            else:
                categories = self.get_categories(st)
                if len(categories) > 0:
                    core.apply_organization(context, space_type=st)
                else:
                    # 尚无任何分类时，保持原生侧边栏清爽，绝不胡乱劫持
                    PanelStateManager.restore_all()
        except Exception as e:
            print(f"[M8 NPanel] Error on enabled changed: {e}")

        # 触发全视口即刻刷新
        if context and getattr(context, "area", None):
            try:
                context.area.tag_redraw()
            except Exception:
                pass
        if context and getattr(context, "screen", None):
            try:
                for area in context.screen.areas:
                    area.tag_redraw()
            except Exception:
                pass

    def _update_subtabs_header(self, context):
        try:
            from . import backup
            backup.save_presets_to_disk(context)
        except Exception:
            pass
        st = self.active_space_type
        if self.is_space_enabled(st):
            try:
                from . import core
                core.apply_organization(context, space_type=st)
            except Exception:
                pass
        else:
            try:
                from .state import PanelStateManager
                PanelStateManager.restore_all()
            except Exception:
                pass
        if context and getattr(context, "area", None):
            try:
                context.area.tag_redraw()
            except Exception:
                pass
        if context and getattr(context, "screen", None):
            try:
                for area in context.screen.areas:
                    area.tag_redraw()
            except Exception:
                pass


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
