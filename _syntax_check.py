import py_compile
import os
import sys

root = r'c:\Users\20269\AppData\Roaming\Blender Foundation\Blender\5.2\scripts\addons\M8'
errors = []
total = 0

for dirpath, _, filenames in os.walk(root):
    for filename in filenames:
        if not filename.endswith('.py'):
            continue
        total += 1
        filepath = os.path.join(dirpath, filename)
        try:
            py_compile.compile(filepath, doraise=True)
        except py_compile.PyCompileError as e:
            rel = os.path.relpath(filepath, root)
            errors.append(f"{rel}: {e}")

print(f"Checked {total} .py files")
if errors:
    print(f"Found {len(errors)} error(s):")
    for err in errors:
        print(f"  - {err}")
else:
    print("All files compile successfully!")
