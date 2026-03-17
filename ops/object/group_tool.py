import bpy
from mathutils import Vector
from ...utils.ray_cast import mouse_2d_ray_cast

class M8_OT_GroupObjects(bpy.types.Operator):
    bl_idname = "m8.group_objects"
    bl_label = "Group Objects (Ctrl+G)"
    bl_description = "创建空物体作为父级并绑定选中物体"
    bl_options = {'REGISTER', 'UNDO'}

    hide_empty: bpy.props.BoolProperty(name="隐藏组空物体", default=False)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def invoke(self, context, event):
        root_pkg = (__package__ or "").split(".")[0]
        addon = context.preferences.addons.get(root_pkg)
        if addon and addon.preferences:
            self.hide_empty = getattr(addon.preferences, "group_tool_hide_empty", False)
        return self.execute(context)

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            return {'CANCELLED'}

        # Calculate center
        center = Vector((0.0, 0.0, 0.0))
        for obj in selected_objects:
            center += obj.matrix_world.translation
        center /= len(selected_objects)

        # Get prefs
        root_pkg = (__package__ or "").split(".")[0]
        addon = context.preferences.addons.get(root_pkg)
        
        empty_type = 'SPHERE'
        radius = 1.0
        
        if addon and addon.preferences:
            prefs = addon.preferences
            radius = getattr(prefs, "group_tool_radius", 1.0)
            empty_type = getattr(prefs, "group_tool_empty_type", 'SPHERE')

        # Create Empty
        bpy.ops.object.empty_add(type=empty_type, location=center)
        group_empty = context.active_object
        
        # Name the group
        group_name = "Group"
        if selected_objects:
             # Use active object name or first selected
             base_obj = context.active_object if context.active_object in selected_objects else selected_objects[0]
             # If base object is already a group, maybe use its name? But we are creating a NEW parent.
             group_name = f"{base_obj.name}_Grp"
        
        group_empty.name = group_name
        group_empty.empty_display_size = radius
        group_empty["m8_is_group"] = True
        
        if self.hide_empty:
            group_empty.hide_viewport = True

        # Parent objects
        for obj in selected_objects:
            if obj != group_empty:
                # Keep transform
                mat = obj.matrix_world.copy()
                obj.parent = group_empty
                obj.matrix_parent_inverse = group_empty.matrix_world.inverted()
                # Ensure visual transform is kept (redundant with matrix_parent_inverse but safe)
                obj.matrix_world = mat

        # Select the group empty
        bpy.ops.object.select_all(action='DESELECT')
        group_empty.select_set(True)
        context.view_layer.objects.active = group_empty

        return {'FINISHED'}

def is_m8_group(obj):
    if not obj: return False
    # Check for custom property
    if obj.get("m8_is_group"): return True
    # Check for Empty with children (legacy or manual groups)
    if obj.type == 'EMPTY' and len(obj.children) > 0: return True
    return False

class M8_OT_DissolveGroup(bpy.types.Operator):
    bl_idname = "m8.dissolve_group"
    bl_label = "解散组"
    bl_description = "解除组绑定并删除组父物体"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and is_m8_group(context.active_object)

    def execute(self, context):
        group_obj = context.active_object
        
        # Collect children
        children = group_obj.children_recursive
        
        # Unparent children keeping transform
        for child in children:
            if child.parent == group_obj:
                matrix = child.matrix_world.copy()
                child.parent = None
                child.matrix_world = matrix
        
        # Delete group object
        bpy.ops.object.select_all(action='DESELECT')
        group_obj.select_set(True)
        bpy.ops.object.delete()
        
        # Select children back
        for child in children:
            child.select_set(True)
            
        if children:
            context.view_layer.objects.active = children[0]
            
        return {'FINISHED'}

