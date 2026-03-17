import bpy
from bpy.types import Menu
from ...utils.i18n import _T

class VIEW3D_MT_M8SmartPie(Menu):
    bl_label = "Smart Pie"
    bl_idname = "VIEW3D_MT_M8SmartPie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        prefs = None
        try:
            root_pkg = (__package__ or "").split(".")[0]
            addon = bpy.context.preferences.addons.get(root_pkg) if bpy.context and bpy.context.preferences else None
            prefs = addon.preferences if addon else None
        except Exception:
            prefs = None

        pie.operator("m8.smart_vert", text=_T("智能顶点"), icon="VERTEXSEL")
        op_face = pie.operator("m8.smart_face", text=_T("智能面"), icon="FACESEL")
        if prefs:
            try:
                op_face.focus_mode = bool(getattr(prefs, "smart_face_focus_mode", False))
                op_face.stay_on_original = bool(getattr(prefs, "smart_face_stay_on_original", False))
            except Exception:
                pass
        pie.operator("m8.smart_edge", text=_T("智能边"), icon="EDGESEL")

        col = pie.column()
        col.label(text=_T("路径"))
        col.operator("m8.smart_paths_merge", text=_T("合并"), icon="AUTOMERGE_OFF")
        col.operator("m8.smart_paths_connect", text=_T("连接"), icon="CONSTRAINT")

        pie.operator("m8.smart_merge_center", text=_T("中心合并"), icon="PIVOT_CURSOR")
        pie.operator("m8.smart_slide_extend", text=_T("滑动延伸"), icon="TRANSFORM_ORIGINS")
        
        pie.operator("m8.smart_toggle_sharp", text=_T("切换锐边"), icon="SHARPCURVE")
        
        pie.operator("m8.smart_offset_edges", text=_T("偏移边线"), icon="MOD_BEVEL")

classes = (
    VIEW3D_MT_M8SmartPie,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
