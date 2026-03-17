import bpy
from mathutils import Vector


def reprovision_rotate(obj) -> None:
    if obj.type == "EMPTY":
        obj.matrix_world @= obj.matrix_world.to_euler().to_matrix().to_4x4().inverted_safe()
    else:
        x = Vector((1, 0, 0))
        r = obj.matrix_world.to_euler().to_matrix().to_4x4()
        b = r @ x
        bx = b.copy()
        bx.z = 0
        xa = x.angle(bx)
        __rotate__(-xa, "Z")
        bpy.context.view_layer.update()

        rr = obj.matrix_world.to_euler().to_matrix().to_4x4()
        c = rr @ x
        ca = x.angle(c)
        __rotate__(-ca, "Y")
        bpy.context.view_layer.update()

        y = Vector((0, 1, 0))
        rrr = obj.matrix_world.to_euler().to_matrix().to_4x4()
        d = rrr @ y
        ya = y.angle(d)
        __rotate__(ya, "X")
        bpy.context.view_layer.update()


def __rotate__(value, axis='X', orient_type='GLOBAL'):
    bpy.ops.transform.rotate(value=value, orient_axis=axis, orient_type=orient_type,
                             orient_matrix=((1, -0, -0), (-0, 1, -0), (0, -0, 1)), orient_matrix_type='VIEW',
                             mirror=False, use_proportional_edit=False, proportional_edit_falloff='SMOOTH',
                             proportional_size=1, use_proportional_connected=False, use_proportional_projected=False,
                             snap=False, snap_elements={'INCREMENT'}, use_snap_project=False, snap_target='CLOSEST',
                             use_snap_self=True, use_snap_edit=True, use_snap_nonedit=True, use_snap_selectable=False)


def get_object_subdivision_level(obj) -> int:
    """获取物体的细分级数"""
    levels = 0
    for mod in obj.modifiers:
        if mod.type == "SUBSURF" and mod.show_viewport:
            levels += mod.levels
    return levels
