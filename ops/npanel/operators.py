"""
M8 N-Panel Manager: Interactive Operators
包含：子标签增量瞬切、一键智能自动归类、一键无痕复原、分类管理操作符
"""
import bpy
from . import classifier
from . import core
from . import backup
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
    bl_options = {"REGISTER", "UNDO"}

    category_name: bpy.props.StringProperty()
    tab_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")
    multi_select: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        self.multi_select = bool(event.shift)
        return self.execute(context)

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)

        cat = None
        for c in categories:
            if c.name == self.category_name:
                cat = c
                break
        if not cat:
            return {"CANCELLED"}

        is_shift = self.multi_select

        for tab in cat.tabs:
            if tab.name == self.tab_name:
                if is_shift:
                    tab.is_active = not tab.is_active
                else:
                    tab.is_active = True
            else:
                if not is_shift:
                    tab.is_active = False

        core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelSmartAutoGroup(bpy.types.Operator):
    """⚡ 一键智能自动归类所有第三方侧边栏标签"""
    bl_idname = "m8.npanel_smart_auto_group"
    bl_label = _T("智能一键归档")
    bl_description = _T("扫描当前安装的所有第三方插件，基于特征指纹库自动分类收纳（3秒极速整理）")
    bl_options = {"INTERNAL"}

    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type

        # 扫描现有所有标签
        all_tabs, tab_modules = core.scan_all_tabs(st)
        if not all_tabs:
            self.report({"WARNING"}, _T("未扫描到有效的第三方侧边栏标签"))
            return {"CANCELLED"}

        # 若开启「仅当前可见」，严格过滤掉当前模式未渲染的休眠标签
        if settings.filter_live_only:
            all_tabs = [t for t in all_tabs if core.is_tab_live(t, context, space_type=st)]

        # 若开启「仅第三方插件」，过滤掉系统原生基础标签 (Item, Tool, View, Animation)
        if settings.filter_addons_only:
            all_tabs = [t for t in all_tabs if core.get_tab_origin_badge(t, space_type=st)[1]]

        if not all_tabs:
            self.report({"WARNING"}, _T("当前过滤条件下没有可归档的活跃标签"))
            return {"CANCELLED"}

        # 智能归档计算
        grouped = classifier.auto_group_tabs(all_tabs, tab_modules, space_type=st)
        if not grouped:
            self.report({"WARNING"}, _T("所有标签均在排除列表中，未产生新分类"))
            return {"CANCELLED"}

        # 清空重构现有分类数据
        categories = settings.get_categories(st)
        categories.clear()
        total_tabs = 0

        for cat_name, subtabs in grouped.items():
            cat = categories.add()
            cat.name = cat_name
            cat.is_expanded = True
            for i, tab_name in enumerate(subtabs):
                tab_item = cat.tabs.add()
                tab_item.name = tab_name
                tab_item.custom_name = classifier.get_tab_display_label(tab_name)
                tab_item.is_active = (i == 0)  # 默认激活第一个子标签
                total_tabs += 1

        settings.enabled = True
        core.apply_organization(context, space_type=st)
        backup.save_presets_to_disk(context)
        _tag_redraw_safely(context)

        msg = f"{_T('已成功将')} {total_tabs} {_T('个标签智能归纳为')} {len(grouped)} {_T('个大分类！')}"
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class M8_OT_NPanelRestoreDefault(bpy.types.Operator):
    """🔄 一键无痕还原原生侧边栏"""
    bl_idname = "m8.npanel_restore_default"
    bl_label = _T("恢复默认侧栏")
    bl_description = _T("完全清除分类与隐藏劫持，瞬间将侧边栏 100% 还原至 Blender 原生状态（无需重启）")
    bl_options = {"INTERNAL"}

    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if settings:
            settings.enabled = False
            # 清理全空间分类数据，彻底还原
            settings.categories.clear()
            settings.categories_image_editor.clear()
            settings.categories_node_editor.clear()
            # 彻底擦除磁盘持久化文件，严防幽灵配置复活
            backup.clear_presets_on_disk()

        PanelStateManager.restore_all()
        _tag_redraw_safely(context)
        self.report({"INFO"}, _T("已 0 延迟无痕恢复 Blender 原生侧边栏状态！"))
        return {"FINISHED"}


