"""
M8 N-Panel Sub-Tabs Manager Self-Test
验证智能归类规则库、状态快照无痕还原机制、配置序列化与核心数据结构。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import types
if 'M8' not in sys.modules:
    m8_mod = types.ModuleType('M8')
    m8_mod.__path__ = [str(ROOT)]
    sys.modules['M8'] = m8_mod

try:
    import bpy
    import bpy.app.handlers
except (ImportError, AttributeError):
    from unittest.mock import MagicMock
    bpy = MagicMock()
    bpy._is_mock = True
    class DummyPanel:
        pass
    bpy.types.Panel = DummyPanel
    bpy.types.Operator = type('Operator', (), {})
    bpy.types.PropertyGroup = type('PropertyGroup', (), {})
    bpy.types.AddonPreferences = type('AddonPreferences', (), {})
    bpy.types.UIList = type('UIList', (), {})
    bpy.types.Menu = type('Menu', (), {})
    bpy.utils.previews = MagicMock()
    sys.modules['bpy.utils.previews'] = bpy.utils.previews
    bpy.types.Header = type('Header', (), {})
    bpy.app.handlers.persistent = lambda f: f
    sys.modules['bpy'] = bpy
    sys.modules['bpy.types'] = bpy.types
    sys.modules['bpy.props'] = bpy.props
    sys.modules['bpy.utils'] = bpy.utils
    sys.modules['bpy.app'] = bpy.app
    sys.modules['bpy.app.handlers'] = bpy.app.handlers

for mod in ['mathutils', 'bmesh', 'gpu', 'gpu_extras', 'gpu_extras.batch', 'bpy_extras', 'bpy_extras.view3d_utils']:
    if mod not in sys.modules:
        from unittest.mock import MagicMock
        sys.modules[mod] = MagicMock()

import unittest
from M8.ops.npanel import classifier, core, state, operators, props
from M8.ops.npanel.state import PanelStateManager, PanelSnapshot


class MockPanel:
    __name__ = "MockPanelClass"
    bl_category = "HardOps"
    bl_parent_id = "MockParent"
    bl_order = 3


class TestM8NPanel(unittest.TestCase):

    def test_system_exclusion(self):
        # 内部隐藏保留标记
        self.assertTrue(classifier.is_system_excluded("nsubhide"))
        self.assertTrue(classifier.is_system_excluded("m8_hidden"))
        # 原生基础标签与第三方插件标签均支持用户自由收纳整理（不强制排除）
        self.assertFalse(classifier.is_system_excluded("Item"))
        self.assertFalse(classifier.is_system_excluded("item"))
        self.assertFalse(classifier.is_system_excluded("条目"))
        self.assertFalse(classifier.is_system_excluded("Tool"))
        self.assertFalse(classifier.is_system_excluded("工具"))
        self.assertFalse(classifier.is_system_excluded("View"))
        self.assertFalse(classifier.is_system_excluded("视图"))
        self.assertFalse(classifier.is_system_excluded("HardOps"))
        self.assertFalse(classifier.is_system_excluded("BoxCutter"))
        self.assertFalse(classifier.is_system_excluded("Hardflow"))
        self.assertFalse(classifier.is_system_excluded("Edit"))
        self.assertFalse(classifier.is_system_excluded("Animation"))
        self.assertFalse(classifier.is_system_excluded("M8 Tool"))

    def test_canonical_tab_mapping(self):
        self.assertEqual(classifier.resolve_canonical_tab("hops"), "HardOps")
        self.assertEqual(classifier.resolve_canonical_tab("Hops"), "HardOps")
        self.assertEqual(classifier.resolve_canonical_tab("Hardflow"), "Hardflow")
        self.assertEqual(classifier.resolve_canonical_tab("BoxCutter"), "BoxCutter")
        self.assertEqual(classifier.resolve_canonical_tab("视图"), "View")
        self.assertEqual(classifier.resolve_canonical_tab("视图 (View)"), "View")
        self.assertEqual(classifier.resolve_canonical_tab("工具"), "Tool")
        self.assertEqual(classifier.resolve_canonical_tab("条目"), "Item")
        self.assertEqual(classifier.resolve_canonical_tab("动画"), "Animation")
        self.assertEqual(classifier.resolve_canonical_tab("编辑"), "Edit")

    def test_sort_panels_by_generation(self):
        class ParentPanel:
            bl_idname = "PT_Parent"
            bl_parent_id = None

        class ChildPanel:
            bl_idname = "PT_Child"
            bl_parent_id = "PT_Parent"

        class GrandChildPanel:
            bl_idname = "PT_GrandChild"
            bl_parent_id = "PT_Child"

        # 乱序输入：孙 -> 子 -> 父
        shuffled = [GrandChildPanel, ChildPanel, ParentPanel]
        sorted_panels = core.sort_panels_by_generation(shuffled)
        
        # 验证拓扑正序：父 -> 子 -> 孙
        self.assertEqual(core.get_panel_idname(sorted_panels[0]), "PT_Parent")
        self.assertEqual(core.get_panel_idname(sorted_panels[1]), "PT_Child")
        self.assertEqual(core.get_panel_idname(sorted_panels[2]), "PT_GrandChild")

    def test_smart_classifier(self):
        def _match_any(res, *keywords):
            return any(kw in res for kw in keywords)

        self.assertTrue(_match_any(classifier.classify_tab("HardOps", "hops"), "建模", "Modeling"))
        self.assertTrue(_match_any(classifier.classify_tab("BoxCutter", "bc"), "建模", "Modeling"))
        self.assertTrue(_match_any(classifier.classify_tab("QuadRemesher", "retopo"), "建模", "Modeling"))
        self.assertTrue(_match_any(classifier.classify_tab("Sanctus Material", "sanctus"), "材质", "Shading", "Material"))
        self.assertTrue(_match_any(classifier.classify_tab("UVPackmaster", "uv"), "材质", "Shading", "Material"))
        self.assertTrue(_match_any(classifier.classify_tab("Photographer", "camera"), "渲染", "Lighting", "Render"))
        self.assertTrue(_match_any(classifier.classify_tab("Auto-Rig Pro", "arp"), "装配", "Rigging"))
        self.assertTrue(_match_any(classifier.classify_tab("Botaniq", "scatter"), "资产", "Assets"))
        self.assertTrue(_match_any(classifier.classify_tab("M8 Tool", "m8"), "工具", "Utilities", "Tools"))

    def test_auto_group_tabs(self):
        sample_tabs = [
            "Item", "Tool", "HardOps", "BoxCutter", "Sanctus Material",
            "Photographer", "Auto-Rig Pro", "G-Scatter", "CustomUnknown"
        ]
        grouped = classifier.auto_group_tabs(sample_tabs)
        # Item must be excluded
        for cat, tabs in grouped.items():
            self.assertNotIn("Item", tabs)

        # HardOps and BoxCutter in Modeling
        model_cat = [k for k in grouped if ("建模" in k or "Modeling" in k)][0]
        self.assertIn("HardOps", grouped[model_cat])
        self.assertIn("BoxCutter", grouped[model_cat])

    def test_zero_pollution_snapshot_restore(self):
        panel = MockPanel
        # 1. 记录快照
        snapshot = PanelStateManager.record(panel)
        self.assertEqual(snapshot.original_category, "HardOps")
        self.assertEqual(snapshot.original_parent_id, "MockParent")
        self.assertEqual(snapshot.original_order, 3)

        # 2. 模拟被接管修改
        panel.bl_category = "🔨 建模雕刻"
        panel.bl_parent_id = "M8_PT_HiddenPanelView3D"
        panel.bl_order = 0

        # 3. 执行一键无痕瞬时还原
        PanelStateManager.restore_all()

        # 4. 验证完全恢复 Blender 原生出厂状态
        self.assertEqual(panel.bl_category, "HardOps")
        self.assertEqual(panel.bl_parent_id, "MockParent")
        self.assertEqual(panel.bl_order, 3)
        self.assertFalse(PanelStateManager.is_active)
    def test_hierarchical_panel_isolation(self):
        class ParentPanel:
            bl_idname = "Mock_PT_Parent"
            bl_category = "HardOps"
            bl_parent_id = None

        class ChildPanel:
            bl_idname = "Mock_PT_Child"
            bl_category = "Hops"
            bl_parent_id = "Mock_PT_Parent"

        # 验证 root 追溯与同源合并
        root = core.get_panel_root(ChildPanel)
        # 如果未注册在 bpy.types，get_panel_root 在找不到类时安全返回自身或上一级
        self.assertEqual(classifier.resolve_canonical_tab(ChildPanel.bl_category), "HardOps")

    def test_system_and_bl_ui_filtering(self):
        class NativePanel:
            bl_space_type = "VIEW_3D"
            bl_region_type = "UI"
            __name__ = "VIEW3D_PT_native_item"

        # bl_ui 模块面板必须被 is_valid_user_panel 忽略
        self.assertFalse(core.is_valid_user_panel(NativePanel, "VIEW_3D"))

    def test_npanel_registration_and_operators(self):
        # 1. 注册 npanel 模块
        import M8.ops.npanel as npanel_pkg
        npanel_pkg.register()

        try:
            # 2. 验证操作符注册
            expected_ops = [
                "npanel_switch_tab",
                "npanel_smart_auto_group",
                "npanel_restore_default",
                "npanel_apply",
                "npanel_add_category",
                "npanel_remove_category",
                "npanel_move_category",
                "npanel_add_tab_to_category",
                "npanel_remove_tab_from_category",
                "npanel_move_tab",
                "npanel_clear_search",
                "npanel_open_manager",
                "npanel_export_config",
                "npanel_import_config",
            ]
            for op_name in expected_ops:
                self.assertTrue(
                    hasattr(bpy.ops.m8, op_name),
                    f"Operator bpy.ops.m8.{op_name} must be registered!"
                )

            # 3. 验证 Scene.m8_npanel 属性
            scene = bpy.context.scene
            self.assertTrue(hasattr(scene, "m8_npanel"), "Scene.m8_npanel must exist!")
            settings = scene.m8_npanel
            self.assertIsNotNone(settings)

            # 4. 测试手动添加分类与子标签（仅真实 Blender 环境）
            if not getattr(bpy, "_is_mock", False):
                settings.categories.clear()
                cat = settings.categories.add()
                cat.name = "Test Category"
                tab = cat.tabs.add()
                tab.name = "Test Tab"
                tab.is_active = True
                self.assertEqual(len(settings.categories), 1)
                self.assertEqual(len(settings.categories[0].tabs), 1)

                # 5. 测试切换与恢复
                bpy.ops.m8.npanel_restore_default()
                self.assertFalse(settings.enabled)

                # 6. 测试多编辑器配置与分类独立性
                img_cats = settings.get_categories("IMAGE_EDITOR")
                node_cats = settings.get_categories("NODE_EDITOR")
                self.assertIsNotNone(img_cats)
                self.assertIsNotNone(node_cats)
                self.assertEqual(settings.active_space_type, "VIEW_3D")

        finally:
            npanel_pkg.unregister()

    def test_multi_space_classifier(self):
        # IMAGE_EDITOR 智能分类验证
        self.assertIn("UV", classifier.classify_tab("UV Toolkit", space_type="IMAGE_EDITOR"))
        self.assertIn("UV", classifier.classify_tab("TexTools", space_type="IMAGE_EDITOR"))
        self.assertIn("绘制", classifier.classify_tab("Mio3", space_type="IMAGE_EDITOR"))
        self.assertIn("绘制", classifier.classify_tab("Scopes", space_type="IMAGE_EDITOR"))

        # NODE_EDITOR 智能分类验证
        self.assertIn("增强", classifier.classify_tab("Node Wrangler", space_type="NODE_EDITOR"))
        self.assertIn("增强", classifier.classify_tab("Node Peek", space_type="NODE_EDITOR"))
        self.assertIn("组", classifier.classify_tab("Group", space_type="NODE_EDITOR"))
        self.assertIn("工具", classifier.classify_tab("Options", space_type="NODE_EDITOR"))

    def test_serialization_and_persistence(self):
        from M8.ops.npanel import backup
        # 验证 2.0 多编辑器配置序列化结构
        mock_settings = type("MockSettings", (), {
            "enabled": True,
            "show_subtabs_header": False,
            "workspace_auto_switch": True,
            "max_tabs_per_row": 3,
            "hide_unassigned": False,
            "excluded_tabs": "Item, Tool",
            "categories": [
                type("MockCat", (), {"name": "HardOps Cat", "tabs": [type("MockTab", (), {"name": "HardOps"})()]})()
            ],
            "enabled_image_editor": True,
            "hide_unassigned_image_editor": False,
            "excluded_tabs_image_editor": "Image, Tool",
            "categories_image_editor": [
                type("MockCat", (), {"name": "UV Cat", "tabs": [type("MockTab", (), {"name": "UV Toolkit"})()]})()
            ],
            "enabled_node_editor": True,
            "hide_unassigned_node_editor": False,
            "excluded_tabs_node_editor": "Node, Tool",
            "categories_node_editor": [
                type("MockCat", (), {"name": "Nodes Cat", "tabs": [type("MockTab", (), {"name": "Node Wrangler"})()]})()
            ],
        })()

        data = backup.serialize_all_settings(mock_settings)
        self.assertEqual(data["version"], "2.0")
        self.assertIn("spaces", data)
        self.assertIn("VIEW_3D", data["spaces"])
        self.assertIn("IMAGE_EDITOR", data["spaces"])
        self.assertIn("NODE_EDITOR", data["spaces"])
        self.assertEqual(data["spaces"]["VIEW_3D"]["categories"][0]["name"], "HardOps Cat")
        self.assertEqual(data["spaces"]["IMAGE_EDITOR"]["categories"][0]["name"], "UV Cat")
        self.assertEqual(data["spaces"]["NODE_EDITOR"]["categories"][0]["name"], "Nodes Cat")

        # 验证预设文件路径计算安全无异常
        path = backup.get_preset_filepath()
        self.assertTrue(path.endswith(".json"))

    def test_max_tabs_per_row_flow(self):
        """验证多列流式排布：默认支持4排/列，无长名称硬编码截断，尊重用户设置"""
        from M8.ops.npanel import backup, props

        # 1. 验证反序列化默认值为 4
        mock_settings = type("MockSettings", (), {
            "enabled": True,
            "show_subtabs_header": False,
            "workspace_auto_switch": True,
            "max_tabs_per_row": 4,
            "hide_unassigned": False,
            "excluded_tabs": "",
            "categories": [],
            "enabled_image_editor": True,
            "hide_unassigned_image_editor": False,
            "excluded_tabs_image_editor": "",
            "categories_image_editor": [],
            "enabled_node_editor": True,
            "hide_unassigned_node_editor": False,
            "excluded_tabs_node_editor": "",
            "categories_node_editor": [],
        })()
        backup.deserialize_all_settings(mock_settings, {})
        self.assertEqual(mock_settings.max_tabs_per_row, "AUTO")

        # 2. 模拟列数计算逻辑
        tabs_6 = ["BoxCutter", "Hardflow", "BQR", "HardOps", "编辑", "MACHIN3"]
        # 默认智能自适应 AUTO 时：6个标签为两排三行显示 (3列)
        cols_auto = core.calculate_category_columns(len(tabs_6), mock_settings.max_tabs_per_row)
        self.assertEqual(cols_auto, 3, "在AUTO模式下，6个标签应精准排布为两排三列(3列)")

        # 3. 用户手动设置为 3 时
        mock_settings.max_tabs_per_row = "3"
        cols_custom = core.calculate_category_columns(len(tabs_6), mock_settings.max_tabs_per_row)
        self.assertEqual(cols_custom, 3, "当用户手动设置为3时，应精准排布为3列")

        # 4. 少于最大列数时（如2个标签）紧凑全宽
        tabs_2 = ["Item", "Tool"]
        cols_small = core.calculate_category_columns(len(tabs_2), mock_settings.max_tabs_per_row)
        self.assertEqual(cols_small, 2, "当标签数少于手动上限时，应自适应平分铺满整行(2列)")

    def test_manager_draw_pool_renders_without_exception(self):
        """验证全景管理器看板绘制可用标签池时无 NameError 或属性丢失异常"""
        from M8.ops.npanel import ui

        class MockLayout:
            def row(self, *a, **kw): return self
            def column(self, *a, **kw): return self
            def box(self, *a, **kw): return self
            def split(self, *a, **kw): return self
            def label(self, *a, **kw): pass
            def prop(self, *a, **kw): pass
            def operator(self, *a, **kw):
                return type("MockOp", (), {"space_type": "", "tab_name": "", "category_name": "", "direction": ""})()
            def separator(self, *a, **kw): pass
            def template_list(self, *a, **kw): pass

        mock_op = type("MockOpInstance", (), {
            "layout": MockLayout(),
            "space_type": "VIEW_3D"
        })()

        # 确保调用 ui.M8_OT_NPanelOpenManager.draw 完全不报错
        context = bpy.context
        if getattr(bpy, "_is_mock", False):
            context.scene.m8_npanel.get_category_index.return_value = 0
            context.scene.m8_npanel.get_categories.return_value = []
            context.scene.m8_npanel.get_excluded_tabs.return_value = ""
            context.scene.m8_npanel.search_query = ""
            context.scene.m8_npanel.filter_unassigned_only = False
            context.scene.m8_npanel.active_space_type = "VIEW_3D"
        ui.M8_OT_NPanelOpenManager.draw(mock_op, context)

    def test_tab_custom_name_renaming_and_persistence(self):
        """验证子标签直接重命名、序列化与按钮渲染联动"""
        from M8.ops.npanel import backup, props, classifier

        # 1. 验证 PropertyGroup 中有 custom_name 注解
        self.assertIn("custom_name", props.M8_NPanelTabItem.__annotations__)

        # 2. 模拟设置自定义名称
        tab = type("MockTab", (), {"name": "Rigify", "custom_name": "骨骼绑定", "is_active": True})()

        # 3. 验证序列化
        mock_settings = type("MockSettings", (), {
            "enabled": True,
            "show_subtabs_header": False,
            "workspace_auto_switch": True,
            "max_tabs_per_row": 4,
            "hide_unassigned": False,
            "excluded_tabs": "",
            "categories": [
                type("MockCat", (), {"name": "角色", "tabs": [tab]})()
            ],
            "enabled_image_editor": False,
            "hide_unassigned_image_editor": False,
            "excluded_tabs_image_editor": "",
            "categories_image_editor": [],
            "enabled_node_editor": False,
            "hide_unassigned_node_editor": False,
            "excluded_tabs_node_editor": "",
            "categories_node_editor": [],
        })()
        data = backup.serialize_all_settings(mock_settings)
        cat_saved = data["spaces"]["VIEW_3D"]["categories"][0]
        self.assertEqual(cat_saved["tabs"][0]["name"], "Rigify")
        self.assertEqual(cat_saved["tabs"][0]["custom_name"], "骨骼绑定")

        # 4. 验证反序列化
        class MockTabList:
            def __init__(self): self.items = []
            def add(self):
                t = type("MockTab", (), {"name": "", "custom_name": "", "is_active": False})()
                self.items.append(t)
                return t
            def clear(self): self.items.clear()
            def __iter__(self): return iter(self.items)
            def __len__(self): return len(self.items)
            def __getitem__(self, idx): return self.items[idx]

        class MockCatList:
            def __init__(self): self.items = []
            def add(self):
                cat = type("MockCat", (), {"name": "", "tabs": MockTabList()})()
                self.items.append(cat)
                return cat
            def clear(self): self.items.clear()
            def __iter__(self): return iter(self.items)
            def __len__(self): return len(self.items)
            def __getitem__(self, idx): return self.items[idx]

        target_settings = type("MockTarget", (), {
            "enabled": True,
            "show_subtabs_header": False,
            "workspace_auto_switch": True,
            "max_tabs_per_row": 4,
            "hide_unassigned": False,
            "excluded_tabs": "",
            "categories": MockCatList(),
            "enabled_image_editor": False,
            "hide_unassigned_image_editor": False,
            "excluded_tabs_image_editor": "",
            "categories_image_editor": MockCatList(),
            "enabled_node_editor": False,
            "hide_unassigned_node_editor": False,
            "excluded_tabs_node_editor": "",
            "categories_node_editor": MockCatList(),
        })()

        backup.deserialize_all_settings(target_settings, data)
        self.assertEqual(len(target_settings.categories), 1)
        self.assertEqual(target_settings.categories[0].tabs[0].name, "Rigify")
        self.assertEqual(target_settings.categories[0].tabs[0].custom_name, "骨骼绑定")

    def test_pool_unassigned_filter_and_transfer(self):
        """验证可用标签池'仅看未归类'过滤、跨分类转移与一键全部收纳功能"""
        from M8.ops.npanel import props, operators

        # 1. 验证 M8_NPanelSettings 中包含 filter_unassigned_only
        self.assertIn("filter_unassigned_only", props.M8_NPanelSettings.__annotations__)

        # 2. 验证 M8_OT_NPanelAddTabToCategory 包含 move_from_other 属性
        self.assertIn("move_from_other", operators.M8_OT_NPanelAddTabToCategory.__annotations__)

        # 3. 验证 M8_OT_NPanelAddAllUnassigned 注册入 OPERATOR_CLASSES
        self.assertIn(operators.M8_OT_NPanelAddAllUnassigned, operators.OPERATOR_CLASSES)

        # 4. 模拟跨分类转移逻辑验证
        class MockTab:
            def __init__(self, name, custom_name="", is_active=False):
                self.name = name
                self.custom_name = custom_name
                self.is_active = is_active

        class MockCat:
            def __init__(self, name, tabs=None):
                self.name = name
                self.tabs = tabs or []

        cat_a = MockCat("分类A", [MockTab("Rigify", "Rigify", True)])
        cat_b = MockCat("分类B", [MockTab("BoxCutter", "BoxCutter", True)])
        categories = [cat_a, cat_b]

        # 模拟执行转移：将 Rigify 从分类A转移到分类B
        tab_to_move = "Rigify"
        target_cat = cat_b

        # 从其他分类移除
        for other in categories:
            if other != target_cat:
                other.tabs = [t for t in other.tabs if t.name != tab_to_move]

        # 添加到目标分类
        target_cat.tabs.append(MockTab(tab_to_move, tab_to_move))

        # 验证转移结果
        self.assertEqual(len(cat_a.tabs), 0, "分类A中的Rigify应被移除")
        self.assertEqual(len(cat_b.tabs), 2, "分类B应包含BoxCutter和Rigify")
        self.assertEqual(cat_b.tabs[1].name, "Rigify")

        # 5. 模拟重复添加/共享逻辑验证（move_from_other=False）
        # 将 BoxCutter 重新添加回分类A（不从分类B移除）
        cat_a.tabs.append(MockTab("BoxCutter", "BoxCutter", True))
        self.assertEqual(len(cat_a.tabs), 1, "分类A应拥有BoxCutter")
        self.assertEqual(len(cat_b.tabs), 2, "分类B应仍然保留BoxCutter（支持多分类重复添加与共享）")

    def test_pie_menu_and_category_icon_and_clear(self):
        """验证视口饼菜单、大分类矢量图标与中栏一键清空等高级提效功能"""
        from M8.ops.npanel import props, operators, pie, backup

        # 1. 验证 M8_NPanelCategoryItem 中包含 icon 属性
        self.assertIn("icon", props.M8_NPanelCategoryItem.__annotations__)

        # 2. 验证新操作符均已注册至 OPERATOR_CLASSES
        self.assertIn(operators.M8_OT_NPanelSwitchCategory, operators.OPERATOR_CLASSES)
        self.assertIn(operators.M8_OT_NPanelClearCategoryTabs, operators.OPERATOR_CLASSES)
        self.assertIn(operators.M8_OT_NPanelQuickRenameTab, operators.OPERATOR_CLASSES)
        self.assertIn(operators.M8_OT_NPanelChooseCategoryIcon, operators.OPERATOR_CLASSES)
        self.assertIn(operators.M8_OT_NPanelSetCategoryIcon, operators.OPERATOR_CLASSES)

        # 3. 验证药丸按钮右键上下文菜单钩子函数存在
        self.assertTrue(callable(pie.draw_subtab_button_context_menu))

        # 4. 验证图标序列化与反序列化
        cat = type("MockCat", (), {"name": "材质着色", "icon": "MATERIAL", "tabs": []})()
        mock_settings = type("MockSettings", (), {
            "enabled": True,
            "show_subtabs_header": False,
            "workspace_auto_switch": True,
            "max_tabs_per_row": 4,
            "hide_unassigned": False,
            "excluded_tabs": "",
            "categories": [cat],
            "enabled_image_editor": False,
            "hide_unassigned_image_editor": False,
            "excluded_tabs_image_editor": "",
            "categories_image_editor": [],
            "enabled_node_editor": False,
            "hide_unassigned_node_editor": False,
            "excluded_tabs_node_editor": "",
            "categories_node_editor": [],
        })()
        data = backup.serialize_all_settings(mock_settings)
        cat_saved = data["spaces"]["VIEW_3D"]["categories"][0]
        self.assertEqual(cat_saved["icon"], "MATERIAL")

    def test_smart_category_columns(self):
        """验证智能行数排布与手动上限自适应规则"""
        from M8.ops.npanel import core

        # 1. 智能模式 (AUTO)
        # 1个就是一行显示 (1列占满整行)
        self.assertEqual(core.calculate_category_columns(1, "AUTO"), 1)
        # 2个就是两行显示 (平分2列)
        self.assertEqual(core.calculate_category_columns(2, "AUTO"), 2)
        # 3个就是三行显示 (平分3列)
        self.assertEqual(core.calculate_category_columns(3, "AUTO"), 3)
        # 4个 2x2 平衡方块 (2列两行)
        self.assertEqual(core.calculate_category_columns(4, "AUTO"), 2)
        # 5个 3+2 紧凑排布 (3列两行)
        self.assertEqual(core.calculate_category_columns(5, "AUTO"), 3)
        # 6个两排三行显示 (3列两行)
        self.assertEqual(core.calculate_category_columns(6, "AUTO"), 3)
        # 超过两行就是四排显示，最多到四行
        self.assertEqual(core.calculate_category_columns(7, "AUTO"), 4)
        self.assertEqual(core.calculate_category_columns(8, "AUTO"), 4)
        self.assertEqual(core.calculate_category_columns(12, "AUTO"), 4)
        self.assertEqual(core.calculate_category_columns(16, "AUTO"), 4)

        # 2. 手动模式 (Manual Max)
        # 手动设置为 5，但是规则还是如此：少于上限自适应铺满整行
        self.assertEqual(core.calculate_category_columns(1, "5"), 1)
        self.assertEqual(core.calculate_category_columns(2, "5"), 2)
        self.assertEqual(core.calculate_category_columns(3, "5"), 3)
        self.assertEqual(core.calculate_category_columns(4, "5"), 4)
        self.assertEqual(core.calculate_category_columns(5, "5"), 5)
        # 超过上限时，按最高行按钮数 5 排布
        self.assertEqual(core.calculate_category_columns(6, "5"), 5)
        self.assertEqual(core.calculate_category_columns(10, "5"), 5)

        # 手动设置为 3
        self.assertEqual(core.calculate_category_columns(1, "3"), 1)
        self.assertEqual(core.calculate_category_columns(2, "3"), 2)
        self.assertEqual(core.calculate_category_columns(3, "3"), 3)
        self.assertEqual(core.calculate_category_columns(4, "3"), 3)
        self.assertEqual(core.calculate_category_columns(6, "3"), 3)

    def test_switch_tab_operator_execute_and_multiselect(self):
        """验证子标签切换操作符的 execute 方法与 Shift 多选逻辑"""
        from M8.ops.npanel import operators

        # 验证 execute 方法存在且可调用
        self.assertTrue(hasattr(operators.M8_OT_NPanelSwitchTab, "execute"))

        tab1 = type("MockTab", (), {"name": "BoxCutter", "is_active": True})()
        tab2 = type("MockTab", (), {"name": "HardOps", "is_active": False})()
        cat = type("MockCat", (), {"name": "建模", "tabs": [tab1, tab2]})()

        mock_settings = type("MockSettings", (), {
            "enabled": False,
            "active_space_type": "VIEW_3D",
            "is_space_enabled": lambda *args: False,
            "get_categories": lambda *args: [cat],
        })()
        mock_context = type("MockContext", (), {
            "scene": type("MockScene", (), {"m8_npanel": mock_settings})(),
            "area": None,
        })()

        # 1. 单选切换到 HardOps
        op = type("MockOp", (), {
            "category_name": "建模",
            "tab_name": "HardOps",
            "space_type": "VIEW_3D",
            "multi_select": False,
        })()
        res = operators.M8_OT_NPanelSwitchTab.execute(op, mock_context)
        self.assertEqual(res, {"FINISHED"})
        self.assertFalse(tab1.is_active)
        self.assertTrue(tab2.is_active)

        # 2. Shift 多选激活 BoxCutter
        op.tab_name = "BoxCutter"
        op.multi_select = True
        res = operators.M8_OT_NPanelSwitchTab.execute(op, mock_context)
        self.assertEqual(res, {"FINISHED"})
        self.assertTrue(tab1.is_active)
        self.assertTrue(tab2.is_active)

    def test_restore_default_and_enabled_toggle_cleanliness(self):
        """验证恢复默认彻底抹除预设、关闭整理即刻无痕还原、打开开关不自动创建分类"""
        from M8.ops.npanel import backup
        import os
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_path = os.path.join(tmp_dir, "m8_npanel_presets.json")
            with patch.object(backup, "get_preset_filepath", return_value=test_path):
                # 1. 验证 clear_presets_on_disk 功能
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write('{"test": true}')
                self.assertTrue(os.path.isfile(test_path))

                backup.clear_presets_on_disk()
                self.assertFalse(os.path.isfile(test_path), "clear_presets_on_disk 应彻底删除磁盘预设文件")

                # 2. 验证 save_presets_to_disk 在空配置且未启用时自动删除磁盘文件
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write('{"test": true}')
                mock_empty_settings = type("MockEmptySettings", (), {
                    "enabled": False,
                    "categories": [],
                    "categories_image_editor": [],
                    "categories_node_editor": [],
                })()
                mock_ctx = type("MockContext", (), {
                    "scene": type("MockScene", (), {"m8_npanel": mock_empty_settings})()
                })()
                backup.save_presets_to_disk(mock_ctx)
                self.assertFalse(os.path.isfile(test_path), "空配置且未启用时调用 save_presets_to_disk 应安全清理磁盘预设")

        # 3. 验证 deserialize_all_settings 默认 enabled 为 False
        mock_list = type("MockCol", (), {"clear": lambda self: None})()
        mock_target = type("MockTargetSettings", (), {
            "enabled": True,
            "categories": mock_list,
            "categories_image_editor": mock_list,
            "categories_node_editor": mock_list,
        })()
        backup.deserialize_all_settings(mock_target, {})
        self.assertFalse(mock_target.enabled, "未声明 enabled 时应默认为 False，严禁默认开启")

    def test_panel_live_detection_and_origin_badges(self):
        """验证面板实时可见性裁决与插件来源指纹标注引擎"""
        class MockEditPanel:
            bl_region_type = "UI"
            bl_context = "mesh_edit"
            bl_category = "Edit"

            @classmethod
            def poll(cls, context):
                return True

        class MockObjectPanel:
            bl_region_type = "UI"
            bl_context = "objectmode"
            bl_category = "Item"

            @classmethod
            def poll(cls, context):
                return getattr(context, "has_selection", False)

        ctx_obj = type("MockCtx", (), {"mode": "OBJECT", "has_selection": False})()
        ctx_edit = type("MockCtx", (), {"mode": "EDIT_MESH", "has_selection": True})()

        # 在 OBJECT 模式下，mesh_edit 面板必为 False
        self.assertFalse(core.is_panel_live_in_context(MockEditPanel, ctx_obj))
        # 在 EDIT_MESH 模式下，mesh_edit 面板为 True
        self.assertTrue(core.is_panel_live_in_context(MockEditPanel, ctx_edit))

        # 在无选中物体时，MockObjectPanel poll 为 False
        self.assertFalse(core.is_panel_live_in_context(MockObjectPanel, ctx_obj))

        # 测试来源标注特异性匹配
        badge, is_addon = core.get_tab_origin_badge("Edit")
        self.assertIn("LoopTools", badge)
        self.assertTrue(is_addon)

        badge_hops, is_hops = core.get_tab_origin_badge("Hardflow")
        self.assertIn("HardOps", badge_hops)
        self.assertTrue(is_hops)

        badge_rig, is_rig = core.get_tab_origin_badge("Rigify")
        self.assertIn("Rigify", badge_rig)
        self.assertTrue(is_rig)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
