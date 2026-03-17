import bpy
import uuid
from mathutils import Vector, Matrix
from ...utils import (
    ensure_object_mode,
    is_size_cage,
    get_backup_suffix,
    get_or_create_collection,
    get_backup_collection_name,
    move_object_to_collection,
    get_archive_default_bake,
    matrix_world_to_tuple16,
    tuple16_to_matrix_world,
    get_transparent_material,
    call_object_op_with_selection,
    CAGE_TAG_KEY,
    SNAP_GROUP_KEY,
    SNAP_MATRIX_WORLD_KEY,
    SNAP_APPLIED_SCALE_KEY,
    SNAP_SIZE_KEY,
    SNAP_LOC_KEY,
    CAGE_ORIG_SIZE_KEY
)

def _selected_meshes(context):
    return [obj for obj in context.selected_objects if obj.type == 'MESH']

def _targets_from_context(context):
    obj = context.active_object
    selected = _selected_meshes(context)
    if selected:
        return selected
    if obj and obj.type == 'MESH':
        return [obj]
    if obj and is_size_cage(obj):
        return [c for c in obj.children if c.type == 'MESH']
    return []

def _expand_by_group(context, targets):
    group_ids = {obj.get(SNAP_GROUP_KEY) for obj in targets if obj.get(SNAP_GROUP_KEY)}
    if not group_ids:
        return {None: targets}
    group_to_targets = {}
    for gid in group_ids:
        group_to_targets[gid] = [
            obj for obj in context.scene.objects
            if obj.type == 'MESH' and obj.get(SNAP_GROUP_KEY) == gid
        ]
    return group_to_targets

def _archive_cage(cage):
    if not cage:
        return
    suffix = get_backup_suffix()
    if CAGE_TAG_KEY in cage:
        del cage[CAGE_TAG_KEY]
    base_name = cage.name
    if base_name.endswith(suffix):
        new_name = base_name
    else:
        new_name = f"{base_name}{suffix}"
    cage.name = new_name
    cage.hide_render = True
    cage.hide_select = True
    try:
        cage.hide_set(True)
    except Exception:
        cage.hide_viewport = True
    backup_coll = get_or_create_collection(get_backup_collection_name())
    backup_coll.hide_render = True
    backup_coll.hide_viewport = True
    move_object_to_collection(cage, backup_coll)

def _unarchive_cage(cage):
    if not cage:
        return
    suffix = get_backup_suffix()
    if cage.name.endswith(suffix):
        cage.name = cage.name[: -len(suffix)]
    cage[CAGE_TAG_KEY] = 1
    cage.display_type = 'WIRE'
    cage.show_in_front = True
    cage.hide_render = True
    cage.hide_select = False
    try:
        cage.hide_set(False)
    except Exception:
        cage.hide_viewport = False

