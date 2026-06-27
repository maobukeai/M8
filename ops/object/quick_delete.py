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
                self.report({"INFO"}, "已删除节点")
                return {"FINISHED"}
            except Exception:
                self.report({"WARNING"}, "删除节点失败")
                return {"CANCELLED"}

        count = len(context.selected_objects)
        try:
            bpy.ops.object.delete(confirm=False)
        except Exception:
            self.report({"WARNING"}, "删除物体失败")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已删除 {count} 个物体")
        return {"FINISHED"}
