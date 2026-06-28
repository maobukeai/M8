import bpy

from ...utils.i18n import _T


def _get_addon_prefs(context):
    root_pkg = ".".join(__package__.split(".")[:3]) if (__package__ or "").startswith("bl_ext") else (__package__ or "").split(".")[0]
    addon = context.preferences.addons.get(root_pkg) if context.preferences else None
    return addon.preferences if addon else None


def _status_icon(status):
    if status == "OK":
        return "CHECKMARK"
    if status == "WARNING":
        return "ERROR"
    if status == "ERROR":
        return "CANCEL"
    return "INFO"


class VIEW3D_PT_M8_Diagnostics(bpy.types.Panel):
    bl_label = _T("M8 诊断")
    bl_idname = "VIEW3D_PT_m8_diagnostics"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "m8"
    bl_order = 99
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        prefs = _get_addon_prefs(context)
        return bool(getattr(prefs, "show_diagnostics_panels", False))

    def draw(self, context):
        layout = self.layout
        wm_state = getattr(context.window_manager, "m8", None)

        row = layout.row(align=True)
        row.operator("m8.run_health_check", text=_T("运行"), icon="FILE_REFRESH")
        op = row.operator("m8.run_full_system_check", text=_T("完整"))
        op.scene_scope = "VISIBLE"
        row.operator("m8.copy_health_report", text="", icon="COPYDOWN")
        row.operator("m8.copy_full_system_report", text="", icon="COPY_ID")

        if not wm_state:
            layout.label(text=_T("M8 状态未就绪"), icon="ERROR")
            return

        status = getattr(wm_state, "health_status", "UNKNOWN")
        summary = getattr(wm_state, "health_summary", "")
        checked_at = getattr(wm_state, "health_checked_at", "")
        details = getattr(wm_state, "health_details", "")
        full_status = getattr(wm_state, "full_check_status", "UNKNOWN")
        full_summary = getattr(wm_state, "full_check_summary", "")
        full_checked_at = getattr(wm_state, "full_check_checked_at", "")

        box = layout.box()
        box.label(text=status, icon=_status_icon(status))
        if summary:
            box.label(text=summary)
        if checked_at:
            box.label(text=checked_at, icon="TIME")
        if full_summary:
            box.label(text=full_summary[:110], icon=_status_icon(full_status))
        if full_checked_at:
            box.label(text=full_checked_at, icon="TIME")

        if details:
            detail_box = layout.box()
            for line in details.splitlines()[:18]:
                detail_box.label(text=line[:110])
