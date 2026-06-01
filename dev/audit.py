import re

file_path = r'C:\Users\20269\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\M8\property\preferences.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract each draw function and audit its toolbar pattern
draw_funcs = [
    'draw_transform_settings',
    'draw_switch_mode_settings',
    'draw_delete_settings',
    'draw_edge_property_settings',
    'draw_align_settings',
    'draw_shading_settings',
    'draw_save_settings',
    'draw_rename_settings',
    'draw_mirror_settings',
    'draw_group_settings',
    'draw_smart_pie_settings',
    'draw_toggle_area_settings',
    'draw_switch_editor_settings',
]

# Standard pattern checks
checks = {
    'use_property_split = False': 'row.use_property_split = False',
    'use_property_decorate = False': 'row.use_property_decorate = False',
    'toggle=True, icon="KEYINGSET"': 'toggle=True, icon="KEYINGSET"',
    'toggle=True, icon="PREFERENCES"': 'toggle=True, icon="PREFERENCES"',
    '"置顶"': '_T("置顶")',
    '"恢复默认"': '_T("恢复默认")',
    'icon="SORT_ASC"': 'icon="SORT_ASC"',
    'icon="LOOP_BACK"': 'icon="LOOP_BACK"',
    'col.separator()': 'col.separator()',
}

for func_name in draw_funcs:
    # Extract function body
    pattern = r'def ' + func_name + r'\(self, layout\):.*?(?=\n    def |\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print(f"[MISSING] {func_name} - function not found!")
        continue
    
    body = match.group(0)
    missing = []
    for label, pattern_str in checks.items():
        if pattern_str not in body:
            missing.append(label)
    
    if missing:
        print(f"[ISSUE] {func_name}:")
        for m in missing:
            print(f"    - Missing: {m}")
    else:
        print(f"[OK] {func_name}")

print("\n--- Property declaration check ---")
ui_props_used = set(re.findall(r'ui_show_([a-z_]+)', content))
ui_props_declared = set()
for m in re.finditer(r'(ui_show_[a-z_]+):\s*bpy\.props\.BoolProperty', content):
    ui_props_declared.add(m.group(1).replace('ui_show_', ''))

# Check for properties used in draw funcs but not declared
for func_name in draw_funcs:
    pattern = r'def ' + func_name + r'\(self, layout\):.*?(?=\n    def |\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        continue
    body = match.group(0)
    used_in_func = re.findall(r'"(ui_show_[a-z_]+)"', body)
    for prop in used_in_func:
        # Check if this property is declared
        decl_pattern = prop + r':\s*bpy\.props\.BoolProperty'
        if not re.search(decl_pattern, content):
            print(f"[UNDECLARED] {prop} used in {func_name} but never declared!")

print("\n--- Operator existence check ---")
ops_used = set(re.findall(r'row\.operator\("(size_tool\.force_[^"]+)"', content))
for op in sorted(ops_used):
    bl_pattern = f'bl_idname = "{op}"'
    if bl_pattern not in content:
        print(f"[MISSING OP] {op} - used in UI but no class defined!")
    else:
        print(f"[OK] {op}")

print("\n--- Classes tuple registration check ---")
op_classes = set(re.findall(r'class (SIZE_TOOL_OT_Force\w+)\(', content))
registered = set(re.findall(r'(SIZE_TOOL_OT_Force\w+),', content))
for cls in sorted(op_classes):
    if cls in registered:
        print(f"[OK] {cls} registered")
    else:
        print(f"[NOT REGISTERED] {cls}")
