import bpy

PIE_MENU_ID = "VIEW3D_MT_size_tool_transform_pie"
SWITCH_MODE_PIE_ID = "VIEW3D_MT_m8_switch_mode_pie"
EDGE_PROPERTY_PIE_ID = "VIEW3D_MT_m8_edge_property_pie"
MIRROR_OP_ID = "m8.mirror"

TRANSFORM_PIE_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
    ("3D View Generic", "EMPTY"),
)
SWITCH_MODE_KEYMAP_BINDINGS = (
    ("Object Non-modal", "EMPTY"),
    ("Image", "IMAGE_EDITOR"),
    ("Node Editor", "NODE_EDITOR"),
    # Grease Pencil
    ("Grease Pencil", "EMPTY"),
    ("Grease Pencil (Legacy)", "EMPTY"),  # 旧版蜡笔 keymap 可能带后缀
    ("Grease Pencil Stroke Edit Mode", "EMPTY"),
    ("Grease Pencil Paint Mode", "EMPTY"),
    ("Grease Pencil Sculpt Mode", "EMPTY"),
    ("Grease Pencil Weight Paint Mode", "EMPTY"),
    ("Grease Pencil Vertex Paint Mode", "EMPTY"),
    # Grease Pencil 3.0 (Blender 4.3+)
    ("Grease Pencil Edit Mode", "EMPTY"),
    ("Grease Pencil Draw Mode", "EMPTY"),
    ("Grease Pencil Sculpt Mode", "EMPTY"), # 新版可能复用名称，但也可能不同
)
QUICK_DELETE_KEYMAP_BINDINGS = (
    ("Object Mode", "EMPTY"),
    ("Object Non-modal", "EMPTY"),
    ("Node Editor", "NODE_EDITOR"),
    ("Node Generic", "NODE_EDITOR"),
)
DELETE_PIE_KEYMAP_BINDINGS = (
    ("Mesh", "EMPTY"),
)
DELETE_PIE_ID = "VIEW3D_MT_M8DeletePie"
EDGE_PROPERTY_PIE_KEYMAP_BINDINGS = (
    ("Mesh", "EMPTY"),
)
ALIGN_OBJECT_PIE_ID = "M8_MT_ALIGN_OBJECT"
ALIGN_MESH_PIE_ID = "M8_MT_ALIGN_MESH"
ALIGN_UV_PIE_ID = "M8_MT_ALIGN_UV"
ALIGN_GENERIC_OP_ID = "m8.align_pie_context_call"

SHADING_PIE_ID = "VIEW3D_MT_m8_shading_pie"
SHADING_PIE_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
)

SAVE_PIE_ID = "VIEW3D_MT_m8_save_pie"
SAVE_PIE_KEYMAP_BINDINGS = (
    ("Window", "EMPTY"),
)

RENAME_KEYMAP_BINDINGS = (
    ("Window", "EMPTY"),
)

MIRROR_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
    ("3D View Generic", "VIEW_3D"),
)

GROUP_TOOL_KEYMAP_BINDINGS = (
    ("Object Mode", "EMPTY"),
)

DOUBLE_CLICK_GROUP_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
)

ALIGN_PIE_KEYMAP_BINDINGS = (
    ("Object Mode", "VIEW_3D"),
    ("Mesh", "VIEW_3D"),
    ("UV Editor", "EMPTY"),
    ("3D View Generic", "VIEW_3D"),
)

SMART_PIE_ID = "VIEW3D_MT_M8SmartPie"
SMART_PIE_KEYMAP_BINDINGS = (
    ("Mesh", "EMPTY"),
)

TOGGLE_AREA_OP_ID = "m8.toggle_area"
TOGGLE_AREA_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
    ("Node Editor", "NODE_EDITOR"),
    ("Image", "IMAGE_EDITOR"),
)

# Global list to store registered keymap items: list of (km, kmi)
addon_keymaps = []

def _get_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg) if bpy.context and bpy.context.preferences else None
    return addon.preferences if addon else None

# Helper to ensure our keymap is at the top (priority)
def _ensure_pie_keymap_priority(km, kmi):
    try:
        items = list(km.keymap_items)
        idx = items.index(kmi)
        if idx > 0:
            km.keymap_items.move(idx, 0)
    except Exception:
        pass

def _iter_switch_mode_keymap_bindings(wm):
    bindings = []
    seen = set()
    for item in SWITCH_MODE_KEYMAP_BINDINGS:
        if item not in seen:
            bindings.append(item)
            seen.add(item)
    try:
        for km in wm.keyconfigs.active.keymaps:
            name = getattr(km, "name", "")
            if not name:
                continue
            if "Grease Pencil" not in name and "GPencil" not in name:
                continue
            space_type = getattr(km, "space_type", "EMPTY") or "EMPTY"
            item = (name, space_type)
            if item in seen:
                continue
            bindings.append(item)
            seen.add(item)
    except Exception:
        pass
    return bindings

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
    # Default to True if prefs not loaded yet
    
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

    def is_toggle_area(kmi):
        return kmi.idname == TOGGLE_AREA_OP_ID

    # Get pref values
    # Note: 'self' is the preferences instance
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
        except Exception:
            pass

def _on_prefs_update(self, context):
    update_keymaps(self, context)

def _on_autoorigin_update(self, context):
    try:
        from ..ops.origin.auto_origin import register as reg_auto, unregister as unreg_auto
        if getattr(self, "auto_new_object_origin_bottom", False):
            reg_auto()
        else:
            unreg_auto()
    except Exception:
        pass

def _on_autopack_update(self, context):
    try:
        from ..ops.file.auto_pack import register as reg_auto, unregister as unreg_auto
        enabled = bool(getattr(self, "auto_pack_resources_on_save", False)) or bool(getattr(self, "auto_purge_unused_materials_on_save", False))
        if enabled:
            reg_auto()
        else:
            unreg_auto()
    except Exception:
        pass

# --- Finder Functions for UI / Operators ---
# These now search wm.keyconfigs.addon directly (standard) OR could use addon_keymaps.
# Using standard search is safer for UI drawing as it finds what is actually there.

def _is_our_pie_keymap_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") in {PIE_MENU_ID, SWITCH_MODE_PIE_ID, EDGE_PROPERTY_PIE_ID, SMART_PIE_ID}

def _is_our_switch_mode_item(kmi):
    return getattr(kmi, "idname", "") == 'object.switch_mode'

def _is_our_quick_delete_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.quick_delete'

def _is_our_delete_pie_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") == DELETE_PIE_ID

def _is_our_edge_property_pie_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") == EDGE_PROPERTY_PIE_ID

def _is_our_smart_pie_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") == SMART_PIE_ID

