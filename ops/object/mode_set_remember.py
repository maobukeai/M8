import bpy


class M8_OT_ModeSetRemember(bpy.types.Operator):
    bl_idname = "m8.mode_set_remember"
    bl_label = "Mode Set (Remember)"
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
            return {"CANCELLED"}
        return {"FINISHED"}
