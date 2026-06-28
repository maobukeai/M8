import bpy

from ...utils.i18n import _T


class M8_OT_CameraLensStep(bpy.types.Operator):
    bl_idname = "m8.camera_lens_step"
    bl_label = _T("焦距步进")
    bl_options = {"REGISTER", "UNDO"}

    delta: bpy.props.FloatProperty(name="Delta", default=5.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "CAMERA" and obj.data and hasattr(obj.data, "lens"))

    def execute(self, context):
        cam = context.active_object.data
        try:
            cam.lens = max(1.0, float(cam.lens) + float(self.delta))
        except Exception:
            self.report({"WARNING"}, _T("调整焦距失败"))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{_T('焦距：')}{cam.lens:.1f}mm")
        return {"FINISHED"}
