import bpy
from mathutils import Vector, Matrix


def bound_to_tuple(obj: bpy.types.Object, matrix: [None | Matrix] = None) -> tuple:
    """
    :param obj:输入一个物体,反回物体的边界框列表
    :type obj:bpy.types.Object
    :param matrix:矩阵
    :type matrix:mathutils.Vector
    :return tuple:
    """
    if matrix:
        return tuple(matrix @ Vector(i[:]) for i in obj.bound_box)
    else:
        return tuple(i[:] for i in obj.bound_box)


def from_vector_get_bound_box(cbb: list[Vector]) -> list[Vector]:
    """获取边界框"""
    xl = [c[0] for c in cbb]
    yl = [c[1] for c in cbb]
    zl = [c[2] for c in cbb]
    max_x, min_x = max(xl), min(xl)
    max_y, min_y = max(yl), min(yl)
    max_z, min_z = max(zl), min(zl)
    return [
        Vector((max_x, min_y, min_z)),
        Vector((max_x, min_y, max_z)),
        Vector((max_x, max_y, max_z)),
        Vector((max_x, max_y, min_z)),
        Vector((min_x, min_y, min_z)),
        Vector((min_x, min_y, max_z)),
        Vector((min_x, max_y, max_z)),
        Vector((min_x, max_y, min_z)),
    ]
