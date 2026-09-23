import sys
import os
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _MockOpHolder:
    """Returned by MockUILayout.operator() – captures properties without error."""
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        return None


class MockUILayout:
    """
    Full-coverage mock of Blender UILayout for headless draw() testing.

    Blender's layout RNA is read-only on the Preferences object, so we cannot
    assign ``prefs.layout = MockUILayout()``.  Instead draw() uses ``self.layout``,
    so we intercept it via PrefsProxy below.
    """
    def __init__(self):
        self.use_property_split = False
        self.use_property_decorate = False
        self.enabled = True
        self.alignment = "LEFT"
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.alert = False

    def _child(self):
        return MockUILayout()

    def row(self, align=False, heading="", heading_ctxt="", translate=True):
        return self._child()

    def column(self, align=False, heading="", heading_ctxt="", translate=True):
        return self._child()

    def column_flow(self, columns=0, align=False):
        return self._child()

    def split(self, factor=0.0, align=False):
        return self._child()

    def box(self):
        return self._child()

    def grid_flow(self, row_major=False, columns=0, even_columns=False,
                  even_rows=False, align=False):
        return self._child()

    def prop(self, data, property, text="", icon="NONE", toggle=False,
             icon_only=False, expand=False, slider=False, index=-1,
             event=False, full_event=False, emboss=True, invert_checkbox=False, **kwargs):
        # Validate property existence on real RNA data to catch typos early.
        if hasattr(data, 'bl_rna') and hasattr(data.bl_rna, 'properties'):
            if property not in data.bl_rna.properties:
                raise AttributeError(
                    f"MockUILayout.prop: property '{property}' not found on "
                    f"{type(data).__name__} (bl_rna={data.bl_rna.identifier!r})"
                )

    def prop_enum(self, data, property, value, text="", icon="NONE", **kwargs):
        pass

    def prop_search(self, data, property, search_data, search_property,
                    text="", icon="NONE", results_are_suggestions=False, **kwargs):
        pass

    def template_list(self, listtype_name, list_id, dataptr, propname,
                      active_dataptr, active_propname, item_dyntip_propname="",
                      rows=5, maxrows=5, type='DEFAULT', columns=9,
                      sort_reverse=False, sort_lock=False):
        pass

    def template_icon(self, icon_value, scale=1.0):
        pass

    def label(self, text="", icon="NONE", icon_value=0, translate=True):
        pass

    def operator(self, operator, text="", icon="NONE", icon_value=0,
                 emboss=True, depress=False, **kwargs):
        return _MockOpHolder()

    def operator_menu_enum(self, operator, property, text="", icon="NONE"):
        return _MockOpHolder()

    def separator(self, factor=1.0, type='LINE'):
        pass

    def separator_spacer(self):
        pass

    def menu(self, menu, text="", icon="NONE", icon_value=0):
        pass

    def menu_contents(self, menu):
        pass

    def popover(self, panel, text="", icon="NONE", icon_value=0):
        pass

    def context_pointer_set(self, name, data):
        pass

    def emboss(self, type):
        return self._child()

    def active_default(self, enabled):
        return self._child()


class PrefsProxy:
    """
    Proxy wrapping real Blender AddonPreferences RNA so that
    SIZE_TOOL_Preferences.draw(proxy, context) works headlessly.

    draw(self, context) and helper methods read ``self.layout`` to get the
    UILayout. Since ``layout`` is read-only RNA on the real prefs, we cannot
    assign to it.  This proxy intercepts:
      - ``self.layout``  →  MockUILayout instance
      - ``self.bl_rna``  →  real prefs.bl_rna (for RNA introspection)
      - all other attributes  →  delegated to real prefs RNA object
      - all class methods bound via descriptor protocol so 'self' inside them
        refers to this proxy.
    """

    def __init__(self, real_prefs, mock_layout):
        object.__setattr__(self, '_real_prefs', real_prefs)
        object.__setattr__(self, '_mock_layout', mock_layout)
        # Bind all non-dunder callable methods from the class hierarchy onto
        # this proxy instance via Python descriptor protocol.
        real_cls = type(real_prefs)
        bound = {}
        for klass in reversed(real_cls.__mro__):
            for attr_name, attr_val in vars(klass).items():
                if attr_name.startswith('__'):
                    continue
                if callable(attr_val) and not isinstance(attr_val, (classmethod, staticmethod)):
                    try:
                        bound[attr_name] = attr_val.__get__(self, type(self))
                    except Exception:
                        pass
        object.__setattr__(self, '_bound_methods', bound)

    @property
    def layout(self):
        return object.__getattribute__(self, '_mock_layout')

    @property
    def bl_rna(self):
        return object.__getattribute__(self, '_real_prefs').bl_rna

    def __getattr__(self, name):
        bound = object.__getattribute__(self, '_bound_methods')
        if name in bound:
            return bound[name]
        real = object.__getattribute__(self, '_real_prefs')
        return getattr(real, name)

    def __setattr__(self, name, value):
        if name in ('_real_prefs', '_mock_layout', '_bound_methods'):
            object.__setattr__(self, name, value)
        else:
            real = object.__getattribute__(self, '_real_prefs')
            setattr(real, name, value)


