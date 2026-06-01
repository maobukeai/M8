import os
import re

file_path = r'C:\Users\20269\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\M8\property\preferences.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add properties to SIZE_TOOL_Preferences
props_to_add = """
    ui_show_shading_advanced: bpy.props.BoolProperty(name="高级", default=False)
    ui_show_smart_pie_advanced: bpy.props.BoolProperty(name="高级", default=False)
    ui_show_toggle_area_advanced: bpy.props.BoolProperty(name="高级", default=False)
    ui_show_switch_editor_advanced: bpy.props.BoolProperty(name="高级", default=False)
    ui_show_delete_advanced: bpy.props.BoolProperty(name="高级", default=False)
"""

if 'ui_show_shading_advanced: bpy.props.BoolProperty' not in content:
    # Find a good place to insert, like after ui_show_shading_keymap
    content = content.replace('ui_show_shading_keymap: bpy.props.BoolProperty(name="快捷键", default=False)',
                              'ui_show_shading_keymap: bpy.props.BoolProperty(name="快捷键", default=False)' + props_to_add)

# 2. Update the draw methods
# Shading
old_shading = '''        if activate_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_shading_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shading_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            col.separator()'''
new_shading = '''        if activate_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_shading_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shading_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_shading_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_shading_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_shading_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            if getattr(self, "ui_show_shading_advanced", False):
                sub_col = col.column()
                sub_col.label(text=_T("该模块暂无内置的快捷键冲突配置"), icon="INFO")'''
content = content.replace(old_shading, new_shading)

# Smart Pie
old_smart_pie = '''        if self.activate_smart_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_smart_pie_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            col.separator()'''
new_smart_pie = '''        if self.activate_smart_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_smart_pie_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_smart_pie_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_smart_pie_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_smart_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            if getattr(self, "ui_show_smart_pie_advanced", False):
                sub_col = col.column()
                sub_col.label(text=_T("该模块暂无内置的快捷键冲突配置"), icon="INFO")'''
content = content.replace(old_smart_pie, new_smart_pie)

# Toggle Area
old_toggle_area = '''        if self.activate_toggle_area:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_toggle_area_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            col.separator()'''
new_toggle_area = '''        if self.activate_toggle_area:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_toggle_area_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_toggle_area_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_toggle_area_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_toggle_area_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            if getattr(self, "ui_show_toggle_area_advanced", False):
                sub_col = col.column()
                sub_col.label(text=_T("该模块暂无内置的快捷键冲突配置"), icon="INFO")'''
content = content.replace(old_toggle_area, new_toggle_area)

# Switch Editor
old_switch_editor = '''        if getattr(self, "activate_switch_editor_pie", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_switch_editor_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_editor_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            col.separator()'''
new_switch_editor = '''        if getattr(self, "activate_switch_editor_pie", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_switch_editor_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_editor_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_switch_editor_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_editor_advanced", text=_T("映射"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_switch_editor_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            
            if getattr(self, "ui_show_switch_editor_advanced", False):
                # Switch editor already had mapping settings below, let's just make it visible under advanced toggle
                pass # The mappings below will just follow. Actually we need to wrap the mapping block
'''
# I will not wrap the mapping block for switch_editor just to be safe. It just means the button does nothing for now but adds UI consistency, wait, actually I can just leave the mapping box as is, and the `映射` button is a dummy or controls the mapping box.
# Let's wrap the mapping box in switch_editor.
content = content.replace(old_switch_editor, new_switch_editor)
content = content.replace('''            box = col.box()
            box.label(text="映射", icon="KEYINGSET")''', '''            if getattr(self, "ui_show_switch_editor_advanced", False):
                box = col.box()
                box.label(text="映射", icon="KEYINGSET")''')

# Fix indentation for switch editor mappings
import re
def indent_lines(match):
    lines = match.group(0).split('\\n')
    return '\\n'.join(['    ' + line if line.strip() else line for line in lines])

content = re.sub(r'                box = col\.box\(\)\n                box\.label\(text="映射", icon="KEYINGSET"\)\n.*?(?=\n    def draw_switch_mode_settings)', lambda m: '                box = col.box()\n                box.label(text="映射", icon="KEYINGSET")\n' + '\n'.join(['    ' + l if not l.startswith('    def') else l for l in m.group(0).split('\n')[2:]]), content, flags=re.DOTALL)


# Delete
old_delete = '''        if self.activate_quick_delete or self.activate_delete_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_delete_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.prop(self, "ui_show_delete_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            col.separator()'''
new_delete = '''        if self.activate_quick_delete or self.activate_delete_pie:
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            row.prop(self, "ui_show_delete_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.prop(self, "ui_show_delete_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_delete_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()'''
content = content.replace(old_delete, new_delete)


# 3. Add Operator Classes
ops_to_add = """
class SIZE_TOOL_OT_ForceShadingPiePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_shading_pie_priority"
    bl_label = "强制置顶快捷键(Z)"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        items = _find_shading_pie_keymap_items()
        for _, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceSmartPiePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_smart_pie_priority"
    bl_label = "强制置顶快捷键(1)"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        items = _find_smart_pie_keymap_items()
        for _, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceToggleAreaPriority(bpy.types.Operator):
    bl_idname = "size_tool.force_toggle_area_priority"
    bl_label = "强制置顶快捷键(T)"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        items = _find_toggle_area_keymap_items()
        for kc, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceSwitchEditorPriority(bpy.types.Operator):
    bl_idname = "size_tool.force_switch_editor_priority"
    bl_label = "强制置顶快捷键(F12)"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        items = _find_switch_editor_pie_keymap_items()
        for _, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

class SIZE_TOOL_OT_ForceDeletePiePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_delete_pie_priority"
    bl_label = "强制置顶快捷键(X/Del)"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        items = _find_delete_pie_keymap_items() + _find_quick_delete_keymap_items()
        for _, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        return {'FINISHED'}

"""

# Insert before registration
content = content.replace("classes = (", ops_to_add + "\nclasses = (")

# Add to classes tuple
content = content.replace("    SIZE_TOOL_OT_ForceTransformPiePriority,",
                          "    SIZE_TOOL_OT_ForceTransformPiePriority,\n    SIZE_TOOL_OT_ForceShadingPiePriority,\n    SIZE_TOOL_OT_ForceSmartPiePriority,\n    SIZE_TOOL_OT_ForceToggleAreaPriority,\n    SIZE_TOOL_OT_ForceSwitchEditorPriority,\n    SIZE_TOOL_OT_ForceDeletePiePriority,")


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Added missing UI and operators")
