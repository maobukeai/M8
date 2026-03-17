import bpy
from mathutils import Vector, Matrix
from ...utils import ensure_object_mode, call_object_op_with_selection

class OBJECT_OT_SnapToFloor(bpy.types.Operator):
    bl_idname = "object.snap_to_floor"
    bl_label = "对齐地面"
    bl_description = "将选中物体对齐到 Z=0 平面（基于物体最低点）"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Support more types
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        processed = 0
        for obj in context.selected_objects:
            # Check supported types
            if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
                continue
            
            if not getattr(obj, "bound_box", None):
                continue
                
            bbox = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            if not bbox:
                continue
                
            min_z = min(v.z for v in bbox)

            mw = obj.matrix_world.copy()
            mw.translation.z -= min_z
            obj.matrix_world = mw
            processed += 1
            
        self.report({'INFO'}, f"已将 {processed} 个物体对齐到地面")
        return {'FINISHED'}

class OBJECT_OT_FreezeTransformsMaya(bpy.types.Operator):
    bl_idname = "object.freeze_transforms_maya"
    bl_label = "冻结变换"
    bl_options = {'REGISTER', 'UNDO'}

    freeze_location: bpy.props.BoolProperty(name="位置", description="将位置烘焙到网格并清零位置", default=True)
    freeze_rotation: bpy.props.BoolProperty(name="旋转", description="将旋转烘焙到网格并清零旋转", default=True)
    freeze_scale: bpy.props.BoolProperty(name="缩放", description="将缩放烘焙到网格并重置缩放为 1", default=True)
    make_single_user: bpy.props.BoolProperty(name="自动单用户网格", description="当多个物体共享同一网格数据时，自动复制网格，避免误影响其它物体", default=True)
    # keep_hierarchy option is removed as logic is simplified and robust without cursor hacks
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ensure_object_mode(context)
        processed = 0
        
        # Collect children that need their world transform restored
        # These are children of selected objects that are NOT selected themselves.
        children_to_restore = {}
        selected_set = set(context.selected_objects)
        
        for obj in context.selected_objects:
            if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
                continue
            for child in obj.children:
                if child not in selected_set:
                    children_to_restore[child] = child.matrix_world.copy()

        for obj in context.selected_objects:
            if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
                continue
            
            # Check for data transform capability
            if not hasattr(obj.data, "transform"):
                continue

            if self.make_single_user and obj.data and getattr(obj.data, "users", 1) > 1:
                try:
                    obj.data = obj.data.copy()
                except Exception:
                    pass

            # Calculate transform matrix to bake
            loc = obj.location.copy() if self.freeze_location else Vector((0.0, 0.0, 0.0))
            rot = obj.rotation_euler.copy() if self.freeze_rotation else obj.rotation_euler.__class__((0.0, 0.0, 0.0))
            scale = obj.scale.copy() if self.freeze_scale else Vector((1.0, 1.0, 1.0))
            
            # Matrix to apply to geometry
            # Note: This matrix represents the transform we are "removing" from the object properties
            # and "adding" to the geometry data.
            transform_matrix = Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal(scale).to_4x4()

            # Apply to geometry
            try:
                obj.data.transform(transform_matrix)
                obj.data.update()
            except Exception:
                continue

            # Reset properties
            if self.freeze_location:
                obj.location = (0.0, 0.0, 0.0)
            if self.freeze_rotation:
                obj.rotation_euler = (0.0, 0.0, 0.0)
                obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            if self.freeze_scale:
                obj.scale = (1.0, 1.0, 1.0)
             
            processed += 1

        # Restore children world transforms
        for child, old_matrix in children_to_restore.items():
            try:
                child.matrix_world = old_matrix
            except Exception:
                pass

        self.report({'INFO'}, f"已冻结 {processed} 个物体的变换")
        return {'FINISHED'}
