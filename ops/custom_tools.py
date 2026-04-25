import bpy
import bmesh
from mathutils import Matrix, Vector

# 1. 材质排序
class M8_OT_SortMaterials(bpy.types.Operator):
    bl_idname = "m8.sort_materials"
    bl_label = "材质排序"
    bl_description = "重新排序物体材质并修复面索引"
    bl_options = {'REGISTER', 'UNDO'}

    sort_mode: bpy.props.EnumProperty(
        name="排序方式",
        items=[
            ('NAME_ASC', "名称 (A-Z)", "按材质名称升序排列"),
            ('NAME_DESC', "名称 (Z-A)", "按材质名称降序排列"),
            ('COUNT_DESC', "面数 (多->少)", "使用面数多的排在前面"),
            ('COUNT_ASC', "面数 (少->多)", "使用面数少的排在前面"),
        ],
        default='NAME_ASC'
    )

    remove_unused: bpy.props.BoolProperty(
        name="移除未使用材质",
        description="移除未分配给任何面的材质槽",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        # 如果从面板点击，尝试同步 Scene 属性到 Operator
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            self.sort_mode = props.sort_mode
            self.remove_unused = props.remove_unused
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        
        # 1. 统计每个材质的使用面数，并记录每个面当前对应的材质对象
        face_material_map = []
        mat_usage_count = {} # {Material: count}
        
        # 初始化计数器 (包括所有槽位中的材质，防止某些材质虽然有槽但没面用到，如果不想移除的话需要保留)
        for slot in obj.material_slots:
            if slot.material:
                mat_usage_count[slot.material] = 0

        for f in mesh.polygons:
            # 获取该面当前关联的材质对象
            mat = None
            if f.material_index < len(obj.material_slots):
                mat = obj.material_slots[f.material_index].material
            
            face_material_map.append(mat)
            
            if mat:
                if mat not in mat_usage_count:
                    mat_usage_count[mat] = 0
                mat_usage_count[mat] += 1

        # 2. 获取待处理的材质列表
        # 根据是否移除未使用来筛选
        valid_mats = []
        for slot in obj.material_slots:
            mat = slot.material
            if not mat:
                continue
            
            count = mat_usage_count.get(mat, 0)
            if self.remove_unused and count == 0:
                continue
            
            valid_mats.append(mat)

        # 去重
        unique_mats = list(set(valid_mats))

        # 3. 排序
        if self.sort_mode == 'NAME_ASC':
            sorted_mats = sorted(unique_mats, key=lambda m: m.name)
        elif self.sort_mode == 'NAME_DESC':
            sorted_mats = sorted(unique_mats, key=lambda m: m.name, reverse=True)
        elif self.sort_mode == 'COUNT_DESC':
            sorted_mats = sorted(unique_mats, key=lambda m: mat_usage_count.get(m, 0), reverse=True)
        elif self.sort_mode == 'COUNT_ASC':
            sorted_mats = sorted(unique_mats, key=lambda m: mat_usage_count.get(m, 0))
        else:
            sorted_mats = sorted(unique_mats, key=lambda m: m.name)

        # 4. 重置物体的材质槽
        obj.data.materials.clear()
        for mat in sorted_mats:
            obj.data.materials.append(mat)

        # 5. 重新分配面的索引
        for i, f in enumerate(mesh.polygons):
            original_mat = face_material_map[i]
            
            # 如果面原来的材质还在新列表中（可能因为移除未使用而被删掉了，或者本来就是None）
            if original_mat in sorted_mats:
                f.material_index = sorted_mats.index(original_mat)
            else:
                # 如果原来的材质被移除了（比如它是未使用的，但逻辑上不应该发生，因为是按面统计的）
                # 或者原来的材质是None
                # 或者原来的材质虽然有面用，但被强制移除了（不应该发生）
                # 默认给第一个，如果没有材质槽了就0
                f.material_index = 0
        
        self.report({'INFO'}, f"材质排序完成: {obj.name} (模式: {self.sort_mode})")
        return {'FINISHED'}

# 2. 合并相近物体
class M8_OT_MergeNearbyObjects(bpy.types.Operator):
    bl_idname = "m8.merge_nearby_objects"
    bl_label = "合并相近物体"
    bl_description = "合并距离小于阈值的物体"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(
        name="合并距离数值",
        default=0.1,
        min=0.00001,
        description="物体几何中心距离小于此值时合并",
        precision=3
    )

    unit: bpy.props.EnumProperty(
        name="单位",
        items=[
            ('M', "米 (m)", "Meters"),
            ('CM', "厘米 (cm)", "Centimeters"),
            ('MM', "毫米 (mm)", "Millimeters"),
        ],
        default='M'
    )

    @classmethod
    def poll(cls, context):
        return len([obj for obj in context.selected_objects if obj.type == 'MESH']) >= 2

    def invoke(self, context, event):
        # 如果从面板点击，尝试同步 Scene 属性到 Operator
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            self.threshold = props.merge_threshold
            self.unit = props.merge_unit
        return self.execute(context)

    def execute(self, context):
        # 确保在物体模式
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        # 计算实际阈值（转换为米）
        scale = 1.0
        if self.unit == 'CM':
            scale = 0.01
        elif self.unit == 'MM':
            scale = 0.001
        
        actual_threshold = self.threshold * scale

        selected_names = [obj.name for obj in context.selected_objects if obj.type == 'MESH']
        merged_count = 0

        # 辅助函数：获取物体世界坐标下的几何中心
        def get_world_center(obj):
            local_bbox_center = 0.125 * sum((Vector(b) for b in obj.bound_box), Vector())
            return obj.matrix_world @ local_bbox_center

        while selected_names:
            current_name = selected_names.pop(0)
            obj = bpy.data.objects.get(current_name)
            if not obj:
                continue
            
            # 获取当前物体的几何中心
            center_a = get_world_center(obj)
                
            to_merge = [obj]
            others_to_remove_from_list = []

            for other_name in selected_names:
                other_obj = bpy.data.objects.get(other_name)
                if not other_obj:
                    continue
                
                # 获取对比物体的几何中心
                center_b = get_world_center(other_obj)
                
                # 计算几何中心距离，而不是原点距离
                dist = (center_a - center_b).length
                
                if dist <= actual_threshold:
                    to_merge.append(other_obj)
                    others_to_remove_from_list.append(other_name)
            
            if len(to_merge) > 1:
                bpy.ops.object.select_all(action='DESELECT')
                for o in to_merge:
                    o.select_set(True)
                
                context.view_layer.objects.active = to_merge[0]
                bpy.ops.object.join()
                merged_count += 1
                
                for name in others_to_remove_from_list:
                    if name in selected_names:
                        selected_names.remove(name)

        self.report({'INFO'}, f"合并完成，共进行了 {merged_count} 组合并。")
        return {'FINISHED'}

# 3. 批量复制并对齐
class M8_OT_BatchCopyAlign(bpy.types.Operator):
    bl_idname = "m8.batch_copy_align"
    bl_label = "批量复制并对齐"
    bl_description = "将激活物体复制并对齐到其他选中物体"
    bl_options = {'REGISTER', 'UNDO'}

    remove_target: bpy.props.BoolProperty(name="删除目标物体", default=False)
    hide_target: bpy.props.BoolProperty(name="隐藏目标物体", default=True)
    move_target: bpy.props.BoolProperty(name="移动到集合", default=False)

    @classmethod
    def poll(cls, context):
        return context.active_object and len(context.selected_objects) > 1

    def invoke(self, context, event):
        # 如果从面板点击，尝试同步 Scene 属性到 Operator
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            mode = props.copy_align_mode
            
            if mode == 'REMOVE':
                self.remove_target = True
                self.hide_target = False
                self.move_target = False
            elif mode == 'HIDE':
                self.remove_target = False
                self.hide_target = True
                self.move_target = False
            elif mode == 'MOVE':
                self.remove_target = False
                self.hide_target = False
                self.move_target = True
            else: # KEEP
                self.remove_target = False
                self.hide_target = False
                self.move_target = False
                
        return self.execute(context)

    def execute(self, context):
        source_obj = context.active_object
        targets = [obj for obj in context.selected_objects if obj != source_obj]
        
        if not targets:
            self.report({'WARNING'}, "请至少选择一个目标物体，最后再加选源物体。")
            return {'CANCELLED'}

        # 准备移动集合
        backup_col = None
        if self.move_target:
            col_name = "M8_Backup"
            backup_col = bpy.data.collections.get(col_name)
            if not backup_col:
                backup_col = bpy.data.collections.new(col_name)
                context.scene.collection.children.link(backup_col)

        created_objects = []

        for target in targets:
            new_obj = source_obj.copy()
            context.collection.objects.link(new_obj)
            new_obj.matrix_world = target.matrix_world
            created_objects.append(new_obj)
            
            if self.remove_target:
                bpy.data.objects.remove(target, do_unlink=True)
            elif self.hide_target:
                target.hide_viewport = True
                target.hide_render = True
            elif self.move_target and backup_col:
                # 移动目标物体到备份集合
                try:
                    # 先链接到新集合
                    if backup_col.name not in [c.name for c in target.users_collection]:
                        backup_col.objects.link(target)
                    # 从旧集合移除
                    for col in target.users_collection:
                        if col != backup_col:
                            col.objects.unlink(target)
                except Exception as e:
                    print(f"移动物体出错: {e}")

        bpy.ops.object.select_all(action='DESELECT')
        for obj in created_objects:
            obj.select_set(True)
        
        context.view_layer.objects.active = source_obj
        self.report({'INFO'}, f"完成！已生成 {len(created_objects)} 个新物体。")
        return {'FINISHED'}

# 4. 原点对齐法向
class M8_OT_AlignOriginToNormal(bpy.types.Operator):
    bl_idname = "m8.align_origin_to_normal"
    bl_label = "原点对齐法向"
    bl_description = "将物体原点方向对齐到编辑模式下的平均法向"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        selected_objs = [obj for obj in context.selected_objects if obj.type == 'MESH']
        count = 0

        for obj in selected_objs:
            mesh = obj.data
            mw = obj.matrix_world.copy()
            
            bm = bmesh.new()
            bm.from_mesh(mesh)
            avg_normal = Vector((0, 0, 0))
            if bm.faces:
                for face in bm.faces:
                    avg_normal += face.normal
                avg_normal.normalize()
            else:
                bm.free()
                continue

            if avg_normal.length < 0.0001:
                bm.free()
                continue

            rot_quat = Vector((0, 0, 1)).rotation_difference(avg_normal)
            rot_mat = rot_quat.to_matrix().to_4x4()

            loc, rot, scale = mw.decompose()
            new_rot = rot @ rot_quat
            
            bm.transform(rot_mat.inverted())
            bm.to_mesh(mesh)
            bm.free()

            obj.matrix_world = Matrix.LocRotScale(loc, new_rot, scale)
            mesh.update()
            count += 1

        self.report({'INFO'}, f"处理完成：{count} 个物体已对齐。")
        return {'FINISHED'}

class M8_CustomTools_Props(bpy.types.PropertyGroup):
    sort_mode: bpy.props.EnumProperty(
        name="排序方式",
        items=[
            ('NAME_ASC', "名称 (A-Z)", "按材质名称升序排列"),
            ('NAME_DESC', "名称 (Z-A)", "按材质名称降序排列"),
            ('COUNT_DESC', "面数 (多->少)", "使用面数多的排在前面"),
            ('COUNT_ASC', "面数 (少->多)", "使用面数少的排在前面"),
        ],
        default='NAME_ASC'
    )

    remove_unused: bpy.props.BoolProperty(
        name="移除未使用材质",
        description="移除未分配给任何面的材质槽",
        default=True
    )

    merge_threshold: bpy.props.FloatProperty(
        name="合并距离",
        default=0.1,
        min=0.00001,
        description="物体几何中心距离小于此值时合并",
        step=1,
        precision=3
    )

    merge_unit: bpy.props.EnumProperty(
        name="单位",
        items=[
            ('M', "米 (m)", "Meters"),
            ('CM', "厘米 (cm)", "Centimeters"),
            ('MM', "毫米 (mm)", "Millimeters"),
        ],
        default='M'
    )

    copy_align_mode: bpy.props.EnumProperty(
        name="目标处理",
        items=[
            ('HIDE', "隐藏目标", "隐藏被复制的目标物体"),
            ('REMOVE', "删除目标", "删除被复制的目标物体"),
            ('MOVE', "移动到集合", "将目标物体移动到 'M8_Backup' 集合中"),
            ('KEEP', "保留目标", "保留被复制的目标物体"),
        ],
        default='HIDE'
    )

# 5. 面板类
class VIEW3D_PT_M8_CustomTools(bpy.types.Panel):
    bl_label = "M8 常用工具"
    bl_idname = "VIEW3D_PT_m8_custom_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm8'  # 保持和 M8 其他面板在同一个标签页
    bl_order = 1 # 靠前显示
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        
        # 材质工具
        col = layout.column(align=True)
        col.label(text="材质工具", icon='MATERIAL')
        
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            col.prop(props, "sort_mode", text="")
            col.prop(props, "remove_unused")
        
        col.operator("m8.sort_materials", icon='SORTALPHA', text="执行排序")
        
        col.separator()
        col.label(text="物体合并", icon='GROUP')
        
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            row = col.row(align=True)
            row.prop(props, "merge_threshold")
            row.prop(props, "merge_unit", text="")

        col.operator("m8.merge_nearby_objects", icon='MOD_BUILD', text="执行合并")
        
        col.separator()
        col.label(text="复制与对齐", icon='DUPLICATE')
        
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            col.prop(props, "copy_align_mode", text="")

        col.operator("m8.batch_copy_align", icon='COPYDOWN', text="批量复制")
        col.operator("m8.align_origin_to_normal", icon='ORIENTATION_NORMAL', text="原点对齐法向")
