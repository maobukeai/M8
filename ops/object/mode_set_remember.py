import bpy


class M8_OT_ModeSetRemember(bpy.types.Operator):
    bl_idname = "m8.mode_set_remember"
    bl_label = "切换模式（记忆）"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.StringProperty()
    toggle: bpy.props.BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return bool(context.active_object)

    def execute(self, context):
        wm = context.window_manager
        obj = context.active_object
        if obj:
            try:
                obj.m8.last_object_mode = obj.type
                obj.m8.last_object_mode = self.mode
            except Exception:
                pass

        try:
            bpy.ops.object.mode_set(mode=self.mode, toggle=self.toggle)
        except Exception:
            self.report({"WARNING"}, f"无法切换到 {self.mode} 模式")
            return {"CANCELLED"}
        mode_label = {"OBJECT": "物体", "EDIT": "编辑", "POSE": "姿态", "SCULPT": "雕刻"}.get(self.mode, self.mode)
        self.report({"INFO"}, f"已切换到 {mode_label} 模式")
        return {"FINISHED"}