class M8_OT_AddToGroup(bpy.types.Operator):
    bl_idname = "m8.add_to_group"
    bl_label = "加入到组"
    bl_description = "将选中物体加入到激活的组中"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT' or not context.selected_objects:
            return False
        # Active object must be a group or belong to a group
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        target_group = None
        obj = context.active_object
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        selected = context.selected_objects
        added_count = 0
        
        for o in selected:
            if o == target_group: continue
            if o.parent == target_group: continue
            
            # Keep transform
            mat = o.matrix_world.copy()
            o.parent = target_group
            o.matrix_parent_inverse = target_group.matrix_world.inverted()
            o.matrix_world = mat
            added_count += 1
            
        if added_count > 0:
            self.report({'INFO'}, f"Added {added_count} objects to {target_group.name}")
            return {'FINISHED'}
        
        return {'CANCELLED'}

class M8_OT_RemoveFromGroup(bpy.types.Operator):
    bl_idname = "m8.remove_from_group"
    bl_label = "从组中移除"
    bl_description = "将选中物体从组中移除"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT' or not context.selected_objects:
            return False
        # At least one selected object must have a parent that is a group
        for o in context.selected_objects:
            if o.parent and is_m8_group(o.parent):
                return True
        return False

    def execute(self, context):
        removed_count = 0
        for o in context.selected_objects:
            if o.parent and is_m8_group(o.parent):
                mat = o.matrix_world.copy()
                o.parent = None
                o.matrix_world = mat
                removed_count += 1
        
        if removed_count > 0:
            self.report({'INFO'}, f"Removed {removed_count} objects from group")
            return {'FINISHED'}
            
        return {'CANCELLED'}

class M8_OT_SetGroupOrigin(bpy.types.Operator):
    bl_idname = "m8.set_group_origin"
    bl_label = "设置组原点"
    bl_description = "将组原点设置到3D游标位置（不移动子物体）"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            self.report({'WARNING'}, "未找到组对象")
            return {'CANCELLED'}
            
        cursor_loc = context.scene.cursor.location
        
        # Store children world matrices
        children = target_group.children
        child_matrices = {c: c.matrix_world.copy() for c in children}
        
        # Move parent to cursor
        # Use matrix assignment to be safe and ensure update
        mw = target_group.matrix_world.copy()
        mw.translation = cursor_loc
        target_group.matrix_world = mw
        
        # Force update dependency graph
        context.view_layer.update()
        
        # Restore children world matrices
        for c in children:
            if c in child_matrices:
                c.matrix_world = child_matrices[c]
            
        return {'FINISHED'}

class M8_OT_RecalculateGroupCenter(bpy.types.Operator):
    bl_idname = "m8.recalculate_group_center"
    bl_label = "重算中心点"
    bl_description = "将组父物体移动到所有子物体的中心（不移动子物体）"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        children = [c for c in target_group.children]
        if not children:
            return {'CANCELLED'}
            
        # Calc center (average of children locations)
        center = Vector((0.0, 0.0, 0.0))
        for c in children:
            center += c.matrix_world.translation
        center /= len(children)
        
        # Store children world matrices
        child_matrices = {c: c.matrix_world.copy() for c in children}
        
        # Move parent
        target_group.matrix_world.translation = center
        
        # Restore children world matrices
        for c in children:
            c.matrix_world = child_matrices[c]
            
        return {'FINISHED'}

class M8_OT_SelectGroupParent(bpy.types.Operator):
    bl_idname = "m8.select_group_parent"
    bl_label = "仅选择组父级"
    bl_description = "只选择组的父物体"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        bpy.ops.object.select_all(action='DESELECT')
        target_group.select_set(True)
        context.view_layer.objects.active = target_group
        return {'FINISHED'}

class M8_OT_LockGroup(bpy.types.Operator):
    bl_idname = "m8.lock_group"
    bl_label = "锁定组 (子物体不可选)"
    bl_description = "使所有子物体不可选中 (只有父物体可选)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        children = target_group.children_recursive
        for c in children:
            c.hide_select = True
            
        # Ensure parent is selected and active
        bpy.ops.object.select_all(action='DESELECT')
        target_group.hide_select = False
        target_group.select_set(True)
        context.view_layer.objects.active = target_group
        
        self.report({'INFO'}, f"Group locked: {target_group.name}")
        return {'FINISHED'}

