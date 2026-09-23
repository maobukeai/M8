import os
import ast
import re
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

chinese_char = re.compile(r'[\u4e00-\u9fff]')

print("==================================================")
print("  M8 AUDIT 1: CHECKING FOR _T(f'...') DYNAMIC F-STRINGS")
print("==================================================")

class DynamicTVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.dynamic_t = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "_T":
            if node.args:
                arg = node.args[0]
                if isinstance(arg, ast.JoinedStr):  # f-string
                    self.dynamic_t.append((node.lineno, "f-string inside _T()"))
                elif isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):  # "%" formatting inside _T
                    self.dynamic_t.append((node.lineno, "% formatting inside _T()"))
                elif isinstance(arg, ast.Call) and getattr(arg.func, "attr", None) == "format":
                    self.dynamic_t.append((node.lineno, ".format() inside _T()"))
        self.generic_visit(node)

dynamic_t_issues = []
for root, dirs, files in os.walk(BASE_DIR):
    if any(ignore in root for ignore in [".git", "__pycache__", "dev", ".mission", "build", "dist"]):
        continue
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            relpath = os.path.relpath(filepath, BASE_DIR)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            try:
                tree = ast.parse(source, filename=filepath)
                v = DynamicTVisitor(relpath)
                v.visit(tree)
                for lineno, desc in v.dynamic_t:
                    dynamic_t_issues.append((relpath, lineno, desc))
            except Exception:
                pass

print(f"Dynamic _T() calls found: {len(dynamic_t_issues)}")
for path, lineno, desc in dynamic_t_issues:
    print(f"  {path}:{lineno} -> {desc}")

print("\n==================================================")
print("  M8 AUDIT 2: CHECKING FOR RAW CHINESE IN UI CALLS")
print("==================================================")

class RawChineseUIVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.raw_chinese_calls = []

    def visit_Call(self, node):
        # 1. self.report({'...'}, "Chinese")
        if isinstance(node.func, ast.Attribute) and node.func.attr == "report":
            if len(node.args) >= 2:
                arg2 = node.args[1]
                if isinstance(arg2, ast.Constant) and isinstance(arg2.value, str) and chinese_char.search(arg2.value):
                    self.raw_chinese_calls.append((node.lineno, "report", arg2.value))
                elif isinstance(arg2, ast.JoinedStr):
                    for part in arg2.values:
                        if isinstance(part, ast.Constant) and isinstance(part.value, str) and chinese_char.search(part.value):
                            self.raw_chinese_calls.append((node.lineno, "report(f-string)", f"report f-string contains raw Chinese: {repr(part.value)}"))
                            break

        # 2. layout.label, layout.operator, layout.prop, layout.menu text="Chinese"
        for kw in node.keywords:
            if kw.arg in ("text", "title"):
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str) and chinese_char.search(kw.value.value):
                    self.raw_chinese_calls.append((node.lineno, f"kwarg {kw.arg}", kw.value.value))
                elif isinstance(kw.value, ast.JoinedStr):
                    for part in kw.value.values:
                        if isinstance(part, ast.Constant) and isinstance(part.value, str) and chinese_char.search(part.value):
                            self.raw_chinese_calls.append((node.lineno, f"kwarg {kw.arg}(f-string)", f"kwarg {kw.arg} contains raw Chinese: {repr(part.value)}"))
                            break

        self.generic_visit(node)

raw_chinese_issues = []
for root, dirs, files in os.walk(BASE_DIR):
    if any(ignore in root for ignore in [".git", "__pycache__", "dev", ".mission", "build", "dist"]):
        continue
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            relpath = os.path.relpath(filepath, BASE_DIR)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            try:
                tree = ast.parse(source, filename=filepath)
                v = RawChineseUIVisitor(relpath)
                v.visit(tree)
                for lineno, call_type, val in v.raw_chinese_calls:
                    raw_chinese_issues.append((relpath, lineno, call_type, val))
            except Exception:
                pass

print(f"Raw Chinese in UI/report calls: {len(raw_chinese_issues)}")
for path, lineno, call_type, val in raw_chinese_issues:
    print(f"  {path}:{lineno} [{call_type}] -> {repr(val)}")

print("\n==================================================")
print("  M8 AUDIT 3: SCANNING ALL .prop() WITHOUT text=")
print("==================================================")

# Check all prop definitions: target: bpy.props.XxxProperty(...)
all_prop_names_with_chinese = {}

class PropDefVisitor(ast.NodeVisitor):
    def visit_Assign(self, node):
        self.check_prop_call(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        call_node = node.value if node.value else node.annotation
        self.check_prop_call([node.target], call_node)
        self.generic_visit(node)

    def check_prop_call(self, targets, call_node):
        if not call_node or not isinstance(call_node, ast.Call):
            return
        func = call_node.func
        is_prop = False
        if isinstance(func, ast.Attribute) and "Property" in func.attr:
            is_prop = True
        elif isinstance(func, ast.Name) and "Property" in func.id:
            is_prop = True
        if is_prop:
            name_val = None
            for kw in call_node.keywords:
                if kw.arg == "name":
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        name_val = kw.value.value
                    elif isinstance(kw.value, ast.Call) and getattr(kw.value.func, "id", "") == "_T":
                        if kw.value.args and isinstance(kw.value.args[0], ast.Constant):
                            name_val = kw.value.args[0].value
            if name_val and chinese_char.search(name_val):
                for t in targets:
                    if isinstance(t, ast.Name):
                        all_prop_names_with_chinese[t.id] = name_val

for root, dirs, files in os.walk(BASE_DIR):
    if any(ignore in root for ignore in [".git", "__pycache__", "dev", ".mission", "build", "dist"]):
        continue
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            try:
                tree = ast.parse(source, filename=filepath)
                PropDefVisitor().visit(tree)
            except Exception:
                pass

print(f"Total RNA properties with Chinese default names registered: {len(all_prop_names_with_chinese)}")

# Now find where layout.prop(target, "prop_name") is called WITHOUT text=
class PropCallVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.missing_text_props = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "prop":
            # Check args: arg[0] is target, arg[1] is prop_name
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                p_name = node.args[1].value
                if p_name in all_prop_names_with_chinese:
                    # Check if text= is specified in keywords
                    has_text = any(kw.arg == "text" for kw in node.keywords)
                    # Check if expand=True (radio buttons where each item has its own text)
                    is_expand = any(kw.arg == "expand" and getattr(kw.value, "value", None) is True for kw in node.keywords)
                    if not has_text and not is_expand:
                        self.missing_text_props.append((node.lineno, p_name, all_prop_names_with_chinese[p_name]))
        self.generic_visit(node)

missing_prop_draws = []
for root, dirs, files in os.walk(BASE_DIR):
    if any(ignore in root for ignore in [".git", "__pycache__", "dev", ".mission", "build", "dist"]):
        continue
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            relpath = os.path.relpath(filepath, BASE_DIR)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            try:
                tree = ast.parse(source, filename=filepath)
                v = PropCallVisitor(relpath)
                v.visit(tree)
                for lineno, p_name, ch_label in v.missing_text_props:
                    missing_prop_draws.append((relpath, lineno, p_name, ch_label))
            except Exception:
                pass

print(f"Total .prop() calls displaying Chinese without text=: {len(missing_prop_draws)}")
for path, lineno, p_name, ch_label in missing_prop_draws:
    print(f"  {path}:{lineno} -> prop: '{p_name}', Chinese label: '{ch_label}'")
