import os
import re

def replace_in_file(filepath, pattern, replacement):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = re.sub(pattern, replacement, content)
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {filepath}')

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            replace_in_file(path, r'getattr\(context\.scene, "size_tool_padding"', 'getattr(context.scene.m8, "size_tool_padding"')
            replace_in_file(path, r"hasattr\(context\.scene, ['\"]m8_clean_props['\"]\)", 'hasattr(context.scene, "m8")')
            replace_in_file(path, r"hasattr\(context\.scene, ['\"]m8_custom_tools['\"]\)", 'hasattr(context.scene, "m8")')
            replace_in_file(path, r'getattr\(wm, "m8_last_curve_handle_type"', 'getattr(wm.m8, "last_curve_handle_type"')
            replace_in_file(path, r'getattr\(wm, "m8_last_curve_edit_action"', 'getattr(wm.m8, "last_curve_edit_action"')
            replace_in_file(path, r'context\.window_manager\.m8_last_curve', 'context.window_manager.m8.last_curve')
