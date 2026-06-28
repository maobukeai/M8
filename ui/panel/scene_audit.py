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


class VIEW3D_PT_M8_SceneAudit(bpy.types.Panel):
    bl_label = _T("M8 场景审计")
    bl_idname = "VIEW3D_PT_m8_scene_audit"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "m8"
    bl_order = 98
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        prefs = _get_addon_prefs(context)
        return bool(getattr(prefs, "show_diagnostics_panels", False))

    def draw(self, context):
        layout = self.layout
        wm_state = getattr(context.window_manager, "m8", None)

        if not wm_state:
            layout.label(text=_T("M8 状态未就绪"), icon="ERROR")
            return

        layout.prop(wm_state, "scene_audit_high_poly_threshold", text=_T("高面数"))
        row = layout.row(align=True)
        row.prop(wm_state, "scene_audit_make_backup", text=_T("备份"))
        row.prop(wm_state, "scene_audit_backup_collection_name", text="")

        row = layout.row(align=True)
        op = row.operator("m8.run_scene_audit", text=_T("选中"))
        op.scope = "SELECTED"
        op.high_poly_threshold = wm_state.scene_audit_high_poly_threshold
        op = row.operator("m8.run_scene_audit", text=_T("可见"))
        op.scope = "VISIBLE"
        op.high_poly_threshold = wm_state.scene_audit_high_poly_threshold
        op = row.operator("m8.run_scene_audit", text=_T("场景"))
        op.scope = "ALL"
        op.high_poly_threshold = wm_state.scene_audit_high_poly_threshold

        row = layout.row(align=True)
        row.operator("m8.select_scene_audit_problem_objects", text=_T("选择问题"), icon="RESTRICT_SELECT_OFF")
        row.operator("m8.copy_scene_audit_report", text="", icon="COPYDOWN")

        last_scope = getattr(wm_state, "scene_audit_last_scope", "SELECTED")
        fix_row = layout.row(align=True)
        op = fix_row.operator("m8.fix_scene_audit_safe_issues", text=_T("安全修复"), icon="BRUSH_DATA")
        op.scope = last_scope
        op.fix_geometry = True
        op.fix_materials = True
        op.rescan = True
        op.make_backup = wm_state.scene_audit_make_backup
        op.backup_collection_name = wm_state.scene_audit_backup_collection_name
        op = fix_row.operator("m8.select_scene_audit_issue_objects", text=_T("安全几何"))
        op.scope = last_scope
        op.issue_filter = "SAFE_GEOMETRY"

        row = layout.row(align=True)
        op = row.operator("m8.select_scene_audit_issue_objects", text=_T("拓扑"))
        op.scope = last_scope
        op.issue_filter = "TOPOLOGY"
        op = row.operator("m8.select_scene_audit_issue_objects", text=_T("材质"))
        op.scope = last_scope
        op.issue_filter = "MATERIALS"
        op = row.operator("m8.select_scene_audit_issue_objects", text=_T("变换"))
        op.scope = last_scope
        op.issue_filter = "TRANSFORMS"
        op = row.operator("m8.select_scene_audit_issue_objects", text=_T("高面数"))
        op.scope = last_scope
        op.issue_filter = "HIGH_POLY"

        backup_row = layout.row(align=True)
        op = backup_row.operator("m8.select_scene_audit_backups", text=_T("备份"), icon="PRESET")
        op.backup_collection_name = wm_state.scene_audit_backup_collection_name
        op.reveal = True
        op = backup_row.operator("m8.restore_scene_audit_selected_backups", text=_T("恢复选中"))
        op.rescan = True
        op.delete_backups = False
        op = backup_row.operator("m8.restore_scene_audit_latest_backups", text=_T("恢复最新"))
        op.backup_collection_name = wm_state.scene_audit_backup_collection_name
        op.rescan = True
        op.delete_backups = False

        manage_row = layout.row(align=True)
        op = manage_row.operator("m8.refresh_scene_audit_backups", text=_T("刷新"))
        op.backup_collection_name = wm_state.scene_audit_backup_collection_name
        manage_row.operator("m8.copy_scene_audit_backup_report", text="", icon="COPYDOWN")
        manage_row.prop(wm_state, "scene_audit_backup_keep_per_source", text=_T("保留"))
        op = manage_row.operator("m8.prune_scene_audit_backups", text=_T("清理"))
        op.backup_collection_name = wm_state.scene_audit_backup_collection_name
        op.keep_per_source = wm_state.scene_audit_backup_keep_per_source

        status = getattr(wm_state, "scene_audit_status", "UNKNOWN")
        summary = getattr(wm_state, "scene_audit_summary", "")
        checked_at = getattr(wm_state, "scene_audit_checked_at", "")
        details = getattr(wm_state, "scene_audit_details", "")
        last_fix = getattr(wm_state, "scene_audit_last_fix_summary", "")
        last_restore = getattr(wm_state, "scene_audit_last_restore_summary", "")
        last_backup_manage = getattr(wm_state, "scene_audit_last_backup_manage_summary", "")
        backup_status = getattr(wm_state, "scene_audit_backup_status", "UNKNOWN")
        backup_summary = getattr(wm_state, "scene_audit_backup_summary", "")
        backup_checked_at = getattr(wm_state, "scene_audit_backup_checked_at", "")
        fix_history = getattr(wm_state, "scene_audit_fix_history", "")

        box = layout.box()
        box.label(text=status, icon=_status_icon(status))
        if summary:
            box.label(text=summary[:110])
        if checked_at:
            box.label(text=checked_at, icon="TIME")
        if last_fix:
            box.label(text=last_fix[:110], icon="TOOL_SETTINGS")
        if last_restore:
            box.label(text=last_restore[:110], icon="PRESET")
        if last_backup_manage:
            box.label(text=last_backup_manage[:110], icon="PRESET")
        if backup_summary:
            box.label(text=backup_summary[:110], icon=_status_icon(backup_status))
        if backup_checked_at:
            box.label(text=backup_checked_at, icon="TIME")
        if fix_history:
            history_box = layout.box()
            history_box.label(text=_T("审计历史"), icon="PRESET")
            for line in fix_history.splitlines()[:5]:
                history_box.label(text=line[:110])

        if details:
            detail_box = layout.box()
            for line in details.splitlines()[:16]:
                detail_box.label(text=line[:110])
