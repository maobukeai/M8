import bpy


def get_custom_icon(name="None"):
    """
    获取自定义图标
    load icon
    :param name:
    :return: int icon_id
    """
    from ..src.icons import previews_icons
    name_lower = name.lower()
    if name_lower in previews_icons:
        return previews_icons[name_lower].icon_id
    print(f"M8 Align Warning: Icon '{name}' not found in previews_icons.")
    return 0 # Fallback to no icon


def get_tow_blender_icon(icon_style):
    """反回两个图标

    Args:
        icon_style (类型或直接输入两个已设置的图标, optional): 图标风格,也可以自已设置图标id. Defaults to 'TRIA' | 'ARROW' | 'TRI' | (str, str).
    Returns:
        (str,str): _description_
    """
    icon_data = {
        'TRI': ('DISCLOSURE_TRI_DOWN', 'DISCLOSURE_TRI_RIGHT'),
        'TRIA': ('TRIA_DOWN', 'TRIA_RIGHT'),
        'SORT': ('SORT_ASC', 'SORT_DESC'),
        'ARROW': ('DOWNARROW_HLT', 'RIGHTARROW'),
        'CHECKBOX': ('CHECKBOX_HLT', 'CHECKBOX_DEHLT'),
        'RESTRICT_SELECT': ('RESTRICT_SELECT_OFF', 'RESTRICT_SELECT_ON'),
        'HIDE': ('HIDE_OFF', 'HIDE_ON'),
        'ALIGN': ('ALIGN_LEFT', 'ALIGN_RIGHT'),
    }
    if icon_style in icon_data:
        return icon_data[icon_style]
    else:
        return icon_data['TRI']


def get_blender_icon(icon: str) -> str:
    """获取Blender图标
    部分图标在新版本被删除或是改变了名称
    """
    version = bpy.app.version[:2]
    if icon == "INTERNET" and version <= (4, 1):
        icon = "URL"
    if icon == "FILE_ALIAS" and version <= (4, 2):
        icon = "FOLDER_REDIRECT"
    return icon


def blender_icon_two(bool_prop, style='CHECKBOX', custom_icon: tuple[str, str] = None, ) -> str:
    """输入一个布尔值,反回图标类型str
    Args:
        bool_prop (_type_): _description_
        custom_icon (tuple[str, str], optional): 输入两个自定义的图标名称,True反回前者. Defaults to None.
        Style (str, optional): 图标的风格. Defaults to 'CHECKBOX'.
    Returns:
        str: 反回图标str
    """
    icon_true, icon_false = custom_icon if custom_icon else get_tow_blender_icon(style)
    return icon_true if bool_prop else icon_false


def get_item_icon(item: bpy.types.Object | bpy.types.Collection):

    if isinstance(item, bpy.types.Collection):
        return {'icon': "OUTLINER_COLLECTION"}
    elif isinstance(item, bpy.types.Object):
        if item.type == "LIGHT":
            for i in item.data.bl_rna.properties['type'].enum_items:
                if item.data.type == i.identifier:
                    return {"icon": i.icon}
        elif hasattr(item, 'data'):
            try:
                icon_value = bpy.types.UILayout.icon(item.data)
                if icon_value != 157:
                    return {"icon_value": icon_value}
            except Exception:
                ...
        if item.type == "EMPTY":
            return {"icon": "EMPTY_DATA"}
        else:
            return {"icon": "OBJECT_DATA"}
    return {"icon": "QUESTION"}
