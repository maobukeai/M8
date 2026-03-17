import bpy

from .hub import MeshHub
from .mesh_preview import MeshPreview
from ....utils.items import AXIS


class MirrorMesh(MeshHub, MeshPreview):

    @staticmethod
    def get_selected_mesh_objects(context):
        return [i for i in context.selected_objects if i.type == "MESH"]

    def draw_mesh(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        main = layout.column(align=True)
        header = main.row(align=True)
        header.scale_y = 1.2
        header.prop(self, "use_modifier", text="使用修改器" if self.use_modifier else "直接镜像", toggle=True)

        opt = main.box()
        opt_col = opt.column(align=True)
        row = opt_col.row(align=True)
        row.enabled = bool(self.use_modifier)
        row.prop(self, "use_parent")
        sub = row.row(align=True)
        sub.enabled = bool(self.use_modifier and self.axis_mode == "ACTIVE" and context.mode == "OBJECT")
        sub.prop(self, "use_mirror_active", text="镜像活动项")

        row = opt_col.row(align=True)
        row.prop(self, "bisect")
        sub = row.row(align=True)
        sub.enabled = bool(self.bisect)
        sub.prop(self, "is_negative_axis", text="反向")

        adv = main.box()
        adv.use_property_split = True
        adv.use_property_decorate = False
        adv.prop(self, "threshold")

        axes = main.box()
        axes_col = axes.column(align=True)
        axes_col.row(align=True).prop(self, "axis_mode", expand=True)
        axes_col.row(align=True).prop(self, "axis", expand=True)

    def execute_mesh(self, context):
        """
        TODO 在编辑模式保留修改器后撤销出现问题
        """
        self.update_matrix(context)

        print("Mirror execute", self.bl_idname, context.mode, self.bisect)

        last_mode = context.mode
        if last_mode == "EDIT_MESH" and self.use_modifier is False:
            bpy.ops.object.mode_set("EXEC_DEFAULT", False, mode='OBJECT', toggle=True)

        active = self.get_mesh_active_object(context)
        collection = active.users_collection[0]
        
        # Sort names to ensure consistent empty name regardless of selection order
        selected_meshes = self.get_selected_mesh_objects(context)
        obj_names = [obj.name for obj in selected_meshes]
        obj_names.sort()
        empty_name = "_".join(obj_names)

        mirror_empty = self.create_mirror_empty(context, empty_name, collection)

        mirror_list = []

        if last_mode == "EDIT_MESH":
            mirror_list.append(self.create_modifier(context, active, mirror_empty))
        else:
            for obj in self.get_selected_mesh_objects(context):
                if self.axis_mode == "ACTIVE" and len(self.get_selected_mesh_objects(context)) != 1:
                    if self.use_mirror_active:
                        if obj == active:
                            mirror_list.append(self.create_modifier(context, obj, None, reverse_parent=True))
                        else:
                            mirror_list.append(self.create_modifier(context, obj, active, reverse_parent=True))
                    else:
                        if obj != active:
                            mirror_list.append(self.create_modifier(context, obj, active, reverse_parent=True))
                else:
                    mirror_list.append(self.create_modifier(context, obj, mirror_empty, reverse_parent=True))

        if self.use_modifier:
            # 如果是修改器模式，检查是否所有轴都关闭了
            # 如果都关闭了，移除修改器
            # 我们需要重新获取修改器对象，因为上面可能新建了或者获取了引用
            
            # 这里需要遍历所有相关物体
            objects_to_check = []
            if last_mode == "EDIT_MESH":
                 objects_to_check.append(active)
            else:
                 objects_to_check = [obj for obj, mod in mirror_list]
                 
            for obj in objects_to_check:
                # 查找修改器
                new_mod_name = "M8_mirror"
                old_mod_name = "MP7 Mirror"
                target_mod_name = self.modifier_name if self.modifier_name else new_mod_name
                mod_index = obj.modifiers.find(target_mod_name)
                if mod_index == -1 and target_mod_name == new_mod_name:
                    mod_index = obj.modifiers.find(old_mod_name)
                    if mod_index != -1:
                        try:
                            obj.modifiers[mod_index].name = new_mod_name
                            self.modifier_name = new_mod_name
                        except Exception:
                            pass
                        mod_index = obj.modifiers.find(new_mod_name)
                if mod_index != -1:
                    mod = obj.modifiers[mod_index]
                    if mod.type == 'MIRROR':
                        # 检查是否有任何轴开启
                        any_axis = any(mod.use_axis)
                        mirror_obj = mod.mirror_object
                        if not any_axis:
                            obj.modifiers.remove(mod)
                            # Humanized: Clean up unused empty
                            if mirror_obj:
                                self._cleanup_unused_empty(context, mirror_obj)
        else:
            for (obj, mod) in mirror_list:
                context.view_layer.objects.active = obj
                bpy.ops.object.modifier_apply("EXEC_DEFAULT", False, modifier=mod.name)

            if mirror_empty:
                # Direct mode always cleans up the empty we created
                try:
                    bpy.data.objects.remove(mirror_empty)
                except:
                    pass

            context.view_layer.objects.active = active

        self.update_mesh_preview(context, is_preview=False)
        if last_mode == "EDIT_MESH" and self.use_modifier is False:
            bpy.ops.object.mode_set("EXEC_DEFAULT", False, mode='EDIT', toggle=True)

        return {"FINISHED"}

    def _cleanup_unused_empty(self, context, empty_obj):
        """Clean up the empty object if it's not used by any modifiers"""
        if not empty_obj or not (empty_obj.name.endswith("_MP7_Mirror_Empty") or empty_obj.name.endswith("_M8_mirror_Empty")):
            return
            
        # Check users count. 
        # 1 user usually means it's only in the collection.
        # Modifiers using it will increase the user count.
        if empty_obj.users <= 1:
            try:
                bpy.data.objects.remove(empty_obj)
            except:
                pass

    def create_modifier(self, context, obj, mirror_obj=None, reverse_parent=False):
        """
        'GREASE_PENCIL_VERTEX_WEIGHT_PROXIMITY', 'DATA_TRANSFER', 'MESH_CACHE', 'MESH_SEQUENCE_CACHE', 'NORMAL_EDIT', 'WEIGHTED_NORMAL', 'UV_PROJECT', 'UV_WARP', 'VERTEX_WEIGHT_EDIT', 'VERTEX_WEIGHT_MIX', 'VERTEX_WEIGHT_PROXIMITY', 'GREASE_PENCIL_COLOR', 'GREASE_PENCIL_TINT', 'GREASE_PENCIL_OPACITY', 'GREASE_PENCIL_VERTEX_WEIGHT_ANGLE', 'GREASE_PENCIL_TIME', 'GREASE_PENCIL_TEXTURE', 'ARRAY', 'BEVEL', 'BOOLEAN', 'BUILD', 'DECIMATE', 'EDGE_SPLIT', 'NODES', 'MASK', 'MIRROR', 'MESH_TO_VOLUME', 'MULTIRES', 'REMESH', 'SCREW', 'SKIN', 'SOLIDIFY', 'SUBSURF', 'TRIANGULATE', 'VOLUME_TO_MESH', 'WELD', 'WIREFRAME', 'GREASE_PENCIL_ARRAY', 'GREASE_PENCIL_BUILD', 'GREASE_PENCIL_LENGTH', 'LINEART', 'GREASE_PENCIL_MIRROR', 'GREASE_PENCIL_MULTIPLY', 'GREASE_PENCIL_SIMPLIFY', 'GREASE_PENCIL_SUBDIV', 'GREASE_PENCIL_ENVELOPE', 'GREASE_PENCIL_OUTLINE', 'ARMATURE', 'CAST', 'CURVE', 'DISPLACE', 'HOOK', 'LAPLACIANDEFORM', 'LATTICE', 'MESH_DEFORM', 'SHRINKWRAP', 'SIMPLE_DEFORM', 'SMOOTH', 'CORRECTIVE_SMOOTH', 'LAPLACIANSMOOTH', 'SURFACE_DEFORM', 'WARP', 'WAVE', 'VOLUME_DISPLACE', 'GREASE_PENCIL_HOOK', 'GREASE_PENCIL_NOISE', 'GREASE_PENCIL_OFFSET', 'GREASE_PENCIL_SMOOTH', 'GREASE_PENCIL_THICKNESS', 'GREASE_PENCIL_LATTICE', 'GREASE_PENCIL_DASH', 'GREASE_PENCIL_ARMATURE', 'GREASE_PENCIL_SHRINKWRAP', 'CLOTH', 'COLLISION', 'DYNAMIC_PAINT', 'EXPLODE', 'FLUID', 'OCEAN', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SOFT_BODY', 'SURFACE')
        C.object.modifiers.new()
        使用其它坐标系的内容
        bpy.data.objects["平面"].modifiers["M8_mirror"].merge_threshold
        """

        # Toggle logic: Check existing axes if modifier exists
        existing_axes = [False, False, False]
        existing_bisect = [False, False, False]
        existing_flip = [False, False, False]
        
        # Check if modifier already exists (before creating new one or getting reference)
        # We need to do this carefully. 
        new_mod_name = "M8_mirror"
        old_mod_name = "MP7 Mirror"
        target_mod_name = self.modifier_name if self.modifier_name else new_mod_name
        mod_index = obj.modifiers.find(target_mod_name)
        if mod_index == -1 and self.modifier_name is None:
            mod_index = obj.modifiers.find(old_mod_name)
            if mod_index != -1:
                try:
                    obj.modifiers[mod_index].name = new_mod_name
                except Exception:
                    pass
                mod_index = obj.modifiers.find(new_mod_name)
        
        if mod_index != -1:
            existing_mod = obj.modifiers[mod_index]
            if existing_mod.type == 'MIRROR':
                existing_axes = list(existing_mod.use_axis)
                existing_bisect = list(existing_mod.use_bisect_axis)
                existing_flip = list(existing_mod.use_bisect_flip_axis)
                if self.modifier_name is None:
                    self.modifier_name = existing_mod.name

        if self.modifier_name is None:
            mod = obj.modifiers.new(new_mod_name, "MIRROR")
            self.modifier_name = mod.name
            
            # Humanized: Move new modifier to top (usually preferred)
            # Only if we have other modifiers
            if len(obj.modifiers) > 1:
                try:
                    # Need active object context for operator
                    prev_active = context.view_layer.objects.active
                    context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
                    context.view_layer.objects.active = prev_active
                except Exception as e:
                    print(f"Failed to move modifier to top: {e}")
        else:
            mod_index = obj.modifiers.find(self.modifier_name)
            if mod_index == -1:
                mod = obj.modifiers.new(new_mod_name, "MIRROR")
                self.modifier_name = mod.name
            else:
                mod = obj.modifiers[mod_index]
        
        # Apply toggle logic
        new_axes = list(mod.use_axis) # Start with current (which might be empty if new) or existing
        new_bisect = list(mod.use_bisect_axis)
        new_flip = list(mod.use_bisect_flip_axis)
        
        # AXIS = ['X', 'Y', 'Z']
        for i, axis_name in enumerate(AXIS):
            is_target_axis = (axis_name == self.axis)
            
            if is_target_axis:
                # Toggle logic:
                # If axis was ON, turn it OFF
                # If axis was OFF, turn it ON
                # But wait, if we are in modal, we want to set it to ON if user selects it.
                # If user selects X, and X is already ON, maybe they want to update parameters (like bisect flip)?
                # Or maybe they want to toggle it OFF?
                # A true toggle is best for adding/removing axes.
                
                # However, if we just toggle, how does the user update Bisect Flip direction?
                # E.g. X axis is ON (Positive). User moves mouse to Negative side and releases.
                # They expect X axis to update to Negative flip.
                # If we just toggle OFF, that's annoying.
                
                # So logic should be:
                # If axis is OFF -> Turn ON (with current bisect settings)
                # If axis is ON -> 
                #    If bisect/flip settings are DIFFERENT -> Update settings (Keep ON)
                #    If bisect/flip settings are SAME -> Turn OFF
                
                current_flip = not self.is_negative_axis
                
                was_on = existing_axes[i]
                was_bisect = existing_bisect[i]
                was_flip = existing_flip[i]
                
                # Check if settings changed
                settings_changed = False
                if self.bisect != was_bisect: settings_changed = True
                if self.bisect and (current_flip != was_flip): settings_changed = True
                
                if was_on and not settings_changed:
                    # Toggle OFF
                    new_axes[i] = False
                    new_bisect[i] = False # Clear bisect too
                else:
                    # Turn ON or Update
                    new_axes[i] = True
                    new_bisect[i] = self.bisect
                    new_flip[i] = current_flip
            else:
                # Keep existing state for other axes
                if mod_index != -1: # Only if we are editing existing modifier
                    new_axes[i] = existing_axes[i]
                    new_bisect[i] = existing_bisect[i]
                    new_flip[i] = existing_flip[i]
        
        mod.use_axis = tuple(new_axes)
        mod.use_bisect_axis = tuple(new_bisect)
        mod.use_bisect_flip_axis = tuple(new_flip)
        
        mod.use_clip = True  # Enable clipping by default
        mod.show_on_cage = True
        mod.mirror_object = mirror_obj
        mod.merge_threshold = self.threshold


        if self.use_parent and self.use_modifier and mirror_obj:
            if reverse_parent:
                obj.parent = mirror_obj
            else:
                mirror_obj.parent = obj.parent

            obj.matrix_world = self.backups_matrix[obj.name]

        return obj, mod

    def create_mirror_empty(self, context, name, collection):
        if self.axis_mode == "ORIGIN":
            return None
        elif self.axis_mode == "ACTIVE" and context.mode != "EDIT_MESH":
            return None

        # Truncate name to avoid issues with Blender's 63 char limit (suffix is 17 chars)
        if len(name) > 46:
            name = name[:46]

        new_suffix = "_M8_mirror_Empty"
        old_suffix = "_MP7_Mirror_Empty"
        target_name = f"{name}{new_suffix}"

        # Try to reuse existing empty
        existing_empty = bpy.data.objects.get(target_name)
        if existing_empty is None:
            existing_empty = bpy.data.objects.get(f"{name}{old_suffix}")
            if existing_empty and existing_empty.type == 'EMPTY':
                try:
                    existing_empty.name = target_name
                except Exception:
                    pass
                existing_empty = bpy.data.objects.get(target_name)
        if existing_empty and existing_empty.type == 'EMPTY':
            # Ensure it's linked to the collection if not already
            if existing_empty.name not in collection.objects:
                try:
                    collection.objects.link(existing_empty)
                except Exception:
                    pass
            
            existing_empty.matrix_world = self.origin_matrix
            return existing_empty

        empty = bpy.data.objects.new(target_name, None)

        collection.objects.link(empty)

        context.view_layer.update()

        empty.matrix_world = self.origin_matrix

        return empty
