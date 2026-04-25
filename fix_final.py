import re

file_path = r'C:\Users\20269\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\M8\property\preferences.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# ============================================================
# 1. Add 5 missing BoolProperty declarations
# ============================================================
# Insert after ui_show_group_advanced line
old_props = '    ui_show_group_advanced: bpy.props.BoolProperty(name="显示高级(Group)", default=False)'
new_props = '''    ui_show_group_advanced: bpy.props.BoolProperty(name="显示高级(Group)", default=False)

    # --- Additional UI toggle properties ---
    ui_show_shading_advanced: bpy.props.BoolProperty(name="高级(Shading)", default=False)
    ui_show_smart_pie_advanced: bpy.props.BoolProperty(name="高级(SmartPie)", default=False)
    ui_show_toggle_area_advanced: bpy.props.BoolProperty(name="高级(ToggleArea)", default=False)
    ui_show_switch_editor_advanced: bpy.props.BoolProperty(name="映射(SwitchEditor)", default=False)
    ui_show_rename_keymap: bpy.props.BoolProperty(name="快捷键(Rename)", default=False)'''

if 'ui_show_shading_advanced: bpy.props.BoolProperty' not in content:
    content = content.replace(old_props, new_props)
    print("[OK] Added 5 missing BoolProperty declarations")
else:
    print("[SKIP] BoolProperty declarations already exist")

# ============================================================
# 2. Rewrite draw_rename_settings to match standard layout
# ============================================================
old_rename = '''    def draw_rename_settings(self, layout):
        col = layout.column()
        row = col.row(align=True)
        row.prop(self, "activate_advanced_rename", text=_T("启用高级重命名 (F2)"))
        
        sub_col = col.column()
        try:
            import rna_keymap_ui
            rename_items = _find_rename_keymap_items()
            
            if not rename_items:
                    sub_col.label(text=_T("未找到重命名相关绑定"), icon="INFO")
            else:
                for kc, km, kmi in rename_items:
                    rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
        except Exception:
            pass'''

new_rename = '''    def draw_rename_settings(self, layout):
        col = layout.column()
        col.prop(self, "activate_advanced_rename", text=_T("启用高级重命名 (F2)"))

        if getattr(self, "activate_advanced_rename", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            if "ui_show_rename_keymap" in self.bl_rna.properties:
                row.prop(self, "ui_show_rename_keymap", text=_T("快捷键"), toggle=True, icon="KEYINGSET")
            row.operator("size_tool.force_rename_priority", text=_T("置顶"), icon="SORT_ASC")
            row.operator("m8.reset_prefs_ui", text=_T("恢复默认"), icon="LOOP_BACK")
            col.separator()

            if getattr(self, "ui_show_rename_keymap", False):
                sub_col = col.column()
                try:
                    import rna_keymap_ui
                    rename_items = _find_rename_keymap_items()
                    
                    if not rename_items:
                            sub_col.label(text=_T("未找到重命名相关绑定"), icon="INFO")
                    else:
                        for kc, km, kmi in rename_items:
                            rna_keymap_ui.draw_kmi([], kc, km, kmi, sub_col, 0)
                except Exception:
                    pass'''

if old_rename in content:
    content = content.replace(old_rename, new_rename)
    print("[OK] Rewrote draw_rename_settings")
else:
    print("[WARN] draw_rename_settings old block not found")

# ============================================================
# 3. Clean up switch_editor pass placeholder
# ============================================================
old_pass = '''            if getattr(self, "ui_show_switch_editor_advanced", False):
                # Switch editor already had mapping settings below, let's just make it visible under advanced toggle
                pass # The mappings below will just follow. Actually we need to wrap the mapping block

            if getattr(self, "ui_show_switch_editor_keymap", False):'''

new_pass = '''            if getattr(self, "ui_show_switch_editor_keymap", False):'''

if old_pass in content:
    content = content.replace(old_pass, new_pass)
    print("[OK] Cleaned up switch_editor pass placeholder")
else:
    print("[WARN] switch_editor pass block not found")

# ============================================================
# 4. Add ForceRenamePriority operator
# ============================================================
rename_op = '''
class SIZE_TOOL_OT_ForceRenamePriority(bpy.types.Operator):
    bl_idname = "size_tool.force_rename_priority"
    bl_label = "强制置顶快捷键(F2)"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        items = _find_rename_keymap_items()
        if not items:
            self.report({'WARNING'}, "未找到 F2 绑定")
            return {'CANCELLED'}
        for _, km, kmi in items:
            _ensure_pie_keymap_priority(km, kmi)
        self.report({'INFO'}, f"已置顶 {len(items)} 个 F2 绑定")
        return {'FINISHED'}

'''

if 'force_rename_priority' not in content:
    # Insert before the classes tuple
    content = content.replace("\nclasses = (", rename_op + "classes = (")
    print("[OK] Added ForceRenamePriority operator")
else:
    print("[SKIP] ForceRenamePriority already exists")

# Register the new operator in classes tuple
if 'SIZE_TOOL_OT_ForceRenamePriority,' not in content:
    content = content.replace(
        '    SIZE_TOOL_OT_ForceDeletePiePriority,',
        '    SIZE_TOOL_OT_ForceDeletePiePriority,\n    SIZE_TOOL_OT_ForceRenamePriority,'
    )
    print("[OK] Registered ForceRenamePriority in classes")
else:
    print("[SKIP] ForceRenamePriority already registered")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n=== All fixes applied ===")
