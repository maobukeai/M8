import bpy

class OBJECT_OT_SwitchUnit(bpy.types.Operator):
    bl_idname = "scene.switch_unit"
    bl_label = "切换单位"
    unit_type: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.unit_settings.system = 'METRIC'
        units = {'MM': 'MILLIMETERS', 'CM': 'CENTIMETERS', 'M': 'METERS'}
        context.scene.unit_settings.length_unit = units.get(self.unit_type, 'METERS')
        return {'FINISHED'}

class SCENE_OT_ResetSizeToolPadding(bpy.types.Operator):
    bl_idname = "scene.reset_size_tool_padding"
    bl_label = "重置"
    bl_description = "将 Padding 重置为插件偏好设置里的默认值"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Use root package name
        root_pkg = (__package__ or "").split(".")[0]
        prefs = context.preferences.addons.get(root_pkg).preferences if context.preferences.addons.get(root_pkg) else None
        default_padding = float(getattr(prefs, "default_padding", 0.0)) if prefs else 0.0
        context.scene.size_tool_padding = max(0.0, default_padding)
        return {'FINISHED'}
