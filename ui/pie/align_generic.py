import bpy
from ...utils import get_menu_bl_idname

class M8_OT_AlignPieContextCall(bpy.types.Operator):
    bl_idname = "m8.align_pie_context_call"
    bl_label = "对齐菜单 (自动识别模式)"
    bl_description = "根据当前模式弹出对应的对齐饼菜单"

    def execute(self, context):
        try:
            area = getattr(context, "area", None)
            if area and getattr(area, "type", None) == "IMAGE_EDITOR":
                bpy.ops.wm.call_menu_pie(name=get_menu_bl_idname("ALIGN_UV"))
            elif context.mode in {"EDIT_MESH", "MESH"}:
                bpy.ops.wm.call_menu_pie(name=get_menu_bl_idname("ALIGN_MESH"))
            elif context.mode == "OBJECT":
                bpy.ops.wm.call_menu_pie(name=get_menu_bl_idname("ALIGN_OBJECT"))
            else:
                self.report({'INFO'}, f"当前模式 ({context.mode}) 不支持对齐菜单")
        except Exception as e:
            self.report({'ERROR'}, f"无法弹出对齐菜单: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}
