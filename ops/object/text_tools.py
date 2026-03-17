import bpy


class M8_OT_TextQuickSettings(bpy.types.Operator):
    bl_idname = "m8.text_quick_settings"
    bl_label = "文字快速设置"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "FONT" and obj.data)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        data = obj.data

        layout.use_property_split = True
        layout.use_property_decorate = False

        if hasattr(data, "body"):
            row = layout.row()
            row.prop(data, "body", text="文本")

        box = layout.box()
        box.label(text="排版", icon="ALIGN_CENTER")
        box.use_property_split = True
        box.use_property_decorate = False
        if hasattr(data, "align_x"):
            box.prop(data, "align_x")
        if hasattr(data, "align_y"):
            box.prop(data, "align_y")
        if hasattr(data, "space_character"):
            box.prop(data, "space_character")
        if hasattr(data, "space_word"):
            box.prop(data, "space_word")
        if hasattr(data, "space_line"):
            box.prop(data, "space_line")

        box = layout.box()
        box.label(text="尺寸/几何", icon="MOD_SOLIDIFY")
        box.use_property_split = True
        box.use_property_decorate = False
        if hasattr(data, "size"):
            box.prop(data, "size")
        if hasattr(data, "extrude"):
            box.prop(data, "extrude")
        if hasattr(data, "bevel_depth"):
            box.prop(data, "bevel_depth")
        if hasattr(data, "bevel_resolution"):
            box.prop(data, "bevel_resolution")

    def execute(self, context):
        return {"FINISHED"}
