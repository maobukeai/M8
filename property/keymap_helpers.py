import bpy
from ..utils.logger import get_logger
from ..utils.i18n import _T
from ..utils.adapter import get_adapter_blender_icon as _ICON
from .keymap_constants import *

logger = get_logger()

# Global list to store registered keymap items: list of (km, kmi)
addon_keymaps = []

def _get_addon_prefs():
    root_pkg = ".".join(__package__.split(".")[:3]) if (__package__ or "").startswith("bl_ext") else (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg) if bpy.context and bpy.context.preferences else None
    return addon.preferences if addon else None

def _copy_operator_properties(src_kmi, dst_kmi):
    src_props = getattr(src_kmi, "properties", None)
    dst_props = getattr(dst_kmi, "properties", None)
    if not src_props or not dst_props:
        return

    try:
        rna_props = getattr(getattr(src_props, "bl_rna", None), "properties", [])
        for prop in rna_props:
            identifier = getattr(prop, "identifier", "")
            if not identifier or identifier == "rna_type" or getattr(prop, "is_readonly", False):
                continue
            try:
                setattr(dst_props, identifier, getattr(src_props, identifier))
            except Exception:
                pass
    except Exception:
        pass

    try:
        for key in src_props.keys():
            try:
                dst_props[key] = src_props[key]
            except Exception:
                pass
    except Exception:
        pass


def _new_keymap_item_at_head(km, kmi):
    items = getattr(km, "keymap_items", None)
    if not items:
        return None

    new_from_item = getattr(items, "new_from_item", None)
    if new_from_item:
        try:
            new_kmi = new_from_item(kmi, head=True)
            try:
                new_kmi.active = bool(getattr(kmi, "active", True))
            except Exception:
                pass
            return new_kmi
        except TypeError:
            pass
        except Exception as exc:
            logger.debug(f"new_from_item failed while prioritizing keymap item: {exc}")

    kwargs = {
        "any": bool(getattr(kmi, "any", False)),
        "shift": bool(getattr(kmi, "shift", False)),
        "ctrl": bool(getattr(kmi, "ctrl", False)),
        "alt": bool(getattr(kmi, "alt", False)),
        "oskey": bool(getattr(kmi, "oskey", False)),
        "key_modifier": getattr(kmi, "key_modifier", "NONE") or "NONE",
        "direction": getattr(kmi, "direction", "ANY") or "ANY",
        "repeat": bool(getattr(kmi, "repeat", False)),
        "head": True,
    }

    attempts = (
        kwargs,
        {key: value for key, value in kwargs.items() if key != "repeat"},
        {key: value for key, value in kwargs.items() if key != "direction"},
        {key: value for key, value in kwargs.items() if key not in {"direction", "repeat"}},
    )
    for attempt in attempts:
        try:
            new_kmi = items.new(
                getattr(kmi, "idname", ""),
                getattr(kmi, "type", "NONE"),
                getattr(kmi, "value", "PRESS"),
                **attempt,
            )
            _copy_operator_properties(kmi, new_kmi)
            try:
                new_kmi.active = bool(getattr(kmi, "active", True))
            except Exception:
                pass
            return new_kmi
        except TypeError:
            continue
        except Exception as exc:
            logger.debug(f"keymap_items.new failed while prioritizing keymap item: {exc}")
            break
    return None


def _replace_addon_keymap_reference(km, old_kmi, new_kmi):
    for index, (stored_km, stored_kmi) in enumerate(addon_keymaps):
        if stored_km == km and (stored_kmi == old_kmi or stored_kmi is old_kmi):
            addon_keymaps[index] = (km, new_kmi)


