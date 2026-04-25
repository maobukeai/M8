import bpy
from ..utils.logger import get_logger

logger = get_logger()

class M8_OT_SmartPassThroughWrapper(bpy.types.Operator):
    """
    Template Operator for Smart Interception (PASS_THROUGH).
    Instead of binding directly to 'wm.call_menu_pie' and disabling other addons,
    bind your hotkey to this operator. 
    
    This operator checks if the context is appropriate for M8. 
    If yes, it opens the M8 menu.
    If no (e.g. user is in a specific mode M8 shouldn't override), 
    it returns {'PASS_THROUGH'} allowing the default Blender hotkey or 
    other addons (like HardOps/Boxcutter) to handle the event.
    """
    bl_idname = "m8.smart_passthrough_wrapper"
    bl_label = "M8 Smart Hotkey Wrapper"
    bl_options = {'INTERNAL'}

    # Properties to tell the wrapper what menu or operator to call if successful
    target_menu: bpy.props.StringProperty(name="Target Menu ID", default="")
    target_operator: bpy.props.StringProperty(name="Target Operator ID", default="")

    @classmethod
    def poll(cls, context):
        # Always return True so we can handle the logic in invoke/execute
        return True

    def invoke(self, context, event):
        # --- Context evaluation logic ---
        # Example: only override Shift+S if we have selected objects.
        # Otherwise, pass through to Blender's default.
        
        # You can add custom logic here depending on the target_menu.
        # For demonstration, we just always call the target.
        # To truly pass through, use: return {'PASS_THROUGH'}
        
        should_intercept = True 
        
        # Example check:
        # if not context.active_object:
        #     should_intercept = False
            
        if not should_intercept:
            logger.debug(f"M8 Wrapper yielding to other addons for {self.target_menu or self.target_operator}")
            return {'PASS_THROUGH'}
            
        # Execute the actual M8 tool
        if self.target_menu:
            bpy.ops.wm.call_menu_pie('INVOKE_DEFAULT', name=self.target_menu)
            return {'FINISHED'}
        elif self.target_operator:
            # Dynamically call the target operator
            try:
                op_module, op_name = self.target_operator.split('.')
                op_func = getattr(getattr(bpy.ops, op_module), op_name)
                op_func('INVOKE_DEFAULT')
                return {'FINISHED'}
            except Exception as e:
                logger.error(f"Smart wrapper failed to call operator {self.target_operator}: {e}")
                return {'CANCELLED'}

        return {'PASS_THROUGH'}

def register():
    bpy.utils.register_class(M8_OT_SmartPassThroughWrapper)

def unregister():
    bpy.utils.unregister_class(M8_OT_SmartPassThroughWrapper)
