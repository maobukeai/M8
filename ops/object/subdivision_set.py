import bpy
from ...utils.i18n import _T

class M8_OT_SubdivisionSet(bpy.types.Operator):
    bl_idname = "m8.subdivision_set"
    bl_label = _T("设置细分级别")
    bl_options = {"REGISTER", "UNDO"}

    level: bpy.props.IntProperty(name=_T("级别"), default=1, min=0, max=6)

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "OBJECT" and context.selected_objects)

    def execute(self, context):
        # Filter all selected mesh objects
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not mesh_objects:
            self.report({'WARNING'}, _T("未选择任何网格物体"))
            return {'CANCELLED'}

        modified_count = 0
        for obj in mesh_objects:
            # Find the last Subdivision Surface modifier
            subsurf = None
            for mod in reversed(obj.modifiers):
                if mod.type == 'SUBSURF':
                    subsurf = mod
                    break
            
            if subsurf:
                subsurf.levels = self.level
                # Keep render levels at least equal to viewport levels
                if subsurf.render_levels < self.level:
                    subsurf.render_levels = self.level
                modified_count += 1
            else:
                # If level is 0 and no modifier exists, we don't need to add one
                if self.level > 0:
                    mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
                    mod.levels = self.level
                    mod.render_levels = self.level
                    if hasattr(mod, "show_only_control_edges"):
                        mod.show_only_control_edges = True
                    modified_count += 1

        if modified_count > 0:
            self.report({'INFO'}, f"{_T('已设置 ')}{modified_count}{_T(' 个物体的细分级别为 ')}{self.level}")
        return {'FINISHED'}
