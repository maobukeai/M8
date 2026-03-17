import bpy
from mathutils import Vector, Euler, Matrix

from . import get_pref
from ..registration import KEYS_DICT

register_keymap_items = {}


def match_user_keymaps_by_tool() -> "dict":
    """
    {
    tool:[(km, kmi),(None,None)]
    }
    """
    res = {}

    match_data = {}  # {{"properties":dict,"idname":str}:tool_name}
    for tool, keymap_items in register_keymap_items.items():
        for (km, kmi) in keymap_items:
            if km.name not in match_data:
                match_data[km.name] = {}
            key = (kmi.idname, get_kmi_operator_as_tuple(kmi, as_key=True))
            match_data[km.name][key] = tool.upper()

    # find user keymap
    kc = bpy.context.window_manager.keyconfigs.user
    for km in kc.keymaps:
        if km.name in match_data:
            for kmi in km.keymap_items:
                key = (kmi.idname, get_kmi_operator_as_tuple(kmi, as_key=True))

                if key in match_data[km.name]:
                    tool = match_data[km.name].pop(key)
                    if tool not in res:
                        res[tool] = []
                    res[tool].append((km, kmi))

    # Processing keymap not found
    for keymap_name, item in match_data.items():
        for key, tool in item.items():
            if tool not in res:
                res[tool] = []
            res[tool].append((None, None))

    return res


def match_user_keymap_by_keymap() -> "dict":
    """
    {
     keymap_name:[(km,kmi,None),(None,None,tool)...]
    }
    """
    res = {}
    match_data = {}  # {{"properties":dict,"idname":str}:tool_name}
    for tool, keymap_items in register_keymap_items.items():
        for (km, kmi) in keymap_items:
            if km.name not in match_data:
                match_data[km.name] = {}
            key = (kmi.idname, get_kmi_operator_as_tuple(kmi, as_key=True))
            match_data[km.name][key] = tool.upper()

    # find user keymap
    kc = bpy.context.window_manager.keyconfigs.user
    for km in kc.keymaps:
        if km.name in match_data:
            for kmi in km.keymap_items:
                key = (kmi.idname, get_kmi_operator_as_tuple(kmi, as_key=True))

                if key in match_data[km.name]:
                    tool = match_data[km.name].pop(key)
                    if km.name not in res:
                        res[km.name] = []
                    res[km.name].append((km, kmi, tool))

    # Processing keymap not found
    for keymap_name, item in match_data.items():
        for key, tool in item.items():
            if keymap_name not in res:
                res[keymap_name] = []
            res[keymap_name].append((None, None, tool))

    return res


def get_keymap(keymap_name):
    kc = bpy.context.window_manager.keyconfigs
    addon = kc.addon
    keymap = kc.default.keymaps.get(keymap_name, None)

    km = addon.keymaps.get(keymap_name, None)
    if km:
        return km

    return addon.keymaps.new(keymap_name, space_type=keymap.space_type)


def register_keymaps(identifier) -> int:
    global register_keymap_items
    DEBUG_KEYMAP_DETAILED = False

    count = 0

    if identifier not in KEYS_DICT:
        print(f"Keymap {identifier} not found in KEYS_DICT!")
        return count
    if identifier in register_keymap_items:
        if DEBUG_KEYMAP_DETAILED:
            print(f"Keymap {identifier} already registered")
        return count

    keymap_items = []
    for item in KEYS_DICT[identifier]:
        keymap_name = item.get("keymap")
        km = get_keymap(keymap_name)

        idname = item.get("idname")
        key_type = item.get("type")
        value = item.get("value")

        shift = item.get("shift", False)
        ctrl = item.get("ctrl", False)
        alt = item.get("alt", False)

        kmi = km.keymap_items.new(idname, key_type, value, shift=shift, ctrl=ctrl, alt=alt)

        if kmi:
            properties = item.get("properties")
            if properties:
                for name, value in properties.items():
                    setattr(kmi.properties, name, value)
        if DEBUG_KEYMAP_DETAILED:
            print(f"MP7Tools ADD KMI", kmi.idname, "\t\t", kmi.name, "\t", get_kmi_operator_properties(kmi))
        keymap_items.append((km, kmi))
        count += 1
    register_keymap_items[identifier] = keymap_items
    return count


