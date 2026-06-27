import bpy


class M8_OT_LightQuickSettings(bpy.types.Operator):
    bl_idname = "m8.light_quick_settings"
    bl_label = "灯光快速设置"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "LIGHT" and obj.data)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        light = obj.data

        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(light, "type")
        if hasattr(light, "color"):
            layout.prop(light, "color")
        if hasattr(light, "energy"):
            layout.prop(light, "energy")

        if getattr(light, "type", "") == "POINT":
            if hasattr(light, "shadow_soft_size"):
                layout.prop(light, "shadow_soft_size", text="半径")
        elif getattr(light, "type", "") == "SUN":
            if hasattr(light, "angle"):
                layout.prop(light, "angle")
        elif getattr(light, "type", "") == "SPOT":
            if hasattr(light, "spot_size"):
                layout.prop(light, "spot_size")
            if hasattr(light, "spot_blend"):
                layout.prop(light, "spot_blend")
            if hasattr(light, "shadow_soft_size"):
                layout.prop(light, "shadow_soft_size")
        elif getattr(light, "type", "") == "AREA":
            if hasattr(light, "shape"):
                layout.prop(light, "shape")
            if hasattr(light, "size"):
                layout.prop(light, "size")
            if hasattr(light, "size_y") and getattr(light, "shape", "") in {"RECTANGLE", "ELLIPSE"}:
                layout.prop(light, "size_y")

        if hasattr(light, "use_shadow"):
            layout.prop(light, "use_shadow", text="投影")

    def execute(self, context):
        return {"FINISHED"}
