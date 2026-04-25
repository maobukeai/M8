import re

file_path = r"C:\Users\20269\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\M8\property\preferences.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

def replace_block(old, new):
    global content
    if old in content:
        content = content.replace(old, new)
    else:
        print("COULD NOT FIND:\n" + old)

# 1. Transform Settings
old_transform = '''        if enable_pie:
            row = col.row(align=True)
            if "ui_show_shift_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shift_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_shift_s_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_shift_s_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("m8.reset_prefs_ui", text="", icon="TRASH")
            col.separator()
            # Safe access to ui_show_shift_keymap
            show_keymap = getattr(self, "ui_show_shift_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    kc, km, kmi = _find_pie_keymap_item()
                    if kc and km and kmi:
                        rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                    else:
                        sub_col.label(text=_T("未找到 Shift+S 绑定"), icon="INFO")
                except Exception:
                    pass

            # Safe access to ui_show_shift_s_advanced
            show_advanced = getattr(self, "ui_show_shift_s_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_transform_pie_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_shift_s_conflicts", text=_T("恢复冲突"))
                row = sub_col.row(align=True)
                row.operator("size_tool.force_transform_pie_priority", text=_T("强制置顶"))
                row.operator("size_tool.reset_transform_pie_keymap", text=_T("恢复默认"))'''

new_transform = '''        if enable_pie:
            row = col.row(align=True)
            if "ui_show_shift_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shift_keymap", text="", toggle=True, icon="KEYINGSET")
            if "ui_show_shift_s_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_shift_s_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_transform_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("size_tool.reset_transform_pie_keymap", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            
            # Safe access to ui_show_shift_keymap
            show_keymap = getattr(self, "ui_show_shift_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    kc, km, kmi = _find_pie_keymap_item()
                    if kc and km and kmi:
                        rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                    else:
                        sub_col.label(text=_T("未找到 Shift+S 绑定"), icon="INFO")
                except Exception:
                    pass

            # Safe access to ui_show_shift_s_advanced
            show_advanced = getattr(self, "ui_show_shift_s_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_transform_pie_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_shift_s_conflicts", text=_T("恢复冲突"))'''

replace_block(old_transform, new_transform)


# 2. Switch Mode Settings
old_switch = '''        if getattr(self, "activate_switch_mode", False):
            row = col.row(align=True)
            if "ui_show_tab_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_tab_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_switch_mode_mapping" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_mode_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_switch_mode_priority", text=_T("置顶"), icon=_ICON("SORT_DESC"))
            row.operator("m8.reset_switch_mode_prefs", text=_T("恢复默认"), icon=_ICON("LOOP_BACK"))
            col.separator()'''

new_switch = '''        if getattr(self, "activate_switch_mode", False):
            row = col.row(align=True)
            if "ui_show_tab_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_tab_keymap", text="", toggle=True, icon="KEYINGSET")
            if "ui_show_switch_mode_mapping" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_mode_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_switch_mode_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_switch_mode_prefs", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()'''

replace_block(old_switch, new_switch)


# 3. Delete Settings
old_delete = '''        if self.activate_quick_delete or self.activate_delete_pie:
            row = col.row(align=True)
            row.prop(self, "ui_show_delete_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.prop(self, "ui_show_delete_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            col.separator()'''

new_delete = '''        if self.activate_quick_delete or self.activate_delete_pie:
            row = col.row(align=True)
            row.prop(self, "ui_show_delete_keymap", text="", toggle=True, icon="KEYINGSET")
            row.prop(self, "ui_show_delete_mapping", text=_T("映射"), toggle=True, icon="PREFERENCES")
            col.separator()'''

replace_block(old_delete, new_delete)


