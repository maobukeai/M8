"""
M8 N-Panel Manager: Backup & Auto-Persistence Engine
支持跨会话/跨工程自动持久化与加载、多编辑器 (3D/Image/Node) 独立分类导出与导入。
"""
import bpy
import json
import os
from ...utils.i18n import _T
from . import core
from . import classifier


def get_preset_filepath() -> str:
    """获取用户预设持久化文件路径（位于 Blender 用户配置目录）"""
    try:
        config_dir = bpy.utils.user_resource("CONFIG")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "m8_npanel_presets.json")
    except Exception:
        home = os.path.expanduser("~")
        return os.path.join(home, ".m8_npanel_presets.json")


def serialize_all_settings(settings) -> dict:
    """完整序列化多编辑器配置与全局参数"""
    data = {
        "version": "2.0",
        "enabled": settings.enabled,
        "show_subtabs_header": getattr(settings, "show_subtabs_header", False),
        "workspace_auto_switch": settings.workspace_auto_switch,
        "max_tabs_per_row": settings.max_tabs_per_row,
        "spaces": {}
    }

    space_keys = [
        ("VIEW_3D", settings.categories, settings.hide_unassigned, settings.excluded_tabs, settings.enabled),
        ("IMAGE_EDITOR", settings.categories_image_editor, settings.hide_unassigned_image_editor, settings.excluded_tabs_image_editor, settings.enabled_image_editor),
        ("NODE_EDITOR", settings.categories_node_editor, settings.hide_unassigned_node_editor, settings.excluded_tabs_node_editor, settings.enabled_node_editor),
    ]

    for space_type, cat_prop, hide_un, excl, en_space in space_keys:
        space_data = {
            "enabled": en_space,
            "hide_unassigned": hide_un,
            "excluded_tabs": excl,
            "categories": []
        }
        for cat in cat_prop:
            space_data["categories"].append({
                "name": cat.name,
                "icon": getattr(cat, "icon", "") or "OUTLINER_COLLECTION",
                "tabs": [
                    {"name": t.name, "custom_name": getattr(t, "custom_name", "")}
                    if getattr(t, "custom_name", "") else t.name
                    for t in cat.tabs
                ]
            })
        data["spaces"][space_type] = space_data

    # 兼容 1.0 格式：顶层保留 VIEW_3D 数据
    data["categories"] = data["spaces"]["VIEW_3D"]["categories"]
    data["hide_unassigned"] = settings.hide_unassigned
    data["excluded_tabs"] = settings.excluded_tabs
    return data


def deserialize_all_settings(settings, data: dict):
    """反序列化配置至 settings（向下兼容 1.0 格式与 2.0 多编辑器格式）"""
    settings.enabled = data.get("enabled", False)
    settings.show_subtabs_header = data.get("show_subtabs_header", False)
    settings.workspace_auto_switch = data.get("workspace_auto_switch", True)
    raw_max = data.get("max_tabs_per_row", "AUTO")
    if isinstance(raw_max, int):
        raw_max = str(raw_max)
    if str(raw_max) not in {"AUTO", "1", "2", "3", "4", "5", "6", "7", "8"}:
        raw_max = "AUTO"
    settings.max_tabs_per_row = raw_max

    spaces = data.get("spaces", {})
    if not spaces:
        # 兼容 1.0 单空间老格式
        spaces = {
            "VIEW_3D": {
                "enabled": settings.enabled,
                "hide_unassigned": data.get("hide_unassigned", False),
                "excluded_tabs": data.get("excluded_tabs", ""),
                "categories": data.get("categories", [])
            }
        }

    # 1. VIEW_3D
    v3d_data = spaces.get("VIEW_3D", {})
    if v3d_data:
        settings.hide_unassigned = v3d_data.get("hide_unassigned", False)
        settings.excluded_tabs = v3d_data.get("excluded_tabs", "")
        settings.categories.clear()
        for cat_data in v3d_data.get("categories", []):
            cat = settings.categories.add()
            cat.name = cat_data.get("name", "分类")
            cat.icon = cat_data.get("icon", "") or "OUTLINER_COLLECTION"
            for i, tab_info in enumerate(cat_data.get("tabs", [])):
                t = cat.tabs.add()
                if isinstance(tab_info, dict):
                    t.name = tab_info.get("name", "")
                    t.custom_name = tab_info.get("custom_name", "") or classifier.get_tab_display_label(t.name)
                else:
                    t.name = str(tab_info)
                    t.custom_name = classifier.get_tab_display_label(t.name)
                t.is_active = (i == 0)

    # 2. IMAGE_EDITOR
    img_data = spaces.get("IMAGE_EDITOR", {})
    if img_data:
        settings.enabled_image_editor = img_data.get("enabled", True)
        settings.hide_unassigned_image_editor = img_data.get("hide_unassigned", False)
        settings.excluded_tabs_image_editor = img_data.get("excluded_tabs", "Image, Tool, View, 图像, 工具, 视图")
        settings.categories_image_editor.clear()
        for cat_data in img_data.get("categories", []):
            cat = settings.categories_image_editor.add()
            cat.name = cat_data.get("name", "分类")
            cat.icon = cat_data.get("icon", "") or "OUTLINER_COLLECTION"
            for i, tab_info in enumerate(cat_data.get("tabs", [])):
                t = cat.tabs.add()
                if isinstance(tab_info, dict):
                    t.name = tab_info.get("name", "")
                    t.custom_name = tab_info.get("custom_name", "") or classifier.get_tab_display_label(t.name)
                else:
                    t.name = str(tab_info)
                    t.custom_name = classifier.get_tab_display_label(t.name)
                t.is_active = (i == 0)

    # 3. NODE_EDITOR
    node_data = spaces.get("NODE_EDITOR", {})
    if node_data:
        settings.enabled_node_editor = node_data.get("enabled", True)
        settings.hide_unassigned_node_editor = node_data.get("hide_unassigned", False)
        settings.excluded_tabs_node_editor = node_data.get("excluded_tabs", "Node, Tool, View, Options, 节点, 工具, 视图, 选项")
        settings.categories_node_editor.clear()
        for cat_data in node_data.get("categories", []):
            cat = settings.categories_node_editor.add()
            cat.name = cat_data.get("name", "分类")
            cat.icon = cat_data.get("icon", "") or "OUTLINER_COLLECTION"
            for i, tab_info in enumerate(cat_data.get("tabs", [])):
                t = cat.tabs.add()
                if isinstance(tab_info, dict):
                    t.name = tab_info.get("name", "")
                    t.custom_name = tab_info.get("custom_name", "") or classifier.get_tab_display_label(t.name)
                else:
                    t.name = str(tab_info)
                    t.custom_name = classifier.get_tab_display_label(t.name)
                t.is_active = (i == 0)


