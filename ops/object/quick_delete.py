import bpy


class M8_OT_QuickDelete(bpy.types.Operator):
    bl_idname = "m8.quick_delete"
    bl_label = "快速删除"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if getattr(context.area, "type", "") == 'NODE_EDITOR':
            return True
        return bool(context.mode == "OBJECT" and context.selected_objects)

    def execute(self, context):
        if context.area.type == 'NODE_EDITOR':
            try:
                bpy.ops.node.delete()
                return {"FINISHED"}
            except Exception:
                return {"CANCELLED"}

        try:
            bpy.ops.object.delete(confirm=False)
        except Exception:
            return {"CANCELLED"}
        return {"FINISHED"}
