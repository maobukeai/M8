import bpy
from .keymap_constants import *
from .keymap_helpers import (
    addon_keymaps,
    _get_addon_prefs,
    _ensure_pie_keymap_priority,
    _iter_switch_mode_keymap_bindings,
    _find_pie_keymap_item,
    _find_switch_mode_keymap_items,
    _find_quick_delete_keymap_items,
    _find_delete_pie_keymap_items,
    _find_edge_property_pie_keymap_items,
    _find_align_pie_keymap_items,
    _find_shading_pie_keymap_items,
    _find_save_pie_keymap_items,
    _find_switch_editor_pie_keymap_items,
    _find_rename_keymap_items,
    _find_mirror_keymap_items,
    _find_group_tool_keymap_items,
    _find_double_click_select_group_keymap_items,
    _find_smart_pie_keymap_items,
    _find_toggle_area_keymap_items,
    _find_subdivision_keymap_items,
)

def register_keymaps(force_default=False):
    """
    Registers all keymaps unconditionally.
    Active state is determined by preferences (or default True).
    """
    global addon_keymaps
    
    # Avoid duplicate registration
    if addon_keymaps:
        return

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    prefs = _get_addon_prefs()
    
    def get_pref(name, default=True):
        if force_default: return True
        if prefs:
            return getattr(prefs, name, default)
        return default

    # 1. Transform Pie (Shift+S)
    active = get_pref("enable_transform_pie", True)
    for keymap_name, space_type in TRANSFORM_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('wm.call_menu_pie', 'S', 'PRESS', shift=True)
        kmi.properties.name = PIE_MENU_ID
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 2. Switch Mode (Tab)
    active = get_pref("activate_switch_mode", True)
    for keymap_name, space_type in _iter_switch_mode_keymap_bindings(wm):
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('object.switch_mode', 'TAB', 'PRESS')
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    active = get_pref("activate_switch_mode", True) and get_pref("switch_mode_double_click_edit_switch", False)
    km = kc.keymaps.new(name="Mesh", space_type="EMPTY")
    kmi = km.keymap_items.new('m8.double_click_edit_switch', 'LEFTMOUSE', 'DOUBLE_CLICK')
    kmi.active = active
    _ensure_pie_keymap_priority(km, kmi)
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('m8.double_click_edit_switch', 'LEFTMOUSE', 'DOUBLE_CLICK', shift=True)
    kmi.active = active
    _ensure_pie_keymap_priority(km, kmi)
    addon_keymaps.append((km, kmi))

    # 3. Quick Delete (X, Del)
    active = get_pref("activate_quick_delete", True)
    for keymap_name, space_type in QUICK_DELETE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        
        kmi1 = km.keymap_items.new('m8.quick_delete', 'X', 'PRESS')
        kmi1.active = active
        _ensure_pie_keymap_priority(km, kmi1)
        addon_keymaps.append((km, kmi1))
        
        kmi2 = km.keymap_items.new('m8.quick_delete', 'DEL', 'PRESS')
        kmi2.active = active
        _ensure_pie_keymap_priority(km, kmi2)
        addon_keymaps.append((km, kmi2))

    # 4. Delete Pie (Mesh Edit)
    active = get_pref("activate_delete_pie", True)
    for keymap_name, space_type in DELETE_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        
        kmi1 = km.keymap_items.new('wm.call_menu_pie', 'X', 'PRESS')
        kmi1.properties.name = DELETE_PIE_ID
        kmi1.active = active
        _ensure_pie_keymap_priority(km, kmi1)
        addon_keymaps.append((km, kmi1))
        
        kmi2 = km.keymap_items.new('wm.call_menu_pie', 'DEL', 'PRESS')
        kmi2.properties.name = DELETE_PIE_ID
        kmi2.active = active
        _ensure_pie_keymap_priority(km, kmi2)
        addon_keymaps.append((km, kmi2))

    # 5. Align Pie (Alt+A)
    active = get_pref("activate_align_pie", True)
    for keymap_name, space_type in ALIGN_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        
        pie_id = ALIGN_OBJECT_PIE_ID
        if keymap_name == "Mesh": pie_id = ALIGN_MESH_PIE_ID
        elif keymap_name == "UV Editor": pie_id = ALIGN_UV_PIE_ID
        
        if keymap_name == "3D View Generic":
            kmi = km.keymap_items.new(ALIGN_GENERIC_OP_ID, 'A', 'PRESS', alt=True)
        else:
            kmi = km.keymap_items.new('wm.call_menu_pie', 'A', 'PRESS', alt=True)
            kmi.properties.name = pie_id
            
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 6. Shading Pie (Z)
    active = get_pref("activate_shading_pie", True)
    for keymap_name, space_type in SHADING_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('wm.call_menu_pie', 'Z', 'PRESS')
        kmi.properties.name = SHADING_PIE_ID
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 7. Save Pie (Ctrl+S)
    active = get_pref("activate_save_pie", True)
    for keymap_name, space_type in SAVE_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('wm.call_menu_pie', 'S', 'PRESS', ctrl=True)
        kmi.properties.name = SAVE_PIE_ID
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 8. Rename (F2)
    active = get_pref("activate_advanced_rename", True)
    for keymap_name, space_type in RENAME_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('m8.advanced_rename', 'F2', 'PRESS')
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 9. Edge Property Pie (Shift+E)
    active = get_pref("activate_edge_property_pie", True)
    for keymap_name, space_type in EDGE_PROPERTY_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('wm.call_menu_pie', 'E', 'PRESS', shift=True)
        kmi.properties.name = EDGE_PROPERTY_PIE_ID
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 10. Mirror (Shift+Alt+X)
    active = get_pref("activate_mirror", True)
    for keymap_name, space_type in MIRROR_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new(MIRROR_OP_ID, 'X', 'PRESS', shift=True, alt=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 11. Group Tool (Ctrl+G)
    active = get_pref("activate_group_tool", True)
    for keymap_name, space_type in GROUP_TOOL_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('m8.group_objects', 'G', 'PRESS', ctrl=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 12. Double Click Select Group
    active = get_pref("activate_double_click_select_group", False)
    for keymap_name, space_type in DOUBLE_CLICK_GROUP_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('m8.select_group', 'LEFTMOUSE', 'DOUBLE_CLICK')
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 13. Smart Pie (1)
    active = get_pref("activate_smart_pie", True)
    for keymap_name, space_type in SMART_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new('wm.call_menu_pie', 'ONE', 'PRESS')
        kmi.properties.name = SMART_PIE_ID
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_merge_center', 'ONE', 'PRESS', shift=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_paths_merge', 'ONE', 'PRESS', alt=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_paths_connect', 'ONE', 'PRESS', ctrl=True, alt=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_slide_extend', 'ONE', 'PRESS', shift=True, alt=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_edge', 'TWO', 'PRESS')
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_edge_toggle_mode', 'TWO', 'PRESS', shift=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_offset_edges', 'TWO', 'PRESS', ctrl=True)
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.clean_up', 'THREE', 'PRESS')
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_face', 'FOUR', 'PRESS')
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_face', 'FOUR', 'PRESS', shift=True)
        kmi.properties.face_action = "DUPLICATE"
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_face', 'FOUR', 'PRESS', alt=True)
        kmi.properties.face_action = "DISSOLVE"
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        kmi = km.keymap_items.new('m8.smart_face', 'FOUR', 'PRESS', ctrl=True)
        kmi.properties.face_action = "EXTRACT"
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # 14. Toggle Area (T)
    active = get_pref("activate_toggle_area", True)
    for keymap_name, space_type in TOGGLE_AREA_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        kmi = km.keymap_items.new(TOGGLE_AREA_OP_ID, 'T', 'PRESS')
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

    # Switch Editor Pie (F12)
    active = get_pref("activate_switch_editor_pie", True)
    km = kc.keymaps.new(name="Window", space_type="EMPTY")
    kmi = km.keymap_items.new('wm.call_menu_pie', 'F12', 'PRESS')
    kmi.properties.name = SWITCH_EDITOR_PIE_ID
    kmi.active = active
    _ensure_pie_keymap_priority(km, kmi)
    addon_keymaps.append((km, kmi))

    # 15. Subdivision Level Shortcuts (Ctrl+0..4)
    active = get_pref("activate_subdivision_shortcuts", True)
    for keymap_name, space_type in SUBDIVISION_KEYMAP_BINDINGS:
        km = kc.keymaps.new(name=keymap_name, space_type=space_type)
        
        # Ctrl + 0
        kmi = km.keymap_items.new('m8.subdivision_set', 'ZERO', 'PRESS', ctrl=True)
        kmi.properties.level = 0
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        # Ctrl + 1
        kmi = km.keymap_items.new('m8.subdivision_set', 'ONE', 'PRESS', ctrl=True)
        kmi.properties.level = 1
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        # Ctrl + 2
        kmi = km.keymap_items.new('m8.subdivision_set', 'TWO', 'PRESS', ctrl=True)
        kmi.properties.level = 2
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        # Ctrl + 3
        kmi = km.keymap_items.new('m8.subdivision_set', 'THREE', 'PRESS', ctrl=True)
        kmi.properties.level = 3
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))

        # Ctrl + 4
        kmi = km.keymap_items.new('m8.subdivision_set', 'FOUR', 'PRESS', ctrl=True)
        kmi.properties.level = 4
        kmi.active = active
        _ensure_pie_keymap_priority(km, kmi)
        addon_keymaps.append((km, kmi))