# Helper to ensure our keymap is at the top (priority)
def _ensure_pie_keymap_priority(km, kmi):
    if not km or not kmi:
        return kmi

    try:
        items = list(km.keymap_items)
    except Exception:
        return kmi

    if not items or items[0] == kmi or items[0] is kmi:
        return kmi
    if kmi not in items:
        return kmi

    new_kmi = _new_keymap_item_at_head(km, kmi)
    if not new_kmi:
        logger.warning(f"Failed to prioritize keymap item {getattr(kmi, 'idname', '<unknown>')} in {getattr(km, 'name', '<unknown>')}")
        return kmi

    try:
        km.keymap_items.remove(kmi)
    except Exception as exc:
        try:
            km.keymap_items.remove(new_kmi)
        except Exception:
            pass
        logger.warning(f"Failed to replace keymap item while prioritizing {getattr(kmi, 'idname', '<unknown>')}: {exc}")
        return kmi

    _replace_addon_keymap_reference(km, kmi, new_kmi)
    return new_kmi

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

def _on_prefs_update(self, context):
    from .keymap_manager import update_keymaps
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

def _switch_editor_items(self, context):
    from ..ui.pie.switch_editor_pie import EDITOR_TYPES
    items = []
    for val, name_en, name_zh, icon, _ in EDITOR_TYPES:
        name = name_en if getattr(self, "addon_language", "ZH") == "EN" else name_zh
        items.append((val, name, "", icon, _))
    return items

def _active_tab_items(self, context):
    return [
        ("GENERAL", _T("常规设置"), ""),
        ("ABOUT", _T("关于"), ""),
    ]

def _smart_face_action_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("SEPARATE", "Separate", ""),
            ("DUPLICATE", "Duplicate & Separate", ""),
            ("DISSOLVE", "Dissolve", ""),
            ("EXTRACT", "Extract & Separate", ""),
        ]
    return [
        ("SEPARATE", _T("分离"), ""),
        ("DUPLICATE", _T("复制后分离"), ""),
        ("DISSOLVE", _T("溶解"), ""),
        ("EXTRACT", _T("提取后分离"), ""),
    ]

def _clean_up_affect_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("ALL", "All", ""),
            ("SELECTED", "Selected", ""),
        ]
    return [
        ("ALL", _T("全部"), ""),
        ("SELECTED", _T("仅选中"), ""),
    ]

def _switch_mode_tab_behavior_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("INSTANT", "Instant (Compatible)", "Press Tab to switch immediately"),
            ("TAP_HOLD", "Tap Switch / Hold Menu", "Tap for default action, hold for the switch menu"),
        ]
    return [
        ("INSTANT", _T("立即执行(兼容)"), _T("按下 Tab 立即执行（与 Blender 默认更接近）")),
        ("TAP_HOLD", _T("轻按切换 / 长按菜单"), _T("轻按执行默认行为，长按弹出模式切换饼菜单")),
    ]

def _screencast_align_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("LEFT", "Left", ""),
            ("CENTER", "Center", ""),
            ("RIGHT", "Right", ""),
        ]
    return [
        ("LEFT", _T("左"), ""),
        ("CENTER", _T("中"), ""),
        ("RIGHT", _T("右"), ""),
    ]

def _screencast_operator_label_mode_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("ZH", "Chinese First", ""),
            ("EN", "English", ""),
            ("BOTH", "Chinese/English", ""),
        ]
    return [
        ("ZH", _T("中文优先"), ""),
        ("EN", _T("英文"), ""),
        ("BOTH", _T("中文/英文"), ""),
    ]

def _screencast_stack_direction_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("UP", "Bottom-Up", "New entries appear above"),
            ("DOWN", "Top-Down", "New entries appear below"),
        ]
    return [
        ("UP", _T("向上 (Bottom-Up)"), _T("新消息在上方")),
        ("DOWN", _T("向下 (Top-Down)"), _T("新消息在下方")),
    ]

def _screencast_mouse_display_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("ICON", "Icon", "Display mouse icon figure"),
            ("TEXT", "Text", "Display mouse click text events"),
            ("BOTH", "Icon & Text", "Display both icon figure and text events"),
            ("NONE", "None", "Do not display mouse events"),
        ]
    return [
        ("ICON", _T("图标 (Icon)"), _T("常驻显示矢量鼠标图标")),
        ("TEXT", _T("文本 (Text)"), _T("仅在事件列表中记录鼠标点击文本")),
        ("BOTH", _T("图标与文本 (Both)"), _T("同时显示矢量鼠标图标与按键文本")),
        ("NONE", _T("不显示 (None)"), _T("不显示任何鼠标事件")),
    ]

