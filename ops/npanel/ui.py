"""
M8 N-Panel Manager: UI Presentation Layer
包含：宽屏三栏全景管理看板 (Kanban View)、3D 视图顶栏入口、首选项设置面板
"""
import bpy
from . import core
from . import classifier
from ...utils.i18n import _T


class M8_UL_NPanelCategoryList(bpy.types.UIList):
    """大分类列表控件"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            icon_id = getattr(item, "icon", "") or "OUTLINER_COLLECTION"
            row.label(text="", icon=icon_id)
            row.prop(item, "name", text="", emboss=False)
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

    space_type: bpy.props.StringProperty(default="")

    def check(self, context):
        # 核心保证：每次内部操作（添加、删除、归类、切换）均即时重绘，不自动关闭弹窗
        return True

    def invoke(self, context, event):
        settings = getattr(context.scene, "m8_npanel", None)
        if settings:
            # 自动从用户配置目录加载全局持久化预设（若当前场景为空）
            from . import backup
            backup.load_presets_from_disk(context, force=False)

            if self.space_type:
                settings.active_space_type = self.space_type
            else:
                s_type = getattr(context.space_data, "type", "VIEW_3D")
                if s_type in {"VIEW_3D", "IMAGE_EDITOR", "NODE_EDITOR"}:
                    settings.active_space_type = s_type

            # 预填充所有已有子标签显示名称，确保用户点击即在已有文字上更改，无需从空白重新输入
            for sp in ("VIEW_3D", "IMAGE_EDITOR", "NODE_EDITOR"):
                for cat in settings.get_categories(sp):
                    for tab in cat.tabs:
                        if not tab.custom_name.strip():
                            tab.custom_name = classifier.get_tab_display_label(tab.name)

        # 视窗居中机制：将鼠标光标预先对准当前 Blender 视窗几何中心，确保弹窗居中弹出
        try:
            import ctypes, ctypes.wintypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                cx = rect.left + w // 2
                cy = rect.top + max(60, h // 2 - 200)
                ctypes.windll.user32.SetCursorPos(cx, cy)
        except Exception:
            pass

        return context.window_manager.invoke_props_dialog(
            self,
            width=820,
            confirm_text=_T("完成并关闭"),
            cancel_default=False
        )

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        st = self.space_type or (settings.active_space_type if settings else "VIEW_3D")
        from . import backup
        backup.save_presets_to_disk(context)
        if settings and settings.is_space_enabled(st):
            categories = settings.get_categories(st)
            if len(categories) > 0:
                core.apply_organization(context, space_type=st)
            else:
                from .state import PanelStateManager
                PanelStateManager.restore_all()
        else:
            from .state import PanelStateManager
            PanelStateManager.restore_all()
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            layout.label(text=_T("未初始化侧边栏设置"), icon="ERROR")
            return

        st = settings.active_space_type

        # 0. 顶栏编辑器类型自由切换器 (Segmented Switcher)
        editor_bar = layout.row(align=True)
        editor_bar.scale_y = 1.25
        editor_bar.prop(settings, "active_space_type", expand=True)

        layout.separator(factor=0.3)

        # 1. 顶部全局控制条
        top_box = layout.box()
        top_row = top_box.row(align=True)
        top_row.prop(settings, "enabled", text=_T("启用侧栏整理"), toggle=True, icon="CHECKMARK")
        top_row.separator()
        if st == "IMAGE_EDITOR":
            top_row.prop(settings, "hide_unassigned_image_editor", text=_T("隐藏未分配标签"), toggle=True, icon="HIDE_OFF")
        elif st == "NODE_EDITOR":
            top_row.prop(settings, "hide_unassigned_node_editor", text=_T("隐藏未分配标签"), toggle=True, icon="HIDE_OFF")
        else:
            top_row.prop(settings, "hide_unassigned", text=_T("隐藏未分配标签"), toggle=True, icon="HIDE_OFF")
        top_row.separator()
        top_row.prop(settings, "show_subtabs_header", text=_T("显示分类标题栏"), toggle=True, icon="DOWNARROW_HLT")
        top_row.separator()
        top_row.prop(settings, "workspace_auto_switch", text=_T("工作区联动"), toggle=True, icon="WORKSPACE")
        top_row.separator()
        top_row.prop(settings, "max_tabs_per_row", text=_T("每行按钮数"))

        layout.separator(factor=0.5)

        categories = settings.get_categories(st)
        cur_cat_idx = settings.get_category_index(st)

        # 2. 三栏宽屏全景看板 (Kanban Layout)
        main_split = layout.split(factor=0.33)

        # -----------------------------
        # 左栏：主分类列表
        # -----------------------------
        left_col = main_split.column()
        left_box = left_col.box()
        left_header = left_box.row(align=True)
        left_header.label(text=_T("主分类列表"), icon="OUTLINER_COLLECTION")
        add_cat_op = left_header.operator("m8.npanel_add_category", text="", icon="ADD")
        add_cat_op.space_type = st

        prop_cat = "categories_image_editor" if st == "IMAGE_EDITOR" else ("categories_node_editor" if st == "NODE_EDITOR" else "categories")
        prop_idx = "category_index_image_editor" if st == "IMAGE_EDITOR" else ("category_index_node_editor" if st == "NODE_EDITOR" else "category_index")

        left_box.template_list(
            "M8_UL_NPanelCategoryList",
            "",
            settings,
            prop_cat,
            settings,
            prop_idx,
            rows=8
        )

        cur_cat = None
        if 0 <= cur_cat_idx < len(categories):
            cur_cat = categories[cur_cat_idx]

        cat_ops_row = left_box.row(align=True)
        op_up = cat_ops_row.operator("m8.npanel_move_category", text="", icon="TRIA_UP")
        op_up.direction = "UP"
        op_up.space_type = st
        op_down = cat_ops_row.operator("m8.npanel_move_category", text="", icon="TRIA_DOWN")
        op_down.direction = "DOWN"
        op_down.space_type = st
        cat_ops_row.separator()
        if cur_cat:
            ico_op = cat_ops_row.operator("m8.npanel_choose_category_icon", text=_T("更换图标"), icon="IMAGE_PLANE")
            ico_op.category_name = cur_cat.name
            ico_op.space_type = st
        cat_ops_row.separator()
        if categories:
            del_op = cat_ops_row.operator("m8.npanel_remove_category", text=_T("删除分类"), icon="TRASH")
            del_op.category_index = cur_cat_idx
            del_op.space_type = st

        # -----------------------------
        # 中栏：当前分类包含的子标签
        # -----------------------------
        right_split = main_split.split(factor=0.5)
        mid_col = right_split.column()
        mid_box = mid_col.box()

        mid_header = mid_box.row(align=True)
        if cur_cat:
            cat_icon = getattr(cur_cat, "icon", "") or "OUTLINER_COLLECTION"
            icon_op = mid_header.operator("m8.npanel_choose_category_icon", text="", icon=cat_icon, emboss=True)
            icon_op.category_name = cur_cat.name
            icon_op.space_type = st
            mid_header.label(text=_T("包含子标签:"), translate=False)
            mid_header.prop(cur_cat, "name", text="")
            if cur_cat.tabs:
                clr_op = mid_header.operator("m8.npanel_clear_category_tabs", text=_T("清空"), icon="TRASH")
                clr_op.category_name = cur_cat.name
                clr_op.space_type = st
        else:
            mid_header.label(text=_T("包含子标签: 未选择分类"), icon="WINDOW")

        if cur_cat:
            if not cur_cat.tabs:
                mid_box.label(text=_T("（暂无子标签，请从右侧点击 + 添加）"), icon="INFO")
            else:
                for tab in cur_cat.tabs:
                    tab_row = mid_box.row(align=True)
                    default_label = classifier.get_tab_display_label(tab.name)
                    
                    # 鼠标点击/双击可直接在已有名称上原地更改（更改而非重新输入）
                    tab_row.prop(
                        tab,
                        "custom_name",
                        text="",
                        icon="RESTRICT_VIEW_OFF" if not tab.is_active else "RESTRICT_VIEW_ON"
                    )

                    # 若已被用户自定义修改，显示一键恢复默认按钮
                    if getattr(tab, "custom_name", "").strip() != default_label:
                        rst_op = tab_row.operator("m8.npanel_reset_tab_name", text="", icon="BACK")
                        rst_op.category_name = cur_cat.name
                        rst_op.tab_name = tab.name
                        rst_op.space_type = st

                    op_tup = tab_row.operator("m8.npanel_move_tab", text="", icon="TRIA_UP")
                    op_tup.category_name = cur_cat.name
                    op_tup.tab_name = tab.name
                    op_tup.direction = "UP"
                    op_tup.space_type = st

                    op_tdn = tab_row.operator("m8.npanel_move_tab", text="", icon="TRIA_DOWN")
                    op_tdn.category_name = cur_cat.name
                    op_tdn.tab_name = tab.name
                    op_tdn.direction = "DOWN"
                    op_tdn.space_type = st

                    rem_op = tab_row.operator("m8.npanel_remove_tab_from_category", text="", icon="PANEL_CLOSE")
                    rem_op.category_name = cur_cat.name
                    rem_op.tab_name = tab.name
                    rem_op.space_type = st
        else:
            mid_box.label(text=_T("请在左侧选择或点击 + 新建一个分类"), icon="INFO")

        # -----------------------------
        # 右栏：待整理可用标签池
        # -----------------------------
        all_tabs, _ = core.scan_all_tabs(st)
        cat_tabs_set = set()
        if cur_cat:
            cat_tabs_set = {t.name for t in cur_cat.tabs}

        # 建立全局分类标签归属映射: tab_name / canonical -> [category_name, ...]
        assigned_map = {}
        for c in categories:
            for t_item in c.tabs:
                assigned_map.setdefault(t_item.name, []).append(c.name)
                canon = classifier.resolve_canonical_tab(t_item.name)
                if canon and canon != t_item.name:
                    assigned_map.setdefault(canon, []).append(c.name)

        # 根据当前过滤选项动态计算参与展示的可用标签集合
        def _is_tab_visible(t_name):
            if settings.filter_live_only and not core.is_tab_live(t_name, context, space_type=st):
                return False
            if settings.filter_addons_only and not core.get_tab_origin_badge(t_name, space_type=st)[1]:
                return False
            return True

        visible_all_tabs = [t for t in all_tabs if _is_tab_visible(t)]

        # 计算当前完全未归入任何分类的独立未归档标签
        unassigned_tabs = [
            t for t in visible_all_tabs
            if t not in assigned_map and (not classifier.resolve_canonical_tab(t) or classifier.resolve_canonical_tab(t) not in assigned_map)
        ]

        search_q = settings.search_query.strip().lower()

        right_col = right_split.column()
        right_box = right_col.box()
        right_header = right_box.row(align=True)
        right_header.label(
            text=f"{_T('可用标签池')} (共 {len(visible_all_tabs)} 项 · 待归档 {len(unassigned_tabs)} 项)",
            icon="LAYER_USED"
        )

        # 搜索过滤输入框与一键清空
        search_row = right_box.row(align=True)
        search_row.prop(settings, "search_query", text="", icon="VIEWZOOM")
        if settings.search_query:
            search_row.operator("m8.npanel_clear_search", text="", icon="X")

        # 3 个多维精准过滤切换按钮：[未归类] [当前可见] [仅插件]
        filter_row = right_box.row(align=True)
        filter_row.prop(settings, "filter_unassigned_only", text=_T("未归类"), toggle=True, icon="FILTER")
        filter_row.prop(settings, "filter_live_only", text=_T("当前可见"), toggle=True, icon="RESTRICT_VIEW_OFF")
        filter_row.prop(settings, "filter_addons_only", text=_T("仅插件"), toggle=True, icon="PACKAGE")

        # 当存在未归类标签且当前选中分类时，提供醒目的「一键收纳未归类」快捷横条（精简文案避免裁切）
        if cur_cat and unassigned_tabs:
            batch_row = right_box.row(align=True)
            batch_op = batch_row.operator(
                "m8.npanel_add_all_unassigned",
                text=f"{_T('一键收纳未归类')} ({len(unassigned_tabs)})",
                icon="FORWARD"
            )
            batch_op.space_type = st

        pool_col = right_box.column(align=True)
        added_count = 0
        for t in visible_all_tabs:
            canon_t = classifier.resolve_canonical_tab(t)
            # 已在当前选中分类中的子标签，不在右侧池重复显示（已在中栏展示）
            if t in cat_tabs_set or (canon_t and canon_t in cat_tabs_set):
                continue

            cats_for_t = assigned_map.get(t) or (assigned_map.get(canon_t) if canon_t else None)
            is_assigned = bool(cats_for_t)

            # 开启「仅看未归类」时过滤掉已归档在其他分类中的标签
            if settings.filter_unassigned_only and is_assigned:
                continue

            # 获取标签来源特征与视口可见性
            badge_text, is_addon = core.get_tab_origin_badge(t, space_type=st)
            is_live = core.is_tab_live(t, context, space_type=st)

            display_label = classifier.get_tab_display_label(t)
            match_str = f"{t} {display_label} {badge_text}".lower()
            if search_q and search_q not in match_str:
                continue

            # 确定行图标
            if is_assigned:
                icon_name = "CHECKMARK"
            elif not is_addon:
                icon_name = "BLENDER"
            elif not is_live:
                icon_name = "RESTRICT_VIEW_ON"
            else:
                icon_name = "BOOKMARKS"

            # 格式化展示文本：标签名 + 来源/分类标记
            if is_assigned:
                if len(cats_for_t) == 1:
                    c_badge = f"[{cats_for_t[0]}]"
                else:
                    c_badge = f"[{_T('已在')} {len(cats_for_t)} {_T('个分类')}]"
                full_label = f"{display_label} {c_badge} · {badge_text}"
            else:
                full_label = f"{display_label}  [{badge_text}]"

            pool_row = pool_col.row(align=True)
            split_r = pool_row.split(factor=0.82, align=True)
            split_r.label(text=full_label, translate=False, icon=icon_name)

            btn_row = split_r.row(align=True)
            if is_assigned:
                # 1. [+] 添加（支持多分类重复添加/共享引用）
                add_op = btn_row.operator("m8.npanel_add_tab_to_category", text="", icon="ADD")
                add_op.tab_name = t
                add_op.space_type = st
                add_op.move_from_other = False

                # 2. [⇄] 转移（从原分类移出并转移至当前分类）
                trans_op = btn_row.operator("m8.npanel_add_tab_to_category", text="", icon="ARROW_LEFTRIGHT")
                trans_op.tab_name = t
                trans_op.space_type = st
                trans_op.move_from_other = True
            else:
                # 未归类标签
                add_op = btn_row.operator("m8.npanel_add_tab_to_category", text="", icon="ADD")
                add_op.tab_name = t
                add_op.space_type = st
                add_op.move_from_other = False
                btn_row.label(text="")  # 占位使两列按钮宽度严格对齐

            added_count += 1
            if added_count >= 100:
                pool_col.label(text=_T("...（更多标签请输入关键字搜索）"))
                break

        if added_count == 0:
            if settings.filter_live_only and settings.filter_addons_only:
                pool_col.label(text=_T("当前模式下暂无可见的第三方插件标签"), icon="INFO")
            elif settings.filter_live_only:
                pool_col.label(text=_T("当前模式下暂无物理渲染中的可见标签"), icon="INFO")
            elif settings.filter_addons_only:
                pool_col.label(text=_T("未检测到其他第三方插件标签"), icon="INFO")
            elif settings.filter_unassigned_only:
                pool_col.label(text=_T("所有可用标签均已完成归类！"), icon="CHECKMARK")
            else:
                pool_col.label(text=_T("暂无匹配的标签"), icon="CHECKMARK")

        # 3. 底部操作快捷工具条
        layout.separator(factor=0.5)
        bot_row = layout.row(align=True)
        bot_row.scale_y = 1.25
        auto_op = bot_row.operator("m8.npanel_smart_auto_group", text=_T("⚡ 智能一键归档"), icon="AUTO")
        auto_op.space_type = st
        rst_op = bot_row.operator("m8.npanel_restore_default", text=_T("🔄 恢复默认侧栏"), icon="RECOVER_LAST")
        rst_op.space_type = st
        app_op = bot_row.operator("m8.npanel_apply", text=_T("✔ 立即应用"), icon="CHECKMARK")
        app_op.space_type = st
        bot_row.separator()
        bot_row.operator("m8.npanel_export_config", text=_T("📤 导出备份"), icon="EXPORT")
        bot_row.operator("m8.npanel_import_config", text=_T("📥 导入备份"), icon="IMPORT")


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
        sub_box.prop(settings, "show_subtabs_header", text=_T("显示分类面板标题栏"))
        sub_box.prop(settings, "workspace_auto_switch", text=_T("根据工作区自动切换分类"))
        sub_box.prop(settings, "max_tabs_per_row", text=_T("每行最多按钮数"))
        sub_box.prop(settings, "excluded_tabs", text=_T("排除标签白名单"))


UI_CLASSES = (
    M8_UL_NPanelCategoryList,
    M8_OT_NPanelOpenManager,
)
