from functools import cache

import addon_utils
import bpy


def addon_keys():
    """获取插件keys"""
    if bpy.app.version >= (4, 2, 0):
        return addon_utils.modules().mapping.keys()
    else:
        return [addon.__name__ for addon in addon_utils.modules()]


def addon_items():
    """获取插件items{id:mod}"""
    if bpy.app.version >= (4, 2, 0):
        return addon_utils.modules().mapping.items()
    else:
        return {addon.__name__: addon for addon in addon_utils.modules()}


def __draw_addon_layout__(context, pie, identifier, url, draw_func, *, draw_header=None):
    """如果没有安装显示安装按钮,已安装未开启显示开启按钮
    """
    from .icon import get_blender_icon
    column = pie.column(align=True)
    if draw_header:
        draw_header(context, column.row(align=True))
    else:
        column.label(text=identifier.title())
    if not check_addon_installed(identifier):
        text = "Manual install"
        row = column.row(align=True)
        if bpy.app.version >= (4, 2, 0):
            repos = context.preferences.extensions.repos
            for index, repo in enumerate(repos):
                if repo.remote_url == r"https://extensions.blender.org/api/v1/extensions/":
                    ops = row.operator("extensions.package_install")
                    ops.pkg_id = identifier
                    ops.repo_index = 0
                    text = ""
                    break
        else:
            column.label(text="No online extension library for version 4.1 and below")
            text = "Please install this Addon manually"
        ops = row.operator("wm.url_open", text=text, icon=get_blender_icon("INTERNET"))
        ops.url = url
    elif not check_addon_enabled(identifier):
        column.operator("preferences.addon_enable").module = find_addon_module_identifier(identifier)
    else:
        draw_func(context, column)


@cache
def check_addon_enabled(addon_name="M8") -> bool:
    """检查插件是否启用"""
    for addon in bpy.context.preferences.addons.keys():
        name = addon.split(".")[-1]
        if name == addon_name:
            return True
    return False


@cache
def check_addon_installed(addon_name="M8") -> bool:
    """检查插件ID是否安装"""
    for addon in addon_keys():
        name = addon.split(".")[-1]
        if name == addon_name:
            return True
    return False


@cache
def check_addon_expanded(addon_identifier="bl_ext.blender_org.M8") -> bool:
    import addon_utils
    addon_utils.modules_refresh()
    for addon, mod in addon_items():
        if addon == addon_identifier:
            bl_info = addon_utils.module_bl_info(mod)
            return bl_info["show_expanded"]
    return False


@cache
def find_addon_module_identifier(addon_name="M8") -> str | None:
    """查找插件的模块
    M8
    bl_ext.user_default.M8
    """
    for addon in addon_keys():
        name = addon.split(".")[-1]
        if name == addon_name:
            return addon
    return None


def clear_cache():
    check_addon_enabled.cache_clear()
    check_addon_installed.cache_clear()
    find_addon_module_identifier.cache_clear()


def draw_addon(context, layout: bpy.types.UILayout, identifier: str):
    """输入Id绘制插件"""
    from ..src.requires import REQUIRES_ADDON
    for item in REQUIRES_ADDON:
        if item["identifier"] == identifier:
            url = item["url"]
            draw_func = item["draw"]
            header = item.get("draw_header", None)
            __draw_addon_layout__(
                context,
                layout,
                item["identifier"],
                url=url,
                draw_func=draw_func,
                draw_header=header)
            return
    else:
        layout.label(text=f"未找到插件 {identifier}")


def draw_addon_install(context, layout: bpy.types.UILayout, items, left=False):
    from .icon import get_blender_icon
    for item in items:
        label = item["label"]
        url = item["url"]
        identifier = item["identifier"]
        description = item["description"]
        column = layout.box().column(align=True)

        def draw(c, dl: bpy.types.UILayout):
            row = dl.row(align=True)
            row.label(text="Enabled")

        def header(c, h: bpy.types.UILayout):
            from ..utils.addon import check_addon_enabled
            row = h.row(align=True)
            rr = row.row(align=True)
            if left:
                rr.operator("wm.url_open", text="", emboss=False, icon=get_blender_icon("INTERNET")).url = url

            rr.label(text=label, translate=False)
            if check_addon_enabled(identifier):
                rr.label(text="✓")

            row.separator()
            if not left:
                row.operator("wm.url_open", text="", emboss=False, icon=get_blender_icon("INTERNET")).url = url

        __draw_addon_layout__(
            context,
            column,
            identifier,
            url,
            draw_func=draw,
            draw_header=header,
        )
        column.label(text=description)


def draw_check_keymap_conflicts(context, layout: bpy.types.UILayout):
    if check_addon_enabled("viewport_pie_menus"):
        from ..src.url import KEYMAP_CONFLICTS_BUG_TRACKING_URL
        column = layout.box().column()
        ac = column.column()
        ac.alert = True
        ac.label(text="Detected Keymap Conflicts")
        ac.label(text="Due to the Addon ‘3D Viewport Pie Menus’ all Keymaps for M8 will be removed")
        ac.label(text="M8 will be affected by this and all Keymaps will be disabled!")
        column.label(text="So please disable this Addon")
        column.label(text="Don't use this Addon for now until the Addon fixes this issue")
        column.label(text="After disabling the Addon and re-enabling M8, it will be back to normal")

        row = column.row(align=True)
        ops = row.operator("preferences.addon_disable", text="Disable this Addon")
        ops.module = find_addon_module_identifier("viewport_pie_menus")
        row.operator(
            "wm.url_open",
            text="Bug Tracking",
        ).url = KEYMAP_CONFLICTS_BUG_TRACKING_URL
