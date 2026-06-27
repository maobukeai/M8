import bpy
from mathutils import Vector


class M8_OT_CameraFocusSelected(bpy.types.Operator):
    bl_idname = "m8.camera_focus_selected"
    bl_label = "对焦到选中"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        cam_obj = context.active_object if getattr(context, "active_object", None) else None
        if not cam_obj or cam_obj.type != "CAMERA":
            cam_obj = getattr(getattr(context, "scene", None), "camera", None)
        
        return bool(cam_obj and cam_obj.type == "CAMERA")

    def execute(self, context):
        # 1. Find Camera
        cam_obj = None
        # Priority 1: Active Object if it is a Camera
        if context.active_object and context.active_object.type == 'CAMERA':
            cam_obj = context.active_object
        
        # Priority 2: Selected Camera
        if not cam_obj:
            cam_obj = next((o for o in context.selected_objects if o.type == 'CAMERA'), None)
            
        # Priority 3: Scene Camera
        if not cam_obj:
            cam_obj = context.scene.camera
            
        if not cam_obj or cam_obj.type != 'CAMERA':
            self.report({"ERROR"}, "未找到相机对象")
            return {"CANCELLED"}

        # 2. Find Target Object
        target = None
        active = context.active_object
        
        # Priority 1: Active Object if it's not the camera itself
        if active and active != cam_obj and active.type != 'CAMERA':
            target = active
        
        # Priority 2: Any other selected object
        if not target:
            for o in context.selected_objects:
                if o != cam_obj and o.type != 'CAMERA':
                    target = o
                    break
        
        if not target:
            self.report({"WARNING"}, "未找到目标物体，请选中除摄像机外的物体")
            return {"CANCELLED"}

        # 3. Perform Focus
        cam = cam_obj.data
        try:
            # Enable Depth of Field
            cam.dof.use_dof = True
            
            # Clear focus object (use distance instead)
            cam.dof.focus_object = None
            
            # Calculate distance
            # Vector from camera to target
            p1 = cam_obj.matrix_world.translation
            p2 = target.matrix_world.translation
            v = p2 - p1
            
            # Camera forward vector (Local -Z)
            # matrix_world.col[2] is the Z axis vector. We need -Z.
            forward = -cam_obj.matrix_world.col[2].to_3d()
            
            # Projected distance along the camera view axis
            dist = v.dot(forward)
            
            # Set focus distance (ensure positive)
            cam.dof.focus_distance = abs(dist)
            
            self.report({"INFO"}, f"已对焦到: {target.name} (距离: {abs(dist):.2f}m)")
            
        except Exception as e:
            self.report({"ERROR"}, f"对焦失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"CANCELLED"}

        return {"FINISHED"}
