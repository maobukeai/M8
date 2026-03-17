import os

import bpy.utils.previews

previews_icons = None
thumbnail_suffix = [".png", ".jpg"]  # 缩略图后缀列表


def get_dat_icon(name):
    return os.path.normpath(os.path.join(os.path.dirname(__file__), name))


def _ensure_previews():
    global previews_icons
    if previews_icons is None:
        previews_icons = bpy.utils.previews.new()
    return previews_icons


def load_icons():
    """预加载图标
    在启动blender或是启用插件时加载图标
    """
    from os.path import dirname, join, isfile
    pcoll = _ensure_previews()
    for root, dirs, files in os.walk(dirname(__file__)):
        for file in files:
            icon_path = join(root, file)
            is_file = isfile(icon_path)
            is_icon = file[-4:] in thumbnail_suffix

            name = file[:-4].lower()
            if is_icon and is_file:
                pcoll.load(name, icon_path, "IMAGE", )


def clear():
    global previews_icons
    if previews_icons is None:
        return
    previews_icons.clear()


def register():
    load_icons()


def unregister():
    global previews_icons
    if previews_icons is None:
        return
    try:
        previews_icons.clear()
    except Exception:
        pass
    try:
        bpy.utils.previews.remove(previews_icons)
    except Exception:
        pass
    previews_icons = None
