import bpy


class M8_OT_SwitchUVMode(bpy.types.Operator):
    bl_idname = "m8.switch_uv_mode"
    bl_label = "Switch UV Mode"
    bl_options = {"REGISTER", "UNDO"}

    uv_mode: bpy.props.StringProperty(default="")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        if context.mode == "OBJECT":
            bpy.ops.object.mode_set(mode="EDIT", toggle=False)

        if context.object and context.object.type == "MESH":
            if len(context.object.data.uv_layers[:]) == 0:
                bpy.ops.mesh.uv_texture_add()

        tool_settings = context.tool_settings
        is_sync = tool_settings.use_uv_select_sync
        ops = bpy.ops.mesh.select_mode if is_sync else bpy.ops.uv.select_mode
        ops("INVOKE_DEFAULT", type=self.uv_mode)
        return {"FINISHED"}