class M8_OT_UnlockGroup(bpy.types.Operator):
    bl_idname = "m8.unlock_group"
    bl_label = "解锁组"
    bl_description = "使所有子物体可选中"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        children = target_group.children_recursive
        for c in children:
            c.hide_select = False
            
        self.report({'INFO'}, f"Group unlocked: {target_group.name}")
        return {'FINISHED'}

class M8_OT_DuplicateGroup(bpy.types.Operator):
    bl_idname = "m8.duplicate_group"
    bl_label = "复制组层级"
    bl_description = "复制组及其所有子物体"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        # Select Hierarchy
        bpy.ops.object.select_all(action='DESELECT')
        target_group.select_set(True)
        context.view_layer.objects.active = target_group
        bpy.ops.object.select_grouped(type='CHILDREN_RECURSIVE')
        target_group.select_set(True)
        
        # Duplicate
        bpy.ops.object.duplicate(linked=False)
        
        new_group = context.active_object
        self.report({'INFO'}, f"Group duplicated: {new_group.name}")
        return {'FINISHED'}

class M8_OT_HideGroup(bpy.types.Operator):
    bl_idname = "m8.hide_group"
    bl_label = "隐藏组"
    bl_description = "隐藏组及其所有子物体"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        target_group.hide_viewport = True
        children = target_group.children_recursive
        for c in children:
            c.hide_viewport = True
            
        self.report({'INFO'}, f"Group hidden: {target_group.name}")
        return {'FINISHED'}

class M8_OT_IsolateGroup(bpy.types.Operator):
    bl_idname = "m8.isolate_group"
    bl_label = "隔离组"
    bl_description = "隐藏除当前组以外的所有物体"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group:
            return {'CANCELLED'}
            
        # Collect all objects to keep
        keep_objects = {target_group}
        keep_objects.update(target_group.children_recursive)
        
        # Iterate all objects in scene (or visible ones)
        # Better: iterate all objects in view layer
        for o in context.view_layer.objects:
            if o not in keep_objects:
                o.hide_viewport = True
            else:
                o.hide_viewport = False
                
        self.report({'INFO'}, f"Group isolated: {target_group.name}")
        return {'FINISHED'}

class M8_OT_ShowAllGroups(bpy.types.Operator):
    bl_idname = "m8.show_all_groups"
    bl_label = "显示全部"
    bl_description = "显示场景中的所有物体"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        for o in context.view_layer.objects:
            o.hide_viewport = False
        self.report({'INFO'}, "All objects shown")
        return {'FINISHED'}

class M8_OT_ToggleGroupEmptyVisibility(bpy.types.Operator):
    bl_idname = "m8.toggle_group_empty_visibility"
    bl_label = "显示/隐藏组空物体"
    bl_description = "切换组父物体(Empty)的可见性"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT': return False
        obj = context.active_object
        if not obj: return False
        return is_m8_group(obj) or (obj.parent and is_m8_group(obj.parent))

    def execute(self, context):
        obj = context.active_object
        target_group = None
        if is_m8_group(obj):
            target_group = obj
        elif obj.parent and is_m8_group(obj.parent):
            target_group = obj.parent
            
        if not target_group: return {'CANCELLED'}
        
        target_group.hide_viewport = not target_group.hide_viewport
        return {'FINISHED'}

