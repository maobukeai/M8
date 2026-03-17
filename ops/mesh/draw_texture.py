import bpy


class M8_OT_DrawSelected(bpy.types.Operator):
    bl_idname = "m8.draw_selected"
    bl_label = "绘制所选"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def execute(self, context):
        obj = context.object
        try:
            obj["_m8_draw_selected"] = 1
        except Exception:
            pass

        if hasattr(obj.data, "use_paint_mask"):
            obj.data.use_paint_mask = True

        try:
            bpy.ops.object.mode_set(mode="TEXTURE_PAINT", toggle=False)
        except Exception:
            return {"CANCELLED"}
        return {"FINISHED"}


class M8_OT_CancelDrawSelected(bpy.types.Operator):
    bl_idname = "m8.cancel_draw_selected"
    bl_label = "退出绘制"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != "MESH":
            return False
        return context.mode == "TEXTURE_PAINT"

    def execute(self, context):
        obj = context.object
        
        # 1. 尝试关闭遮罩 (非阻塞)
        if hasattr(obj.data, "use_paint_mask"):
            try:
                obj.data.use_paint_mask = False
            except Exception:
                pass

        # 2. 清理属性 (非阻塞)
        try:
            if "_m8_draw_selected" in obj:
                del obj["_m8_draw_selected"]
        except Exception:
            pass

        # 3. 切换模式 (核心逻辑)
        try:
            # 确保当前对象是激活对象
            if context.view_layer.objects.active != obj:
                context.view_layer.objects.active = obj
                
            bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        except Exception as e:
            print(f"M8 Debug: Direct switch to EDIT failed: {e}")
            # Fallback: Try to switch to OBJECT first then EDIT
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
                bpy.ops.object.mode_set(mode="EDIT")
            except Exception as e2:
                self.report({'ERROR'}, f"退出绘制失败: {e2}")
                return {"CANCELLED"}
                
        return {"FINISHED"}