def unregister_keymaps(identifier) -> int:
    global register_keymap_items
    DEBUG_KEYMAP_DETAILED = False

    count = 0

    if identifier not in register_keymap_items:
        print(f"Keymap {identifier} not found in register_keymap_items!")
        return count
    for keymap, kmi in register_keymap_items.pop(identifier):
        try:
            if DEBUG_KEYMAP_DETAILED:
                print("MP7Tools RM KMI", kmi.idname, "\t\t", kmi.name, "\t", get_kmi_operator_properties(kmi))
            if kmi in keymap.keymap_items[:]:
                keymap.keymap_items.remove(kmi)
                count += 1
            else:
                print(f"MP7 意料之外的清况 {kmi} 未在 {keymap} 内")
        except ReferenceError as e:
            print(e)
            import traceback
            traceback.print_exc()
            traceback.print_stack()
    return count


def get_kmi_operator_properties(kmi: 'bpy.types.KeyMapItem') -> dict:
    """获取kmi操作符的属性"""
    properties = kmi.properties
    if not properties:
        return {}
    prop_keys = dict(properties.items()).keys()
    dictionary = {i: getattr(properties, i, None) for i in prop_keys}
    del_key = []
    for item in dictionary:
        prop = getattr(properties, item, None)
        typ = type(prop)
        if prop:
            if typ == Vector:
                # 属性阵列-浮点数组
                dictionary[item] = dictionary[item].to_tuple()
            elif typ == Euler:
                dictionary[item] = dictionary[item][:]
            elif typ == Matrix:
                dictionary[item] = tuple(i[:] for i in dictionary[item])
            elif typ == bpy.types.bpy_prop_array:
                dictionary[item] = dictionary[item][:]
            elif typ in (str, bool, float, int, set, list, tuple):
                ...
            elif typ.__name__ in [
                "TRANSFORM_OT_shrink_fatten",
                "TRANSFORM_OT_translate",
                "TRANSFORM_OT_edge_slide",
                "NLA_OT_duplicate",
                "ACTION_OT_duplicate",
                "GRAPH_OT_duplicate",
                "TRANSFORM_OT_translate",
                "OBJECT_OT_duplicate",
                "MESH_OT_loopcut",
                "MESH_OT_rip_edge",
                "MESH_OT_rip",
                "MESH_OT_duplicate",
                "MESH_OT_offset_edge_loops",
                "MESH_OT_extrude_faces_indiv",
                "ARMATURE_OT_extrude",
                "ARMATURE_OT_duplicate",
                "UV_OT_rip",
            ]:  # 一些奇怪的操作符属性,不太好解析也用不上
                ...
                del_key.append(item)
            else:
                print('emm 未知属性,', typ, dictionary[item])
                del_key.append(item)
    for i in del_key:
        dictionary.pop(i)
    return dictionary


def get_kmi_operator_as_tuple(kmi: 'bpy.types.KeyMapItem', as_key=True) -> tuple:
    """将kmi属性当key的时候使用
    如果数据里面出现set将无法作为key来使用
    """
    if as_key:
        return tuple((k, str(v) if isinstance(v, set) else v) for k, v in get_kmi_operator_properties(kmi).items())
    return tuple((k, v) for k, v in get_kmi_operator_properties(kmi).items())


def from_kmi_find_ops(kmi):
    is_menu = kmi.idname in {"wm.call_menu_pie", }
    if is_menu:
        class_name = kmi.properties.name
        return getattr(bpy.types, class_name, None)
    else:
        a, b = kmi.idname.split(".")
        cls = getattr(getattr(bpy.ops, a, None), b, None)
        if cls is not None:
            return cls.get_rna_type()
    return False


def from_kmi_find_description(kmi) -> str | None:
    ops = from_kmi_find_ops(kmi)
    if ops is not None:
        if hasattr(ops, "bl_description"):
            return ops.bl_description
        elif hasattr(ops, "description"):
            if hasattr(ops, "identifier"):
                ops_cls = getattr(bpy.types, ops.identifier, None)
                if ops_cls and hasattr(ops_cls, "description") and hasattr(ops_cls.description, "__call__"):
                    return ops_cls.description(bpy.context, kmi.properties)
            if isinstance(ops.description, str):
                return ops.description
            elif hasattr(ops.description, "__call__"):
                return ops.description(bpy.context, kmi.properties)
    return None


def draw_kmi_description(layout, kmi):
    desc = from_kmi_find_description(kmi)
    if desc:
        column = layout.column(align=True)
        for text in desc.split("\n"):
            column.label(text=text)
        if kmi.idname == "mp7_tools.switch_mode":
            from ..ui.pie.switch_mode import SwitchModePie
            for text in SwitchModePie.description(None, None).split("\n"):
                column.label(text=text)


