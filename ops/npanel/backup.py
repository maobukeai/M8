"""
M8 N-Panel Manager: Backup & Restore (JSON Export / Import)
支持将分类与子标签配置完整导出为 JSON 文件，或跨设备一键恢复。
"""
import bpy
import json
import os
from ...utils.i18n import _T
from . import core


class M8_OT_NPanelExportConfig(bpy.types.Operator):
    """导出 N 侧栏分类配置为 JSON"""
    bl_idname = "m8.npanel_export_config"
    bl_label = _T("导出侧栏配置")
    bl_description = _T("将当前所有侧边栏大分类与子标签配置导出为 JSON 备份文件")
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

        data = {
            "version": "1.0",
            "enabled": settings.enabled,
            "hide_unassigned": settings.hide_unassigned,
            "excluded_tabs": settings.excluded_tabs,
            "max_tabs_per_row": settings.max_tabs_per_row,
            "categories": []
        }

        for cat in settings.categories:
            cat_data = {
                "name": cat.name,
                "tabs": [t.name for t in cat.tabs]
            }
            data["categories"].append(cat_data)

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
    bl_description = _T("从外部 JSON 备份文件导入侧边栏分类配置并立即生效")
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

            settings.categories.clear()
            settings.enabled = data.get("enabled", True)
            settings.hide_unassigned = data.get("hide_unassigned", False)
            settings.excluded_tabs = data.get("excluded_tabs", "Item, Tool, View")
            settings.max_tabs_per_row = data.get("max_tabs_per_row", 4)

            for cat_data in data.get("categories", []):
                cat = settings.categories.add()
                cat.name = cat_data.get("name", "未命名分类")
                for i, tab_name in enumerate(cat_data.get("tabs", [])):
                    t = cat.tabs.add()
                    t.name = tab_name
                    t.is_active = (i == 0)

            core.apply_organization(context)
            if context and getattr(context, "area", None):
                context.area.tag_redraw()
            self.report({"INFO"}, _T("已成功导入侧边栏配置！"))
        except Exception as e:
            self.report({"ERROR"}, f"{_T('导入失败')}: {e}")
            return {"CANCELLED"}

        return {"FINISHED"}


BACKUP_CLASSES = (
    M8_OT_NPanelExportConfig,
    M8_OT_NPanelImportConfig,
)