class OBJECT_OT_CreateCage(bpy.types.Operator):
    bl_idname = "object.create_size_cage"
    bl_label = "1. 创建调节盒"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ensure_object_mode(context)
        selected_objs = _selected_meshes(context)
        if not selected_objs:
            self.report({'WARNING'}, "请先选中至少一个网格物体")
            return {'CANCELLED'}

        # Optimization: Check if already has a cage parent?
        # If so, maybe warn or skip?
        # For now, allow nesting or re-caging.
        
        group_id = uuid.uuid4().hex

        all_coords = []
        valid_objs = []
        for obj in selected_objs:
            # Ensure we can read bounding box
            if not getattr(obj, "bound_box", None):
                continue
            
            obj[SNAP_GROUP_KEY] = group_id
            obj[SNAP_MATRIX_WORLD_KEY] = matrix_world_to_tuple16(obj.matrix_world)
            for v in obj.bound_box:
                all_coords.append(obj.matrix_world @ Vector(v))
            valid_objs.append(obj)
            
        if not all_coords:
             self.report({'WARNING'}, "无法获取选中物体的边界信息")
             return {'CANCELLED'}

        min_c = Vector((min(c.x for c in all_coords), min(c.y for c in all_coords), min(c.z for c in all_coords)))
        max_c = Vector((max(c.x for c in all_coords), max(c.y for c in all_coords), max(c.z for c in all_coords)))
        pad = float(getattr(context.scene, "size_tool_padding", 0.0) or 0.0)
        if pad > 0:
            p = Vector((pad, pad, pad))
            min_c -= p
            max_c += p
        center = (min_c + max_c) / 2
        size = max_c - min_c
        
        # Ensure non-zero size for stability
        size.x = max(size.x, 0.001)
        size.y = max(size.y, 0.001)
        size.z = max(size.z, 0.001)

        bpy.ops.mesh.primitive_cube_add(location=center)
        cage = context.active_object
        cage.name = "Dimension_Control_Box"
        cage[CAGE_TAG_KEY] = 1
        cage[SNAP_GROUP_KEY] = group_id

        cage[CAGE_ORIG_SIZE_KEY] = size
        cage.dimensions = size
        
        call_object_op_with_selection(
            context,
            bpy.ops.object.transform_apply,
            active_object=cage,
            selected_objects=[cage],
            scale=True,
            location=False,
            rotation=False,
        )

        cage.display_type = 'WIRE'
        cage.show_in_front = True
        cage.hide_render = True
        if hasattr(cage, "color"):
             cage.color = (1.0, 0.5, 0.0, 1.0) # Optional: Set color for visibility
        
        # Use existing material if possible or create new only if needed
        mat = get_transparent_material()
        if mat:
            if not cage.data.materials:
                cage.data.materials.append(mat)
            else:
                cage.data.materials[0] = mat

        for obj in valid_objs:
            obj[SNAP_SIZE_KEY] = tuple(size)
            obj[SNAP_LOC_KEY] = tuple(center)

        # Parent with keep transform
        call_object_op_with_selection(
            context,
            bpy.ops.object.parent_set,
            active_object=cage,
            selected_objects=[*valid_objs, cage],
            type='OBJECT',
            keep_transform=True,
        )

        context.view_layer.objects.active = cage
        self.report({'INFO'}, f"已为 {len(valid_objs)} 个物体创建调节盒")
        return {'FINISHED'}

class OBJECT_OT_UpdateSnapshot(bpy.types.Operator):
    bl_idname = "object.update_size_snapshot"
    bl_label = "保存快照(当前)"
    bl_description = "将当前选中物体（或调节盒子物体）的状态写回为新的快照基准"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ensure_object_mode(context)
        targets = _targets_from_context(context)
        if not targets:
            self.report({'WARNING'}, "请选中至少一个网格物体或调节盒")
            return {'CANCELLED'}

        group_to_targets = _expand_by_group(context, targets)
        updated = 0
        for gid, group_targets in group_to_targets.items():
            if gid is None:
                gid = uuid.uuid4().hex
                for obj in group_targets:
                    obj[SNAP_GROUP_KEY] = gid

            all_coords = []
            for obj in group_targets:
                obj[SNAP_GROUP_KEY] = gid
                obj[SNAP_MATRIX_WORLD_KEY] = matrix_world_to_tuple16(obj.matrix_world)
                if SNAP_APPLIED_SCALE_KEY in obj:
                    del obj[SNAP_APPLIED_SCALE_KEY]
                for v in obj.bound_box:
                    all_coords.append(obj.matrix_world @ Vector(v))
                updated += 1

            if all_coords:
                min_c = Vector((min(c.x for c in all_coords), min(c.y for c in all_coords), min(c.z for c in all_coords)))
                max_c = Vector((max(c.x for c in all_coords), max(c.y for c in all_coords), max(c.z for c in all_coords)))
                pad = float(getattr(context.scene, "size_tool_padding", 0.0) or 0.0)
                if pad > 0:
                    p = Vector((pad, pad, pad))
                    min_c -= p
                    max_c += p
                center = (min_c + max_c) / 2
                size = max_c - min_c
                for obj in group_targets:
                    obj[SNAP_SIZE_KEY] = tuple(size)
                    obj[SNAP_LOC_KEY] = tuple(center)

        self.report({'INFO'}, f"已保存 {updated} 个物体的快照")
        return {'FINISHED'}

