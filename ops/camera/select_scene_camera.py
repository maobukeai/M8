import bpy

from ...utils.i18n import _T


class M8_OT_SelectSceneCamera(bpy.types.Operator):
    bl_idname = "m8.select_scene_camera"
    bl_label = _T("选择活动相机")
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
            self.report({"WARNING"}, _T("无法选中场景相机"))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{_T('已选中场景相机')} '{cam.name}'")
        return {"FINISHED"}