def _is_our_smart_tool_item(kmi):
    return getattr(kmi, "idname", "") in {
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

def _is_our_align_pie_item(kmi):
    if kmi.idname == 'wm.call_menu_pie':
        return getattr(kmi.properties, "name", "") in {ALIGN_OBJECT_PIE_ID, ALIGN_MESH_PIE_ID, ALIGN_UV_PIE_ID}
    return kmi.idname == ALIGN_GENERIC_OP_ID

def _is_our_shading_pie_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") == SHADING_PIE_ID

def _is_our_save_pie_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") == SAVE_PIE_ID

def _is_our_rename_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.advanced_rename'

def _is_our_mirror_item(kmi):
    return getattr(kmi, "idname", "") == MIRROR_OP_ID

def _is_our_group_tool_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.group_objects'

def _is_our_double_click_select_group_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.select_group'

def _find_pie_keymap_item():
    # Helper to find the transform pie item for the UI/Operators
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return None, None, None
    for keymap_name, _ in TRANSFORM_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_pie_keymap_item(kmi): return kc, km, kmi
    return kc, None, None

def _find_switch_mode_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc:
        return []
    items = []
    try:
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if _is_our_switch_mode_item(kmi):
                    items.append((kc, km, kmi))
    except Exception:
        pass
    return items

def _find_quick_delete_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in QUICK_DELETE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_quick_delete_item(kmi): items.append((kc, km, kmi))
    return items

def _find_delete_pie_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in DELETE_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_delete_pie_item(kmi): items.append((kc, km, kmi))
    return items

def _find_edge_property_pie_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in EDGE_PROPERTY_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_edge_property_pie_item(kmi): items.append((kc, km, kmi))
    return items

def _find_align_pie_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in ALIGN_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_align_pie_item(kmi): items.append((kc, km, kmi))
    return items

def _find_shading_pie_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in SHADING_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_shading_pie_item(kmi): items.append((kc, km, kmi))
    return items

def _find_save_pie_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in SAVE_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_save_pie_item(kmi): items.append((kc, km, kmi))
    return items

def _find_rename_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in RENAME_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_rename_item(kmi): items.append((kc, km, kmi))
    return items

def _find_mirror_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in MIRROR_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_mirror_item(kmi): items.append((kc, km, kmi))
    return items

def _find_group_tool_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in GROUP_TOOL_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_group_tool_item(kmi): items.append((kc, km, kmi))
    return items

def _find_double_click_select_group_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in DOUBLE_CLICK_GROUP_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_double_click_select_group_item(kmi): items.append((kc, km, kmi))
    return items

def _find_smart_pie_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc:
        return []
    items = []
    for keymap_name, _ in SMART_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if not km:
            continue
        for kmi in km.keymap_items:
            if _is_our_smart_pie_item(kmi) or _is_our_smart_tool_item(kmi):
                items.append((kc, km, kmi))
    return items

# --- Conflict Handling ---
def _kmi_signature(kmi):
    try:
        return (
            getattr(kmi, "type", None),
            getattr(kmi, "value", None),
            bool(getattr(kmi, "any", False)),
            bool(getattr(kmi, "shift", False)),
            bool(getattr(kmi, "ctrl", False)),
            bool(getattr(kmi, "alt", False)),
            bool(getattr(kmi, "oskey", False)),
            getattr(kmi, "key_modifier", None),
        )
    except Exception:
        return None

def _match_signature(kmi, sig):
    if not sig: return False
    return _kmi_signature(kmi) == sig

def _our_shortcut_signatures():
    # Gather signatures from currently registered keymaps
    sigs = []
    for km, kmi in addon_keymaps:
        sig = _kmi_signature(kmi)
        if sig and sig not in sigs:
            sigs.append(sig)
    return sigs

def _disable_conflicts_for_signatures(kc, signatures):
    if not kc: return 0
    disabled = 0
    # Search all maps where we put keys
    all_bindings = list(TRANSFORM_PIE_KEYMAP_BINDINGS) + list(ALIGN_PIE_KEYMAP_BINDINGS) + \
                   list(SWITCH_MODE_KEYMAP_BINDINGS) + list(QUICK_DELETE_KEYMAP_BINDINGS) + \
                   list(DELETE_PIE_KEYMAP_BINDINGS) + list(SAVE_PIE_KEYMAP_BINDINGS) + \
                   list(RENAME_KEYMAP_BINDINGS) + list(GROUP_TOOL_KEYMAP_BINDINGS)
    
    seen_km = set()
    for keymap_name, _ in all_bindings:
        if keymap_name in seen_km: continue
        seen_km.add(keymap_name)
        
        km = kc.keymaps.get(keymap_name)
        if not km: continue
        
        for kmi in km.keymap_items:
            if not getattr(kmi, "active", True): continue
            
            # Skip our own items (checked via ID/Name)
            is_ours = (_is_our_pie_keymap_item(kmi) or 
                       _is_our_align_pie_item(kmi) or 
                       _is_our_switch_mode_item(kmi) or 
                       _is_our_quick_delete_item(kmi) or 
                       _is_our_delete_pie_item(kmi) or
                       _is_our_shading_pie_item(kmi) or
                       _is_our_save_pie_item(kmi) or
                       _is_our_rename_item(kmi) or
                       _is_our_mirror_item(kmi) or
                       _is_our_group_tool_item(kmi) or
                       _is_our_double_click_select_group_item(kmi))
            if is_ours: continue
            
            for sig in signatures:
                if _match_signature(kmi, sig):
                    try:
                        kmi.active = False
                        disabled += 1
                    except Exception:
                        pass
                    break
    return disabled

def _restore_conflicts_for_signatures(kc, signatures):
    if not kc: return 0
    restored = 0
    all_bindings = list(TRANSFORM_PIE_KEYMAP_BINDINGS) + list(ALIGN_PIE_KEYMAP_BINDINGS) + \
                   list(SWITCH_MODE_KEYMAP_BINDINGS) + list(QUICK_DELETE_KEYMAP_BINDINGS) + \
                   list(DELETE_PIE_KEYMAP_BINDINGS) + list(SAVE_PIE_KEYMAP_BINDINGS) + \
                   list(RENAME_KEYMAP_BINDINGS) + list(GROUP_TOOL_KEYMAP_BINDINGS)
    
    seen_km = set()
    for keymap_name, _ in all_bindings:
        if keymap_name in seen_km: continue
        seen_km.add(keymap_name)

        km = kc.keymaps.get(keymap_name)
        if not km: continue
        for kmi in km.keymap_items:
            if getattr(kmi, "active", True): continue
            
            is_ours = (_is_our_pie_keymap_item(kmi) or 
                       _is_our_align_pie_item(kmi) or 
                       _is_our_switch_mode_item(kmi) or 
                       _is_our_quick_delete_item(kmi) or 
                       _is_our_delete_pie_item(kmi) or
                       _is_our_shading_pie_item(kmi) or
                       _is_our_save_pie_item(kmi) or
                       _is_our_rename_item(kmi) or
                       _is_our_mirror_item(kmi) or
                       _is_our_group_tool_item(kmi) or
                       _is_our_double_click_select_group_item(kmi))
            if is_ours: continue

            for sig in signatures:
                if _match_signature(kmi, sig):
                    try:
                        kmi.active = True
                        restored += 1
                    except Exception:
                        pass
                    break
    return restored

# --- Operators ---
class SIZE_TOOL_OT_ResetTransformPieKeymap(bpy.types.Operator):
    bl_idname = "size_tool.reset_transform_pie_keymap"
    bl_label = "恢复默认快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        unregister_keymaps()
        register_keymaps(force_default=True)
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceTransformPiePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_transform_pie_priority"
    bl_label = "强制置顶快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # We can just iterate our addon_keymaps and move them to top
        # But for now, use old find logic to report errors if missing
        kc, km, kmi = _find_pie_keymap_item()
        if not (kc and km and kmi):
            self.report({'WARNING'}, "未找到变换辅助饼菜单的快捷键项")
            return {'CANCELLED'}
        _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceSwitchModePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_switch_mode_priority"
    bl_label = "强制置顶快捷键(Tab)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        items = _find_switch_mode_keymap_items()
        if not items:
            self.report({'WARNING'}, "未找到 Tab 绑定")
            return {'CANCELLED'}
        for _, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        self.report({'INFO'}, f"已置顶 {len(items)} 个 Tab 绑定")
        return {'FINISHED'}

class SIZE_TOOL_OT_ExclusiveTransformPieHotkey(bpy.types.Operator):
    bl_idname = "size_tool.exclusive_transform_pie_hotkey"
    bl_label = "独占 Shift+S"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法调整冲突快捷键")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = _our_shortcut_signatures() or [("S", "PRESS", False, True, False, False, False, 'NONE')]
        disabled = _disable_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            disabled += _disable_conflicts_for_signatures(wm.keyconfigs.user, signatures)
        
        # Ensure ours is at top
        kc2, km2, kmi2 = _find_pie_keymap_item()
        if km2 and kmi2:
            _ensure_pie_keymap_priority(km2, kmi2)

        if disabled:
            self.report({'INFO'}, f"已禁用 {disabled} 个插件冲突的 Shift+S 快捷键")
        else:
            self.report({'INFO'}, "未发现插件层面的 Shift+S 冲突快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_RestoreShiftSConflicts(bpy.types.Operator):
    bl_idname = "size_tool.restore_shift_s_conflicts"
    bl_label = "恢复被禁用的 Shift+S"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法恢复")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = _our_shortcut_signatures() or [("S", "PRESS", False, True, False, False, False, 'NONE')]
        restored = _restore_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            restored += _restore_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        self.report({'INFO'}, f"已恢复 {restored} 个被禁用的 Shift+S 快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceAlignPiePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_align_pie_priority"
    bl_label = "强制置顶对齐快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        items = _find_align_pie_keymap_items()
        if not items:
            self.report({'WARNING'}, "未找到对齐辅助饼菜单的快捷键项")
            return {'CANCELLED'}
        for kc, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ExclusiveAlignPieHotkey(bpy.types.Operator):
    bl_idname = "size_tool.exclusive_align_pie_hotkey"
    bl_label = "独占 Alt+A"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法调整冲突快捷键")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("A", "PRESS", False, False, False, True, False, 'NONE')]
        
        disabled = _disable_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            disabled += _disable_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        # Ensure ours is at top
        items = _find_align_pie_keymap_items()
        for kc2, km2, kmi2 in items:
            _ensure_pie_keymap_priority(km2, kmi2)

        if disabled:
            self.report({'INFO'}, f"已禁用 {disabled} 个插件冲突的 Alt+A 快捷键")
        else:
            self.report({'INFO'}, "未发现插件层面的 Alt+A 冲突快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_RestoreAltAConflicts(bpy.types.Operator):
    bl_idname = "size_tool.restore_alt_a_conflicts"
    bl_label = "恢复被禁用的 Alt+A"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法恢复")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("A", "PRESS", False, False, False, True, False, 'NONE')]
        restored = _restore_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            restored += _restore_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        self.report({'INFO'}, f"已恢复 {restored} 个被禁用的 Alt+A 快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceSavePiePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_save_pie_priority"
    bl_label = "强制置顶保存快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        items = _find_save_pie_keymap_items()
        if not items:
            self.report({'WARNING'}, "未找到保存饼菜单的快捷键项")
            return {'CANCELLED'}
        for kc, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ExclusiveSavePieHotkey(bpy.types.Operator):
    bl_idname = "size_tool.exclusive_save_pie_hotkey"
    bl_label = "独占 Ctrl+S"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法调整冲突快捷键")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("S", "PRESS", False, False, True, False, False, 'NONE')]

        disabled = _disable_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            disabled += _disable_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        items = _find_save_pie_keymap_items()
        for kc2, km2, kmi2 in items:
            _ensure_pie_keymap_priority(km2, kmi2)

        if disabled:
            self.report({'INFO'}, f"已禁用 {disabled} 个插件冲突的 Ctrl+S 快捷键")
        else:
            self.report({'INFO'}, "未发现插件层面的 Ctrl+S 冲突快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_RestoreCtrlSConflicts(bpy.types.Operator):
    bl_idname = "size_tool.restore_ctrl_s_conflicts"
    bl_label = "恢复被禁用的 Ctrl+S"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法恢复")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("S", "PRESS", False, False, True, False, False, 'NONE')]
        restored = _restore_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            restored += _restore_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        self.report({'INFO'}, f"已恢复 {restored} 个被禁用的 Ctrl+S 快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceEdgePropertyPiePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_edge_property_pie_priority"
    bl_label = "强制置顶边属性快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        items = _find_edge_property_pie_keymap_items()
        if not items:
            self.report({'WARNING'}, "未找到边属性饼菜单的快捷键项")
            return {'CANCELLED'}
        for kc, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ExclusiveEdgePropertyPieHotkey(bpy.types.Operator):
    bl_idname = "size_tool.exclusive_edge_property_pie_hotkey"
    bl_label = "独占 Shift+E"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法调整冲突快捷键")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("E", "PRESS", False, True, False, False, False, 'NONE')]

        disabled = _disable_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            disabled += _disable_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        items = _find_edge_property_pie_keymap_items()
        for kc2, km2, kmi2 in items:
            _ensure_pie_keymap_priority(km2, kmi2)

        if disabled:
            self.report({'INFO'}, f"已禁用 {disabled} 个插件冲突的 Shift+E 快捷键")
        else:
            self.report({'INFO'}, "未发现插件层面的 Shift+E 冲突快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_RestoreShiftEConflicts(bpy.types.Operator):
    bl_idname = "size_tool.restore_shift_e_conflicts"
    bl_label = "恢复被禁用的 Shift+E"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法恢复")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("E", "PRESS", False, True, False, False, False, 'NONE')]
        restored = _restore_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            restored += _restore_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        self.report({'INFO'}, f"已恢复 {restored} 个被禁用的 Shift+E 快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceMirrorPriority(bpy.types.Operator):
    bl_idname = "size_tool.force_mirror_priority"
    bl_label = "强制置顶镜像快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        items = _find_mirror_keymap_items()
        if not items:
            self.report({'WARNING'}, "未找到镜像的快捷键项")
            return {'CANCELLED'}
        for kc, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ExclusiveMirrorHotkey(bpy.types.Operator):
    bl_idname = "size_tool.exclusive_mirror_hotkey"
    bl_label = "独占 Shift+Alt+X"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法调整冲突快捷键")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("X", "PRESS", False, True, False, True, False, 'NONE')]

        disabled = _disable_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            disabled += _disable_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        items = _find_mirror_keymap_items()
        for kc2, km2, kmi2 in items:
            _ensure_pie_keymap_priority(km2, kmi2)

        if disabled:
            self.report({'INFO'}, f"已禁用 {disabled} 个插件冲突的 Shift+Alt+X 快捷键")
        else:
            self.report({'INFO'}, "未发现插件层面的 Shift+Alt+X 冲突快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_RestoreShiftAltXConflicts(bpy.types.Operator):
    bl_idname = "size_tool.restore_shift_alt_x_conflicts"
    bl_label = "恢复被禁用的 Shift+Alt+X"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法恢复")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("X", "PRESS", False, True, False, True, False, 'NONE')]
        restored = _restore_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            restored += _restore_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        self.report({'INFO'}, f"已恢复 {restored} 个被禁用的 Shift+Alt+X 快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceGroupToolPriority(bpy.types.Operator):
    bl_idname = "size_tool.force_group_tool_priority"
    bl_label = "强制置顶打组快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        items = _find_group_tool_keymap_items()
        if not items:
            self.report({'WARNING'}, "未找到打组的快捷键项")
            return {'CANCELLED'}
        for kc, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ExclusiveGroupToolHotkey(bpy.types.Operator):
    bl_idname = "size_tool.exclusive_group_tool_hotkey"
    bl_label = "独占 Ctrl+G"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法调整冲突快捷键")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("G", "PRESS", False, False, True, False, False, 'NONE')]

        disabled = _disable_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            disabled += _disable_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        items = _find_group_tool_keymap_items()
        for kc2, km2, kmi2 in items:
            _ensure_pie_keymap_priority(km2, kmi2)

        if disabled:
            self.report({'INFO'}, f"已禁用 {disabled} 个插件冲突的 Ctrl+G 快捷键")
        else:
            self.report({'INFO'}, "未发现插件层面的 Ctrl+G 冲突快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_RestoreCtrlGConflicts(bpy.types.Operator):
    bl_idname = "size_tool.restore_ctrl_g_conflicts"
    bl_label = "恢复被禁用的 Ctrl+G"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = bpy.context.window_manager if bpy.context else None
        if not wm or not wm.keyconfigs:
            self.report({'WARNING'}, "未找到 KeyConfig，无法恢复")
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        include_user = bool(getattr(prefs, "auto_exclusive_shift_s_include_user", True)) if prefs else True

        signatures = [("G", "PRESS", False, False, True, False, False, 'NONE')]
        restored = _restore_conflicts_for_signatures(wm.keyconfigs.addon, signatures)
        if include_user:
            restored += _restore_conflicts_for_signatures(wm.keyconfigs.user, signatures)

        self.report({'INFO'}, f"已恢复 {restored} 个被禁用的 Ctrl+G 快捷键")
        return {'FINISHED'}

class SIZE_TOOL_OT_ExclusiveAllHotkeys(bpy.types.Operator):
    bl_idname = "size_tool.exclusive_all_hotkeys"
    bl_label = "一键独占所有快捷键"
    bl_description = "自动禁用 Blender 内置或其它插件冲突的 Shift+S, Shift+E, Alt+A, Ctrl+S 等快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            bpy.ops.size_tool.exclusive_transform_pie_hotkey()
            bpy.ops.size_tool.exclusive_align_pie_hotkey()
            bpy.ops.size_tool.exclusive_edge_property_pie_hotkey()
            bpy.ops.size_tool.exclusive_save_pie_hotkey()
            bpy.ops.size_tool.exclusive_mirror_hotkey()
            self.report({'INFO'}, "已执行所有独占操作")
        except Exception as e:
            self.report({'WARNING'}, f"部分操作失败: {e}")
        return {'FINISHED'}

class SIZE_TOOL_OT_RestoreAllConflicts(bpy.types.Operator):
    bl_idname = "size_tool.restore_all_conflicts"
    bl_label = "一键恢复所有冲突"
    bl_description = "恢复被本插件禁用的所有冲突快捷键"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            bpy.ops.size_tool.restore_shift_s_conflicts()
            bpy.ops.size_tool.restore_alt_a_conflicts()
            bpy.ops.size_tool.restore_shift_e_conflicts()
            bpy.ops.size_tool.restore_ctrl_s_conflicts()
            bpy.ops.size_tool.restore_shift_alt_x_conflicts()
            self.report({'INFO'}, "已执行所有恢复操作")
        except Exception as e:
            self.report({'WARNING'}, f"部分操作失败: {e}")
        return {'FINISHED'}

class M8_OT_ResetSwitchModePrefs(bpy.types.Operator):
    bl_idname = "m8.reset_switch_mode_prefs"
    bl_label = "恢复默认(切换模式)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        prefs.switch_mode_smart_focus = True
        prefs.switch_mode_tab_behavior = "INSTANT"
        prefs.switch_mode_hold_ms = 220

        prefs.switch_mode_up = "SWITCH_MODE"
        prefs.switch_mode_down = "EDGE"
        prefs.switch_mode_left = "VERT"
        prefs.switch_mode_right = "FACE"

        prefs.switch_bone_mode_up = "EDIT_OR_OBJECT"
        prefs.switch_bone_mode_down = "EDIT"
        prefs.switch_bone_mode_left = "POSE"
        prefs.switch_bone_mode_right = "BONE_POSITION"

        prefs.ui_show_switch_mode_mapping = False
        prefs.ui_show_tab_keymap = False
        return {'FINISHED'}

class M8_OT_ResetPrefsUI(bpy.types.Operator):
    bl_idname = "m8.reset_prefs_ui"
    bl_label = "重置偏好界面"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        prefs.ui_show_tab_keymap = False
        prefs.ui_show_shift_keymap = False
        prefs.ui_show_switch_mode_mapping = False
        prefs.ui_show_shift_s_advanced = False
        prefs.ui_show_delete_keymap = False
        prefs.ui_show_delete_mapping = False
        prefs.ui_show_save_keymap = False
        prefs.ui_show_save_advanced = False
        
        prefs.ui_show_section_switch_mode = True
        prefs.ui_show_section_transform_pie = True
        prefs.ui_show_section_delete = True
        prefs.ui_show_section_other = True
        return {'FINISHED'}

class M8_MP7_MockDrawProperty(bpy.types.PropertyGroup):
    enable_name_translation: bpy.props.BoolProperty(name="Enable Name Translation", default=True)

class SIZE_TOOL_Preferences(bpy.types.AddonPreferences):
    bl_idname = (__package__ or "").split(".")[0]

    backup_suffix: bpy.props.StringProperty(name="备用盒后缀", default="_Backup")
    backup_collection_name: bpy.props.StringProperty(name="备用盒集合名", default="SizeTool_Backups")
    default_padding: bpy.props.FloatProperty(name="默认 Padding", default=0.0, min=0.0, unit='LENGTH')
    archive_default_bake: bpy.props.BoolProperty(name="备用盒默认烘焙", default=False)
    enable_transform_pie: bpy.props.BoolProperty(name="启用变换辅助饼菜单", default=True, update=_on_prefs_update)
    activate_switch_mode: bpy.props.BoolProperty(name="启用模式切换(Tab)", default=True, update=_on_prefs_update)
    activate_quick_delete: bpy.props.BoolProperty(name="快速删除(无确认)", default=True, update=_on_prefs_update)
    activate_delete_pie: bpy.props.BoolProperty(name="启用删除饼菜单(Edit)", default=True, update=_on_prefs_update)
    activate_align_pie: bpy.props.BoolProperty(name="启用对齐饼菜单 (Alt+A)", default=True, update=_on_prefs_update)
    activate_shading_pie: bpy.props.BoolProperty(name="启用着色饼菜单 (Z)", default=True, update=_on_prefs_update)
    activate_save_pie: bpy.props.BoolProperty(name="启用保存饼菜单 (Ctrl+S)", default=True, update=_on_prefs_update)
    activate_advanced_rename: bpy.props.BoolProperty(name="启用高级重命名 (F2)", default=True, update=_on_prefs_update)
    activate_mirror: bpy.props.BoolProperty(name="启用镜像 (Shift+Alt+X)", default=True, update=_on_prefs_update)
    activate_group_tool: bpy.props.BoolProperty(name="启用打组 (Ctrl+G)", default=True, update=_on_prefs_update)
    activate_smart_pie: bpy.props.BoolProperty(name="启用智能饼菜单 (1)", default=True, update=_on_prefs_update)
    
    # --- Toggle Area ---
    activate_toggle_area: bpy.props.BoolProperty(name="启用区域切换 (T)", default=True, update=_on_prefs_update)
    toggle_area_close_range: bpy.props.FloatProperty(name="关闭范围 (%)", default=30.0, min=0.0, max=100.0, description="以区域宽/高的百分比表示与边界的接近度")
    toggle_area_prefer_left_right: bpy.props.BoolProperty(name="首选左/右切换", default=True, description="在使用 Close Range 确定是否切换另一对之前，首选左/右切换，而不是 下/上")
    toggle_area_asset_shelf: bpy.props.BoolProperty(name="切换资产架", default=True, description="如果可用，则切换“资产工具架”而不是“浏览器”")
    toggle_area_asset_browser_top: bpy.props.BoolProperty(name="切换资产浏览器到顶部", default=True)
    toggle_area_asset_browser_bottom: bpy.props.BoolProperty(name="切换资产浏览器到底部", default=True)
    toggle_area_split_factor: bpy.props.FloatProperty(name="分割比例", default=0.25, min=0.1, max=0.8, description="切换出的资产浏览器占区域高度的比例")
    toggle_area_wrap_mouse: bpy.props.BoolProperty(name="鼠标跟随", default=False, description="将鼠标包围到资源浏览器边框")
    ui_show_toggle_area_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Toggle Area)", default=False)

    ui_show_smart_pie_keymap: bpy.props.BoolProperty(name="显示快捷键详情(智能饼菜单)", default=False)
    smart_edge_mode: bpy.props.EnumProperty(
        name="Smart Edge 模式",
        items=[
            ("SELECT", "选择区域 (Select)", "将闭合边环转换为面选择"),
            ("SHARPS", "锐边 (Sharps)", "标记或清除锐边"),
            ("BRIDGE", "桥接 (Bridge)", "桥接两个边环"),
            ("FILL", "填充 (Fill)", "填充闭合区域"),
        ],
        default="SELECT",
    )
    smart_face_focus_mode: bpy.props.BoolProperty(name="Smart Face: 聚焦模式", default=False)
    smart_face_stay_on_original: bpy.props.BoolProperty(name="Smart Face: 停留在原始对象", default=False)
    smart_face_action: bpy.props.EnumProperty(
        name="Smart Face 默认动作",
        items=[
            ("SEPARATE", "分离", ""),
            ("DUPLICATE", "复制后分离", ""),
            ("DISSOLVE", "溶解", ""),
            ("EXTRACT", "提取后分离", ""),
        ],
        default="SEPARATE",
    )
    clean_up_merge_distance: bpy.props.FloatProperty(name="Clean Up: 合并距离", default=0.0001, min=0.0)
    clean_up_affect: bpy.props.EnumProperty(
        name="Clean Up: 影响范围",
        items=[
            ("ALL", "全部", ""),
            ("SELECTED", "仅选中", ""),
        ],
        default="ALL",
    )
    clean_up_degenerate_dist: bpy.props.FloatProperty(name="Clean Up: 退化阈值", default=0.00001, min=0.0)
    clean_up_recalc_normals: bpy.props.BoolProperty(name="Clean Up: 重算法线", default=False)
    activate_double_click_select_group: bpy.props.BoolProperty(name="双击选择组", default=False, update=_on_prefs_update)
    group_tool_radius: bpy.props.FloatProperty(name="组半径", default=1.0, min=0.1, unit='LENGTH')
    group_tool_empty_type: bpy.props.EnumProperty(
        name="空物体类型",
        items=[
            ("PLAIN_AXES", "十字 (Plain Axes)", ""),
            ("ARROWS", "坐标轴 (Arrows)", ""),
            ("SINGLE_ARROW", "单箭头 (Single Arrow)", ""),
            ("CIRCLE", "圆环 (Circle)", ""),
            ("CUBE", "方块 (Cube)", ""),
            ("SPHERE", "球体 (Sphere)", ""),
            ("CONE", "锥体 (Cone)", ""),
            ("IMAGE", "图片 (Image)", ""),
        ],
        default="SPHERE",
    )
    group_tool_hide_empty: bpy.props.BoolProperty(name="隐藏组空物体", default=False, description="创建组时自动隐藏组父物体")
    activate_restart_blender: bpy.props.BoolProperty(name="启用重启 Blender 按钮", default=True)

    active_tab: bpy.props.EnumProperty(
        name="Tab",
        items=[
            ("GENERAL", "常规设置", "插件的主要功能设置"),
            ("ABOUT", "关于", "关于本插件"),
        ],
        default="GENERAL",
    )

    navigation_tab: bpy.props.EnumProperty(
        name="Navigation",
        items=[
            ("TRANSFORM", "变换", "Transform Pie"),
            ("SWITCH_MODE", "切换模式", "Switch Mode"),
            ("DELETE", "删除", "Delete Tools"),
            ("EDGE_PROPERTY", "边属性", "Edge Property"),
            ("ALIGN", "对齐", "Align Pie"),
            ("SHADING", "着色", "Shading Pie"),
            ("SAVE", "保存", "Save Pie"),
            ("RENAME", "重命名", "Advanced Rename"),
            ("MIRROR", "镜像", "Mirror Tool"),
            ("GROUP", "打组", "Group Tool"),
            ("SMART_PIE", "智能饼菜单", "Smart Pie (1)"),
            ("TOGGLE_AREA", "区域切换", "Toggle Area (T)"),
            ("SCREENCAST", "按键显示", "Screencast"),
            ("OTHER", "其它设置", "Other Settings"),
            ("ABOUT", "关于", "About"),
        ],
        default="TRANSFORM",
    )

    ui_show_all_settings: bpy.props.BoolProperty(name="显示全部", default=False)

    fbx_export_unity_preset: bpy.props.BoolProperty(name="FBX 导出使用 Unity 预设", default=False)
    unity_fbx_use_selection: bpy.props.BoolProperty(name="Unity FBX: 仅导出选择", default=True)
    unity_fbx_global_scale: bpy.props.FloatProperty(name="Unity FBX: 全局缩放", default=100.0, min=0.001, max=1000.0)
    unity_fbx_apply_unit_scale: bpy.props.BoolProperty(name="Unity FBX: 应用单位", default=True)
    unity_fbx_apply_scale_options: bpy.props.EnumProperty(
        name="Unity FBX: Apply Scalings",
        items=[
            ("FBX_SCALE_NONE", "All Local", ""),
            ("FBX_SCALE_UNITS", "FBX Units Scale", ""),
            ("FBX_SCALE_CUSTOM", "FBX Custom Scale", ""),
            ("FBX_SCALE_ALL", "FBX All", ""),
        ],
        default="FBX_SCALE_ALL",
    )
    unity_fbx_use_triangles: bpy.props.BoolProperty(name="Unity FBX: 三角化", default=True)
    unity_fbx_use_tspace: bpy.props.BoolProperty(name="Unity FBX: 导出切线", default=True)
    unity_fbx_bake_anim: bpy.props.BoolProperty(name="Unity FBX: 导出动画", default=False)
    unity_fbx_export_dir: bpy.props.StringProperty(name="Unity FBX: 导出目录", default="", subtype="DIR_PATH")
    unity_fbx_use_blend_dir: bpy.props.BoolProperty(name="Unity FBX: 使用 .blend 同目录", default=True)
    unity_fbx_open_folder_after_export: bpy.props.BoolProperty(name="Unity FBX: 导出后打开文件夹", default=False)
    unity_fbx_reveal_after_export: bpy.props.BoolProperty(name="Unity FBX: 导出后定位文件", default=True)
    ui_show_unity_fbx_advanced: bpy.props.BoolProperty(name="Unity FBX: 高级", default=False)

    auto_pack_resources_on_save: bpy.props.BoolProperty(name="保存时自动打包资源", default=False, update=_on_autopack_update)
    auto_purge_unused_materials_on_save: bpy.props.BoolProperty(name="保存时自动清除孤立数据", default=False, update=_on_autopack_update)
    
    auto_new_object_origin_bottom: bpy.props.BoolProperty(name="新建物体默认原点到底部", default=False, update=_on_autoorigin_update)
    auto_new_object_snap_to_floor: bpy.props.BoolProperty(name="新建物体自动落地 (Z=0)", default=False, update=_on_autoorigin_update)
    auto_exclusive_shift_s_on_startup: bpy.props.BoolProperty(name="启动时自动独占所有快捷键", default=True)
    auto_exclusive_shift_s_include_user: bpy.props.BoolProperty(name="同时处理用户键位冲突", default=True)

    # --- MP7Tools Integration Properties ---
    init: bpy.props.BoolProperty(name="Init", default=True, options={"SKIP_SAVE"})
    panel_name: bpy.props.StringProperty(name="Panel Name", default="M8")
    
    # MP7 Hub/Gizmo Settings
    hub_text_color: bpy.props.FloatVectorProperty(name="文本颜色", subtype='COLOR', default=(1, 1, 1, 1), size=4)
    hub_3d_color: bpy.props.FloatVectorProperty(name="轴向颜色", subtype='COLOR', default=(0.2, 0.6, 1, 0.8), size=4)
    hub_area_color: bpy.props.FloatVectorProperty(name="区域颜色", subtype='COLOR', default=(0.2, 0.6, 1, 0.2), size=4)
    hub_line_width: bpy.props.IntProperty(name="线宽", default=2, min=1, max=10)
    hub_vert_size: bpy.props.IntProperty(name="点大小", default=6, min=1, max=20)
    hub_matrix_line_width: bpy.props.IntProperty(name="轴线宽", default=3, min=1, max=10)
    hub_scale: bpy.props.FloatProperty(name="Gizmo 缩放", default=0.35, min=0.1, max=5.0)
    hub_fps: bpy.props.FloatProperty(name="FPS", default=60.0)
    
    # Mirror Preview Properties
    mirror_show_preview: bpy.props.BoolProperty(name="显示网格预览", default=False, description="在操作时显示镜像后的网格预览（可能会影响性能）")
    mirror_preview_vert_size: bpy.props.IntProperty(name="预览点大小", default=6, min=1, max=20)
    mirror_preview_edge_width: bpy.props.IntProperty(name="预览线宽", default=2, min=1, max=10)
    mirror_preview_max_edge_count: bpy.props.IntProperty(name="最大边数优化", default=10000, description="当物体边数超过此值时简化预览以提高性能")
    mirror_preview_optimize: bpy.props.BoolProperty(name="强制简化预览", default=False)
    mirror_preview_alpha: bpy.props.FloatProperty(name="预览透明度", default=0.5, min=0.0, max=1.0)
    mirror_preview_edge_color: bpy.props.FloatVectorProperty(name="预览线颜色", subtype='COLOR', default=(0.2, 0.8, 1.0, 1.0), size=4)
    
    mirror_use_mouse_pos: bpy.props.BoolProperty(name="Gizmo 跟随鼠标", default=True, description="启动时 Gizmo 出现在鼠标位置，而非物体原点")
    mirror_auto_confirm: bpy.props.BoolProperty(name="松开即确认", default=True, description="松开快捷键时自动执行镜像，无需点击左键")
    mirror_sensitivity: bpy.props.FloatProperty(name="感应灵敏度", default=2.0, min=0.1, max=5.0, description="Gizmo 触发距离的缩放系数")
    mirror_use_fixed_scale: bpy.props.BoolProperty(name="使用固定大小", default=False, description="Gizmo 使用固定大小，不随视图缩放变化")
    mirror_fixed_scale_value: bpy.props.FloatProperty(name="固定大小值", default=1.0, min=0.01, max=1000.0)
    
    activate_face_groups: bpy.props.BoolProperty(name="启用面组", default=True)

    origin_default_operator_types: bpy.props.EnumProperty(
        items=[
            ("ROTATE", "Rotate", ""),
            ("LOCATION", "Location", ""),
        ],
        default={"ROTATE", "LOCATION"},
        options={"ENUM_FLAG"},
        name="Default Origin Operator",
        description="Shift Add Selection",
    )
    moving_view_type: bpy.props.EnumProperty(
        default="ANIMATION",
        name="Moving View Type",
        items=[
            ("NONE", "None", "", "RESTRICT_SELECT_ON", 0),
            ("MAINTAINING_ZOOM", "Maintaining Zoom", "", "VIEWZOOM", 1),
            ("ANIMATION", "Animation", "", "ANIM", 2),
        ]
    )
    draw_property: bpy.props.PointerProperty(type=M8_MP7_MockDrawProperty)

    ui_show_tab_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Tab)", default=False)
    ui_show_shift_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Shift+S)", default=False)
    ui_show_switch_mode_mapping: bpy.props.BoolProperty(name="显示方向映射", default=False)
    ui_show_shift_s_advanced: bpy.props.BoolProperty(name="显示高级(Shift+S)", default=False)
    ui_show_other_settings: bpy.props.BoolProperty(name="显示其它设置", default=False)
    ui_show_delete_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Delete)", default=False)
    ui_show_delete_mapping: bpy.props.BoolProperty(name="显示方向映射(Delete)", default=False)
    ui_show_align_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Align)", default=False)
    ui_show_align_advanced: bpy.props.BoolProperty(name="显示高级(Align)", default=False)
    ui_show_shading_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Shading)", default=False)
    ui_show_save_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Save)", default=False)
    ui_show_save_advanced: bpy.props.BoolProperty(name="显示高级(Save)", default=False)

    ui_show_section_switch_mode: bpy.props.BoolProperty(name="切换模式 (Tab)", default=False)
    ui_show_section_transform_pie: bpy.props.BoolProperty(name="变换辅助 (Shift+S)", default=False)
    ui_show_section_delete: bpy.props.BoolProperty(name="删除 (X)", default=False)
    ui_show_section_align_pie: bpy.props.BoolProperty(name="对齐 (Alt+A)", default=False)
    ui_show_section_shading_pie: bpy.props.BoolProperty(name="着色 (Z)", default=False)
    ui_show_section_save_pie: bpy.props.BoolProperty(name="保存 (Ctrl+S)", default=False)
    ui_show_section_rename: bpy.props.BoolProperty(name="重命名 (F2)", default=False)
    ui_show_section_mirror: bpy.props.BoolProperty(name="镜像 (Shift+Alt+X)", default=False)
    ui_show_section_other: bpy.props.BoolProperty(name="其它设置", default=False)
    ui_show_section_screencast: bpy.props.BoolProperty(name="Screencast (投射)", default=False)

    # --- Edge Property Properties ---
    activate_edge_property_pie: bpy.props.BoolProperty(name="启用 Edge Property Pie", default=True, update=_on_prefs_update)
    ui_show_edge_property_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Edge Property)", default=False)
    ui_show_edge_property_advanced: bpy.props.BoolProperty(name="显示高级(Edge Property)", default=False)

    # --- Mirror Properties ---
    ui_show_mirror_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Mirror)", default=False)
    ui_show_mirror_advanced: bpy.props.BoolProperty(name="显示高级(Mirror)", default=False)
    ui_show_group_keymap: bpy.props.BoolProperty(name="显示快捷键详情(Group)", default=False)
    ui_show_group_advanced: bpy.props.BoolProperty(name="显示高级(Group)", default=False)

    # --- Screencast Properties ---
    def _on_screencast_enabled_update(self, context):
        try:
            from ..ops.misc.screencast import M8_OT_InternalScreencast
            # Sync state: If enabled but not running -> Start. If disabled but running -> Stop.
            # We use the operator to toggle state.
            if self.screencast_enabled != M8_OT_InternalScreencast._running:
                # We need a context override for 3D view usually, but 'INVOKE_DEFAULT' might find one?
                # Or we just try running it. The operator checks _running flag globally.
                # But it needs to register handlers in a specific context/area?
                # The operator attaches handler to 'WINDOW', so it covers all views?
                # Actually handler is SpaceView3D.draw_handler_add.
                # So it needs to run in a context that can access SpaceView3D? No, handler is global type based.
                # But 'invoke' usually needs context.
                
                # Let's try finding a context if needed.
                found = False
                for win in context.window_manager.windows:
                    for area in win.screen.areas:
                        if area.type == 'VIEW_3D':
                            with context.temp_override(window=win, area=area):
                                bpy.ops.m8.internal_screencast('INVOKE_DEFAULT')
                            found = True
                            break
                    if found: break
                
                if not found:
                    # Fallback
                    bpy.ops.m8.internal_screencast('INVOKE_DEFAULT')
        except Exception:
            pass

    screencast_enabled: bpy.props.BoolProperty(
        name="启用 Screencast", 
        default=False, 
        description="启用/禁用屏幕投射功能",
        update=_on_screencast_enabled_update
    )
    screencast_font_size: bpy.props.IntProperty(name="字体大小", default=20, min=8, max=100)
    screencast_color: bpy.props.FloatVectorProperty(name="文字颜色", subtype='COLOR', default=(1, 1, 1, 1), size=4, min=0, max=1)
    screencast_bg_color: bpy.props.FloatVectorProperty(name="背景颜色", subtype='COLOR', default=(0.1, 0.1, 0.1, 0.5), size=4, min=0, max=1)
    screencast_offset_x: bpy.props.IntProperty(name="X 偏移", default=50)
    screencast_offset_y: bpy.props.IntProperty(name="Y 偏移", default=50)
    screencast_align: bpy.props.EnumProperty(
        name="对齐", 
        items=[
            ("LEFT", "左", ""), 
            ("CENTER", "中", ""), 
            ("RIGHT", "右", "")
        ], 
        default="LEFT"
    )
    screencast_history_count: bpy.props.IntProperty(name="显示行数", default=5, min=1, max=20)
    screencast_timeout: bpy.props.FloatProperty(name="消失延迟 (秒)", default=2.0, min=0.1, max=10.0)
    screencast_show_mouse: bpy.props.BoolProperty(name="显示鼠标点击", default=True)
    screencast_show_mouse_move: bpy.props.BoolProperty(name="显示鼠标移动", default=False)
    screencast_show_last_operator: bpy.props.BoolProperty(name="显示最后操作", default=True)
    screencast_style: bpy.props.EnumProperty(
        name="显示风格",
        items=[
            ("KEYCAPS", "键帽", ""),
            ("BOX", "文本框", ""),
        ],
        default="KEYCAPS",
    )
    screencast_cap_radius: bpy.props.IntProperty(name="键帽圆角", default=8, min=0, max=50)
    screencast_cap_gap: bpy.props.IntProperty(name="键帽间距", default=6, min=0, max=30)
    screencast_cap_shadow: bpy.props.BoolProperty(name="键帽阴影", default=True)
    screencast_cap_uppercase: bpy.props.BoolProperty(name="键帽大写", default=True)
    screencast_cap_bg_color: bpy.props.FloatVectorProperty(name="键帽背景", subtype='COLOR', default=(0.06, 0.06, 0.06, 0.65), size=4, min=0, max=1)
    screencast_cap_outline_color: bpy.props.FloatVectorProperty(name="键帽描边", subtype='COLOR', default=(1, 1, 1, 0.15), size=4, min=0, max=1)
    screencast_translate_operator_label: bpy.props.BoolProperty(name="汉化操作提示", default=True)
    screencast_operator_label_mode: bpy.props.EnumProperty(
        name="操作提示语言",
        items=[
            ("ZH", "中文优先", ""),
            ("EN", "英文", ""),
            ("BOTH", "中文/英文", ""),
        ],
        default="ZH",
    )
    screencast_use_symbols: bpy.props.BoolProperty(name="使用符号显示修饰键 (⌃⇧⌥⌘)", default=False)
    screencast_smart_merge_numbers: bpy.props.BoolProperty(name="智能合并数字输入", default=True, description="将连续输入的数字（如 1,2,.）合并显示为单个数值")
    screencast_stack_direction: bpy.props.EnumProperty(
        name="堆叠方向",
        items=[
            ("UP", "向上 (Bottom-Up)", "新消息在上方"),
            ("DOWN", "向下 (Top-Down)", "新消息在下方"),
        ],
        default="UP"
    )
    screencast_entry_animation: bpy.props.BoolProperty(name="启用入场动画", default=True)

    # --- Mode Switching Properties ---
    items = [
        ("VERT", "Vert", ""),
        ("EDGE", "Edge", ""),
        ("FACE", "Face", ""),
        ("SWITCH_MODE", "Switch Mode", "")
    ]
    switch_mode_up: bpy.props.EnumProperty(items=items, name="Up", default="SWITCH_MODE")
    switch_mode_down: bpy.props.EnumProperty(items=items, name="Down", default="EDGE")
    switch_mode_left: bpy.props.EnumProperty(items=items, name="Left", default="VERT")
    switch_mode_right: bpy.props.EnumProperty(items=items, name="Right", default="FACE")

    bone_items = [
        ("EDIT_OR_OBJECT", "Edit/Object", ""),
        ("BONE_POSITION", "Bone Position", ""),
        ("POSE", "Pose", ""),
        ("EDIT", "Edit(Only Pose)", "Only show in pose mode"),
        ("VIEW_SELECTED", "View Selected", ""),
        ("TOGGLE_XRAY", "Toggle X-Ray", ""),
        ("TOGGLE_NAMES", "Toggle Names", ""),
        ("TOGGLE_AXES", "Toggle Axes", ""),
    ]
    switch_bone_mode_up: bpy.props.EnumProperty(items=bone_items, name="Up", default="EDIT_OR_OBJECT")
    switch_bone_mode_down: bpy.props.EnumProperty(items=bone_items, name="Down", default="VIEW_SELECTED")
    switch_bone_mode_left: bpy.props.EnumProperty(items=bone_items, name="Left", default="BONE_POSITION")
    switch_bone_mode_right: bpy.props.EnumProperty(items=bone_items, name="Right", default="POSE")

    # --- Delete Pie Properties ---
    delete_items = [
        ("DELETE_VERT", "删除顶点", "", "VERTEXSEL", 1),
        ("DELETE_EDGE", "删除边", "", "EDGESEL", 2),
        ("DELETE_FACE", "删除面", "", "FACESEL", 3),
        ("DISSOLVE_VERT", "融并顶点", "", "VERTEXSEL", 4),
        ("DISSOLVE_EDGE", "融并边", "", "MOD_WIREFRAME", 5),
        ("DISSOLVE_FACE", "融并面", "", "FACESEL", 6),
        ("LIMITED_DISSOLVE", "有限融并", "", "MESH_DATA", 7),
        ("EDGE_LOOP", "循环边", "", "MOD_EDGESPLIT", 8),
        ("EDGE_COLLAPSE", "塌陷边", "", "UV_EDGESEL", 9),
        ("ONLY_EDGE_FACE", "仅边和面", "", "EDGESEL", 10),
        ("ONLY_FACE", "仅面", "", "FACESEL", 11),
        ("DISSOLVE_ALL", "融并点线面", "", "MOD_WIREFRAME", 12),
        ("NONE", "无", "", "X", 0),
    ]
    delete_pie_left: bpy.props.EnumProperty(items=delete_items, name="Left", default="DELETE_VERT")
    delete_pie_right: bpy.props.EnumProperty(items=delete_items, name="Right", default="DELETE_FACE")
    delete_pie_down: bpy.props.EnumProperty(items=delete_items, name="Down", default="DELETE_EDGE")
    delete_pie_up: bpy.props.EnumProperty(items=delete_items, name="Up", default="DISSOLVE_ALL")
    delete_pie_top_left: bpy.props.EnumProperty(items=delete_items, name="Top-Left", default="EDGE_LOOP")
    delete_pie_top_right: bpy.props.EnumProperty(items=delete_items, name="Top-Right", default="EDGE_COLLAPSE")
    delete_pie_bottom_left: bpy.props.EnumProperty(items=delete_items, name="Bottom-Left", default="ONLY_EDGE_FACE")
    delete_pie_bottom_right: bpy.props.EnumProperty(items=delete_items, name="Bottom-Right", default="ONLY_FACE")


    switch_mode_smart_focus: bpy.props.BoolProperty(
        name="Smart Focus",
        description="If the object cannot switch modes, it will focus on the object",
        default=True
    )

    switch_mode_double_click_edit_switch: bpy.props.BoolProperty(
        name="双击切换编辑对象",
        description="网格编辑模式下，双击其他物体切换到其编辑模式",
        default=False,
        update=_on_prefs_update,
    )

    switch_mode_tab_behavior: bpy.props.EnumProperty(
        name="Tab 行为",
        items=[
            ("INSTANT", "立即执行(兼容)", "按下 Tab 立即执行（与 Blender 默认更接近）"),
            ("TAP_HOLD", "轻按切换 / 长按菜单", "轻按执行默认行为，长按弹出模式切换饼菜单"),
        ],
        default="INSTANT",
        update=_on_prefs_update,
    )
    switch_mode_hold_ms: bpy.props.IntProperty(
        name="长按阈值(ms)",
        default=220,
        min=80,
        max=1000,
        update=_on_prefs_update,
    )

    def draw_switch_mode_basic(self, layout):
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "switch_mode_smart_focus")
        layout.prop(self, "switch_mode_double_click_edit_switch")
        layout.prop(self, "switch_mode_tab_behavior")
        sub = layout.column()
        sub.enabled = self.switch_mode_tab_behavior == "TAP_HOLD"
        sub.prop(self, "switch_mode_hold_ms")

    def draw_switch_mode_mapping(self, layout):
        layout.use_property_split = True
        layout.use_property_decorate = False

        draw_data = {1: "up", 3: "left", 5: "right", 7: "down"}
        box_a = layout.box()
        box_a.label(text="3D 视图", icon="VIEW3D")
        box_b = layout.box()
        box_b.label(text="骨骼", icon="ARMATURE_DATA")

        for i in range(3):
            row_a = box_a.row(align=True)
            row_b = box_b.row(align=True)
            for j in range(3):
                index = i * 3 + j
                direction = draw_data.get(index)
                if direction:
                    row_a.prop(self, f"switch_mode_{direction}", text="")
                    row_b.prop(self, f"switch_bone_mode_{direction}", text="")
                else:
                    row_a.label(text="")
                    row_b.label(text="")

    def draw_delete_mapping(self, layout):
        layout.use_property_split = False
        layout.use_property_decorate = False
        
        mapping = {
            0: "delete_pie_top_left", 1: "delete_pie_up", 2: "delete_pie_top_right",
            3: "delete_pie_left",                     5: "delete_pie_right",
            6: "delete_pie_bottom_left", 7: "delete_pie_down", 8: "delete_pie_bottom_right"
        }

        box = layout.box()
        box.label(text="网格编辑模式 (Edit Mesh)", icon="EDITMODE_HLT")
        grid_col = box.column()

        for i in range(3):
            if i > 0:
                grid_col.separator(factor=4.0)
            
            row = grid_col.row()
            split = row.split(factor=0.2)
            col1 = split.column()
            split = split.split(factor=0.25)
            split.column() # Gap
            split = split.split(factor=0.333)
            col2 = split.column()
            split = split.split(factor=0.5)
            split.column() # Gap
            col3 = split.column()
            
            cols = [col1, col2, col3]
            
            for j in range(3):
                idx = i * 3 + j
                prop_name = mapping.get(idx)
                if prop_name:
                    cols[j].prop(self, prop_name, text="")
                else:
                    cols[j].label(text="")

    def draw_about_settings(self, layout):
        col = layout.column(align=True)
        
        # Logo / Title
        row = col.row(align=True)
        row.alignment = 'CENTER'
        row.scale_y = 1.5
        row.label(text="M8 全能工具箱", icon="TOPBAR")
        
        col.separator()
        
        # Info Grid
        box = col.box()
        grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True)
        
        grid.label(text="作者: 猫步可爱")
        grid.label(text="版本: 2.0")
        
        col.separator()
        
        # Description
        box = col.box()
        box.label(text="功能简介:", icon="INFO")
        box.label(text="• 变换辅助: 增强 Shift+S，快速调整原点和游标")
        box.label(text="• 模式切换: 智能 Tab 切换，支持多模式")
        box.label(text="• 智能删除: 快速删除物体和网格元素")
        box.label(text="• 对齐工具: 强大的物体和元素对齐功能")
        box.label(text="• 视图着色: 快速切换透视、线框、实体及渲染预览模式")
        box.label(text="• 保存导出: 自动打包资源、清理材质及 Unity FBX 导出预设")
        box.label(text="• 批量命名: 支持变量、正则替换、序号生成及预览")
        box.label(text="• 按键显示: 实时在视口显示键盘鼠标操作")

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "active_tab", expand=True)
        layout.separator()

        if self.active_tab == "GENERAL":
            self.draw_general(context)
        else:
            self.draw_about_settings(layout)

    def _draw_sidebar_button(self, layout, icon, text, item_value):
        # 移除 row.alignment = 'LEFT' 让按钮充满宽度
        # 增加 scale_y 让按钮稍微高一点，更有点击感
        row = layout.row(align=True)
        row.scale_y = 1.25
        
        # 提示：Blender 的 prop_enum 会自动处理选中状态的高亮
        # 我们使用 EMBOSS (默认) 风格，这样选中时会有凹陷感
        # 如果当前项被选中，我们可以加一个图标或者改变文字来增强提示，但 prop_enum 本身已经足够
        
        if self.navigation_tab == item_value:
            # 选中状态：使用主图标，并且不高亮（保持按下状态）
            row.prop_enum(self, "navigation_tab", item_value, icon=icon, text=text)
        else:
            # 未选中状态：也可以正常绘制，保持可点击
            row.prop_enum(self, "navigation_tab", item_value, icon=icon, text=text)

    def _get_tab_description(self, key=None):
        key = key or self.navigation_tab
        desc = {
            "TRANSFORM": ("变换辅助", "Shift+S 增强版，包含原点调整、游标控制及变换操作"),
            "SWITCH_MODE": ("模式切换", "Tab 智能切换，支持物体、编辑、骨骼及UV模式的快速切换"),
            "DELETE": ("智能删除", "X/Del 键增强，根据选区智能判断删除元素，无需弹窗确认"),
            "EDGE_PROPERTY": ("边属性", "Shift+E 增强，支持快速设置 Crease, Bevel Weight, Seam, Sharp 等"),
            "ALIGN": ("对齐工具", "Alt+A 增强版，提供物体、网格、UV的对齐与分布功能"),
            "SHADING": ("视图着色", "Z 键增强，快速切换透视、线框、实体及渲染预览模式"),
            "SAVE": ("保存导出", "Ctrl+S 增强，支持自动打包资源、清理材质及 Unity FBX 导出预设"),
            "RENAME": ("批量命名", "F2 增强，支持变量($N $T)、正则替换、序号生成及预览"),
            "MIRROR": ("镜像工具", "Shift+Alt+X，提供直观的轴向滑动选择镜像功能"),
            "SMART_PIE": ("智能饼菜单", "编辑模式下 1/2/3 的智能建模操作合集（顶点/边/面/清理/路径等）"),
            "TOGGLE_AREA": ("区域切换", "T 键切换 Toolbar/Sidebar 及 Asset Browser/Shelf"),
            "SCREENCAST": ("按键显示", "实时在视口显示键盘鼠标操作，支持自定义外观"),
            "OTHER": ("系统设置", "包含备份设置、新建物体默认行为等全局选项"),
            "ABOUT": ("关于", "关于 M8 工具箱"),
        }
        return desc.get(key, ("", ""))

    def draw_general(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        icon_map = {
            "TRANSFORM": "PIVOT_CURSOR",
            "SWITCH_MODE": "FILE_REFRESH",
            "DELETE": "TRASH",
            "EDGE_PROPERTY": "EDGESEL",
            "ALIGN": "ALIGN_CENTER",
            "SHADING": "SHADING_RENDERED",
            "SAVE": "FILE_TICK",
            "RENAME": "FONT_DATA",
            "MIRROR": "MOD_MIRROR",
            "GROUP": "EMPTY_AXIS",
            "SMART_PIE": "VIEW3D",
            "TOGGLE_AREA": "FULLSCREEN_ENTER",
            "SCREENCAST": "WINDOW",
            "OTHER": "PREFERENCES",
        }

        split = layout.split(factor=0.23)

        col = split.column(align=True)
        nav_box = col.box()
        col_nav = nav_box.column(align=True)

        col_nav.label(text="核心功能", icon="MODIFIER")
        self._draw_sidebar_button(col_nav, "PIVOT_CURSOR", "变换 (Shift+S)", "TRANSFORM")
        self._draw_sidebar_button(col_nav, "FILE_REFRESH", "切换模式 (Tab)", "SWITCH_MODE")
        self._draw_sidebar_button(col_nav, "TRASH", "删除 (X)", "DELETE")
        self._draw_sidebar_button(col_nav, "EDGESEL", "边属性 (Shift+E)", "EDGE_PROPERTY")
        self._draw_sidebar_button(col_nav, "ALIGN_CENTER", "对齐 (Alt+A)", "ALIGN")
        self._draw_sidebar_button(col_nav, "SHADING_RENDERED", "着色 (Z)", "SHADING")
        self._draw_sidebar_button(col_nav, "MOD_MIRROR", "镜像 (Shift+Alt+X)", "MIRROR")
        self._draw_sidebar_button(col_nav, "EMPTY_AXIS", "打组 (Ctrl+G)", "GROUP")
        self._draw_sidebar_button(col_nav, "FILE_TICK", "保存 (Ctrl+S)", "SAVE")
        self._draw_sidebar_button(col_nav, "VIEW3D", "智能饼菜单 (1)", "SMART_PIE")
        self._draw_sidebar_button(col_nav, "FULLSCREEN_ENTER", "区域切换 (T)", "TOGGLE_AREA")

        col_nav.separator()
        col_nav.label(text="实用工具", icon="TOOL_SETTINGS")
        self._draw_sidebar_button(col_nav, "FONT_DATA", "重命名 (F2)", "RENAME")
        self._draw_sidebar_button(col_nav, "WINDOW", "按键显示", "SCREENCAST")

        col_nav.separator()
        col_nav.label(text="设置", icon="PREFERENCES")
        self._draw_sidebar_button(col_nav, "PREFERENCES", "其它设置", "OTHER")
        col_nav.separator()
        col_nav.prop(self, "ui_show_all_settings", text="显示全部", toggle=True, icon="ALIGN_JUSTIFY")

        col = split.column()

        header_box = col.box()
        header_row = header_box.row(align=True)
        header_row.alignment = "LEFT"
        if self.ui_show_all_settings:
            header_row.label(text="全部设置", icon="PREFERENCES")
        else:
            title, desc = self._get_tab_description()
            header_row.label(text=title, icon=icon_map.get(self.navigation_tab, "INFO"))

        desc_row = header_box.row(align=True)
        desc_row.alignment = "LEFT"
        if self.ui_show_all_settings:
            desc_row.label(text="按模块分区显示全部偏好设置")
        else:
            desc_row.label(text=desc)

        col.separator()

        if self.ui_show_all_settings:
            ordered = [
                "TRANSFORM",
                "SWITCH_MODE",
                "DELETE",
                "EDGE_PROPERTY",
                "ALIGN",
                "SHADING",
                "SAVE",
                "RENAME",
                "MIRROR",
                "GROUP",
                "SMART_PIE",
                "TOGGLE_AREA",
                "SCREENCAST",
                "OTHER",
            ]
            for key in ordered:
                section = col.box()
                row = section.row(align=True)
                row.prop_enum(self, "navigation_tab", key, text=self._get_tab_description(key)[0], icon=icon_map.get(key, "DOT"))
                sub = section.column()
                if key == "TRANSFORM":
                    self.draw_transform_settings(sub)
                elif key == "SWITCH_MODE":
                    self.draw_switch_mode_settings(sub)
                elif key == "DELETE":
                    self.draw_delete_settings(sub)
                elif key == "EDGE_PROPERTY":
                    self.draw_edge_property_settings(sub)
                elif key == "ALIGN":
                    self.draw_align_settings(sub)
                elif key == "SHADING":
                    self.draw_shading_settings(sub)
                elif key == "SAVE":
                    self.draw_save_settings(sub)
                elif key == "RENAME":
                    self.draw_rename_settings(sub)
                elif key == "MIRROR":
                    self.draw_mirror_settings(sub)
                elif key == "GROUP":
                    self.draw_group_settings(sub)
                elif key == "SMART_PIE":
                    self.draw_smart_pie_settings(sub)
                elif key == "TOGGLE_AREA":
                    self.draw_toggle_area_settings(sub)
                elif key == "SCREENCAST":
                    self.draw_screencast_settings(sub)
                elif key == "OTHER":
                    self.draw_other_settings(sub)
        else:
            box = col.box()
            if self.navigation_tab == "TRANSFORM":
                self.draw_transform_settings(box)
            elif self.navigation_tab == "SWITCH_MODE":
                self.draw_switch_mode_settings(box)
            elif self.navigation_tab == "DELETE":
                self.draw_delete_settings(box)
            elif self.navigation_tab == "EDGE_PROPERTY":
                self.draw_edge_property_settings(box)
            elif self.navigation_tab == "ALIGN":
                self.draw_align_settings(box)
            elif self.navigation_tab == "SHADING":
                self.draw_shading_settings(box)
            elif self.navigation_tab == "SAVE":
                self.draw_save_settings(box)
            elif self.navigation_tab == "RENAME":
                self.draw_rename_settings(box)
            elif self.navigation_tab == "MIRROR":
                self.draw_mirror_settings(box)
            elif self.navigation_tab == "GROUP":
                self.draw_group_settings(box)
            elif self.navigation_tab == "SMART_PIE":
                self.draw_smart_pie_settings(box)
            elif self.navigation_tab == "TOGGLE_AREA":
                self.draw_toggle_area_settings(box)
            elif self.navigation_tab == "SCREENCAST":
                self.draw_screencast_settings(box)
            elif self.navigation_tab == "OTHER":
                self.draw_other_settings(box)

    def draw_switch_mode_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_switch_mode")
        row.prop(self, "ui_show_tab_keymap", text="快捷键")
        row.prop(self, "ui_show_switch_mode_mapping", text="映射")
        row.operator("size_tool.force_switch_mode_priority", text="置顶", icon="SORT_DESC")
        row.operator("m8.reset_switch_mode_prefs", text="恢复默认", icon="LOOP_BACK")

        if self.activate_switch_mode:
            self.draw_switch_mode_basic(col)

            if self.ui_show_tab_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    items = _find_switch_mode_keymap_items()
                    if not items:
                        sub_col.label(text="未找到 Tab 绑定", icon="INFO")
                    else:
                        for kc, km, kmi in items:
                            row = sub_col.row(align=True)
                            row.label(text=km.name, icon="DOT")
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass

            if self.ui_show_switch_mode_mapping:
                self.draw_switch_mode_mapping(col)

    def draw_transform_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "enable_transform_pie")
        row.prop(self, "ui_show_shift_keymap", text="快捷键")
        row.prop(self, "ui_show_shift_s_advanced", text="高级")
        row.operator("m8.reset_prefs_ui", text="", icon="TRASH")

        if self.enable_transform_pie:
            if self.ui_show_shift_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    kc, km, kmi = _find_pie_keymap_item()
                    if kc and km and kmi:
                        rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                    else:
                        sub_col.label(text="未找到 Shift+S 绑定", icon="INFO")
                except Exception:
                    pass

            if self.ui_show_shift_s_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_transform_pie_hotkey", text="独占(禁用冲突)")
                row.operator("size_tool.restore_shift_s_conflicts", text="恢复冲突")
                row = sub_col.row(align=True)
                row.operator("size_tool.force_transform_pie_priority", text="强制置顶")
                row.operator("size_tool.reset_transform_pie_keymap", text="恢复默认")
                sub_col.prop(self, "auto_exclusive_shift_s_on_startup")
                sub_col.prop(self, "auto_exclusive_shift_s_include_user")

    def draw_delete_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_quick_delete", text="快速删除 (Object)")
        row.prop(self, "activate_delete_pie", text="饼菜单 (Edit)")
        row.prop(self, "ui_show_delete_keymap", text="快捷键")
        row.prop(self, "ui_show_delete_mapping", text="映射")

        if self.activate_quick_delete or self.activate_delete_pie:
            if self.ui_show_delete_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    quick_items = _find_quick_delete_keymap_items()
                    pie_items = _find_delete_pie_keymap_items()
                    
                    if not quick_items and not pie_items:
                            sub_col.label(text="未找到删除相关绑定", icon="INFO")
                    
                    if quick_items:
                        sub_col.label(text="快速删除 (Object):")
                        for kc, km, kmi in quick_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                            
                    if pie_items:
                        sub_col.label(text="饼菜单 (Edit Mesh):")
                        for kc, km, kmi in pie_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)

                except Exception:
                    pass

            if self.ui_show_delete_mapping and self.activate_delete_pie:
                    self.draw_delete_mapping(col)

    def draw_edge_property_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_edge_property_pie", text="启用 Shift+E")
        row.prop(self, "ui_show_edge_property_keymap", text="快捷键")
        row.prop(self, "ui_show_edge_property_advanced", text="高级")
        row.operator("m8.reset_prefs_ui", text="", icon="TRASH")

        if self.activate_edge_property_pie:
            if self.ui_show_edge_property_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    items = _find_edge_property_pie_keymap_items()
                    
                    if not items:
                        sub_col.label(text="未找到 Edge Property 绑定", icon="INFO")
                    else:
                        for kc, km, kmi in items:
                            row = sub_col.row(align=True)
                            row.label(text=km.name, icon="DOT")
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass

            if self.ui_show_edge_property_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_edge_property_pie_hotkey", text="独占(禁用冲突)")
                row.operator("size_tool.restore_shift_e_conflicts", text="恢复冲突")
                row = sub_col.row(align=True)
                row.operator("size_tool.force_edge_property_pie_priority", text="强制置顶")

    def draw_align_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_align_pie")
        row.prop(self, "ui_show_align_keymap", text="快捷键")
        row.prop(self, "ui_show_align_advanced", text="高级")
        row.operator("m8.reset_prefs_ui", text="", icon="TRASH")

        if self.activate_align_pie:
            if self.ui_show_align_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    align_items = _find_align_pie_keymap_items()
                    
                    if not align_items:
                            sub_col.label(text="未找到对齐相关绑定", icon="INFO")
                    else:
                        for kc, km, kmi in align_items:
                            row = sub_col.row(align=True)
                            mode_label = km.name
                            if mode_label == "3D View Generic": mode_label = "3D 视图通用"
                            elif mode_label == "Object Mode": mode_label = "物体模式"
                            elif mode_label == "Mesh": mode_label = "网格编辑"
                            elif mode_label == "UV Editor": mode_label = "UV 编辑器"
                            
                            row.label(text=mode_label, icon="DOT")
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass
            
            if self.ui_show_align_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_align_pie_hotkey", text="独占(禁用冲突)")
                row.operator("size_tool.restore_alt_a_conflicts", text="恢复冲突")
                row = sub_col.row(align=True)
                row.operator("size_tool.force_align_pie_priority", text="强制置顶")

    def draw_shading_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_shading_pie")
        row.prop(self, "ui_show_shading_keymap", text="快捷键")
        row.operator("m8.reset_prefs_ui", text="", icon="TRASH")

        if self.activate_shading_pie:
            if self.ui_show_shading_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    shading_items = _find_shading_pie_keymap_items()
                    
                    if not shading_items:
                            sub_col.label(text="未找到着色相关绑定", icon="INFO")
                    else:
                        for kc, km, kmi in shading_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass

    def draw_save_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_save_pie")
        row.prop(self, "ui_show_save_keymap", text="快捷键")
        row.prop(self, "ui_show_save_advanced", text="高级")
        row.operator("m8.reset_prefs_ui", text="", icon="TRASH")

        if self.activate_save_pie:
            col.prop(self, "auto_pack_resources_on_save")
            col.prop(self, "auto_purge_unused_materials_on_save")
            col.prop(self, "fbx_export_unity_preset")
            sub = col.column()
            sub.enabled = bool(self.fbx_export_unity_preset)
            sub.operator("m8.reset_unity_fbx_preset", text="设为 Unity 标准", icon="FILE_REFRESH")
            sub.prop(self, "unity_fbx_use_blend_dir")
            row = sub.row(align=True)
            row.enabled = not bool(self.unity_fbx_use_blend_dir)
            row.prop(self, "unity_fbx_export_dir")
            sub.prop(self, "unity_fbx_reveal_after_export")
            sub.prop(self, "ui_show_unity_fbx_advanced", text="Unity FBX 高级")
            if self.ui_show_unity_fbx_advanced:
                sub.prop(self, "unity_fbx_use_selection")
                sub.prop(self, "unity_fbx_global_scale")
                sub.prop(self, "unity_fbx_apply_unit_scale")
                sub.prop(self, "unity_fbx_apply_scale_options")
                sub.prop(self, "unity_fbx_use_triangles")
                sub.prop(self, "unity_fbx_use_tspace")
                sub.prop(self, "unity_fbx_bake_anim")
                sub.prop(self, "unity_fbx_open_folder_after_export")

            if self.ui_show_save_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    save_items = _find_save_pie_keymap_items()
                    
                    if not save_items:
                            sub_col.label(text="未找到保存相关绑定", icon="INFO")
                    else:
                        for kc, km, kmi in save_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass

            if self.ui_show_save_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_save_pie_hotkey", text="独占(禁用冲突)")
                row.operator("size_tool.restore_ctrl_s_conflicts", text="恢复冲突")
                row = sub_col.row(align=True)
                row.operator("size_tool.force_save_pie_priority", text="强制置顶")

    def draw_rename_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_advanced_rename")
        
        sub_col = col.column()
        try:
            import rna_keymap_ui
            rename_items = _find_rename_keymap_items()
            
            if not rename_items:
                    sub_col.label(text="未找到重命名相关绑定", icon="INFO")
            else:
                for kc, km, kmi in rename_items:
                    rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
        except Exception:
            pass

    def draw_mirror_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_mirror")
        row.prop(self, "ui_show_mirror_keymap", text="快捷键")
        row.prop(self, "ui_show_mirror_advanced", text="高级")
        row.operator("m8.reset_prefs_ui", text="", icon="TRASH")

        if self.activate_mirror:
            # Appearance Settings
            box = col.box()
            box.label(text="外观设置:", icon="BRUSH_DATA")
            row = box.row()
            row.prop(self, "hub_scale")
            
            row = box.row()
            row.prop(self, "hub_3d_color")
            row.prop(self, "hub_area_color")
            row.prop(self, "hub_text_color")
            
            row = box.row()
            row.prop(self, "hub_line_width")
            row.prop(self, "hub_matrix_line_width")

            box.label(text="预览设置:", icon="SHADING_WIREFRAME")
            row = box.row()
            row.prop(self, "mirror_show_preview")
            
            if self.mirror_show_preview:
                row = box.row()
                row.prop(self, "mirror_preview_vert_size")
                row.prop(self, "mirror_preview_edge_width")
                row = box.row()
                row.prop(self, "mirror_preview_edge_color")
                row.prop(self, "mirror_preview_alpha")
                row = box.row()
                row.prop(self, "mirror_preview_max_edge_count")
                row.prop(self, "mirror_preview_optimize")
            
            row = box.row()
            row.prop(self, "mirror_use_mouse_pos")
            row.prop(self, "mirror_auto_confirm")
            
            row = box.row()
            row.prop(self, "mirror_sensitivity")
            
            row = box.row()
            row.prop(self, "mirror_use_fixed_scale")
            sub = row.row()
            sub.enabled = self.mirror_use_fixed_scale
            sub.prop(self, "mirror_fixed_scale_value")

            if self.ui_show_mirror_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    mirror_items = _find_mirror_keymap_items()
                    
                    if not mirror_items:
                            sub_col.label(text="未找到镜像相关绑定", icon="INFO")
                    else:
                        for kc, km, kmi in mirror_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass
            
            if self.ui_show_mirror_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_mirror_hotkey", text="独占(禁用冲突)")
                row.operator("size_tool.restore_shift_alt_x_conflicts", text="恢复冲突")
                row = sub_col.row(align=True)
                row.operator("size_tool.force_mirror_priority", text="强制置顶")

    def draw_group_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_group_tool")
        row.prop(self, "ui_show_group_keymap", text="快捷键")
        row.prop(self, "ui_show_group_advanced", text="高级")
        row.operator("m8.reset_prefs_ui", text="", icon="TRASH")

        if self.activate_group_tool:
            col.prop(self, "activate_double_click_select_group")
            col.prop(self, "group_tool_radius")
            col.prop(self, "group_tool_empty_type")
            col.prop(self, "group_tool_hide_empty")

            if self.ui_show_group_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    group_items = _find_group_tool_keymap_items()
                    double_click_items = _find_double_click_select_group_keymap_items()
                    
                    if not group_items and not double_click_items:
                            sub_col.label(text="未找到打组相关绑定", icon="INFO")
                    
                    if group_items:
                        sub_col.label(text="打组 (Ctrl+G):")
                        for kc, km, kmi in group_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                    
                    if double_click_items:
                        sub_col.label(text="双击选择组:")
                        for kc, km, kmi in double_click_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass
            
            if self.ui_show_group_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_group_tool_hotkey", text="独占(禁用冲突)")
                row.operator("size_tool.restore_ctrl_g_conflicts", text="恢复冲突")
                row = sub_col.row(align=True)
                row.operator("size_tool.force_group_tool_priority", text="强制置顶")

    def draw_smart_pie_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_smart_pie")
        row.prop(self, "ui_show_smart_pie_keymap", text="快捷键")

        sub = col.column()
        sub.enabled = bool(self.activate_smart_pie)
        sub.prop(self, "smart_edge_mode")
        sub.prop(self, "smart_face_action")
        sub.prop(self, "smart_face_focus_mode")
        sub.prop(self, "smart_face_stay_on_original")
        sub.prop(self, "clean_up_merge_distance")
        sub.prop(self, "clean_up_affect")
        sub.prop(self, "clean_up_degenerate_dist")
        sub.prop(self, "clean_up_recalc_normals")

        if self.ui_show_smart_pie_keymap:
            try:
                import rna_keymap_ui
                items = _find_smart_pie_keymap_items()
                if not items:
                    sub.label(text="未找到智能饼菜单相关绑定", icon="INFO")
                else:
                    for kc, km, kmi in items:
                        rna_keymap_ui.draw_kmi([], kc, km, kmi, sub, 0)
            except Exception:
                pass
        
    def draw_toggle_area_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_toggle_area")
        row.prop(self, "ui_show_toggle_area_keymap", text="快捷键")
        
        if self.activate_toggle_area:
            col.separator()
            col.prop(self, "toggle_area_close_range")
            col.prop(self, "toggle_area_prefer_left_right")
            col.prop(self, "toggle_area_wrap_mouse")
            
            box = col.box()
            box.label(text="Asset Browser / Shelf (3D View)", icon="ASSET_MANAGER")
            box.prop(self, "toggle_area_asset_shelf")
            box.prop(self, "toggle_area_asset_browser_top")
            box.prop(self, "toggle_area_asset_browser_bottom")
            box.prop(self, "toggle_area_split_factor")

            if self.ui_show_toggle_area_keymap:
                try:
                    import rna_keymap_ui
                    
                    # Helper function needed to find keymaps
                    def _find_toggle_area_keymap_items():
                        wm = bpy.context.window_manager if bpy.context else None
                        kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
                        if not kc: return []
                        items = []
                        for keymap_name, _ in TOGGLE_AREA_KEYMAP_BINDINGS:
                            km = kc.keymaps.get(keymap_name)
                            if km:
                                for kmi in km.keymap_items:
                                    if kmi.idname == TOGGLE_AREA_OP_ID:
                                        items.append((kc, km, kmi))
                        return items

                    items = _find_toggle_area_keymap_items()
                    if not items:
                        col.label(text="未找到相关绑定", icon="INFO")
                    else:
                        sub = col.column()
                        for kc, km, kmi in items:
                            row = sub.row(align=True)
                            row.label(text=km.name, icon="DOT")
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass

    def draw_screencast_settings(self, layout):
        col = layout.column()
        col.prop(self, "screencast_enabled", text="启用 Screencast (按键显示)")
        
        col = col.column()
        col.enabled = self.screencast_enabled
        col.prop(self, "screencast_font_size")
        col.prop(self, "screencast_style")
        col.prop(self, "screencast_color")
        if self.screencast_style == "KEYCAPS":
            col.prop(self, "screencast_cap_bg_color")
            col.prop(self, "screencast_cap_outline_color")
            row = col.row(align=True)
            row.prop(self, "screencast_cap_radius")
            row.prop(self, "screencast_cap_gap")
            row = col.row(align=True)
            row.prop(self, "screencast_cap_shadow")
            row.prop(self, "screencast_cap_uppercase")
        else:
            col.prop(self, "screencast_bg_color")
        
        row = col.row(align=True)
        row.prop(self, "screencast_align")
        
        row = col.row(align=True)
        row.prop(self, "screencast_offset_x")
        row.prop(self, "screencast_offset_y")
        
        col.prop(self, "screencast_history_count")
        col.prop(self, "screencast_timeout")
        col.prop(self, "screencast_stack_direction")
        col.prop(self, "screencast_show_mouse")
        col.prop(self, "screencast_show_mouse_move")
        col.prop(self, "screencast_show_last_operator")
        col.prop(self, "screencast_operator_label_mode")
        col.prop(self, "screencast_use_symbols")
        col.prop(self, "screencast_smart_merge_numbers")
        col.prop(self, "screencast_entry_animation")

    def draw_other_settings(self, layout):
        col = layout.column()
        
        box = col.box()
        box.label(text="全局快捷键管理:", icon="KEYINGSET")
        row = box.row(align=True)
        row.scale_y = 1.2
        row.operator("size_tool.exclusive_all_hotkeys", text="一键独占所有快捷键 (禁用冲突)")
        row.operator("size_tool.restore_all_conflicts", text="一键恢复所有冲突")
        box.prop(self, "auto_exclusive_shift_s_on_startup", text="启动时自动独占所有快捷键")
        
        col.separator()
        col.prop(self, "activate_restart_blender", text="在顶部菜单栏显示重启 Blender 按钮")
        col.separator()
        row = col.row(align=True)
        row.operator("m8.reset_prefs_ui", text="重置界面设置", icon="FILE_REFRESH")
        
        col.prop(self, "backup_suffix")
        col.prop(self, "backup_collection_name")
        col.prop(self, "default_padding")
        col.prop(self, "archive_default_bake")
        col.separator()
        col.prop(self, "auto_new_object_origin_bottom")
        sub = col.column()
        sub.enabled = self.auto_new_object_origin_bottom
        sub.prop(self, "auto_new_object_snap_to_floor")