class OBJECT_OT_FinishDetach(bpy.types.Operator):
    bl_idname = "object.finish_detach"
    bl_label = "完成(不烘焙)"
    bl_description = "解除父级并删除调节盒，不应用缩放（更利于后续精确还原）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ensure_object_mode(context)
        cage = context.active_object
        if not is_size_cage(cage):
            self.report({'WARNING'}, "请选中当前活动的调节盒")
            return {'CANCELLED'}

        children = [child for child in cage.children]
        if not children:
            bpy.data.objects.remove(cage, do_unlink=True)
            self.report({'INFO'}, "调节盒下没有子物体，已直接清理")
            return {'FINISHED'}

        call_object_op_with_selection(
            context,
            bpy.ops.object.parent_clear,
            active_object=children[0],
            selected_objects=children,
            type='CLEAR_KEEP_TRANSFORM',
        )

        bpy.data.objects.remove(cage, do_unlink=True)
        self.report({'INFO'}, "已完成（未烘焙缩放）并清理调节盒")
        return {'FINISHED'}

class OBJECT_OT_FinishArchiveCage(bpy.types.Operator):
    bl_idname = "object.finish_archive_cage"
    bl_label = "完成(保留盒)"
    bl_description = "解除父级（可选烘焙），并把调节盒改名为备用后缀作为备用"
    bl_options = {'REGISTER', 'UNDO'}

    bake: bpy.props.BoolProperty(
        name="烘焙缩放",
        default=False,
    )

    def invoke(self, context, event):
        self.bake = get_archive_default_bake()
        return self.execute(context)

    def execute(self, context):
        ensure_object_mode(context)
        cage = context.active_object
        if not is_size_cage(cage):
            self.report({'WARNING'}, "请选中当前活动的调节盒")
            return {'CANCELLED'}

        children = [child for child in cage.children]
        if children:
            call_object_op_with_selection(
                context,
                bpy.ops.object.parent_clear,
                active_object=children[0],
                selected_objects=children,
                type='CLEAR_KEEP_TRANSFORM',
            )

            if self.bake:
                for child in children:
                    try:
                        child[SNAP_APPLIED_SCALE_KEY] = (float(child.scale.x), float(child.scale.y), float(child.scale.z))
                    except Exception:
                        pass
                call_object_op_with_selection(
                    context,
                    bpy.ops.object.transform_apply,
                    active_object=children[0],
                    selected_objects=children,
                    scale=True,
                    location=False,
                    rotation=False,
                )

        _archive_cage(cage)
        self.report({'INFO'}, f"已完成并保留备用盒（后缀 {get_backup_suffix()}）")
        return {'FINISHED'}

class OBJECT_OT_ActivateBackupCage(bpy.types.Operator):
    bl_idname = "object.activate_backup_cage"
    bl_label = "启用备用盒"
    bl_description = "将选中的备用调节盒恢复为可用调节盒（取消隐藏/不可选）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ensure_object_mode(context)
        suffix = get_backup_suffix()
        candidates = [o for o in context.selected_objects if o.name.endswith(suffix)]
        if not candidates and context.active_object and context.active_object.name.endswith(suffix):
            candidates = [context.active_object]
        if not candidates:
            self.report({'WARNING'}, f"请选中备用调节盒（名称以 {suffix} 结尾）")
            return {'CANCELLED'}

        scene_coll = context.scene.collection
        activated = 0
        for cage in candidates:
            desired = cage.name[: -len(suffix)]
            name = desired
            i = 1
            while bpy.data.objects.get(name) and bpy.data.objects.get(name) != cage:
                name = f"{desired}.{i:03d}"
                i += 1
            cage.name = name
            _unarchive_cage(cage)
            move_object_to_collection(cage, scene_coll)
            activated += 1

        self.report({'INFO'}, f"已启用 {activated} 个备用盒")
        return {'FINISHED'}

