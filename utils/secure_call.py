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


__shield_hazard_type__ = {'Del',
                          'Import',
                          'Lambda',
                          'Return',
                          'Global',
                          'Assert',
                          'ClassDef',
                          'ImportFrom',
                          'Call',
                          #   'Module',
                          #   'Expr',
                          #   'Call',
                          }


def __check_shield__(eval_string):
    dump_data = ast.dump(ast.parse(eval_string), indent=2)
    is_shield = {i for i in __shield_hazard_type__ if i in dump_data}
    if is_shield:
        e = Exception(f'input poll_string is invalid\t{is_shield} of {eval_string}')
        print(e)
        return e
    return None


def secure_call_eval(eval_string: str):
    if __check_shield__(eval_string) is None:
        return eval(eval_string, __secure_call_globals__, __secure_call_args__())


def secure_call_exec(eval_string: str):
    if __check_shield__(eval_string) is None:
        return exec(eval_string, __secure_call_globals__, __secure_call_args__())
