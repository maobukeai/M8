import time
import bpy

from ...utils import ensure_object_mode

edit_mode_list = {
    "SURFACE",
    "META",
    "LATTICE",
    "FONT",
    "VOLUME",
    "LIGHT_PROBE",
    "SPEAKER",
    "CURVE",
}

popup_pie_type = {
    "GPENCIL",
    "GREASEPENCIL",
    "MESH",
    "CURVES",
    "ARMATURE",
    "CURVE",
    "FONT",
    "SURFACE",
    "LIGHT",
    "CAMERA",
    "META",
    "LATTICE",
    "EMPTY",
}

def check_image_editor(context) -> bool:
    return context.area.type == "IMAGE_EDITOR" or context.area.ui_type == "UV" or context.area.type == "NODE_EDITOR"

class M8_OT_SwitchBoneMode(bpy.types.Operator):
    bl_idname = "m8.switch_bone_mode"
    bl_label = "Switch Bone Mode"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "ARMATURE"

    def execute(self, context):
        bpy.ops.object.mode_set(mode="POSE", toggle=True)

        obj = context.object
        if obj and obj.mode == "POSE" and obj.data.pose_position == "REST":
            obj.data.pose_position = "POSE"
            self.report({"INFO"}, "Pose Position")
        return {"FINISHED"}


class OBJECT_OT_SwitchMode(bpy.types.Operator):
    bl_idname = "object.switch_mode"
    bl_label = "Switch Mode"
    bl_description = "Display the corresponding menu or enter the editing mode according to the active object and the current mode"
    bl_options = {"REGISTER", "UNDO"}

    _timer = None
    _press_time = 0.0
    _hold_triggered = False

    def _get_pref(self):
        root_pkg = (__package__ or "").split(".")[0]
        addon = bpy.context.preferences.addons.get(root_pkg)
        return addon.preferences if addon else None

    def _cleanup(self, context):
        wm = context.window_manager if context else None
        if wm and self._timer:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
        self._timer = None

    def _open_pie(self):
        try:
            bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name="VIEW3D_MT_m8_switch_mode_pie")
        except Exception:
            bpy.ops.wm.call_menu_pie(name="VIEW3D_MT_m8_switch_mode_pie")

    def _run_tap_action(self, context):
        pref = self._get_pref()
        behavior = getattr(pref, "switch_mode_tab_behavior", "INSTANT") if pref else "INSTANT"

        is_image_editor = check_image_editor(context)
        is_popup_type = context.object and context.object.type in popup_pie_type
        
        # 强制修正：如果对象是 GPENCIL/GREASEPENCIL，无论何种情况都应该触发饼菜单
        if context.object and context.object.type in {"GPENCIL", "GREASEPENCIL"}:
            is_popup_type = True

        if is_image_editor and context.area.type == "NODE_EDITOR" and behavior == "TAP_HOLD":
            # 材质节点模式下，Tap 键执行进出组操作
            active_node = context.active_node
            is_group_selected = active_node and getattr(active_node, "type", "") == "GROUP"
            
            is_inside_group = False
            space = context.space_data
            if hasattr(space, "path") and len(space.path) > 0:
                is_inside_group = True
            elif hasattr(space, "edit_tree") and hasattr(space, "node_tree") and space.edit_tree != space.node_tree:
                is_inside_group = True

            if is_group_selected:
                bpy.ops.node.group_edit()
                return {"FINISHED"}
            elif is_inside_group:
                bpy.ops.node.tree_path_parent()
                return {"FINISHED"}
            
            # 如果既没选中组也不在组内，则回落到打开饼菜单（或者什么都不做）
            self._open_pie()
            return {"FINISHED"}

        if is_popup_type or is_image_editor:
            self._open_pie()
            return {"FINISHED"}

        if context.area.type == "VIEW_3D":
            if context.object:
                obj_type = context.object.type
                mode = context.mode

                if obj_type == "EMPTY":
                    if pref and getattr(pref, "switch_mode_smart_focus", True):
                        bpy.ops.view3d.view_selected("INVOKE_DEFAULT")
                elif obj_type in {"LIGHT", "VOLUME", "LIGHT_PROBE", "SPEAKER", "CAMERA"}:
                    if pref and getattr(pref, "switch_mode_smart_focus", True):
                        if obj_type == "CAMERA":
                            self._open_pie()
                        elif obj_type == "LIGHT":
                            self._open_pie()
                        else:
                            bpy.ops.view3d.view_selected("INVOKE_DEFAULT")
                elif obj_type in edit_mode_list:
                    target_mode = "OBJECT" if "EDIT" in mode else "EDIT"
                    bpy.ops.object.mode_set(mode=target_mode, toggle=True)
                else:
                    self._open_pie()
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        pref = self._get_pref()
        behavior = getattr(pref, "switch_mode_tab_behavior", "INSTANT") if pref else "INSTANT"

        if behavior == "INSTANT":
            return self._run_tap_action(context)

        self._hold_triggered = False
        self._press_time = time.perf_counter()

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        pref = self._get_pref()
        behavior = getattr(pref, "switch_mode_tab_behavior", "INSTANT") if pref else "INSTANT"
        hold_ms = int(getattr(pref, "switch_mode_hold_ms", 220)) if pref else 220

        if behavior == "INSTANT":
            self._cleanup(context)
            return {"CANCELLED"}

        if event.type in {"ESC"}:
            self._cleanup(context)
            return {"CANCELLED"}

        if event.type == "TIMER" and not self._hold_triggered:
            elapsed_ms = (time.perf_counter() - self._press_time) * 1000.0
            if elapsed_ms >= hold_ms:
                self._hold_triggered = True
                self._cleanup(context)
                self._open_pie()
                return {"FINISHED"}

        if event.type == "TAB" and event.value == "RELEASE":
            self._cleanup(context)
            if self._hold_triggered:
                return {"FINISHED"}
            return self._run_tap_action(context)

        return {"RUNNING_MODAL"}
