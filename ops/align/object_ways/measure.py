import bpy
import numpy as np
from mathutils import Vector

from .to_matrix import location_to_matrix


class Measure:
    __object__: bpy.types.Object
    __bound_box__ = []

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"Measure({self.name},{self.dimensions})"

    def __init__(self, obj):
        self.__object__ = obj

        from .to_ground import get_count_bound_box
        lm = location_to_matrix(obj.location)
        self.__bound_box__ = [lm.inverted() @ Vector(v) for v in get_count_bound_box(obj)]

    @property
    def name(self):
        return self.__object__.name

    @property
    def dimensions(self) -> Vector:
        """物体尺寸"""
        return self.max_bound_box_point - self.min_bound_box_point

    @property
    def x(self):
        return self.dimensions.x

    @property
    def y(self):
        return self.dimensions.y

    @property
    def z(self):
        return self.dimensions.z

    @property
    def center_bound_box_point(self) -> Vector:
        """中心"""
        return (self.max_bound_box_point + self.min_bound_box_point) / 2

    @property
    def max_bound_box_point(self) -> Vector:
        return Vector(np.max(self.__bound_box__, axis=0))

    @property
    def min_bound_box_point(self) -> Vector:
        return Vector(np.min(self.__bound_box__, axis=0))

    @property
    def center(self):
        return self.__object__.location + self.center_bound_box_point

    @property
    def max(self) -> Vector:
        return self.__object__.location + self.max_bound_box_point

    @property
    def min(self) -> Vector:
        return self.__object__.location + self.min_bound_box_point


class MeasureObjects:

    def __repr__(self):
        return f"MeasureObjects({[m.name for m in self.__measures__]})"

    def __init__(self, objects):
        self.__measures__ = [Measure(obj) for obj in objects]
        self.__points__ = []

        for m in self.__measures__:
            self.__points__.extend([m.min, m.max])

    def __iter__(self):
        return iter(self.__measures__)

    @property
    def max(self) -> Vector:
        return Vector(np.max(self.__points__, axis=0))

    @property
    def min(self) -> Vector:
        return Vector(np.min(self.__points__, axis=0))

    @property
    def center(self) -> Vector:
        return (self.max + self.min) / 2

    @property
    def dimensions(self) -> Vector:
        """最大和最小的距离"""
        return self.max - self.min

    @property
    def objs_sum_dimensions(self) -> Vector:
        """所有物体相加的尺寸"""
        v = Vector()
        for m in self.__measures__:
            v += m.dimensions
        return v

    @property
    def fixed_offset(self):
        """分布模式每个物体应间隔多少"""
        return (self.dimensions - self.objs_sum_dimensions) / (len(self.__measures__) - 1)

    def sort_by_axis(self, axis: int) -> list[Measure]:
        """
        ("X", "Y", "Z")
        """
        return sorted(self.__measures__, key=lambda k: k.center[axis])
