import bpy

def draw_row_image_mode(context: bpy.types.Context, pie: bpy.types.UILayout, is_row=True):
    if is_row:
        row = pie.row(align=True)
        row.scale_x = 1.5
        row.scale_y = 1.4
    else:
        row = pie
    for mode, icon in {
        "VIEW": "SEQ_PREVIEW",
        "PAINT": "TPAINT_HLT",
        "MASK": "MOD_MASK",
        "UV": "UV",
    }.items():
        is_uv = mode == "UV"
        # Check current mode to highlight button
        curr_mode = context.area.ui_type if is_uv else getattr(context.space_data, "ui_mode", "VIEW")
        depress = curr_mode == mode
        
        ops = row.operator(
            "object.switch_image_mode",
            icon=icon,
            text="" if is_row else (mode.title() if mode != "UV" else mode),
            depress=depress,
        )
        ops.mode = mode

class OBJECT_OT_SwitchImageMode(bpy.types.Operator):
    bl_idname = "object.switch_image_mode"
    bl_label = "Switch Image Mode"
    bl_description = "Switch between Image/UV Editor modes"
    
    mode: bpy.props.StringProperty()

    def execute(self, context):
        if self.mode == "UV":
            context.area.ui_type = 'UV'
        else:
            context.area.ui_type = 'IMAGE_EDITOR'
            if hasattr(context.space_data, "ui_mode"):
                context.space_data.ui_mode = self.mode
        return {"FINISHED"}
