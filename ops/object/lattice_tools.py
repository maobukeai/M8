import bpy


class M8_OT_LatticeMakeRegular(bpy.types.Operator):
    bl_idname = "m8.lattice_make_regular"
    bl_label = "重置形状"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "LATTICE")

    def execute(self, context):
        obj = context.active_object
        prev_mode = getattr(context, "mode", "OBJECT")
        try:
            if obj not in context.selected_objects:
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                context.view_layer.objects.active = obj

            if prev_mode != "EDIT_LATTICE":
                bpy.ops.object.mode_set(mode="EDIT")

            try:
                bpy.ops.lattice.select_all(action="SELECT")
            except Exception:
                pass

            bpy.ops.lattice.make_regular()
        except Exception as e:
            self.report({"WARNING"}, str(e))
            return {"CANCELLED"}
        finally:
            if prev_mode == "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except Exception:
                    pass
        return {"FINISHED"}

