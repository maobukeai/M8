import re

file_path = r"C:\Users\20269\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\M8\property\preferences.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Refactor draw_save_settings
old_save = '''            if "auto_pack_resources_on_save" in self.bl_rna.properties:
                col.prop(self, "auto_pack_resources_on_save", text=_T("保存时自动打包资源"))
            if "auto_purge_unused_materials_on_save" in self.bl_rna.properties:
                col.prop(self, "auto_purge_unused_materials_on_save", text=_T("保存时自动清除孤立数据"))
            if "fbx_export_unity_preset" in self.bl_rna.properties:
                col.prop(self, "fbx_export_unity_preset", text=_T("FBX 导出使用 Unity 预设"))
            
            # Safe access to fbx_export_unity_preset
            fbx_preset = getattr(self, "fbx_export_unity_preset", False)
            
            sub = col.column()
            sub.enabled = bool(fbx_preset)
            sub.operator("m8.reset_unity_fbx_preset", text=_T("设为 Unity 标准"), icon="FILE_REFRESH")
            if "unity_fbx_use_blend_dir" in self.bl_rna.properties:
                sub.prop(self, "unity_fbx_use_blend_dir", text=_T("Unity FBX: 使用 .blend 同目录"))
            row = sub.row(align=True)
            row.enabled = not bool(self.unity_fbx_use_blend_dir)
            row.prop(self, "unity_fbx_export_dir", text=_T("Unity FBX: 导出目录"))
            sub.prop(self, "unity_fbx_reveal_after_export", text=_T("Unity FBX: 导出后定位文件"))
            sub.prop(self, "ui_show_unity_fbx_advanced", text=_T("Unity FBX: 高级"))
            if self.ui_show_unity_fbx_advanced:
                sub.prop(self, "unity_fbx_use_selection", text=_T("Unity FBX: 仅导出选择"))
                sub.prop(self, "unity_fbx_global_scale", text=_T("Unity FBX: 全局缩放"))
                sub.prop(self, "unity_fbx_apply_unit_scale", text=_T("Unity FBX: 应用单位"))
                sub.prop(self, "unity_fbx_apply_scale_options", text=_T("Unity FBX: 应用缩放方式"))
                sub.prop(self, "unity_fbx_use_triangles", text=_T("Unity FBX: 三角化"))
                sub.prop(self, "unity_fbx_use_tspace", text=_T("Unity FBX: 导出切线"))
                sub.prop(self, "unity_fbx_bake_anim", text=_T("Unity FBX: 导出动画"))
                sub.prop(self, "unity_fbx_open_folder_after_export", text=_T("Unity FBX: 导出后打开文件夹"))'''

new_save = '''            box_auto = col.box()
            box_auto.label(text=_T("常规自动化"), icon="FILE_BLEND")
            if "auto_pack_resources_on_save" in self.bl_rna.properties:
                box_auto.prop(self, "auto_pack_resources_on_save", text=_T("保存时自动打包资源"))
            if "auto_purge_unused_materials_on_save" in self.bl_rna.properties:
                box_auto.prop(self, "auto_purge_unused_materials_on_save", text=_T("保存时自动清除孤立数据"))
            
            box_fbx = col.box()
            box_fbx.label(text=_T("FBX 导出预设"), icon="EXPORT")
            if "fbx_export_unity_preset" in self.bl_rna.properties:
                box_fbx.prop(self, "fbx_export_unity_preset", text=_T("启用 Unity 标准预设"))
            
            # Safe access to fbx_export_unity_preset
            fbx_preset = getattr(self, "fbx_export_unity_preset", False)
            
            sub = box_fbx.column()
            sub.enabled = bool(fbx_preset)
            sub.operator("m8.reset_unity_fbx_preset", text=_T("重置为 Unity 推荐设置"), icon="FILE_REFRESH")
            if "unity_fbx_use_blend_dir" in self.bl_rna.properties:
                sub.prop(self, "unity_fbx_use_blend_dir", text=_T("使用 .blend 同目录"))
            row = sub.row(align=True)
            row.enabled = not bool(self.unity_fbx_use_blend_dir)
            row.prop(self, "unity_fbx_export_dir", text=_T("导出目录"))
            sub.prop(self, "unity_fbx_reveal_after_export", text=_T("导出后定位文件"))
            
            sub.prop(self, "ui_show_unity_fbx_advanced", text=_T("展开高级选项"), toggle=True, icon="PREFERENCES")
            if self.ui_show_unity_fbx_advanced:
                adv_box = sub.box()
                adv_box.prop(self, "unity_fbx_use_selection", text=_T("仅导出选择"))
                adv_box.prop(self, "unity_fbx_global_scale", text=_T("全局缩放"))
                adv_box.prop(self, "unity_fbx_apply_unit_scale", text=_T("应用单位"))
                adv_box.prop(self, "unity_fbx_apply_scale_options", text=_T("应用缩放方式"))
                adv_box.prop(self, "unity_fbx_use_triangles", text=_T("三角化"))
                adv_box.prop(self, "unity_fbx_use_tspace", text=_T("导出切线"))
                adv_box.prop(self, "unity_fbx_bake_anim", text=_T("导出动画"))
                adv_box.prop(self, "unity_fbx_open_folder_after_export", text=_T("导出后打开文件夹"))'''

content = content.replace(old_save, new_save)

# Refactor draw_group_settings
old_group = '''            col.prop(self, "activate_double_click_select_group", text=_T("双击选择组"))
            col.prop(self, "group_tool_radius", text=_T("组半径"))
            col.prop(self, "group_tool_empty_type", text=_T("空物体类型"))
            col.prop(self, "group_tool_hide_empty", text=_T("隐藏组空物体"))'''

new_group = '''            box_group = col.box()
            box_group.label(text=_T("工具设置"), icon="TOOL_SETTINGS")
            box_group.prop(self, "activate_double_click_select_group", text=_T("双击选择组"))
            box_group.prop(self, "group_tool_radius", text=_T("组半径"))
            box_group.prop(self, "group_tool_empty_type", text=_T("空物体类型"))
            box_group.prop(self, "group_tool_hide_empty", text=_T("隐藏组空物体"))'''

content = content.replace(old_group, new_group)

# Refactor draw_toggle_area_settings
old_toggle = '''            col.separator()
            col.prop(self, "toggle_area_close_range", text=_T("关闭范围 (%)"))
            col.prop(self, "toggle_area_prefer_left_right", text=_T("首选左/右切换"))
            col.prop(self, "toggle_area_wrap_mouse", text=_T("鼠标跟随"))'''

new_toggle = '''            col.separator()
            box_toggle = col.box()
            box_toggle.label(text=_T("交互逻辑"), icon="MOUSE_LMB")
            box_toggle.prop(self, "toggle_area_close_range", text=_T("关闭范围 (%)"))
            box_toggle.prop(self, "toggle_area_prefer_left_right", text=_T("首选左/右切换"))
            box_toggle.prop(self, "toggle_area_wrap_mouse", text=_T("鼠标跟随"))'''

content = content.replace(old_toggle, new_toggle)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