def _addon_language_items(self, context):
    return [
        ("ZH", "中文", ""),
        ("EN", "English", ""),
    ]

def _smart_edge_mode_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("SELECT", "Select Region", "Convert a closed edge loop to face selection"),
            ("SHARPS", "Sharps", "Mark or clear sharp edges"),
            ("BRIDGE", "Bridge", "Bridge two edge loops"),
            ("FILL", "Fill", "Fill a closed region"),
        ]
    return [
        ("SELECT", _T("选择区域"), _T("将闭合边环转换为面选择")),
        ("SHARPS", _T("锐边"), _T("标记或清除锐边")),
        ("BRIDGE", _T("桥接"), _T("桥接两个边环")),
        ("FILL", _T("填充"), _T("填充闭合区域")),
    ]

def _group_tool_empty_type_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("PLAIN_AXES", "Plain Axes", ""),
            ("ARROWS", "Arrows", ""),
            ("SINGLE_ARROW", "Single Arrow", ""),
            ("CIRCLE", "Circle", ""),
            ("CUBE", "Cube", ""),
            ("SPHERE", "Sphere", ""),
            ("CONE", "Cone", ""),
            ("IMAGE", "Image", ""),
        ]
    return [
        ("PLAIN_AXES", _T("十字"), ""),
        ("ARROWS", _T("坐标轴"), ""),
        ("SINGLE_ARROW", _T("单箭头"), ""),
        ("CIRCLE", _T("圆环"), ""),
        ("CUBE", _T("方块"), ""),
        ("SPHERE", _T("球体"), ""),
        ("CONE", _T("锥体"), ""),
        ("IMAGE", _T("图片"), ""),
    ]

def _switch_mode_target_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("VERT", "Vertex", ""),
            ("EDGE", "Edge", ""),
            ("FACE", "Face", ""),
            ("SWITCH_MODE", "Switch Mode", ""),
        ]
    return [
        ("VERT", _T("点"), ""),
        ("EDGE", _T("边"), ""),
        ("FACE", _T("面"), ""),
        ("SWITCH_MODE", _T("模式切换"), ""),
    ]

def _switch_bone_mode_target_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("EDIT_OR_OBJECT", "Edit/Object", ""),
            ("BONE_POSITION", "Bone Position", ""),
            ("POSE", "Pose", ""),
            ("EDIT", "Edit (Only Pose)", "Only show in pose mode"),
            ("VIEW_SELECTED", "View Selected", ""),
            ("TOGGLE_XRAY", "Toggle X-Ray", ""),
            ("TOGGLE_NAMES", "Toggle Names", ""),
            ("TOGGLE_AXES", "Toggle Axes", ""),
        ]
    return [
        ("EDIT_OR_OBJECT", _T("编辑/物体"), ""),
        ("BONE_POSITION", _T("骨骼位置"), ""),
        ("POSE", _T("姿态"), ""),
        ("EDIT", _T("编辑(仅姿态)"), _T("仅在姿态模式显示")),
        ("VIEW_SELECTED", _T("视图聚焦选中"), ""),
        ("TOGGLE_XRAY", _T("切换透视(X-Ray)"), ""),
        ("TOGGLE_NAMES", _T("切换名称显示"), ""),
        ("TOGGLE_AXES", _T("切换轴显示"), ""),
    ]

