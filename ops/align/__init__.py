import bpy

from .align_mesh import AlignMesh
from .align_object import AlignObject
from .align_object_by_view import AlignObjectByView
from .align_uv import AlignUV

class_tuples = (
    AlignObject,
    AlignObjectByView,

    AlignMesh,
    
    AlignUV,
)

register_class, unregister_class = bpy.utils.register_classes_factory(class_tuples)


def register():
    register_class()


def unregister():
    unregister_class()
