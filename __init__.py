bl_info = {
    "name": "M8全能工具箱",
    "author": "猫步可爱",
    "version": (3, 0, 1),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar (N) > M8 Tool",
    "description": "在复杂的 3D 建模项目中，效率就是生命。M8 不仅仅是一个工具箱，它是你工作流中的润滑剂。",
    "category": "Object",
}

import bpy
from . import registration

def register():
    registration.register()

def unregister():
    registration.unregister()