class OBJECT_OT_ToggleBackupVisibility(bpy.types.Operator):
    bl_idname = "object.toggle_backup_visibility"
    bl_label = "显示/隐藏备用盒"
    bl_description = "切换备用盒集合的显示状态"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        coll = bpy.data.collections.get(get_backup_collection_name())
        if not coll:
            self.report({'WARNING'}, "未找到备用盒集合")
            return {'CANCELLED'}

        new_hidden = not bool(getattr(coll, "hide_viewport", False))
        coll.hide_viewport = new_hidden
        coll.hide_render = new_hidden
        for obj in list(coll.objects):
            obj.hide_select = new_hidden
            try:
                obj.hide_set(new_hidden)
            except Exception:
                obj.hide_viewport = new_hidden

        self.report({'INFO'}, "已隐藏备用盒" if new_hidden else "已显示备用盒")
        return {'FINISHED'}

class OBJECT_OT_SelectSnapshotGroup(bpy.types.Operator):
    bl_idname = "object.select_size_snapshot_group"
    bl_label = "选择同组"
    bl_description = "选中与当前物体同一快照组的全部物体"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        suffix = get_backup_suffix()
        targets = _targets_from_context(context)
        gid = None
        for obj in targets:
            gid = obj.get(SNAP_GROUP_KEY)
            if gid:
                break
        if not gid:
            self.report({'WARNING'}, "未找到组ID：请先创建调节盒或保存快照")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        count = 0
        for obj in context.scene.objects:
            if obj.get(SNAP_GROUP_KEY) != gid:
                continue
            if obj.name.endswith(suffix):
                continue
            obj.select_set(True)
            count += 1
        if context.selected_objects:
            context.view_layer.objects.active = context.selected_objects[0]
        self.report({'INFO'}, f"已选中同组 {count} 个对象")
        return {'FINISHED'}

class OBJECT_OT_DeleteBackupCages(bpy.types.Operator):
    bl_idname = "object.delete_backup_cages"
    bl_label = "删除备用盒"
    bl_description = "删除选中的备用调节盒（不影响物体）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        suffix = get_backup_suffix()
        candidates = [o for o in context.selected_objects if o.name.endswith(suffix)]
        if not candidates and context.active_object and context.active_object.name.endswith(suffix):
            candidates = [context.active_object]
        if not candidates:
            self.report({'WARNING'}, f"请选中备用调节盒（名称以 {suffix} 结尾）")
            return {'CANCELLED'}

        for cage in candidates:
            bpy.data.objects.remove(cage, do_unlink=True)
        self.report({'INFO'}, f"已删除 {len(candidates)} 个备用盒")
        return {'FINISHED'}

class OBJECT_OT_FinishAndClean(bpy.types.Operator):
    bl_idname = "object.finish_and_clean"
    bl_label = "完成(烘焙)"
    bl_description = "应用尺寸，解除父级，并物理删除调节盒（保持场景干净）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ensure_object_mode(context)
        
        # Support multi-selection of cages
        cages = [obj for obj in context.selected_objects if is_size_cage(obj)]
        active = context.active_object
        if active and is_size_cage(active) and active not in cages:
            cages.append(active)
            
        if not cages:
            self.report({'WARNING'}, "请选中调节盒")
            return {'CANCELLED'}

        processed = 0
        for cage in cages:
            children = [child for child in cage.children]
            if not children:
                bpy.data.objects.remove(cage, do_unlink=True)
                processed += 1
                continue

            call_object_op_with_selection(
                context,
                bpy.ops.object.parent_clear,
                active_object=children[0],
                selected_objects=children,
                type='CLEAR_KEEP_TRANSFORM',
            )
            for child in children:
                try:
                    child[SNAP_APPLIED_SCALE_KEY] = (float(child.scale.x), float(child.scale.y), float(child.scale.z))
                except Exception:
                    pass
            
            # Apply scale to children
            # Note: Transform apply works on selected objects.
            # We need to ensure context is correct for each batch.
            try:
                call_object_op_with_selection(
                    context,
                    bpy.ops.object.transform_apply,
                    active_object=children[0],
                    selected_objects=children,
                    scale=True,
                    location=False,
                    rotation=False,
                )
            except Exception as e:
                print(f"Error applying transform for cage {cage.name}: {e}")

            bpy.data.objects.remove(cage, do_unlink=True)
            processed += 1

        self.report({'INFO'}, f"已清理 {processed} 个调节盒")
        return {'FINISHED'}