def draw_kmi(km, kmi, layout, show_keymap_name=False):
    r"""\scripts\modules\rna_keymap_ui.py
    """
    map_type = kmi.map_type
    col = layout.column(align=True)
    row = col.row()
    split = row.split()

    # header bar
    row = split.row(align=True)
    row.prop(kmi, "show_expanded", text="", emboss=False)
    row.prop(kmi, "active", text="", emboss=False)

    if km.is_modal:
        row.separator()
        row.prop(kmi, "propvalue", text="")
    else:
        row.label(text=kmi.name)
    if show_keymap_name:
        sub_row = row.row(align=True)
        sub_row.enabled = False
        sub_row.label(text=bpy.app.translations.pgettext_iface(km.name))

    row = split.row()
    row.active = kmi.active
    row.prop(kmi, "map_type", text="")
    if map_type == 'KEYBOARD':
        row.prop(kmi, "type", text="", full_event=True)
    elif map_type == 'MOUSE':
        row.prop(kmi, "type", text="", full_event=True)
    elif map_type == 'NDOF':
        row.prop(kmi, "type", text="", full_event=True)
    elif map_type == 'TWEAK':
        subrow = row.row()
        subrow.prop(kmi, "type", text="")
        subrow.prop(kmi, "value", text="")
    elif map_type == 'TIMER':
        row.prop(kmi, "type", text="")
    else:
        row.label()

    if (not kmi.is_user_defined) and kmi.is_user_modified:
        row.operator("preferences.keyitem_restore", text="", icon='BACK').item_id = kmi.id
    else:
        row.operator(
            "preferences.keyitem_remove",
            text="",
            # Abusing the tracking icon, but it works pretty well here.
            icon=('TRACKING_CLEAR_BACKWARDS' if kmi.is_user_defined else 'X')
        ).item_id = kmi.id

    # Expanded, additional event settings
    if kmi.show_expanded:
        s = col.split(factor=0.02)
        s.separator()

        box = s.box()
        draw_kmi_description(box, kmi)
        split = box.split(factor=0.4)
        sub = split.row()

        if km.is_modal:
            # sub.prop(kmi, "propvalue", text="")
            sub.label(text=kmi.propvalue)
        else:
            # sub.prop(kmi, "idname", text="")
            column = sub.column(align=True)
            # column.label(text=kmi.idname)

        if map_type not in {'TEXTINPUT', 'TIMER'}:
            sub = split.column()
            subrow = sub.row(align=True)

            if map_type == 'KEYBOARD':
                subrow.prop(kmi, "type", text="", event=True)
                subrow.prop(kmi, "value", text="")
                subrow_repeat = subrow.row(align=True)
                subrow_repeat.active = kmi.value in {'ANY', 'PRESS'}
                subrow_repeat.prop(kmi, "repeat", text="Repeat")
            elif map_type in {'MOUSE', 'NDOF'}:
                subrow.prop(kmi, "type", text="")
                subrow.prop(kmi, "value", text="")

            if map_type in {'KEYBOARD', 'MOUSE'} and kmi.value == 'CLICK_DRAG':
                subrow = sub.row()
                subrow.prop(kmi, "direction")

            subrow = sub.row()
            subrow.scale_x = 0.75
            subrow.prop(kmi, "any", toggle=True)
            # Use `*_ui` properties as integers aren't practical.
            subrow.prop(kmi, "shift_ui", toggle=True)
            subrow.prop(kmi, "ctrl_ui", toggle=True)
            subrow.prop(kmi, "alt_ui", toggle=True)
            subrow.prop(kmi, "oskey_ui", text="Cmd", toggle=True)

            subrow.prop(kmi, "key_modifier", text="", event=True)


def register():
    pref = get_pref()
    from ..registration import KEYS_DICT
    DEBUG_KEYMAP_DETAILED = False

    register_keymaps_count = 0
    for i in pref.bl_rna.properties:
        identifier = i.identifier
        if identifier.startswith("activate_") and getattr(pref, identifier, False):
            key = identifier[9:].upper()
            if key in KEYS_DICT:
                register_keymaps_count += register_keymaps(key)

    if not DEBUG_KEYMAP_DETAILED:
        print(f"M8 Registered {register_keymaps_count} keymaps")


def unregister():
    DEBUG_KEYMAP_DETAILED = False

    unregister_keymaps_count = 0

    for identifier in list(register_keymap_items.keys()):
        unregister_keymaps_count += unregister_keymaps(identifier)

    if not DEBUG_KEYMAP_DETAILED:
        print(f"M8 Unregistered {unregister_keymaps_count} keymaps")
    register_keymap_items.clear()


def update_keymap(is_register, identifier):
    if get_pref().init:
        if is_register:
            register_keymaps(identifier)
        else:
            unregister_keymaps(identifier)
