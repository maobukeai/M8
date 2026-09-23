"""
M8 N-Panel Icon Preview Manager
Loads sub_tabs.png from the local icons folder for header menu buttons
"""
import os
import bpy
import bpy.utils.previews

_preview_collections = {}


def get_subtabs_icon_id() -> int:
    """获取 sub_tabs 自定义图标的 icon_id，若未加载则返回 0（回退）"""
    global _preview_collections
    pcoll = _preview_collections.get("npanel")
    if pcoll and "sub_tabs" in pcoll:
        return pcoll["sub_tabs"].icon_id
    return 0


def register():
    global _preview_collections
    if "npanel" not in _preview_collections:
        try:
            pcoll = bpy.utils.previews.new()
            icons_dir = os.path.join(os.path.dirname(__file__), "icons")
            icon_path = os.path.join(icons_dir, "sub_tabs.png")
            if os.path.exists(icon_path):
                pcoll.load("sub_tabs", icon_path, "IMAGE")
            _preview_collections["npanel"] = pcoll
        except Exception as e:
            print(f"[M8 NPanel] Failed to load preview icons: {e}")


def unregister():
    global _preview_collections
    pcoll = _preview_collections.pop("npanel", None)
    if pcoll:
        try:
            bpy.utils.previews.remove(pcoll)
        except Exception:
            pass