class M8_OT_NPanelApply(bpy.types.Operator):
    """应用并刷新侧边栏配置"""
    bl_idname = "m8.npanel_apply"
    bl_label = _T("应用设置")
    bl_description = _T("重新应用侧边栏子标签布局与分类状态并保存预设")
    bl_options = {"INTERNAL"}

    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        st = self.space_type or (settings.active_space_type if settings else "VIEW_3D")
        backup.save_presets_to_disk(context)
        core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        self.report({"INFO"}, _T("侧边栏配置已应用并自动保存！"))
        return {"FINISHED"}


class M8_OT_NPanelAddCategory(bpy.types.Operator):
    """新建大分类"""
    bl_idname = "m8.npanel_add_category"
    bl_label = _T("新建分类")
    bl_description = _T("在主分类列表中直接新增一个分类（无需跳出弹窗）")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty(
        name=_T("分类名称"),
        default=""
    )
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)

        name = self.category_name.strip()
        if not name:
            existing = {c.name for c in categories}
            base = _T("自定义分类")
            idx = len(categories) + 1
            name = f"{base} {idx}"
            while name in existing:
                idx += 1
                name = f"{base} {idx}"

        cat = categories.add()
        cat.name = name
        cat.is_expanded = True
        settings.set_category_index(len(categories) - 1, st)

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelRemoveCategory(bpy.types.Operator):
    """删除分类"""
    bl_idname = "m8.npanel_remove_category"
    bl_label = _T("删除分类")
    bl_description = _T("删除此分类及其下的所有子标签映射")
    bl_options = {"INTERNAL"}

    category_index: bpy.props.IntProperty()
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)
        cur_idx = settings.get_category_index(st)

        if 0 <= self.category_index < len(categories):
            categories.remove(self.category_index)
            if cur_idx >= len(categories):
                settings.set_category_index(max(0, len(categories) - 1), st)

            backup.save_presets_to_disk(context)
            if settings.enabled:
                core.apply_organization(context, space_type=st)
            _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelMoveCategory(bpy.types.Operator):
    """调整分类上下顺序"""
    bl_idname = "m8.npanel_move_category"
    bl_label = _T("移动分类")
    bl_description = _T("调整分类在侧边栏的排列顺序")
    bl_options = {"INTERNAL"}

    direction: bpy.props.EnumProperty(
        items=[("UP", "Up", ""), ("DOWN", "Down", "")],
        default="UP"
    )
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)
        idx = settings.get_category_index(st)
        total = len(categories)

        if self.direction == "UP" and idx > 0:
            categories.move(idx, idx - 1)
            settings.set_category_index(idx - 1, st)
        elif self.direction == "DOWN" and idx < total - 1:
            categories.move(idx, idx + 1)
            settings.set_category_index(idx + 1, st)

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelAddTabToCategory(bpy.types.Operator):
    """将指定标签添加到当前分类"""
    bl_idname = "m8.npanel_add_tab_to_category"
    bl_label = _T("添加标签到分类")
    bl_description = _T("将此标签收纳到当前选中的主分类中")
    bl_options = {"INTERNAL"}

    tab_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")
    move_from_other: bpy.props.BoolProperty(
        name="Move From Other",
        description="若该标签已在其他分类中，自动将其从原分类移出并转移至当前分类",
        default=False
    )

    @classmethod
    def description(cls, context, properties):
        if getattr(properties, "move_from_other", False):
            return _T("从原分类移出，并转移到当前分类（独占归属）")
        return _T("添加到当前分类（若已在其他分类中则同时保留，实现多分类共享）")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)

        # 如果当前尚无任何分类，自动创建第一个分类并选中
        if not categories:
            cat = categories.add()
            cat.name = _T("自定义分类 1")
            cat.is_expanded = True
            settings.set_category_index(0, st)

        cat_idx = settings.get_category_index(st)
        if not (0 <= cat_idx < len(categories)):
            settings.set_category_index(0, st)
            cat_idx = 0

        cat = categories[cat_idx]
        canon_t = classifier.resolve_canonical_tab(self.tab_name)

        # 若开启了从原分类转移（move_from_other），先从其他分类中彻底清理该标签
        if self.move_from_other:
            for other_cat in categories:
                if other_cat == cat:
                    continue
                to_remove = []
                for i, t in enumerate(other_cat.tabs):
                    if t.name == self.tab_name or (canon_t and classifier.resolve_canonical_tab(t.name) == canon_t):
                        to_remove.append(i)
                for i in reversed(to_remove):
                    other_cat.tabs.remove(i)
                if other_cat.tabs and not any(t.is_active for t in other_cat.tabs):
                    other_cat.tabs[0].is_active = True

        # 检查是否已存在于当前分类
        if any(t.name == self.tab_name or (canon_t and classifier.resolve_canonical_tab(t.name) == canon_t) for t in cat.tabs):
            return {"FINISHED"}

        tab_item = cat.tabs.add()
        tab_item.name = self.tab_name
        tab_item.custom_name = classifier.get_tab_display_label(self.tab_name)
        tab_item.is_active = (len(cat.tabs) == 1)

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)

        disp = classifier.get_tab_display_label(self.tab_name)
        if self.move_from_other:
            self.report({"INFO"}, _T(f"已将【{disp}】转移至【{cat.name}】！"))
        else:
            self.report({"INFO"}, _T(f"已将【{disp}】添加至【{cat.name}】！"))
        return {"FINISHED"}


