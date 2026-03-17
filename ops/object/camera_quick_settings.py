import bpy


class M8_OT_CameraQuickSettings(bpy.types.Operator):
    bl_idname = "m8.camera_quick_settings"
    bl_label = "摄像机快速设置"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "CAMERA" and obj.data)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        cam = context.active_object.data

        layout.use_property_split = True
        layout.use_property_decorate = False

        if hasattr(cam, "type"):
            layout.prop(cam, "type")
        if hasattr(cam, "lens"):
            layout.prop(cam, "lens")
        if hasattr(cam, "sensor_width"):
            layout.prop(cam, "sensor_width")
        if hasattr(cam, "clip_start"):
            layout.prop(cam, "clip_start")
        if hasattr(cam, "clip_end"):
            layout.prop(cam, "clip_end")

        if hasattr(cam, "show_limits"):
            box = layout.box()
            box.label(text="视图显示", icon="RESTRICT_VIEW_OFF")
            col = box.column(align=True)
            col.prop(cam, "show_limits", text="显示范围")
            col.prop(cam, "show_mist", text="显示雾场")
            col.prop(cam, "show_sensor", text="显示传感器")
            col.prop(cam, "show_name", text="显示名称")
            col.prop(cam, "show_composition_center", text="显示中心点")
            
        if hasattr(cam, "dof"):
            box = layout.box()
            box.label(text="景深", icon="CAMERA_DATA")
            dof = cam.dof
            if hasattr(dof, "use_dof"):
                box.prop(dof, "use_dof")
            sub = box.column()
            sub.enabled = bool(getattr(dof, "use_dof", False))
            if hasattr(dof, "focus_distance"):
                sub.prop(dof, "focus_distance")
            if hasattr(dof, "aperture_fstop"):
                sub.prop(dof, "aperture_fstop")

    def execute(self, context):
        return {"FINISHED"}