# 4. Edge Property Settings
old_edge = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_edge_property_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_edge_property_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_edge_property_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_edge_property_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("m8.reset_prefs_ui", text="", icon="TRASH")
            col.separator()
            # Safe access to ui_show_edge_property_keymap
            show_keymap = getattr(self, "ui_show_edge_property_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    items = _find_edge_property_pie_keymap_items()
                    
                    if not items:
                        sub_col.label(text=_T("未找到 Edge Property 绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in items:
                            row = sub_col.row(align=True)
                            row.label(text=km.name, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass

            # Safe access to ui_show_edge_property_advanced
            show_advanced = getattr(self, "ui_show_edge_property_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_edge_property_pie_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_shift_e_conflicts", text=_T("恢复冲突"))
                row = sub_col.row(align=True)
                row.operator("size_tool.force_edge_property_pie_priority", text=_T("强制置顶"))'''

new_edge = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_edge_property_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_edge_property_keymap", text="", toggle=True, icon="KEYINGSET")
            if "ui_show_edge_property_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_edge_property_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_edge_property_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            # Safe access to ui_show_edge_property_keymap
            show_keymap = getattr(self, "ui_show_edge_property_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    items = _find_edge_property_pie_keymap_items()
                    
                    if not items:
                        sub_col.label(text=_T("未找到 Edge Property 绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in items:
                            row_km = sub_col.row(align=True)
                            row_km.label(text=km.name, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row_km, 0)
                except Exception:
                    pass

            # Safe access to ui_show_edge_property_advanced
            show_advanced = getattr(self, "ui_show_edge_property_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_edge_property_pie_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_shift_e_conflicts", text=_T("恢复冲突"))'''

replace_block(old_edge, new_edge)


# 5. Align Settings
old_align = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_align_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_align_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_align_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_align_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("m8.reset_prefs_ui", text="", icon="TRASH")
            col.separator()
            # Safe access to ui_show_align_keymap
            show_keymap = getattr(self, "ui_show_align_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    align_items = _find_align_pie_keymap_items()
                    
                    if not align_items:
                            sub_col.label(text=_T("未找到对齐相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in align_items:
                            row = sub_col.row(align=True)
                            mode_label = km.name
                            if mode_label == "3D View Generic": mode_label = _T("3D 视图通用")
                            elif mode_label == "Object Mode": mode_label = _T("物体模式")
                            elif mode_label == "Mesh": mode_label = _T("网格编辑")
                            elif mode_label == "UV Editor": mode_label = _T("UV 编辑器")
                            
                            row.label(text=mode_label, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                except Exception:
                    pass
            
            # Safe access to ui_show_align_advanced
            show_advanced = getattr(self, "ui_show_align_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_align_pie_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_alt_a_conflicts", text=_T("恢复冲突"))
                row = sub_col.row(align=True)
                row.operator("size_tool.force_align_pie_priority", text=_T("强制置顶"))'''

new_align = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_align_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_align_keymap", text="", toggle=True, icon="KEYINGSET")
            if "ui_show_align_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_align_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_align_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()
            # Safe access to ui_show_align_keymap
            show_keymap = getattr(self, "ui_show_align_keymap", False)
            if show_keymap:
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    align_items = _find_align_pie_keymap_items()
                    
                    if not align_items:
                            sub_col.label(text=_T("未找到对齐相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in align_items:
                            row_km = sub_col.row(align=True)
                            mode_label = km.name
                            if mode_label == "3D View Generic": mode_label = _T("3D 视图通用")
                            elif mode_label == "Object Mode": mode_label = _T("物体模式")
                            elif mode_label == "Mesh": mode_label = _T("网格编辑")
                            elif mode_label == "UV Editor": mode_label = _T("UV 编辑器")
                            
                            row_km.label(text=mode_label, icon=_ICON("DOT"))
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, row_km, 0)
                except Exception:
                    pass
            
            # Safe access to ui_show_align_advanced
            show_advanced = getattr(self, "ui_show_align_advanced", False)
            if show_advanced:
                sub_col = col.column()
                row_sub = sub_col.row(align=True)
                row_sub.operator("size_tool.exclusive_align_pie_hotkey", text=_T("独占(禁用冲突)"))
                row_sub.operator("size_tool.restore_alt_a_conflicts", text=_T("恢复冲突"))'''

replace_block(old_align, new_align)

# 6. Shading Settings
old_shading = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_shading_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shading_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.operator("m8.reset_prefs_ui", text="", icon="TRASH")
            col.separator()'''

new_shading = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_shading_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_shading_keymap", text="", toggle=True, icon="KEYINGSET")
            col.separator()'''

replace_block(old_shading, new_shading)

# 7. Save Settings
old_save = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_save_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_save_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_save_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_save_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("m8.reset_prefs_ui", text="", icon="TRASH")
            col.separator()'''

new_save = '''        if activate_pie:
            row = col.row(align=True)
            if "ui_show_save_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_save_keymap", text="", toggle=True, icon="KEYINGSET")
            if "ui_show_save_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_save_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_save_pie_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()'''

replace_block(old_save, new_save)
replace_block('''            if self.ui_show_save_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_save_pie_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_ctrl_s_conflicts", text=_T("恢复冲突"))
                row = sub_col.row(align=True)
                row.operator("size_tool.force_save_pie_priority", text=_T("强制置顶"))''',
'''            if self.ui_show_save_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_save_pie_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_ctrl_s_conflicts", text=_T("恢复冲突"))''')

# 8. Mirror Settings
old_mirror = '''        if activate_mirror:
            row = col.row(align=True)
            if "ui_show_mirror_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_mirror_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_mirror_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_mirror_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("m8.reset_prefs_ui", text="", icon="TRASH")
            col.separator()'''

new_mirror = '''        if activate_mirror:
            row = col.row(align=True)
            if "ui_show_mirror_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_mirror_keymap", text="", toggle=True, icon="KEYINGSET")
            if "ui_show_mirror_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_mirror_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_mirror_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()'''

replace_block(old_mirror, new_mirror)
replace_block('''            if self.ui_show_mirror_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_mirror_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_shift_alt_x_conflicts", text=_T("恢复冲突"))
                row = sub_col.row(align=True)
                row.operator("size_tool.force_mirror_priority", text=_T("强制置顶"))''',
'''            if self.ui_show_mirror_advanced:
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_mirror_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_shift_alt_x_conflicts", text=_T("恢复冲突"))''')


# 9. Group Settings
old_group = '''        if getattr(self, "activate_group_tool", False):
            row = col.row(align=True)
            if "ui_show_group_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_group_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            if "ui_show_group_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_group_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("m8.reset_prefs_ui", text="", icon="TRASH")
            col.separator()'''

new_group = '''        if getattr(self, "activate_group_tool", False):
            row = col.row(align=True)
            if "ui_show_group_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_group_keymap", text="", toggle=True, icon="KEYINGSET")
            if "ui_show_group_advanced" in self.bl_rna.properties:
                row.prop(self, "ui_show_group_advanced", text=_T("高级"), toggle=True, icon="PREFERENCES")
            row.operator("size_tool.force_group_tool_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()'''

replace_block(old_group, new_group)
replace_block('''            if getattr(self, "ui_show_group_advanced", False):
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_group_tool_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_ctrl_g_conflicts", text=_T("恢复冲突"))
                row = sub_col.row(align=True)
                row.operator("size_tool.force_group_tool_priority", text=_T("强制置顶"))''',
'''            if getattr(self, "ui_show_group_advanced", False):
                sub_col = col.column()
                row = sub_col.row(align=True)
                row.operator("size_tool.exclusive_group_tool_hotkey", text=_T("独占(禁用冲突)"))
                row.operator("size_tool.restore_ctrl_g_conflicts", text=_T("恢复冲突"))''')

# 10. Smart Pie Settings
old_smart_pie = '''        if self.activate_smart_pie:
            row = col.row(align=True)
            row.prop(self, "ui_show_smart_pie_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            col.separator()'''

new_smart_pie = '''        if self.activate_smart_pie:
            row = col.row(align=True)
            row.prop(self, "ui_show_smart_pie_keymap", text="", toggle=True, icon="KEYINGSET")
            col.separator()'''

replace_block(old_smart_pie, new_smart_pie)

# 11. Toggle Area Settings
old_toggle_area = '''        if self.activate_toggle_area:
            row = col.row(align=True)
            row.prop(self, "ui_show_toggle_area_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            col.separator()'''

new_toggle_area = '''        if self.activate_toggle_area:
            row = col.row(align=True)
            row.prop(self, "ui_show_toggle_area_keymap", text="", toggle=True, icon="KEYINGSET")
            col.separator()'''

replace_block(old_toggle_area, new_toggle_area)

# 12. Switch Editor Settings
old_switch_editor = '''        if getattr(self, "activate_switch_editor_pie", False):
            row = col.row(align=True)
            if "ui_show_switch_editor_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_editor_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            col.separator()'''

new_switch_editor = '''        if getattr(self, "activate_switch_editor_pie", False):
            row = col.row(align=True)
            if "ui_show_switch_editor_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_switch_editor_keymap", text="", toggle=True, icon="KEYINGSET")
            col.separator()'''

replace_block(old_switch_editor, new_switch_editor)


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Applied modifications")