def _delete_pie_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("DELETE_VERT", "Delete Vertices", "", "VERTEXSEL", 1),
            ("DELETE_EDGE", "Delete Edges", "", "EDGESEL", 2),
            ("DELETE_FACE", "Delete Faces", "", "FACESEL", 3),
            ("DISSOLVE_VERT", "Dissolve Vertices", "", "VERTEXSEL", 4),
            ("DISSOLVE_EDGE", "Dissolve Edges", "", "MOD_WIREFRAME", 5),
            ("DISSOLVE_FACE", "Dissolve Faces", "", "FACESEL", 6),
            ("LIMITED_DISSOLVE", "Limited Dissolve", "", "MESH_DATA", 7),
            ("EDGE_LOOP", "Delete Edge Loops", "", "MOD_EDGESPLIT", 8),
            ("EDGE_COLLAPSE", "Collapse Edges", "", "UV_EDGESEL", 9),
            ("ONLY_EDGE_FACE", "Only Edges & Faces", "", "EDGESEL", 10),
            ("ONLY_FACE", "Only Faces", "", "FACESEL", 11),
            ("DISSOLVE_ALL", "Dissolve (Smart)", "", "MOD_WIREFRAME", 12),
            ("NONE", "None", "", "X", 0),
        ]
    return [
        ("DELETE_VERT", _T("删除顶点"), "", "VERTEXSEL", 1),
        ("DELETE_EDGE", _T("删除边"), "", "EDGESEL", 2),
        ("DELETE_FACE", _T("删除面"), "", "FACESEL", 3),
        ("DISSOLVE_VERT", _T("融并顶点"), "", "VERTEXSEL", 4),
        ("DISSOLVE_EDGE", _T("融并边"), "", "MOD_WIREFRAME", 5),
        ("DISSOLVE_FACE", _T("融并面"), "", "FACESEL", 6),
        ("LIMITED_DISSOLVE", _T("有限融并"), "", "MESH_DATA", 7),
        ("EDGE_LOOP", _T("循环边"), "", "MOD_EDGESPLIT", 8),
        ("EDGE_COLLAPSE", _T("塌陷边"), "", "UV_EDGESEL", 9),
        ("ONLY_EDGE_FACE", _T("仅边和面"), "", "EDGESEL", 10),
        ("ONLY_FACE", _T("仅面"), "", "FACESEL", 11),
        ("DISSOLVE_ALL", _T("融并点线面"), "", "MOD_WIREFRAME", 12),
        ("NONE", _T("无"), "", "X", 0),
    ]

def _unity_fbx_apply_scale_options_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("FBX_SCALE_NONE", "All Local", ""),
            ("FBX_SCALE_UNITS", "FBX Units Scale", ""),
            ("FBX_SCALE_CUSTOM", "FBX Custom Scale", ""),
            ("FBX_SCALE_ALL", "FBX All", ""),
        ]
    return [
        ("FBX_SCALE_NONE", _T("全部本地"), ""),
        ("FBX_SCALE_UNITS", _T("FBX 单位缩放"), ""),
        ("FBX_SCALE_CUSTOM", _T("FBX 自定义缩放"), ""),
        ("FBX_SCALE_ALL", _T("FBX 全部"), ""),
    ]

def _origin_default_operator_types_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("ROTATE", "Rotate", "", "NONE", 1),
            ("LOCATION", "Location", "", "NONE", 2),
        ]
    return [
        ("ROTATE", _T("旋转"), "", "NONE", 1),
        ("LOCATION", _T("位置"), "", "NONE", 2),
    ]

def _moving_view_type_items(self, context):
    if getattr(self, "addon_language", "ZH") == "EN":
        return [
            ("NONE", "None", "", "RESTRICT_SELECT_ON", 0),
            ("MAINTAINING_ZOOM", "Maintaining Zoom", "", "VIEWZOOM", 1),
            ("ANIMATION", "Animation", "", "ANIM", 2),
        ]
    return [
        ("NONE", _T("无"), "", "RESTRICT_SELECT_ON", 0),
        ("MAINTAINING_ZOOM", _T("保持缩放"), "", "VIEWZOOM", 1),
        ("ANIMATION", _T("动画"), "", "ANIM", 2),
    ]

# Finder functions
def _is_our_pie_keymap_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") in {PIE_MENU_ID, SWITCH_MODE_PIE_ID, EDGE_PROPERTY_PIE_ID, SMART_PIE_ID, SWITCH_EDITOR_PIE_ID}

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

def _is_our_switch_editor_pie_item(kmi):
    if getattr(kmi, "idname", "") != 'wm.call_menu_pie': return False
    return getattr(kmi.properties, "name", "") == SWITCH_EDITOR_PIE_ID

def _is_our_rename_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.advanced_rename'

def _is_our_mirror_item(kmi):
    return getattr(kmi, "idname", "") == MIRROR_OP_ID