class OBJECT_OT_RestoreFromSnapshot(bpy.types.Operator):
    bl_idname = "object.restore_from_snapshot"
    bl_label = "还原初始比例 (重建)"
    bl_description = "根据物体内存留的快照数据，重新生成一个调节盒并还原比例"
    bl_options = {'REGISTER', 'UNDO'}

    rebuild_cage: bpy.props.BoolProperty(
        name="重建调节盒",
        default=True,
    )

    def execute(self, context):
        ensure_object_mode(context)
        targets = _targets_from_context(context)
        if not targets:
            self.report({'WARNING'}, "请选中至少一个网格物体或调节盒")
            return {'CANCELLED'}

        group_to_targets = _expand_by_group(context, targets)

        total_restored = 0
        total_missing = 0
        last_cage = None

        for gid, targets in group_to_targets.items():
            restored = []
            missing = 0
            for obj in targets:
                if SNAP_MATRIX_WORLD_KEY not in obj:
                    missing += 1
                    continue
                try:
                    # Safely clear parent if exists
                    if obj.parent:
                        # Use matrix_world to keep position before restoration?
                        # No, we want to restore to snapshot state.
                        # Snapshot state is world space.
                        # So simply clearing parent is enough.
                        mw = obj.matrix_world.copy()
                        obj.parent = None
                        obj.matrix_world = mw
                except Exception:
                    pass
                    
                try:
                    if obj.type == 'MESH' and SNAP_APPLIED_SCALE_KEY in obj:
                        sx, sy, sz = obj[SNAP_APPLIED_SCALE_KEY]
                        # Validate scale factors to avoid zero division or extreme values
                        if abs(sx) < 1e-6 or abs(sy) < 1e-6 or abs(sz) < 1e-6:
                             # Skip inverse transform if scale is invalid
                             pass
                        else:
                            inv_sx = 1.0 / sx
                            inv_sy = 1.0 / sy
                            inv_sz = 1.0 / sz
                            
                            if obj.data and getattr(obj.data, "users", 1) > 1:
                                try:
                                    obj.data = obj.data.copy()
                                except Exception:
                                    pass
                                    
                            if getattr(obj.data, "shape_keys", None):
                                # Warn but try to proceed? Or skip?
                                # Restore transform might distort shape keys if we modify mesh data.
                                # But we must invert the applied scale.
                                # Let's skip data transform for shape keys to avoid explosion.
                                print(f"Skipping data transform for {obj.name} due to Shape Keys")
                            else:
                                obj.data.transform(Matrix.Diagonal((inv_sx, inv_sy, inv_sz, 1.0)))
                                obj.data.update()
                                
                        del obj[SNAP_APPLIED_SCALE_KEY]
                        
                    obj.matrix_world = tuple16_to_matrix_world(obj[SNAP_MATRIX_WORLD_KEY])
                    restored.append(obj)
                except Exception as e:
                    print(f"Error restoring {obj.name}: {e}")
                    missing += 1

            if not restored:
                total_missing += missing
                continue

            if self.rebuild_cage:
                all_coords = []
                for obj in restored:
                    if not getattr(obj, "bound_box", None):
                        continue
                    for v in obj.bound_box:
                        all_coords.append(obj.matrix_world @ Vector(v))
                
                if not all_coords:
                    continue

                min_c = Vector((min(c.x for c in all_coords), min(c.y for c in all_coords), min(c.z for c in all_coords)))
                max_c = Vector((max(c.x for c in all_coords), max(c.y for c in all_coords), max(c.z for c in all_coords)))
                center = (min_c + max_c) / 2
                size = max_c - min_c
                
                # Ensure valid size
                size.x = max(size.x, 0.001)
                size.y = max(size.y, 0.001)
                size.z = max(size.z, 0.001)

                bpy.ops.mesh.primitive_cube_add(location=center)
                cage = context.active_object
                cage.name = "Dimension_Control_Box_Restored"
                cage[CAGE_TAG_KEY] = 1
                if gid:
                    cage[SNAP_GROUP_KEY] = gid

                cage[CAGE_ORIG_SIZE_KEY] = size
                cage.dimensions = size
                call_object_op_with_selection(
                    context,
                    bpy.ops.object.transform_apply,
                    active_object=cage,
                    selected_objects=[cage],
                    scale=True,
                    location=False,
                    rotation=False,
                )
                cage.display_type = 'WIRE'
                
                # Add material if available
                mat = get_transparent_material()
                if mat:
                    cage.data.materials.append(mat)

                call_object_op_with_selection(
                    context,
                    bpy.ops.object.parent_set,
                    active_object=cage,
                    selected_objects=[*restored, cage],
                    type='OBJECT',
                    keep_transform=True,
                )
                last_cage = cage

            total_restored += len(restored)
            total_missing += missing

        if not total_restored:
            self.report({'WARNING'}, "未找到可用的矩阵快照，无法还原比例/位置")
            return {'CANCELLED'}

        if last_cage:
            context.view_layer.objects.active = last_cage

        if total_missing:
            self.report({'INFO'}, f"已还原 {total_restored} 个物体（{total_missing} 个无法还原）")
        else:
            self.report({'INFO'}, f"已还原 {total_restored} 个物体并重建调节盒")
        return {'FINISHED'}

