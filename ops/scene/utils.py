import bpy

class SCENE_OT_SwitchUnit(bpy.types.Operator):
    bl_idname = "scene.switch_unit"
    bl_label = "切换单位"
    unit_type: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.unit_settings.system = 'METRIC'
        units = {'MM': 'MILLIMETERS', 'CM': 'CENTIMETERS', 'M': 'METERS'}
        context.scene.unit_settings.length_unit = units.get(self.unit_type, 'METERS')
        self.report({"INFO"}, f"已切换单位为 {self.unit_type}")
        return {'FINISHED'}

class SCENE_OT_ResetSizeToolPadding(bpy.types.Operator):
    bl_idname = "scene.reset_size_tool_padding"
    bl_label = "重置"
    bl_description = "将 Padding 重置为插件偏好设置里的默认值"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Use root package name
        root_pkg = ".".join(__package__.split(".")[:3]) if (__package__ or "").startswith("bl_ext") else (__package__ or "").split(".")[0]
        prefs = context.preferences.addons.get(root_pkg).preferences if context.preferences.addons.get(root_pkg) else None
        default_padding = float(getattr(prefs, "default_padding", 0.0)) if prefs else 0.0
        context.scene.m8.size_tool_padding = max(0.0, default_padding)
        self.report({"INFO"}, f"已重置 Padding 为 {default_padding:.2f}")
        return {'FINISHED'}
