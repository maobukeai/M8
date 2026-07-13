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
        created_count = 0
        hidden_modifier_names = []
        skipped_names = []
        for obj in mesh_objects:
            # Prefer the first viewport-visible Subdivision modifier.  The old
            # "last modifier" rule silently changed a hidden/secondary stack
            # entry on many production assets, which looked like a failed hotkey.
            subsurfs = [mod for mod in obj.modifiers if mod.type == 'SUBSURF']
            subsurf = next((mod for mod in subsurfs if mod.show_viewport), None)
            if subsurf is None and subsurfs:
                subsurf = subsurfs[0]
                hidden_modifier_names.append(f"{obj.name}: {subsurf.name}")
            
            try:
                if subsurf:
                    subsurf.levels = self.level
                    # Keep render levels at least equal to viewport levels.
                    if subsurf.render_levels < self.level:
                        subsurf.render_levels = self.level
                    modified_count += 1
                elif self.level > 0:
                    mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
                    mod.levels = self.level
                    mod.render_levels = self.level
                    if hasattr(mod, "show_only_control_edges"):
                        mod.show_only_control_edges = True
                    modified_count += 1
                    created_count += 1
            except (AttributeError, RuntimeError, TypeError):
                # Linked/read-only data can reject modifier changes.  Continue
                # with the rest of the selection and report the affected object.
                skipped_names.append(obj.name)

        if modified_count > 0:
            details = []
            if created_count:
                details.append(f"{_T('新建')} {created_count}")
            if hidden_modifier_names:
                details.append(f"{_T('修改了隐藏修改器')} {len(hidden_modifier_names)}")
            suffix = f" ({'，'.join(details)})" if details else ""
            self.report({'INFO'}, f"{_T('已设置 ')}{modified_count}{_T(' 个物体的细分级别为 ')}{self.level}{suffix}")
        elif self.level == 0:
            self.report({'INFO'}, _T("选中对象没有细分修改器，无需清零"))
        else:
            self.report({'WARNING'}, _T("没有可修改的细分修改器"))

        if skipped_names:
            self.report({'WARNING'}, f"{_T('以下对象无法修改：')}{', '.join(skipped_names[:3])}")
        return {'FINISHED'}
