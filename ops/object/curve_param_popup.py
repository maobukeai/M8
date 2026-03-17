import bpy


class M8_OT_CurveParamPopup(bpy.types.Operator):
    bl_idname = "m8.curve_param_popup"
    bl_label = "曲线参数"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type in {"CURVE", "FONT", "SURFACE"} and obj.data)

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=320)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        data = obj.data if obj else None
        if not data:
            return

        layout.use_property_split = True
        layout.use_property_decorate = False

        box = layout.box()
        box.label(text=obj.type, icon="CURVE_DATA" if obj.type == "CURVE" else "FONT_DATA" if obj.type == "FONT" else "SURFACE_DATA")
        box.use_property_split = True
        box.use_property_decorate = False

        if hasattr(data, "fill_mode"):
            box.prop(data, "fill_mode")
        if hasattr(data, "use_fill_caps"):
            box.prop(data, "use_fill_caps")

        box = layout.box()
        box.label(text="挤出/倒角", icon="MOD_SOLIDIFY")
        box.use_property_split = True
        box.use_property_decorate = False

        if hasattr(data, "extrude"):
            box.prop(data, "extrude")
        if hasattr(data, "bevel_depth"):
            box.prop(data, "bevel_depth")
        if hasattr(data, "bevel_resolution"):
            box.prop(data, "bevel_resolution")
        if hasattr(data, "offset"):
            box.prop(data, "offset")

    def execute(self, context):
        return {"FINISHED"}
