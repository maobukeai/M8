import bpy


class M8_OT_CameraLensStep(bpy.types.Operator):
    bl_idname = "m8.camera_lens_step"
    bl_label = "焦距步进"
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
            return {"CANCELLED"}
        return {"FINISHED"}
