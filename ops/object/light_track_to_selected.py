import bpy


class M8_OT_LightTrackToSelected(bpy.types.Operator):
    bl_idname = "m8.light_track_to_selected"
    bl_label = "灯光对准选中"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        light_obj = context.active_object
        if not light_obj or light_obj.type != "LIGHT":
            return False
        for o in context.selected_objects:
            if o != light_obj:
                return True
        return False

    def execute(self, context):
        light_obj = context.active_object
        
        # Calculate target center from all selected objects
        target_center = None
        count = 0
        
        # If we have only 2 objects (light + 1 target), use target directly.
        # If multiple targets, maybe create an Empty?
        # Creating an Empty might be intrusive.
        # Standard behavior: Track to the LAST selected (Active if it wasn't the light itself)?
        # Or find the first non-light object.
        
        # Existing logic: First non-light object.
        target = None
        for o in context.selected_objects:
            if o != light_obj:
                target = o
                break
                
        # Optimization: If multiple objects selected, we could pick the active one if it's not the light?
        # But usually user selects Target -> Shift Select Light -> Active is Light.
        # So "first non-light" is reasonable.
        
        if not target:
            self.report({'WARNING'}, "未找到目标物体")
            return {"CANCELLED"}

        con = None
        for c in light_obj.constraints:
            if c.type == "TRACK_TO" and c.name.startswith("M8 Track To"):
                con = c
                break
        if not con:
            try:
                con = light_obj.constraints.new(type="TRACK_TO")
                con.name = "M8 Track To"
            except Exception:
                return {"CANCELLED"}

        con.target = target
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        
        self.report({'INFO'}, f"已追踪到: {target.name}")
        return {"FINISHED"}


class M8_OT_LightClearTrackTo(bpy.types.Operator):
    bl_idname = "m8.light_clear_track_to"
    bl_label = "清除灯光对准"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        light_obj = context.active_object
        if not light_obj or light_obj.type != "LIGHT":
            return False
        for c in light_obj.constraints:
            if c.type == "TRACK_TO" and c.name.startswith("M8 Track To"):
                return True
        return False

    def execute(self, context):
        light_obj = context.active_object
        to_remove = []
        for c in light_obj.constraints:
            if c.type == "TRACK_TO" and c.name.startswith("M8 Track To"):
                to_remove.append(c)
        for c in to_remove:
            try:
                light_obj.constraints.remove(c)
            except Exception:
                pass
        return {"FINISHED"}
