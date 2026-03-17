import bpy


class M8_OT_SelectSceneCamera(bpy.types.Operator):
    bl_idname = "m8.select_scene_camera"
    bl_label = "选择活动相机"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.scene and context.scene.camera)

    def execute(self, context):
        cam = context.scene.camera
        try:
            bpy.ops.object.select_all(action="DESELECT")
        except Exception:
            pass
        try:
            cam.select_set(True)
            context.view_layer.objects.active = cam
        except Exception:
            return {"CANCELLED"}
        return {"FINISHED"}
