import json

import bpy


def _wm_state(context):
    return getattr(getattr(context, "window_manager", None), "m8", None)


def _load_snapshot_names(wm_state):
    if not wm_state:
        return []
    raw = getattr(wm_state, "selection_snapshot_names", "")
    if not raw:
        return []
    try:
        names = json.loads(raw)
    except Exception:
        return []
    return [name for name in names if isinstance(name, str)]


def _store_snapshot(wm_state, names, active_name, summary):
    wm_state.selection_snapshot_names = json.dumps(names)
    wm_state.selection_snapshot_active = active_name if active_name in names else ""
    wm_state.selection_snapshot_summary = summary


def _selected_names(context):
    return [obj.name for obj in context.selected_objects if obj and obj.name]


def _ensure_object_mode(context):
    if getattr(context, "mode", "OBJECT") == "OBJECT":
        return True
    if not bpy.ops.object.mode_set.poll():
        return False
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
        return True
    except Exception:
        return False


class M8_OT_SaveSelectionSnapshot(bpy.types.Operator):
    bl_idname = "m8.save_selection_snapshot"
    bl_label = "保存选择快照"
    bl_description = "保存当前物体选择，便于快速恢复"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return bool(getattr(context, "selected_objects", None))

    def execute(self, context):
        wm_state = _wm_state(context)
        if not wm_state:
            self.report({"ERROR"}, "M8 状态未就绪")
            return {"CANCELLED"}

        names = _selected_names(context)
        if not names:
            self.report({"WARNING"}, "没有选中物体可保存")
            return {"CANCELLED"}

        active = getattr(context.view_layer.objects, "active", None)
        active_name = active.name if active and active.name in names else ""

        _store_snapshot(wm_state, names, active_name, f"{len(names)} object(s) saved")

        self.report({"INFO"}, wm_state.selection_snapshot_summary)
        return {"FINISHED"}


class M8_OT_AddSelectionToSnapshot(bpy.types.Operator):
    bl_idname = "m8.add_selection_to_snapshot"
    bl_label = "添加选择到快照"
    bl_description = "将当前选择添加到已保存的选择快照中"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return bool(getattr(context, "selected_objects", None))

    def execute(self, context):
        wm_state = _wm_state(context)
        if not wm_state:
            self.report({"ERROR"}, "M8 状态未就绪")
            return {"CANCELLED"}

        names = _load_snapshot_names(wm_state)
        existing = set(names)
        added = []
        for name in _selected_names(context):
            if name in existing:
                continue
            names.append(name)
            existing.add(name)
            added.append(name)

        active = getattr(context.view_layer.objects, "active", None)
        active_name = active.name if active and active.name in names else getattr(wm_state, "selection_snapshot_active", "")
        summary = f"{len(names)} object(s) in snapshot"
        if added:
            summary += f", {len(added)} added"
        else:
            summary += ", no new objects"

        _store_snapshot(wm_state, names, active_name, summary)
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class M8_OT_RemoveSelectionFromSnapshot(bpy.types.Operator):
    bl_idname = "m8.remove_selection_from_snapshot"
    bl_label = "从快照移除选择"
    bl_description = "将当前选择从已保存的选择快照中移除"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        wm_state = _wm_state(context)
        return bool(getattr(context, "selected_objects", None) and _load_snapshot_names(wm_state))

    def execute(self, context):
        wm_state = _wm_state(context)
        names = _load_snapshot_names(wm_state)
        if not wm_state or not names:
            self.report({"WARNING"}, "未保存任何选择快照")
            return {"CANCELLED"}

        remove_names = set(_selected_names(context))
        new_names = [name for name in names if name not in remove_names]
        removed_count = len(names) - len(new_names)

        if not new_names:
            wm_state.selection_snapshot_names = ""
            wm_state.selection_snapshot_active = ""
            wm_state.selection_snapshot_summary = "Snapshot cleared"
            self.report({"INFO"}, wm_state.selection_snapshot_summary)
            return {"FINISHED"}

        active_name = getattr(wm_state, "selection_snapshot_active", "")
        if active_name not in new_names:
            active_name = new_names[0]

        summary = f"{len(new_names)} object(s) in snapshot"
        if removed_count:
            summary += f", {removed_count} removed"
        else:
            summary += ", no matching objects"

        _store_snapshot(wm_state, new_names, active_name, summary)
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class M8_OT_RestoreSelectionSnapshot(bpy.types.Operator):
    bl_idname = "m8.restore_selection_snapshot"
    bl_label = "恢复选择快照"
    bl_description = "恢复已保存的物体选择和活动物体"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        wm_state = _wm_state(context)
        return bool(_load_snapshot_names(wm_state))

    def execute(self, context):
        wm_state = _wm_state(context)
        names = _load_snapshot_names(wm_state)
        if not names:
            self.report({"WARNING"}, "未保存任何选择快照")
            return {"CANCELLED"}

        if not _ensure_object_mode(context):
            self.report({"ERROR"}, "无法切换到物体模式")
            return {"CANCELLED"}

        view_object_names = {obj.name for obj in context.view_layer.objects}
        restored = []
        missing = []
        skipped = []

        bpy.ops.object.select_all(action="DESELECT")
        for name in names:
            obj = bpy.data.objects.get(name)
            if not obj:
                missing.append(name)
                continue
            if obj.name not in view_object_names:
                skipped.append(name)
                continue
            try:
                obj.select_set(True)
            except Exception:
                skipped.append(name)
                continue
            restored.append(obj)

        if not restored:
            wm_state.selection_snapshot_summary = "Snapshot has no selectable objects"
            self.report({"WARNING"}, wm_state.selection_snapshot_summary)
            return {"CANCELLED"}

        active_name = getattr(wm_state, "selection_snapshot_active", "")
        active_obj = bpy.data.objects.get(active_name) if active_name else None
        if active_obj not in restored:
            active_obj = restored[0]
        context.view_layer.objects.active = active_obj

        summary = f"{len(restored)} restored"
        if missing:
            summary += f", {len(missing)} missing"
        if skipped:
            summary += f", {len(skipped)} skipped"
        wm_state.selection_snapshot_summary = summary
        self.report({"INFO"}, summary)
        return {"FINISHED"}


class M8_OT_ClearSelectionSnapshot(bpy.types.Operator):
    bl_idname = "m8.clear_selection_snapshot"
    bl_label = "清空选择快照"
    bl_description = "清空已保存的物体选择快照"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return bool(_wm_state(context))

    def execute(self, context):
        wm_state = _wm_state(context)
        if not wm_state:
            self.report({"ERROR"}, "M8 状态未就绪")
            return {"CANCELLED"}
        wm_state.selection_snapshot_names = ""
        wm_state.selection_snapshot_active = ""
        wm_state.selection_snapshot_summary = ""
        self.report({"INFO"}, "已清除选择快照")
        return {"FINISHED"}
