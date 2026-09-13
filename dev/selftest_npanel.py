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
        self.assertTrue(classifier.is_system_excluded("Item"))
        self.assertTrue(classifier.is_system_excluded("Tool"))
        self.assertTrue(classifier.is_system_excluded("View"))
        self.assertTrue(classifier.is_system_excluded("item"))
        self.assertFalse(classifier.is_system_excluded("HardOps"))
        self.assertFalse(classifier.is_system_excluded("M8 Tool"))

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
        # Item and Tool must be excluded
        for cat, tabs in grouped.items():
            self.assertNotIn("Item", tabs)
            self.assertNotIn("Tool", tabs)

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
        self.assertEqual(len(PanelStateManager._snapshots), 0)

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

        finally:
            npanel_pkg.unregister()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
