import bpy

from ...utils.i18n import _T


class M8_OT_QuickDelete(bpy.types.Operator):
    bl_idname = "m8.quick_delete"
    bl_label = _T("快速删除")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if getattr(context.area, "type", "") == 'NODE_EDITOR':
            return True
        return bool(getattr(context, "mode", "") == "OBJECT" and getattr(context, "selected_objects", None))

    def execute(self, context):
        if getattr(context.area, "type", "") == 'NODE_EDITOR':
            try:
                bpy.ops.node.delete()
                self.report({"INFO"}, _T("已删除节点"))
                return {"FINISHED"}
            except Exception:
                self.report({"WARNING"}, _T("删除节点失败"))
                return {"CANCELLED"}

        selected = getattr(context, "selected_objects", [])
        count = len(selected)
        try:
            bpy.ops.object.delete(confirm=False)
        except Exception:
            self.report({"WARNING"}, _T("删除物体失败"))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{_T('已删除 ')}{count}{_T(' 个物体')}")
        return {"FINISHED"}
