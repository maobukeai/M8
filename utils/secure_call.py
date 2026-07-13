import ast

import bpy


def __check_addon_is_enabled__(addon_name):
    """check addon enable state"""
    return addon_name in bpy.context.preferences.addons


__secure_call_globals__ = {
    "__builtins__": None,
    'len': len,
    'is_enabled_addon': __check_addon_is_enabled__,
    'print': print,
    'dict': dict,
    'list': list,
    'max': max,
    'min': min,
    'getattr': getattr,
    'hasattr': hasattr,
}


def __secure_call_args__():
    """
    Returns:
        _type_: _description_
    """
    c = bpy.context
    ob = getattr(bpy.context, "object", None)
    sel_objs = getattr(bpy.context, "selected_objects", [])
    use_sel_obj = ((not ob) and sel_objs)
    active_object = sel_objs[-1] if use_sel_obj else ob

    return {
        "mode": getattr(c, "mode", ""),
        "active_object_name": getattr(active_object, "name", ""),
        "active_object_type": getattr(active_object, "type", ""),
        "selected_objects_count": len(sel_objs),
        "has_active_object": bool(active_object),
    }


_ALLOWED_AST_NODES = {
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Name, ast.Load, ast.Constant, ast.List, ast.Tuple, ast.Dict,
    ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
}


def _validate_expression(expression):
    tree = ast.parse(expression, mode="eval")
    names = __secure_call_args__()
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_AST_NODES:
            raise ValueError(f"Unsupported expression element: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in names:
            raise ValueError(f"Unknown expression name: {node.id}")
    return tree


def secure_call_eval(eval_string: str):
    tree = _validate_expression(eval_string)
    return eval(compile(tree, "<m8-expression>", "eval"), __secure_call_globals__, __secure_call_args__())


def secure_call_exec(eval_string: str):
    raise RuntimeError("secure_call_exec is disabled; use secure_call_eval with a supported expression")
