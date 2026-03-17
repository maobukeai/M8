from math import radians

import bpy


class M8_OT_AutoSmooth(bpy.types.Operator):
    bl_idname = "m8.auto_smooth"
    bl_label = "Auto Smooth"
    bl_options = {"REGISTER", "UNDO"}

    angle: bpy.props.IntProperty(
        name="Angle",
        default=60,
        min=0,
        max=360,
        soft_max=180,
        step=5,
        subtype="ANGLE",
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and any(o.type == "MESH" for o in context.selected_objects)

    def execute(self, context):
        # 0 angle means "Disable Auto Smooth" (Remove modifier or set use_auto_smooth=False)
        disable_auto_smooth = (self.angle <= 0)
        
        # In Blender 4.1+, Auto Smooth is a modifier "Smooth by Angle"
        # In older Blender, it is mesh.use_auto_smooth
        
        has_shade_auto_smooth = hasattr(bpy.ops.object, "shade_auto_smooth")
        
        # First, ensure we process all selected objects
        selected = context.selected_objects
        if not selected:
            return {"CANCELLED"}

        for obj in selected:
            if obj.type != "MESH":
                continue
            
            # Make active for operators that rely on context
            context.view_layer.objects.active = obj
            
            if disable_auto_smooth:
                # Disable Auto Smooth -> Revert to basic Smooth Shading
                # Remove "Smooth by Angle" modifier if exists
                if has_shade_auto_smooth:
                    # Remove modifiers named "Smooth by Angle" or created by auto smooth
                    # Blender 4.1+ modifier name is typically "Smooth by Angle"
                    to_remove = []
                    for mod in obj.modifiers:
                        if mod.type == 'NODES' and "Smooth by Angle" in mod.name:
                             to_remove.append(mod)
                    for mod in to_remove:
                        obj.modifiers.remove(mod)
                    
                    # Also ensure base shading is smooth (or flat? usually smooth base is preferred)
                    try:
                        bpy.ops.object.shade_smooth()
                    except Exception:
                        pass
                else:
                    # Old Blender
                    if hasattr(obj.data, "use_auto_smooth"):
                        obj.data.use_auto_smooth = False
                    try:
                        bpy.ops.object.shade_smooth()
                    except Exception:
                        pass
            else:
                # Enable Auto Smooth with Angle
                if has_shade_auto_smooth:
                    try:
                        # shade_auto_smooth adds/updates modifier
                        bpy.ops.object.shade_auto_smooth(angle=radians(self.angle))
                    except Exception:
                        pass
                else:
                    # Old Blender
                    try:
                        bpy.ops.object.shade_smooth()
                    except Exception:
                        pass
                    if hasattr(obj.data, "use_auto_smooth"):
                        obj.data.use_auto_smooth = True
                    if hasattr(obj.data, "auto_smooth_angle"):
                        obj.data.auto_smooth_angle = radians(self.angle)

        return {"FINISHED"}


def draw_auto_smooth(context: bpy.types.Context, layout: bpy.types.UILayout):
    column = layout.column(align=True)
    column.scale_x = 0.7
    column.scale_y = 1.2

    row = column.split(factor=0.75, align=True)
    row.operator(M8_OT_AutoSmooth.bl_idname, text="自动平滑(60°)").angle = 60
    row.operator(M8_OT_AutoSmooth.bl_idname, text="", icon="PANEL_CLOSE").angle = 0

    row = column.row(align=True)
    for a in (15, 30, 90, 180):
        row.operator(M8_OT_AutoSmooth.bl_idname, text=str(a)).angle = a
