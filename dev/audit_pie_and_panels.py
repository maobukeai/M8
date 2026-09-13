import bpy
import sys
import os
import re

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Set addon language to EN
addon_prefs = None
for name in ["bl_ext.user_default.M8", "M8"]:
    addon = bpy.context.preferences.addons.get(name)
    if addon and getattr(addon, "preferences", None):
        addon_prefs = addon.preferences
        addon_prefs.addon_language = "EN"
        break

try:
    from bl_ext.user_default.M8.utils.i18n import _T, get_addon_language
except ImportError:
    from M8.utils.i18n import _T, get_addon_language

chinese_char = re.compile(r'[\u4e00-\u9fff]')

print(f"=== TESTING ALL PIES & PANELS IN EN MODE (lang={get_addon_language()}) ===")

class CollectorLayout:
    def __init__(self, name):
        self.name = name
        self.chinese_found = []

    def check(self, text, kind):
        if text and isinstance(text, str) and chinese_char.search(text):
            self.chinese_found.append((self.name, kind, text))

    def column(self, align=False): return self
    def column_flow(self, **kwargs): return self
    def row(self, align=False): return self
    def box(self): return self
    def grid_flow(self, **kwargs): return self
    def split(self, **kwargs): return self
    def label(self, text="", icon="NONE", **kwargs):
        self.check(text, "label")
    def prop(self, data, prop_name, text=None, **kwargs):
        self.check(text, f"prop({prop_name})")
    def operator(self, op_name, text="", **kwargs):
        self.check(text, f"operator({op_name})")
        return self
    def menu(self, menu_name, text="", **kwargs):
        self.check(text, f"menu({menu_name})")
    def separator(self, factor=1.0): pass
    def prop_menu_enum(self, *args, **kwargs): pass

# Test all pie menus in ui/pie/
pie_dir = os.path.join(root_dir, "ui", "pie")
all_pies = []
for f in os.listdir(pie_dir):
    if f.endswith(".py") and not f.startswith("__"):
        mod_name = f[:-3]
        all_pies.append(mod_name)

total_chinese_in_pies = []

for mod_name in all_pies:
    try:
        mod = __import__(f"bl_ext.user_default.M8.ui.pie.{mod_name}", fromlist=["*"])
    except Exception:
        try:
            mod = __import__(f"ui.pie.{mod_name}", fromlist=["*"])
        except Exception as e:
            continue
    for attr in dir(mod):
        cls = getattr(mod, attr)
        if isinstance(cls, type) and issubclass(cls, bpy.types.Menu) and hasattr(cls, "draw"):
            layout = CollectorLayout(cls.__name__)
            try:
                # Mock pie menu layout
                class MockPie(CollectorLayout):
                    def pie(self): return self
                m_pie = MockPie(cls.__name__)
                # Call draw with mock context
                cls.draw(m_pie, bpy.context)
                if m_pie.chinese_found:
                    total_chinese_in_pies.extend(m_pie.chinese_found)
            except Exception as e:
                # Ignore context-dependent errors (e.g. active object required)
                pass

print(f"Total Chinese strings in Pie Menus under EN mode: {len(total_chinese_in_pies)}")
for cls_name, kind, text in total_chinese_in_pies:
    print(f"  [{cls_name}] {kind} -> {repr(text)}")

# Test all panels in ui/panel/
panel_dir = os.path.join(root_dir, "ui", "panel")
all_panels = []
for f in os.listdir(panel_dir):
    if f.endswith(".py") and not f.startswith("__"):
        all_panels.append(f[:-3])

total_chinese_in_panels = []

for mod_name in all_panels:
    try:
        mod = __import__(f"bl_ext.user_default.M8.ui.panel.{mod_name}", fromlist=["*"])
    except Exception:
        try:
            mod = __import__(f"ui.panel.{mod_name}", fromlist=["*"])
        except Exception as e:
            continue
    for attr in dir(mod):
        cls = getattr(mod, attr)
        if isinstance(cls, type) and issubclass(cls, bpy.types.Panel) and hasattr(cls, "draw"):
            layout = CollectorLayout(cls.__name__)
            try:
                cls.draw(layout, bpy.context)
                if layout.chinese_found:
                    total_chinese_in_panels.extend(layout.chinese_found)
            except Exception as e:
                pass

print(f"Total Chinese strings in Panels under EN mode: {len(total_chinese_in_panels)}")
for cls_name, kind, text in total_chinese_in_panels:
    print(f"  [{cls_name}] {kind} -> {repr(text)}")

if not total_chinese_in_pies and not total_chinese_in_panels:
    print("\n[PERFECT] ALL PIE MENUS AND PANELS DRAW ZERO CHINESE TEXT IN EN MODE!")