class M8_OT_NPanelAddAllUnassigned(bpy.types.Operator):
    """一键收纳所有未归类标签到当前分类"""
    bl_idname = "m8.npanel_add_all_unassigned"
    bl_label = _T("一键收纳未归类")
    bl_description = _T("将所有尚未加入任何分类的独立标签一键全部收纳到当前选中的主分类中")
    bl_options = {"INTERNAL"}

    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)

        if not categories:
            cat = categories.add()
            cat.name = _T("自定义分类 1")
            cat.is_expanded = True
            settings.set_category_index(0, st)

        cat_idx = settings.get_category_index(st)
        if not (0 <= cat_idx < len(categories)):
            settings.set_category_index(0, st)
            cat_idx = 0

        cur_cat = categories[cat_idx]

        # 收集全部分类中已存在的标签集合（包含规范名）
        assigned_set = set()
        for c in categories:
            for t in c.tabs:
                assigned_set.add(t.name)
                canon = classifier.resolve_canonical_tab(t.name)
                if canon:
                    assigned_set.add(canon)

        all_tabs, _ = core.scan_all_tabs(st)
        if settings.filter_live_only:
            all_tabs = [t for t in all_tabs if core.is_tab_live(t, context, space_type=st)]
        if settings.filter_addons_only:
            all_tabs = [t for t in all_tabs if core.get_tab_origin_badge(t, space_type=st)[1]]

        added_count = 0
        for t in all_tabs:
            canon = classifier.resolve_canonical_tab(t)
            if t in assigned_set or (canon and canon in assigned_set):
                continue

            item = cur_cat.tabs.add()
            item.name = t
            item.custom_name = classifier.get_tab_display_label(t)
            item.is_active = (len(cur_cat.tabs) == 1)
            assigned_set.add(t)
            if canon:
                assigned_set.add(canon)
            added_count += 1

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)

        if added_count > 0:
            self.report({"INFO"}, _T(f"已成功将 {added_count} 个未归类标签收纳至【{cur_cat.name}】！"))
        else:
            self.report({"INFO"}, _T("当前没有待归类的独立标签。"))
        return {"FINISHED"}


