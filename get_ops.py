import re
with open('property/preferences.py', 'r', encoding='utf-8') as f:
    text = f.read()

def extract_ops(func_name):
    match = re.search(r'def ' + func_name + r'\(.*?(?=def draw_|$)', text, re.DOTALL)
    if not match: return 'Not found'
    block = match.group(0)
    priorities = list(set(re.findall(r'operator\(\"(.*?priority.*?)\"', block)))
    resets = list(set(re.findall(r'operator\(\"(.*?reset.*?)\"', block)))
    return f'{func_name}: Priorities={priorities}, Resets={resets}'

funcs = ['draw_transform_settings', 'draw_switch_mode_settings', 'draw_delete_settings', 'draw_edge_property_settings', 'draw_align_settings', 'draw_shading_settings', 'draw_save_settings', 'draw_mirror_settings', 'draw_group_settings', 'draw_smart_pie_settings', 'draw_toggle_area_settings', 'draw_switch_editor_settings']

for f in funcs:
    print(extract_ops(f))
