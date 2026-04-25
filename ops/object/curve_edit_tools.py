import bpy


def ensure_edit_mode(context, obj_type):
    # Ensure all selected objects of type are in Edit Mode
    # If not, switch mode
    # Return True if successful
    
    # If already in Edit Mode, check if all selected are in Edit Mode?
    # Blender allows mix, but operators usually work on "Objects in Edit Mode".
    
    if context.mode != 'EDIT_CURVE': # Or 'EDIT_SURFACE'? 'EDIT_CURVE' covers both usually?
        # Actually context.mode is specific.
        pass
        
    # We want to enable Multi-Edit for all selected curves
    selected = [o for o in context.selected_objects if o.type in {"CURVE", "SURFACE"}]
    if not selected:
        return False
        
    # If active object is not one of them, make one active
    if context.active_object not in selected:
        context.view_layer.objects.active = selected[0]
        
    if context.mode != 'EDIT_CURVE' and context.mode != 'EDIT_SURFACE':
        try:
            bpy.ops.object.mode_set(mode='EDIT')
        except Exception:
            return False
            
    return True

class M8_OT_CurveHandleTypeRemember(bpy.types.Operator):
    bl_idname = "m8.curve_handle_type_remember"
    bl_label = "Handle Type"
    bl_options = {"REGISTER", "UNDO"}

    handle_type: bpy.props.EnumProperty(
        items=[
            ("AUTOMATIC", "Auto", ""),
            ("ALIGNED", "Aligned", ""),
            ("VECTOR", "Vector", ""),
            ("FREE_ALIGN", "Free", ""),
        ],
        default="AUTOMATIC",
    )

    @classmethod
    def poll(cls, context):
        # Allow Object Mode if selected objects are Curves
        if context.mode == 'OBJECT':
             return any(o.type in {"CURVE", "SURFACE"} for o in context.selected_objects)
        return bool(context.mode in {"EDIT_CURVE", "EDIT_SURFACE"} and context.active_object and context.active_object.type in {"CURVE", "SURFACE"})

    def execute(self, context):
        try:
            context.window_manager.m8.last_curve_handle_type = self.handle_type
        except Exception:
            pass
            
        if not ensure_edit_mode(context, "CURVE"):
            return {"CANCELLED"}
            
        # Select All? If we switched from Object Mode, nothing is selected in Edit Mode usually (or everything?).
        # If we came from Object Mode, user expects "Apply to Object".
        # So we should Select All.
        # How to detect "Came from Object Mode"?
        # We can't easily state-track here without props.
        # Assumption: If user uses this tool, they want to apply it.
        # If they are already in Edit Mode, apply to Selection.
        # If they are in Object Mode, apply to All (implicitly).
        
        # But `ensure_edit_mode` just switches.
        # We need to know if we should Select All.
        
        # Let's assume: If nothing is selected in Edit Mode, Select All?
        # Or just Select All if we forced the switch.
        
        # Simpler: Just execute. If selection is empty, nothing happens.
        # But for Object Mode workflow, user expects action on object.
        # So we should Select All.
        
        bpy.ops.curve.select_all(action='SELECT')
        
        try:
            bpy.ops.curve.handle_type_set(type=self.handle_type)
        except Exception:
            return {"CANCELLED"}
        return {"FINISHED"}


class M8_OT_CurveSwitchDirectionRemember(bpy.types.Operator):
    bl_idname = "m8.curve_switch_direction_remember"
    bl_label = "Switch Direction"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
             return any(o.type in {"CURVE", "SURFACE"} for o in context.selected_objects)
        return bool(context.mode in {"EDIT_CURVE", "EDIT_SURFACE"})

    def execute(self, context):
        try:
            context.window_manager.m8.last_curve_edit_action = "SWITCH_DIRECTION"
        except Exception:
            pass
            
        if not ensure_edit_mode(context, "CURVE"):
            return {"CANCELLED"}
            
        bpy.ops.curve.select_all(action='SELECT')
        
        try:
            bpy.ops.curve.switch_direction()
        except Exception:
            return {"CANCELLED"}
        return {"FINISHED"}


class M8_OT_CurveSubdivideRemember(bpy.types.Operator):
    bl_idname = "m8.curve_subdivide_remember"
    bl_label = "Subdivide"
    bl_options = {"REGISTER", "UNDO"}

    number_cuts: bpy.props.IntProperty(name="Cuts", default=1, min=1, max=100)

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
             return any(o.type in {"CURVE", "SURFACE"} for o in context.selected_objects)
        return bool(context.mode in {"EDIT_CURVE", "EDIT_SURFACE"})

    def execute(self, context):
        try:
            context.window_manager.m8.last_curve_edit_action = "SUBDIVIDE"
        except Exception:
            pass
            
        if not ensure_edit_mode(context, "CURVE"):
            return {"CANCELLED"}
            
        bpy.ops.curve.select_all(action='SELECT')
        
        try:
            bpy.ops.curve.subdivide(number_cuts=self.number_cuts)
        except Exception:
            return {"CANCELLED"}
        return {"FINISHED"}


class M8_OT_CurveSmoothRemember(bpy.types.Operator):
    bl_idname = "m8.curve_smooth_remember"
    bl_label = "Smooth"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
             return any(o.type in {"CURVE", "SURFACE"} for o in context.selected_objects)
        return bool(context.mode in {"EDIT_CURVE", "EDIT_SURFACE"})

    def execute(self, context):
        try:
            context.window_manager.m8.last_curve_edit_action = "SMOOTH"
        except Exception:
            pass
            
        if not ensure_edit_mode(context, "CURVE"):
            return {"CANCELLED"}
            
        bpy.ops.curve.select_all(action='SELECT')
        
        try:
            bpy.ops.curve.smooth()
        except Exception:
            return {"CANCELLED"}
        return {"FINISHED"}