class OBJECT_OT_AutoAdjustZ(bpy.types.Operator):
    bl_idname = "object.auto_adjust_z"
    bl_label = "同步 Z 轴比例"

    def execute(self, context):
        cage = context.active_object
        if not cage or CAGE_ORIG_SIZE_KEY not in cage:
            return {'CANCELLED'}
        orig_x, orig_y, orig_z = cage[CAGE_ORIG_SIZE_KEY]
        curr_dims = cage.dimensions
        scale_x = curr_dims.x / orig_x if orig_x != 0 else 1.0
        scale_y = curr_dims.y / orig_y if orig_y != 0 else 1.0
        avg_scale = (scale_x + scale_y) / 2
        cage.dimensions.z = orig_z * avg_scale
        return {'FINISHED'}

class OBJECT_OT_ClearSnapshot(bpy.types.Operator):
    bl_idname = "object.clear_size_snapshot"
    bl_label = "清除快照"
    bl_description = "删除选中物体上由本工具写入的快照键（不影响几何体）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        targets = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not targets and context.active_object and context.active_object.type == 'MESH':
            targets = [context.active_object]
        if not targets:
            self.report({'WARNING'}, "请选中至少一个网格物体")
            return {'CANCELLED'}

        cleared = 0
        for obj in targets:
            removed_any = False
            for k in (SNAP_SIZE_KEY, SNAP_LOC_KEY, SNAP_MATRIX_WORLD_KEY, SNAP_GROUP_KEY, SNAP_APPLIED_SCALE_KEY):
                if k in obj:
                    del obj[k]
                    removed_any = True
            if removed_any:
                cleared += 1

        self.report({'INFO'}, f"已清除 {cleared} 个物体的快照")
        return {'FINISHED'}
