import bpy


class M8_OT_SurfaceSliding(bpy.types.Operator):
    bl_idname = "m8.surface_sliding"
    bl_label = "表面滑动"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def invoke(self, context, event):
        # Prefer Vertex Slide (Shift+V) as it is more versatile for surface sliding
        # But Edge Slide (GG) is common for loops.
        # Surface sliding usually implies moving verts along the surface.
        # Vert Slide works best for single verts or irregular selections.
        
        # Try Vert Slide first if selection mode involves vertices or faces?
        # Actually Edge Slide fails on single vertices. Vert slide works on edges too?
        # Vert slide on edge slides along edge.
        
        # Let's try Vert Slide first, if it fails (e.g. context incorrect), try Edge Slide.
        try:
            return bpy.ops.transform.vert_slide("INVOKE_DEFAULT")
        except Exception:
            pass
            
        try:
            return bpy.ops.transform.edge_slide("INVOKE_DEFAULT")
        except Exception:
            pass
            
        return {"CANCELLED"}


def ui(context: bpy.types.Context, pie: bpy.types.UILayout):
    pie.operator(M8_OT_SurfaceSliding.bl_idname, text="表面滑动", icon="MOD_SHRINKWRAP")