class M8_OT_NPanelRemoveTabFromCategory(bpy.types.Operator):
    """从分类中移出子标签"""
    bl_idname = "m8.npanel_remove_tab_from_category"
    bl_label = _T("移出子标签")
    bl_description = _T("将此标签从当前分类中移除")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    tab_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)

        cat = None
        for c in categories:
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

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelMoveTab(bpy.types.Operator):
    """调整子标签在分类中的排列顺序"""
    bl_idname = "m8.npanel_move_tab"
    bl_label = _T("移动子标签")
    bl_description = _T("调整子标签在置顶面板中的排列顺序")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    tab_name: bpy.props.StringProperty()
    direction: bpy.props.EnumProperty(
        items=[("UP", "Up", ""), ("DOWN", "Down", "")],
        default="UP"
    )
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)

        cat = None
        for c in categories:
            if c.name == self.category_name:
                cat = c
                break
        if not cat:
            return {"CANCELLED"}

        idx = -1
        for i, t in enumerate(cat.tabs):
            if t.name == self.tab_name:
                idx = i
                break

        if idx == -1:
            return {"CANCELLED"}

        total = len(cat.tabs)
        if self.direction == "UP" and idx > 0:
            cat.tabs.move(idx, idx - 1)
        elif self.direction == "DOWN" and idx < total - 1:
            cat.tabs.move(idx, idx + 1)

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelClearSearch(bpy.types.Operator):
    """清空标签搜索框"""
    bl_idname = "m8.npanel_clear_search"
    bl_label = _T("清空搜索")
    bl_description = _T("清空待分配标签搜索过滤关键字")
    bl_options = {"INTERNAL"}

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if settings:
            settings.search_query = ""
            _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelResetTabName(bpy.types.Operator):
    """恢复子标签默认显示名称"""
    bl_idname = "m8.npanel_reset_tab_name"
    bl_label = _T("恢复默认名称")
    bl_description = _T("清除自定义重命名，恢复该子标签的系统默认名称")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    tab_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)
        for cat in categories:
            if cat.name == self.category_name:
                for tab in cat.tabs:
                    if tab.name == self.tab_name:
                        tab.custom_name = classifier.get_tab_display_label(tab.name)
                        break
                break

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


CURATED_CATEGORY_ICONS = [
    # 建模与网格
    ("MOD_SOLIDIFY", "实体化/硬表面"),
    ("EDITMODE_HLT", "编辑模式"),
    ("MESH_CUBE", "立方体网格"),
    ("MOD_BEVEL", "倒角/细分"),
    ("MOD_BOOLEAN", "布尔建模"),
    ("SNAP_VERTEX", "顶点吸附"),
    # 雕刻与绘制
    ("SCULPTMODE_HLT", "雕刻模式"),
    ("BRUSH_DATA", "笔刷工具"),
    ("TPAINT_HLT", "纹理绘制"),
    ("TEXTURE", "纹理贴图"),
    # 材质与着色
    ("MATERIAL", "材质球"),
    ("SHADING_RENDERED", "实时渲染着色"),
    ("NODE", "着色节点"),
    ("COLOR", "色彩管理"),
    # 骨骼与装配
    ("ARMATURE_DATA", "骨架装配"),
    ("POSE_HLT", "姿态模式"),
    ("ANIM", "动画曲线"),
    ("ACTION", "动作编辑"),
    ("DRIVER", "驱动器"),
    # 灯光与摄像机
    ("LIGHT", "灯光照明"),
    ("CAMERA_DATA", "摄像机"),
    ("RENDER_STILL", "渲染输出"),
    # 工具与辅助
    ("TOOL_SETTINGS", "工具设置"),
    ("PREFERENCES", "首选项/设置"),
    ("MODIFIER", "修改器"),
    ("EMPTY_AXIS", "空物体/对齐"),
    ("PIVOT_CURSOR", "3D 游标"),
    # 集合与分类
    ("OUTLINER_COLLECTION", "大纲集合"),
    ("COLLECTION_COLOR_01", "红色集合"),
    ("COLLECTION_COLOR_02", "橙色集合"),
    ("COLLECTION_COLOR_04", "绿色集合"),
    ("COLLECTION_COLOR_06", "蓝色集合"),
    # 扩展与插件
    ("PACKAGE", "插件包/扩展"),
    ("COMMUNITY", "社区插件"),
    ("WORKSPACE", "工作区"),
    ("HELP", "帮助指南"),
]


class M8_OT_NPanelSwitchCategory(bpy.types.Operator):
    """切换激活大分类"""
    bl_idname = "m8.npanel_switch_category"
    bl_label = _T("切换分类")
    bl_description = _T("快速切换当前激活的侧边栏大分类")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)
        for idx, cat in enumerate(categories):
            if cat.name == self.category_name:
                settings.set_category_index(idx, st)
                if cat.tabs and not any(t.is_active for t in cat.tabs):
                    cat.tabs[0].is_active = True
                break

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)

        # 关键机制：同步更新当前 Blender 视口中激活的 N 侧栏标签页高亮
        if self.category_name:
            try:
                wm = getattr(context, "window_manager", None) or bpy.context.window_manager
                for win in getattr(wm, "windows", []):
                    screen = win.screen
                    if not screen:
                        continue
                    for area in screen.areas:
                        if area.type == st:
                            for reg in area.regions:
                                if reg.type == "UI":
                                    reg.active_panel_category = self.category_name
                                    reg.tag_redraw()
            except Exception as e:
                print(f"[M8 NPanel] Error setting active_panel_category: {e}")

        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelClearCategoryTabs(bpy.types.Operator):
    """清空指定大分类的所有子标签"""
    bl_idname = "m8.npanel_clear_category_tabs"
    bl_label = _T("清空分类子标签")
    bl_description = _T("清空当前分类下的所有子标签映射（标签将回到可用池）")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        categories = settings.get_categories(st)
        for cat in categories:
            if cat.name == self.category_name:
                cat.tabs.clear()
                break

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        self.report({"INFO"}, _T(f"已清空分类【{self.category_name}】的所有子标签"))
        return {"FINISHED"}