def clear_presets_on_disk() -> bool:
    """彻底删除磁盘持久化预设文件，杜绝恢复默认后旧配置幽灵复活"""
    try:
        path = get_preset_filepath()
        if os.path.isfile(path):
            os.remove(path)
        return True
    except Exception as e:
        print(f"[M8 NPanel] Failed to clear presets on disk: {e}")
        return False


def save_presets_to_disk(context) -> bool:
    """自动持久化用户分类预设至磁盘"""
    if not context or not hasattr(context, "scene"):
        return False
    settings = getattr(context.scene, "m8_npanel", None)
    if not settings:
        return False

    # 若没有任何分类且未启用，直接清空/删除磁盘预设文件，防止幽灵复活
    if not settings.categories and not settings.categories_image_editor and not settings.categories_node_editor and not settings.enabled:
        clear_presets_on_disk()
        return True

    try:
        path = get_preset_filepath()
        data = serialize_all_settings(settings)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[M8 NPanel] Failed to save presets: {e}")
        return False


def load_presets_from_disk(context, force: bool = False) -> bool:
    """从磁盘加载用户持久化分类预设"""
    if not context or not hasattr(context, "scene"):
        return False
    settings = getattr(context.scene, "m8_npanel", None)
    if not settings:
        return False

    # 若非强制模式，且当前场景已经有配置数据，则不覆盖
    if not force and (len(settings.categories) > 0 or len(settings.categories_image_editor) > 0 or len(settings.categories_node_editor) > 0):
        return False

    path = get_preset_filepath()
    if not os.path.isfile(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        deserialize_all_settings(settings, data)
        return True
    except Exception as e:
        print(f"[M8 NPanel] Failed to load presets: {e}")
        return False


class M8_OT_NPanelExportConfig(bpy.types.Operator):
    """导出 N 侧栏分类配置为 JSON"""
    bl_idname = "m8.npanel_export_config"
    bl_label = _T("导出侧栏配置")
    bl_description = _T("将当前所有编辑器 (3D/图像/节点) 的大分类与子标签配置导出为 JSON 备份文件")
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filename: bpy.props.StringProperty(default="m8_npanel_config.json")

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = os.path.join(os.path.expanduser("~"), "m8_npanel_config.json")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings:
            return {"CANCELLED"}

        data = serialize_all_settings(settings)

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.report({"INFO"}, f"{_T('配置已成功导出至')}: {self.filepath}")
        except Exception as e:
            self.report({"ERROR"}, f"{_T('导出失败')}: {e}")
            return {"CANCELLED"}

        return {"FINISHED"}


class M8_OT_NPanelImportConfig(bpy.types.Operator):
    """从 JSON 导入 N 侧栏分类配置"""
    bl_idname = "m8.npanel_import_config"
    bl_label = _T("导入侧栏配置")
    bl_description = _T("从外部 JSON 备份文件导入多编辑器侧栏配置并立即生效")
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings or not os.path.isfile(self.filepath):
            self.report({"ERROR"}, _T("无效的文件路径"))
            return {"CANCELLED"}

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            deserialize_all_settings(settings, data)
            save_presets_to_disk(context)

            st = getattr(settings, "active_space_type", "VIEW_3D")
            core.apply_organization(context, space_type=st)
            if context and getattr(context, "area", None):
                context.area.tag_redraw()
            self.report({"INFO"}, _T("已成功导入侧边栏配置并持久化生效！"))
        except Exception as e:
            self.report({"ERROR"}, f"{_T('导入失败')}: {e}")
            return {"CANCELLED"}

        return {"FINISHED"}


BACKUP_CLASSES = (
    M8_OT_NPanelExportConfig,
    M8_OT_NPanelImportConfig,
)