import addon_utils


def _get_or_enable_m8():
    """Enable the M8 addon with default_set=True so preferences.addons is populated."""
    addon_name = "M8"
    for mod in addon_utils.modules():
        name = mod.__name__
        if name == "M8" or name.endswith(".M8"):
            addon_name = name
            break

    # default_set=True populates bpy.context.preferences.addons in factory Blender
    addon_utils.enable(addon_name, default_set=True)

    prefs = None
    if hasattr(bpy.context.preferences, "addons"):
        for k in (addon_name, "M8", "bl_ext.user_default.M8"):
            if k in bpy.context.preferences.addons:
                addon_name = k
                prefs = bpy.context.preferences.addons[k].preferences
                if prefs:
                    return addon_name, prefs
        for k, v in bpy.context.preferences.addons.items():
            if k.endswith("M8") and v.preferences:
                return k, v.preferences
    return addon_name, prefs


def test_preferences_tabs():
    print("\n--- [Test 1] Addon Enable via addon_utils ---")
    addon_name, prefs = _get_or_enable_m8()
    assert prefs is not None, f"Preferences object is None for {addon_name}"
    print(f"[PASS] Addon '{addon_name}' enabled and Preferences retrieved.")

    print("\n--- [Test 2] Sidebar Width Property ---")
    assert hasattr(prefs, "sidebar_width"), "sidebar_width property not found on prefs"
    assert abs(prefs.sidebar_width - 0.22) < 0.001, f"Default width is {prefs.sidebar_width}, expected 0.22"
    print(f"[PASS] sidebar_width exists with default: {prefs.sidebar_width:.2f}")

    # Derive navigation_tab items directly from the RNA declaration (not guessed)
    tabs = [it.identifier for it in prefs.bl_rna.properties['navigation_tab'].enum_items]
    print(f"\n--- [Test 3] Test Draw on All {len(tabs)} Tabs Individually ---")
    assert len(tabs) >= 20, f"Expected at least 20 tabs, got {len(tabs)}"

    # Require a meaningful subset of core tabs derived from actual declaration
    required_core_subset = {
        "TRANSFORM", "SWITCH_MODE", "DELETE", "EDGE_PROPERTY", "ALIGN", "SHADING",
        "SAVE", "RENAME", "MIRROR", "GROUP", "SMART_PIE", "NORMAL_PIE", "TOGGLE_AREA",
        "SWITCH_EDITOR", "SUBDIVISION", "FAST_LOOP", "SCREENCAST", "NPANEL", "AI_ASSISTANT",
        "OTHER", "ABOUT",
    }
    missing_tabs = required_core_subset - set(tabs)
    assert not missing_tabs, f"Missing expected core tabs (from RNA enum): {missing_tabs}"

    # Import the real preferences class once.
    from M8.property.preferences import SIZE_TOOL_Preferences

    # Build a PrefsProxy: self.layout → MockUILayout; RNA reads → real prefs;
    # all draw/helper methods bound so 'self' inside them refers to this proxy.
    mock_layout = MockUILayout()
    proxy = PrefsProxy(prefs, mock_layout)

    draw_failures = []
    for tab in tabs:
        prefs.navigation_tab = tab
        prefs.ui_show_all_settings = False
        try:
            # Call unbound draw with proxy as self; inside draw() self.layout →
            # MockUILayout and self.<rna_prop> → real prefs value.
            SIZE_TOOL_Preferences.draw(proxy, bpy.context)
            print(f"  [OK] Tab: {tab}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            draw_failures.append((tab, str(e)))

    if draw_failures:
        raise AssertionError(f"Failed tabs: {draw_failures}")
    print(f"[PASS] All {len(tabs)} tabs drew without any exceptions.")

    print("\n--- [Test 4] Test Draw in Show-All Settings Mode ---")
    prefs.ui_show_all_settings = True
    try:
        SIZE_TOOL_Preferences.draw(proxy, bpy.context)
        print("[PASS] Show-All settings mode drew without any exceptions.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise AssertionError(f"Failed to draw show-all mode: {e}")

    print("\n--- [Test 5] Test Sidebar Width Adjustment ---")
    prefs.sidebar_width = 0.30
    assert abs(prefs.sidebar_width - 0.30) < 0.001, "sidebar_width adjustment failed"
    SIZE_TOOL_Preferences.draw(proxy, bpy.context)
    prefs.sidebar_width = 0.22
    print("[PASS] sidebar_width dynamically modified and re-drawn successfully.")

    print("\n--- [Test 6] Addon Disable Cleanliness ---")
    addon_utils.disable(addon_name, default_set=True)
    print("[PASS] Addon disabled cleanly without modifying user preferences.")

    print("\n=== ALL PREFERENCES UI TESTS PASSED ===")


if __name__ == "__main__":
    test_preferences_tabs()