class M8_MT_GroupContextSubMenu(bpy.types.Menu):
    bl_label = "M8 组工具"
    bl_idname = "M8_MT_GroupContextSubMenu"

    def draw(self, context):
        layout = self.layout
        layout.operator("m8.select_group", text="选择组层级")
        layout.operator("m8.select_group_parent", text="仅选择组父级")
        layout.separator()
        layout.operator("m8.duplicate_group", text="复制组层级")
        layout.separator()
        layout.operator("m8.isolate_group", text="隔离组 (隐藏其他)")
        layout.operator("m8.hide_group", text="隐藏组")
        layout.operator("m8.toggle_group_empty_visibility", text="显示/隐藏组空物体")
        layout.operator("m8.show_all_groups", text="显示全部")
        layout.separator()
        layout.operator("m8.recalculate_group_center", text="重算中心点")
        layout.operator("m8.set_group_origin", text="设置组原点 (到游标)")
        layout.operator("m8.dissolve_group", text="解散组")
        layout.separator()
        layout.operator("m8.add_to_group", text="加入到组")
        layout.operator("m8.remove_from_group", text="从组中移除")
        layout.separator()
        layout.operator("m8.lock_group", text="锁定组 (子物体不可选)")
        layout.operator("m8.unlock_group", text="解锁组")

def draw_group_context_menu(self, context):
    obj = context.active_object
    if not obj: return
    
    is_group = is_m8_group(obj)
    has_group_parent = obj.parent and is_m8_group(obj.parent)
    
    if is_group or has_group_parent:
        self.layout.separator()
        self.layout.menu("M8_MT_GroupContextSubMenu", icon='EMPTY_AXIS')

class M8_OT_SelectGroup(bpy.types.Operator):
    bl_idname = "m8.select_group"
    bl_label = "选择组"
    bl_options = {'REGISTER', 'UNDO'}

    def _get_pref(self):
        root_pkg = (__package__ or "").split(".")[0]
        addon = bpy.context.preferences.addons.get(root_pkg)
        return addon.preferences if addon else None

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == "VIEW_3D"

    def _select_hierarchy(self, context, group_obj):
        # Deselect all first
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select Group
        group_obj.select_set(True)
        context.view_layer.objects.active = group_obj
        
        # Select Hierarchy (Children Recursive)
        bpy.ops.object.select_grouped(type='CHILDREN_RECURSIVE')
        
        # Ensure group is active and selected
        group_obj.select_set(True)
        context.view_layer.objects.active = group_obj

    def execute(self, context):
        # Called from Menu
        obj = context.active_object
        if is_m8_group(obj):
            self._select_hierarchy(context, obj)
            return {'FINISHED'}
        return {'CANCELLED'}

    def invoke(self, context, event):
        # 最终确认：是否启用了该功能？
        pref = self._get_pref()
        
        # Fallback for getting preferences
        if not pref:
             try:
                 # 尝试通过包名获取
                 addon_name = __name__.split(".")[0]
                 pref = context.preferences.addons[addon_name].preferences
             except Exception:
                 pass
        
        if not pref or not getattr(pref, "activate_double_click_select_group", False):
            return {'PASS_THROUGH'}
        
        if context.mode != 'OBJECT':
             return {'PASS_THROUGH'}

        if not hasattr(event, "mouse_region_x") or not hasattr(event, "mouse_region_y"):
            return {'PASS_THROUGH'}

        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        
        try:
             hit, location, normal, index, obj, matrix = mouse_2d_ray_cast(context, mouse)
        except Exception as e:
             return {'PASS_THROUGH'}
        
        if not hit:
            if context.active_object:
                obj = context.active_object
            else:
                return {'PASS_THROUGH'}
        
        if not obj:
             if context.active_object:
                 obj = context.active_object
             else:
                 return {'PASS_THROUGH'}

        # Double click logic:
        # If we clicked a child -> Select Parent Group + Hierarchy
        # If we clicked the Group itself -> Select Hierarchy
        
        target = None
        if obj.parent and is_m8_group(obj.parent):
             target = obj.parent
        elif is_m8_group(obj):
             target = obj
             
        if target:
            # Check if shift is held (extend selection) - For now, let's stick to simple hierarchy selection
            # The user requested "Double click select group is select parent object including child objects"
            self._select_hierarchy(context, target)
            return {'FINISHED'}
            
        return {'PASS_THROUGH'}
