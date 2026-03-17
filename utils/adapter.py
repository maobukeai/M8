"""
version 0.0.1
适配各版本api之间不同的处理
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
    if icon == "RNA_ADD" and version <= (5, 0):
        icon = "ADD"
    if icon not in ALL_ICON:
        icon = "QUESTION"

    return icon
