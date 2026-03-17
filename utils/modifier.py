import bpy


def move_modifier_to_first(obj: bpy.types.Object, mod: bpy.types.Modifier) -> None:
    """将修改器移动到最前面"""
    index = obj.modifiers.values().index(mod)
    if index != 0:
        obj.modifiers.move(index, 0)


def move_modifier_to_last(obj: bpy.types.Object, mod: bpy.types.Modifier) -> None:
    """将修改器移动到最后面"""
    index = obj.modifiers.values().index(mod)
    if index != len(obj.modifiers) - 1:
        obj.modifiers.move(index, len(obj.modifiers) - 1)
