# import sys
#
# import bpy
#
# """
#
#     import ctypes
#     ptr = node.as_pointer()
#     ftype = ctypes.POINTER(ctypes.c_float)
#     offset = offset_map.get(sys.platform, {}).get(bpy.app.version[:2])
#     if not offset:
#         return 0, 0
#     ox = ctypes.cast(ptr + offset[4] * 4, ftype).contents.value
#     oy = ctypes.cast(ptr + offset[5] * 4, ftype).contents.value
#     return ox, oy
# """
#
#
# def get_mesh_face_sets_offset(data: bpy.types.Mesh):
#     # x  y  w  h  ox oy
#     offset_map = {
#         'win32': {
#             (4, 2): [60, 61, 62, 63, 64, 65],
#         },
#         'darwin': {
#             (3, 5): [60, 61, 62, 63, 64, 65],
#         }
#     }
#     import ctypes
#     ptr = data.as_pointer()
#     ftype = ctypes.POINTER(ctypes.c_int)
#     offset = offset_map.get(sys.platform, {}).get(bpy.app.version[:2])
#     if not offset:
#         return 0, 0
#     y = ctypes.cast(ptr + offset[4] * 4, ftype).contents.value
#     for i in range(10000):
#         y = ctypes.cast(ptr + i, ftype).contents.value
#         if y == 0 or y is None:
#             continue
#         print(f"{i} {y}")
#     return y
#
#
# if __name__ == '__main__':
#     print(get_mesh_face_sets_offset(bpy.context.object.data))
#     print()
