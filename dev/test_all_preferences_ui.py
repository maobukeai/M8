import sys
import os
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

class MockUILayout:
    """Mock UILayout that simulates Blender's layout hierarchy."""
    def __init__(self):
        self.use_property_split = False
        self.use_property_decorate = False
        self.enabled = True
        self.alignment = "LEFT"
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.alert = False

    def row(self, align=False):
        return MockUILayout()

    def column(self, align=False):
        return MockUILayout()

    def split(self, factor=0.0, align=False):
        return MockUILayout()

    def box(self):
        return MockUILayout()

    def prop(self, data, property, text="", icon="NONE", toggle=False, **kwargs):
        pass

    def prop_enum(self, data, property, value, text="", icon="NONE", **kwargs):
        pass

    def label(self, text="", icon="NONE"):
        pass

    def operator(self, operator, text="", icon="NONE", **kwargs):
        return MockUILayout()

    def separator(self, factor=1.0):
        pass

    def menu(self, menu, text="", icon="NONE"):
        pass

    def template_icon(self, icon_value, scale=1.0):
        pass


def test_preferences_tabs():
    print("\n--- [Test 1] Addon Enable via bpy.ops ---")
    bpy.ops.preferences.addon_enable(module='M8')
    assert 'M8' in bpy.context.preferences.addons, "M8 addon not found in preferences.addons"
    prefs = bpy.context.preferences.addons['M8'].preferences
    assert prefs is not None, "Preferences object is None"
    print("[PASS] Addon enabled and real Preferences object retrieved.")

    print("\n--- [Test 2] Sidebar Width Property ---")
    assert hasattr(prefs, "sidebar_width"), "sidebar_width property not found on prefs"
    assert abs(prefs.sidebar_width - 0.22) < 0.001, f"Default width is {prefs.sidebar_width}, expected 0.22"
    print(f"[PASS] sidebar_width exists with default: {prefs.sidebar_width:.2f}")

    tabs = [it.identifier for it in prefs.bl_rna.properties['navigation_tab'].enum_items]
    print(f"\n--- [Test 3] Test Draw on All {len(tabs)} Tabs Individually ---")
    assert len(tabs) in (18, 19), f"Expected 18 or 19 tabs, got {len(tabs)}"

    # Temporarily set layout to mock
    mock_layout = MockUILayout()
    prefs.layout = mock_layout

    for tab in tabs:
        prefs.navigation_tab = tab
        prefs.ui_show_all_settings = False
        try:
            prefs.draw(bpy.context)
            print(f"  [OK] Tab: {tab}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise AssertionError(f"Failed to draw tab {tab}: {e}")

    print(f"[PASS] All {len(tabs)} tabs drew without any exceptions.")

    print("\n--- [Test 4] Test Draw in Show-All Settings Mode ---")
    prefs.ui_show_all_settings = True
    try:
        prefs.draw(bpy.context)
        print("[PASS] Show-All settings mode drew without any exceptions.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise AssertionError(f"Failed to draw show-all mode: {e}")

    print("\n--- [Test 5] Test Sidebar Width Adjustment ---")
    prefs.sidebar_width = 0.30
    assert abs(prefs.sidebar_width - 0.30) < 0.001, "sidebar_width adjustment failed"
    prefs.draw(bpy.context)
    prefs.sidebar_width = 0.22
    print("[PASS] sidebar_width dynamically modified and re-drawn successfully.")

    print("\n--- [Test 6] Addon Disable Cleanliness ---")
    bpy.ops.preferences.addon_disable(module='M8')
    assert 'M8' not in bpy.context.preferences.addons, "M8 addon still in preferences.addons"
    print("[PASS] Addon disabled cleanly.")

    print("\n=== ALL PREFERENCES UI TESTS PASSED ===")

if __name__ == "__main__":
    test_preferences_tabs()