class M8_OT_NPanelQuickRenameTab(bpy.types.Operator):
    """快速重命名子标签"""
    bl_idname = "m8.npanel_quick_rename_tab"
    bl_label = _T("快速重命名")
    bl_description = _T("就地快速修改此子标签的显示名称")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    tab_name: bpy.props.StringProperty()
    new_name: bpy.props.StringProperty(name=_T("显示名称"))
    space_type: bpy.props.StringProperty(default="")

    def invoke(self, context, event):
        settings = getattr(context.scene, "m8_npanel", None)
        st = self.space_type or (settings.active_space_type if settings else "VIEW_3D")
        if settings:
            for cat in settings.get_categories(st):
                if cat.name == self.category_name:
                    for t in cat.tabs:
                        if t.name == self.tab_name:
                            self.new_name = t.custom_name or classifier.get_tab_display_label(t.name)
                            break
                    break
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "new_name", text=_T("名称"))

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        for cat in settings.get_categories(st):
            if cat.name == self.category_name:
                for t in cat.tabs:
                    if t.name == self.tab_name:
                        t.custom_name = self.new_name.strip() or classifier.get_tab_display_label(t.name)
                        break
                break

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


class M8_OT_NPanelChooseCategoryIcon(bpy.types.Operator):
    """为大分类选择内置专业 3D 矢量图标"""
    bl_idname = "m8.npanel_choose_category_icon"
    bl_label = _T("选择分类图标")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        grid = layout.grid_flow(columns=6, even_columns=True, even_rows=True, align=True)
        for icon_id, icon_tip in CURATED_CATEGORY_ICONS:
            op = grid.operator("m8.npanel_set_category_icon", text="", icon=icon_id)
            op.category_name = self.category_name
            op.icon_name = icon_id
            op.space_type = self.space_type

    def execute(self, context):
        return {"FINISHED"}


class M8_OT_NPanelSetCategoryIcon(bpy.types.Operator):
    """应用大分类图标"""
    bl_idname = "m8.npanel_set_category_icon"
    bl_label = _T("设置图标")
    bl_options = {"INTERNAL"}

    category_name: bpy.props.StringProperty()
    icon_name: bpy.props.StringProperty()
    space_type: bpy.props.StringProperty(default="")

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        st = self.space_type or settings.active_space_type
        for cat in settings.get_categories(st):
            if cat.name == self.category_name:
                cat.icon = self.icon_name
                break

        backup.save_presets_to_disk(context)
        if settings.enabled:
            core.apply_organization(context, space_type=st)
        _tag_redraw_safely(context)
        return {"FINISHED"}


OPERATOR_CLASSES = (
    M8_OT_NPanelSwitchTab,
    M8_OT_NPanelSwitchCategory,
    M8_OT_NPanelSmartAutoGroup,
    M8_OT_NPanelRestoreDefault,
    M8_OT_NPanelApply,
    M8_OT_NPanelAddCategory,
    M8_OT_NPanelRemoveCategory,
    M8_OT_NPanelMoveCategory,
    M8_OT_NPanelAddTabToCategory,
    M8_OT_NPanelAddAllUnassigned,
    M8_OT_NPanelRemoveTabFromCategory,
    M8_OT_NPanelMoveTab,
    M8_OT_NPanelClearSearch,
    M8_OT_NPanelResetTabName,
    M8_OT_NPanelClearCategoryTabs,
    M8_OT_NPanelQuickRenameTab,
    M8_OT_NPanelChooseCategoryIcon,
    M8_OT_NPanelSetCategoryIcon,
)