def _is_our_group_tool_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.group_objects'

def _is_our_double_click_select_group_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.select_group'

def _is_our_double_click_edit_switch_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.double_click_edit_switch'

def _is_our_subdivision_item(kmi):
    return getattr(kmi, "idname", "") == 'm8.subdivision_set'

def _is_our_keymap_item(kmi):
    return (
        _is_our_pie_keymap_item(kmi) or
        _is_our_align_pie_item(kmi) or
        _is_our_switch_mode_item(kmi) or
        _is_our_quick_delete_item(kmi) or
        _is_our_delete_pie_item(kmi) or
        _is_our_shading_pie_item(kmi) or
        _is_our_save_pie_item(kmi) or
        _is_our_rename_item(kmi) or
        _is_our_mirror_item(kmi) or
        _is_our_group_tool_item(kmi) or
        _is_our_double_click_select_group_item(kmi) or
        _is_our_double_click_edit_switch_item(kmi) or
        _is_our_smart_pie_item(kmi) or
        _is_our_smart_tool_item(kmi) or
        _is_our_switch_editor_pie_item(kmi) or
        _is_our_edge_property_pie_item(kmi) or
        _is_our_subdivision_item(kmi) or
        getattr(kmi, "idname", "") == TOGGLE_AREA_OP_ID
    )

def _find_subdivision_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    if not wm or not wm.keyconfigs:
        return []

    # Older M8 releases could leave a user-keyconfig copy behind.  Include it
    # in priority repair so it cannot shadow the current add-on keymap.
    keyconfigs = []
    for kc in (wm.keyconfigs.addon, wm.keyconfigs.user):
        if kc and kc not in keyconfigs:
            keyconfigs.append(kc)

    items = []
    for kc in keyconfigs:
        for keymap_name, _ in SUBDIVISION_KEYMAP_BINDINGS:
            km = kc.keymaps.get(keymap_name)
            if km:
                for kmi in km.keymap_items:
                    if _is_our_subdivision_item(kmi):
                        items.append((kc, km, kmi))
    return items

def _find_pie_keymap_item():
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
    if not kc: return []
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

def _find_switch_editor_pie_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in SWITCH_EDITOR_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if km:
            for kmi in km.keymap_items:
                if _is_our_switch_editor_pie_item(kmi): items.append((kc, km, kmi))
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
    if not kc: return []
    items = []
    for keymap_name, _ in SMART_PIE_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if not km: continue
        for kmi in km.keymap_items:
            if _is_our_smart_pie_item(kmi) or _is_our_smart_tool_item(kmi):
                items.append((kc, km, kmi))
    return items

def _find_toggle_area_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    for keymap_name, _ in TOGGLE_AREA_KEYMAP_BINDINGS:
        km = kc.keymaps.get(keymap_name)
        if not km: continue
        for kmi in km.keymap_items:
            if kmi.idname == TOGGLE_AREA_OP_ID:
                items.append((kc, km, kmi))
    return items

# Conflict helpers
_disabled_conflict_items = {}


def _conflict_item_key(kc, km, kmi):
    """Return a session-stable identity for a keymap item M8 changed."""
    try:
        return (kc.as_pointer(), km.as_pointer(), kmi.as_pointer())
    except Exception:
        return (id(kc), id(km), id(kmi))


def restore_tracked_conflicts():
    """Restore only shortcuts that this M8 session actually disabled."""
    restored = 0
    for key, kmi in list(_disabled_conflict_items.items()):
        try:
            if not kmi.active:
                kmi.active = True
                restored += 1
            _disabled_conflict_items.pop(key, None)
        except Exception as exc:
            logger.warning(f"Failed to restore tracked shortcut: {exc}")
    return restored


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
    sigs = []
    for km, kmi in addon_keymaps:
        sig = _kmi_signature(kmi)
        if sig and sig not in sigs:
            sigs.append(sig)
    return sigs