def unregister_keymaps():
    global addon_keymaps
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    addon_keymaps.clear()


def update_keymaps(self, context):
    """
    Updates the active state of registered keymaps based on current preferences.
    Called when preferences change.
    """
    if not addon_keymaps:
        return

    # Helper to check if a kmi matches a feature
    def is_transform_pie(kmi):
        return kmi.idname == 'wm.call_menu_pie' and getattr(kmi.properties, "name", "") == PIE_MENU_ID
    
    def is_switch_mode(kmi):
        return kmi.idname == 'object.switch_mode'

    def is_double_click_edit_switch(kmi):
        return kmi.idname == 'm8.double_click_edit_switch'
        
    def is_quick_delete(kmi):
        return kmi.idname == 'm8.quick_delete'
        
    def is_delete_pie(kmi):
        return kmi.idname == 'wm.call_menu_pie' and getattr(kmi.properties, "name", "") == DELETE_PIE_ID
        
    def is_align_pie(kmi):
        if kmi.idname == ALIGN_GENERIC_OP_ID: return True
        return kmi.idname == 'wm.call_menu_pie' and getattr(kmi.properties, "name", "") in {ALIGN_OBJECT_PIE_ID, ALIGN_MESH_PIE_ID, ALIGN_UV_PIE_ID}
        
    def is_shading_pie(kmi):
        return kmi.idname == 'wm.call_menu_pie' and getattr(kmi.properties, "name", "") == SHADING_PIE_ID

    def is_save_pie(kmi):
        return kmi.idname == 'wm.call_menu_pie' and getattr(kmi.properties, "name", "") == SAVE_PIE_ID

    def is_rename(kmi):
        return kmi.idname == 'm8.advanced_rename'

    def is_edge_property_pie(kmi):
        return kmi.idname == 'wm.call_menu_pie' and getattr(kmi.properties, "name", "") == EDGE_PROPERTY_PIE_ID

    def is_mirror(kmi):
        return kmi.idname == MIRROR_OP_ID

    def is_group_tool(kmi):
        return kmi.idname == 'm8.group_objects'

    def is_double_click_select_group(kmi):
        return kmi.idname == 'm8.select_group'

    def is_smart_pie(kmi):
        return kmi.idname == 'wm.call_menu_pie' and getattr(kmi.properties, "name", "") == SMART_PIE_ID
    
    def is_smart_tools(kmi):
        return kmi.idname in {
            "m8.smart_merge_center",
            "m8.smart_paths_merge",
            "m8.smart_paths_connect",
            "m8.smart_slide_extend",
            "m8.smart_edge",
            "m8.smart_edge_toggle_mode",
            "m8.smart_offset_edges",
            "m8.clean_up",
            "m8.smart_face",
        }

    def is_switch_editor_pie(kmi):
        return kmi.idname == "wm.call_menu_pie" and getattr(kmi.properties, "name", "") == SWITCH_EDITOR_PIE_ID

    def is_toggle_area(kmi):
        return kmi.idname == TOGGLE_AREA_OP_ID

    def is_subdivision_shortcut(kmi):
        return kmi.idname == 'm8.subdivision_set'

    # Get pref values
    p_transform = getattr(self, "enable_transform_pie", True)
    p_switch = getattr(self, "activate_switch_mode", True)
    p_switch_double_click = getattr(self, "switch_mode_double_click_edit_switch", False)
    p_quick_del = getattr(self, "activate_quick_delete", True)
    p_del_pie = getattr(self, "activate_delete_pie", True)
    p_align = getattr(self, "activate_align_pie", True)
    p_shading = getattr(self, "activate_shading_pie", True)
    p_save = getattr(self, "activate_save_pie", True)
    p_rename = getattr(self, "activate_advanced_rename", True)
    p_edge_property = getattr(self, "activate_edge_property_pie", True)
    p_mirror = getattr(self, "activate_mirror", True)
    p_group_tool = getattr(self, "activate_group_tool", True)
    p_double_click_select_group = getattr(self, "activate_double_click_select_group", False)
    p_smart_pie = getattr(self, "activate_smart_pie", True)
    p_toggle_area = getattr(self, "activate_toggle_area", True)
    p_switch_editor = getattr(self, "activate_switch_editor_pie", True)
    p_subdivision = getattr(self, "activate_subdivision_shortcuts", True)

    for km, kmi in addon_keymaps:
        try:
            if is_transform_pie(kmi): kmi.active = p_transform
            elif is_switch_mode(kmi): kmi.active = p_switch
            elif is_double_click_edit_switch(kmi): kmi.active = p_switch and p_switch_double_click
            elif is_quick_delete(kmi): kmi.active = p_quick_del
            elif is_delete_pie(kmi): kmi.active = p_del_pie
            elif is_align_pie(kmi): kmi.active = p_align
            elif is_shading_pie(kmi): kmi.active = p_shading
            elif is_save_pie(kmi): kmi.active = p_save
            elif is_rename(kmi): kmi.active = p_rename
            elif is_edge_property_pie(kmi): kmi.active = p_edge_property
            elif is_mirror(kmi): kmi.active = p_mirror
            elif is_group_tool(kmi): kmi.active = p_group_tool
            elif is_double_click_select_group(kmi): kmi.active = p_double_click_select_group
            elif is_smart_pie(kmi): kmi.active = p_smart_pie
            elif is_smart_tools(kmi): kmi.active = p_smart_pie
            elif is_toggle_area(kmi): kmi.active = p_toggle_area
            elif is_switch_editor_pie(kmi): kmi.active = p_switch_editor
            elif is_subdivision_shortcut(kmi): kmi.active = p_subdivision
        except Exception:
            pass

    # Automatically manage subdivision hotkey exclusivity when toggled or updated
    if p_subdivision:
        try:
            bpy.ops.size_tool.exclusive_subdivision_hotkey()
        except Exception:
            pass
    else:
        try:
            bpy.ops.size_tool.restore_subdivision_conflicts()
        except Exception:
            pass

    # Automatically manage toggle area hotkey exclusivity when toggled or updated
    if p_toggle_area:
        try:
            bpy.ops.size_tool.exclusive_toggle_area_hotkey()
        except Exception:
            pass
    else:
        try:
            bpy.ops.size_tool.restore_toggle_area_conflicts()
        except Exception:
            pass
