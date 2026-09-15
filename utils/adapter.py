"""
version 0.0.2
适配各版本 Blender API 之间不同的处理与安全全局视口重绘
"""
import bpy

try:
    _icon_enum = bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items
    ALL_ICON = {i.identifier for i in _icon_enum}
except Exception:
    try:
        ALL_ICON = {i.identifier for i in bpy.types.Property.bl_rna.properties["icon"].enum_items_static}
    except Exception:
        ALL_ICON = set()


def operator_invoke_confirm(self, event, context, title, message) -> set:
    """4.1版本以上需要多传参数
    更改了显示模式,新版本将显示两个按钮"""
    if bpy.app.version >= (4, 1, 0):
        return context.window_manager.invoke_confirm(
            **{
                "operator": self,
                "event": event,
                'title': title,
                'message': message,
            }
        )
    else:
        return context.window_manager.invoke_confirm(
            self, event
        )


def get_adapter_blender_icon(icon=None):
    """获取适配的图标
    每个版本都会对图标进行添加或删除
    """
    if icon is None:
        return "NONE"
    version = bpy.app.version[:2]

    if icon == "INTERNET" and version <= (4, 1):
        icon = "URL"
    if icon == "FILE_ALIAS" and version <= (4, 2):
        icon = "FOLDER_REDIRECT"
    if icon == "RNA_ADD" and "RNA_ADD" not in ALL_ICON:
        icon = "ADD"
    if icon not in ALL_ICON:
        icon = "QUESTION"

    return icon


def tag_redraw_all_areas(area_types=None):
    """安全地标记重绘所有窗口与屏幕区域，可指定 area_types 进行过滤（例如 {'TEXT_EDITOR', 'VIEW_3D', 'PREFERENCES'}）。
    在 bpy.app.timers、多线程异步回调或 context 发生漂移时极其安全，杜绝崩溃。
    """
    ctx = getattr(bpy, "context", None)
    if not ctx:
        return
    wm = getattr(ctx, "window_manager", None)
    if not wm:
        return
    for window in getattr(wm, "windows", []):
        screen = getattr(window, "screen", None)
        if not screen:
            continue
        for area in getattr(screen, "areas", []):
            if area_types is None or area.type in area_types:
                try:
                    area.tag_redraw()
                except Exception:
                    pass