def _conflict_keymap_names(extra_keymap_names=()):
    all_bindings = list(TRANSFORM_PIE_KEYMAP_BINDINGS) + list(ALIGN_PIE_KEYMAP_BINDINGS) + \
                   list(SWITCH_MODE_KEYMAP_BINDINGS) + list(QUICK_DELETE_KEYMAP_BINDINGS) + \
                   list(DELETE_PIE_KEYMAP_BINDINGS) + list(SAVE_PIE_KEYMAP_BINDINGS) + \
                   list(RENAME_KEYMAP_BINDINGS) + list(GROUP_TOOL_KEYMAP_BINDINGS) + \
                   list(DOUBLE_CLICK_GROUP_KEYMAP_BINDINGS) + list(SMART_PIE_KEYMAP_BINDINGS) + \
                   list(TOGGLE_AREA_KEYMAP_BINDINGS) + list(SWITCH_EDITOR_PIE_KEYMAP_BINDINGS) + \
                   list(EDGE_PROPERTY_PIE_KEYMAP_BINDINGS) + list(SHADING_PIE_KEYMAP_BINDINGS) + \
                   list(MIRROR_KEYMAP_BINDINGS) + list(SUBDIVISION_KEYMAP_BINDINGS)

    names = []
    seen = set()
    for keymap_name, _ in all_bindings:
        if keymap_name not in seen:
            names.append(keymap_name)
            seen.add(keymap_name)
    for keymap_name in extra_keymap_names:
        if keymap_name and keymap_name not in seen:
            names.append(keymap_name)
            seen.add(keymap_name)
    return names

def _disable_conflicts_for_signatures(
    kc, signatures, extra_keymap_names=(), scan_all_keymaps=False, keymap_names=None
):
    if not kc: return 0
    disabled = 0

    if keymap_names is not None:
        keymaps = [kc.keymaps.get(name) for name in keymap_names]
    elif scan_all_keymaps:
        keymaps = list(kc.keymaps)
    else:
        keymaps = [kc.keymaps.get(name) for name in _conflict_keymap_names(extra_keymap_names)]

    for km in keymaps:
        if not km:
            continue
        
        for kmi in km.keymap_items:
            if not getattr(kmi, "active", True): continue
            if _is_our_keymap_item(kmi): continue
            
            for sig in signatures:
                if _match_signature(kmi, sig):
                    try:
                        kmi.active = False
                        _disabled_conflict_items[_conflict_item_key(kc, km, kmi)] = kmi
                        disabled += 1
                        logger.info(f"Disabled conflicting hotkey: {kmi.name} ({kmi.idname}) in {km.name}")
                    except Exception as e:
                        logger.error(f"Failed to disable conflict {kmi.idname}: {e}")
                    break
    return disabled

def _restore_conflicts_for_signatures(
    kc, signatures, extra_keymap_names=(), scan_all_keymaps=False, keymap_names=None
):
    if not kc: return 0
    restored = 0

    if keymap_names is not None:
        keymaps = [kc.keymaps.get(name) for name in keymap_names]
    elif scan_all_keymaps:
        keymaps = list(kc.keymaps)
    else:
        keymaps = [kc.keymaps.get(name) for name in _conflict_keymap_names(extra_keymap_names)]

    for km in keymaps:
        if not km:
            continue
        
        for kmi in km.keymap_items:
            if getattr(kmi, "active", True): continue
            if _is_our_keymap_item(kmi): continue
            key = _conflict_item_key(kc, km, kmi)
            if key not in _disabled_conflict_items:
                continue

            for sig in signatures:
                if _match_signature(kmi, sig):
                    try:
                        kmi.active = True
                        _disabled_conflict_items.pop(key, None)
                        restored += 1
                        logger.info(f"Restored conflicting hotkey: {kmi.name} ({kmi.idname}) in {km.name}")
                    except Exception as e:
                        logger.error(f"Failed to restore conflict {kmi.idname}: {e}")
                    break
    return restored

def _find_fast_loop_keymap_items():
    wm = bpy.context.window_manager if bpy.context else None
    kc = wm.keyconfigs.addon if wm and wm.keyconfigs else None
    if not kc: return []
    items = []
    km = kc.keymaps.get("Mesh")
    if km:
        for kmi in km.keymap_items:
            if kmi.idname == "m8.fast_loop":
                items.append((kc, km, kmi))
    return items
