import bpy
import bmesh
from mathutils import Matrix, Vector
from ...utils.i18n import _T

# 1. 材质排序
class M8_OT_SortMaterials(bpy.types.Operator):
    bl_idname = "m8.sort_materials"
    bl_label = _T("材质排序")
    bl_description = _T("重新排序物体材质并修复面索引")
    bl_options = {'REGISTER', 'UNDO'}

    sort_mode: bpy.props.EnumProperty(
        name=_T("排序方式"),
        items=[
            ('NAME_ASC', _T("名称 (A-Z)"), _T("按材质名称升序排列")),
            ('NAME_DESC', _T("名称 (Z-A)"), _T("按材质名称降序排列")),
            ('COUNT_DESC', _T("面数 (多->少)"), _T("使用面数多的排在前面")),
            ('COUNT_ASC', _T("面数 (少->多)"), _T("使用面数少的排在前面")),
        ],
        default='NAME_ASC'
    )

    remove_unused: bpy.props.BoolProperty(
        name=_T("移除未使用材质"),
        description=_T("移除未分配给任何面的材质槽"),
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
        
        self.report({'INFO'}, f"{_T('材质排序完成')}: {obj.name} ({_T('模式')}: {self.sort_mode})")
        return {'FINISHED'}

# 2. 合并相近物体
class M8_OT_MergeNearbyObjects(bpy.types.Operator):
    bl_idname = "m8.merge_nearby_objects"
    bl_label = _T("合并相近物体")
    bl_description = _T("合并距离小于阈值的物体")
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(
        name=_T("合并距离数值"),
        default=0.1,
        min=0.00001,
        description=_T("物体几何中心距离小于此值时合并"),
        precision=3
    )

    unit: bpy.props.EnumProperty(
        name=_T("单位"),
        items=[
            ('M', _T("米 (m)"), "Meters"),
            ('CM', _T("厘米 (cm)"), "Centimeters"),
            ('MM', _T("毫米 (mm)"), "Millimeters"),
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
            self.merge_mode = props.merge_mode
        else:
            self.merge_mode = 'CENTER'
        return self.execute(context)

    def execute(self, context):
        import mathutils
        import bmesh
        import re
        from collections import defaultdict

        # 确保在物体模式
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        merge_mode = 'CENTER'
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            self.threshold = props.merge_threshold
            self.unit = props.merge_unit
            merge_mode = props.merge_mode

        # 计算实际阈值（转换为米）
        scale = 1.0
        if self.unit == 'CM':
            scale = 0.01
        elif self.unit == 'MM':
            scale = 0.001
        
        actual_threshold = self.threshold * scale

        # 辅助函数：获取物体世界坐标下的几何中心
        def get_world_center(obj):
            local_bbox_center = 0.125 * sum((Vector(b) for b in obj.bound_box), Vector())
            return obj.matrix_world @ local_bbox_center

        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if len(selected_meshes) < 2:
            self.report({'WARNING'}, _T("请至少选择两个网格物体"))
            return {'CANCELLED'}

        # 1. 缓存所有选定网格物体的世界中心和名称
        objs_data = []
        for obj in selected_meshes:
            objs_data.append((obj, get_world_center(obj)))

        # 2. 并查集 (Union-Find) 近邻聚类
        parent = {obj.name: obj.name for obj in selected_meshes}
        
        def find(name):
            path = []
            while parent[name] != name:
                path.append(name)
                name = parent[name]
            for node in path:
                parent[node] = name
            return name
            
        def union(name1, name2):
            root1 = find(name1)
            root2 = find(name2)
            if root1 != root2:
                parent[root1] = root2

        # 3. 根据不同的合并模式进行近邻连通分支划分
        if merge_mode == 'CENTER':
            # 3a. 构建 mathutils.kdtree.KDTree 并用几何中心进行近邻聚类
            kd = mathutils.kdtree.KDTree(len(selected_meshes))
            for idx, (obj, center) in enumerate(objs_data):
                kd.insert(center, idx)
            kd.balance()

            for idx, (obj, center) in enumerate(objs_data):
                for co, other_idx, dist in kd.find_range(center, actual_threshold):
                    if other_idx != idx:
                        union(obj.name, objs_data[other_idx][0].name)

        elif merge_mode == 'VERTEX':
            # 3b. 顶点最邻近距离：任意两物体的最近顶点间距小于阈值时合并
            total_verts = sum(len(o.data.vertices) for o in selected_meshes)
            if total_verts > 0:
                kd = mathutils.kdtree.KDTree(total_verts)
                vert_to_obj_idx = []
                v_count = 0
                for obj_idx, obj in enumerate(selected_meshes):
                    mw = obj.matrix_world
                    for v in obj.data.vertices:
                        kd.insert(mw @ v.co, v_count)
                        vert_to_obj_idx.append(obj_idx)
                        v_count += 1
                kd.balance()

                # 对每个网格的所有顶点执行范围查找进行连通合并
                for obj_idx, obj in enumerate(selected_meshes):
                    mw = obj.matrix_world
                    obj_name = obj.name
                    for v in obj.data.vertices:
                        world_co = mw @ v.co
                        for co, other_v_idx, dist in kd.find_range(world_co, actual_threshold):
                            other_obj_idx = vert_to_obj_idx[other_v_idx]
                            other_name = selected_meshes[other_obj_idx].name
                            if find(obj_name) != find(other_name):
                                union(obj_name, other_name)

        elif merge_mode == 'AABB':
            # 3c. 包围盒相交：Axis-Aligned Bounding Box (AABB) 碰撞相交时合并
            def get_world_aabb(obj):
                mw = obj.matrix_world
                coords = [mw @ Vector(b) for b in obj.bound_box]
                xs = [c.x for c in coords]
                ys = [c.y for c in coords]
                zs = [c.z for c in coords]
                return (min(xs) - actual_threshold, max(xs) + actual_threshold,
                        min(ys) - actual_threshold, max(ys) + actual_threshold,
                        min(zs) - actual_threshold, max(zs) + actual_threshold)

            aabbs = []
            for idx, obj in enumerate(selected_meshes):
                aabbs.append((get_world_aabb(obj), obj))

            # 采用 Sweep and Prune 算法 (X轴向)，以 O(N log N) 速度完成 AABB 相交性检测，彻底避免 O(N^2) 卡顿
            aabbs.sort(key=lambda x: x[0][0])
            for i in range(len(aabbs)):
                aabb_a, obj_a = aabbs[i]
                min_x_a, max_x_a, min_y_a, max_y_a, min_z_a, max_z_a = aabb_a
                for j in range(i + 1, len(aabbs)):
                    aabb_b, obj_b = aabbs[j]
                    min_x_b, max_x_b, min_y_b, max_y_b, min_z_b, max_z_b = aabb_b
                    
                    if min_x_b > max_x_a:
                        break # X 轴向无重叠可能，后续已排序的物体均不会重叠
                        
                    # 检查 Y 轴和 Z 轴重叠
                    if min_y_a <= max_y_b and max_y_a >= min_y_b:
                        if min_z_a <= max_z_b and max_z_a >= min_z_b:
                            union(obj_a.name, obj_b.name)

        elif merge_mode == 'MATERIAL':
            # 3d. 相同材质合并：共享任一材质的物体合并到同一组
            mat_to_objs = defaultdict(list)
            for obj in selected_meshes:
                if not obj.data.materials:
                    mat_to_objs["NoMaterial"].append(obj)
                else:
                    for mat in obj.data.materials:
                        if mat:
                            mat_to_objs[mat.name].append(obj)
                            
            for obj_list in mat_to_objs.values():
                for i in range(len(obj_list) - 1):
                    union(obj_list[i].name, obj_list[i+1].name)

        elif merge_mode == 'PREFIX':
            # 3e. 同命名前缀合并：按前缀归类（过滤掉 .001 等 Blender 默认后缀）
            def get_prefix(name):
                base = name.split(".")[0]
                base = re.sub(r'[_ ]\d+$', '', base)
                return base

            prefix_to_objs = defaultdict(list)
            for obj in selected_meshes:
                prefix = get_prefix(obj.name)
                prefix_to_objs[prefix].append(obj)
                
            for obj_list in prefix_to_objs.values():
                for i in range(len(obj_list) - 1):
                    union(obj_list[i].name, obj_list[i+1].name)

        # 4. 根据并查集计算的分组，获取所有需要进行物理合并的组
        clusters = defaultdict(list)
        for obj in selected_meshes:
            root = find(obj.name)
            clusters[root].append(obj)

        groups_to_merge = [group for group in clusters.values() if len(group) > 1]

        if not groups_to_merge:
            self.report({'INFO'}, _T("合并完成，共进行了 0 组合并。"))
            return {'FINISHED'}

        # 5. 执行物理合并
        # 我们使用纯 Python BMesh + 材质/顶点组重映射进行几何体合并，并直接删除源物体
        # 这比调用 Blender 笨重的 bpy.ops.object.join() 算子快百倍，面对数万物体也不会导致 UI 卡死
        merged_count = 0
        objects_to_remove = []
        meshes_to_remove = []

        # 暂时关闭全局撤销以获取最大化合并速度，结束后恢复
        undo_use = context.preferences.edit.use_global_undo
        context.preferences.edit.use_global_undo = False

        # 更新场景中所有物体的世界矩阵，确保 transform 运算的矩阵数据最新
        context.view_layer.update()

        try:
            for group in groups_to_merge:
                # 检查组内物体是否都有效
                valid_group = []
                for o in group:
                    try:
                        o.name
                        valid_group.append(o)
                    except ReferenceError:
                        pass
                
                if len(valid_group) < 2:
                    continue

                target_obj = valid_group[0]
                target_me = target_obj.data
                
                # 初始化目标物体的 BMesh
                bm = bmesh.new()
                bm.from_mesh(target_me)

                mw_target_inv = target_obj.matrix_world.inverted()

                for src_obj in valid_group[1:]:
                    src_me = src_obj.data
                    
                    # 5a. 合并并重映射材质槽
                    mat_map = {}
                    for i, mat in enumerate(src_me.materials):
                        if mat is None:
                            continue
                        try:
                            new_idx = target_me.materials[:].index(mat)
                        except ValueError:
                            target_me.materials.append(mat)
                            new_idx = len(target_me.materials) - 1
                        mat_map[i] = new_idx

                    # 5b. 合并并重映射顶点组 (Vertex Groups)
                    vg_map = {}
                    for vg in src_obj.vertex_groups:
                        target_vg = target_obj.vertex_groups.get(vg.name)
                        if not target_vg:
                            target_vg = target_obj.vertex_groups.new(name=vg.name)
                        vg_map[vg.index] = target_vg.index

                    # 5c. 写入几何体数据
                    start_vert_idx = len(bm.verts)
                    start_face_idx = len(bm.faces)
                    
                    bm.from_mesh(src_me)
                    
                    bm.verts.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()

                    # 5d. 转换新顶点坐标到目标物体本地空间
                    m_rel = mw_target_inv @ src_obj.matrix_world
                    bmesh.ops.transform(bm, matrix=m_rel, verts=bm.verts[start_vert_idx:])

                    # 5e. 修正新面的材质索引
                    for face in bm.faces[start_face_idx:]:
                        face.material_index = mat_map.get(face.material_index, 0)

                    # 5f. 修正新顶点的顶点组权重索引
                    deform_layer = bm.verts.layers.deform.active
                    if deform_layer and vg_map:
                        for v in bm.verts[start_vert_idx:]:
                            g_dict = v[deform_layer]
                            new_weights = {vg_map[g_idx]: weight for g_idx, weight in g_dict.items() if g_idx in vg_map}
                            g_dict.clear()
                            for g_idx, weight in new_weights.items():
                                g_dict[g_idx] = weight

                    # 记录待删除的源物体和旧网格数据
                    objects_to_remove.append(src_obj)
                    if src_me not in meshes_to_remove:
                        meshes_to_remove.append(src_me)

                # 将 BMesh 写回目标物体网格并释放内存
                bm.to_mesh(target_me)
                bm.free()
                target_me.update()
                
                merged_count += 1

            # 6. 一次性从数据库中删除所有被合并的源物体和它们独占的网格数据
            # 6a. 批量删除物体（使用 C 级别的 select + delete，速度比 Python 级逐个 remove 快百倍以上）
            if objects_to_remove:
                # 取消选择所有物体
                bpy.ops.object.select_all(action='DESELECT')
                # 选中待删除物体
                for obj in objects_to_remove:
                    try:
                        obj.select_set(True)
                    except Exception:
                        pass
                # C级一次性删除所有选中的物体，彻底去除更新延迟
                bpy.ops.object.delete(use_global=True)
            
            # 6b. 批量删除无用的旧网格资产
            for me in meshes_to_remove:
                try:
                    bpy.data.meshes.remove(me)
                except Exception:
                    pass

        finally:
            context.preferences.edit.use_global_undo = undo_use

        # 更新视图
        context.view_layer.update()

        self.report({'INFO'}, f"{_T('合并完成，共进行了')} {merged_count} {_T('组合并。')}")
        return {'FINISHED'}

# 3. 批量复制并对齐
class M8_OT_BatchCopyAlign(bpy.types.Operator):
    bl_idname = "m8.batch_copy_align"
    bl_label = _T("批量复制并对齐")
    bl_description = _T("将激活物体复制并对齐到其他选中物体")
    bl_options = {'REGISTER', 'UNDO'}

    remove_target: bpy.props.BoolProperty(name=_T("删除目标物体"), default=False)
    hide_target: bpy.props.BoolProperty(name=_T("隐藏目标物体"), default=True)
    move_target: bpy.props.BoolProperty(name=_T("移动到集合"), default=False)
    copy_type: bpy.props.EnumProperty(
        name=_T("复制类型"),
        items=[
            ('INSTANCE', _T("实例复制 (Alt+D)"), _T("生成与原物体共享网格数据块的关联副本")),
            ('NORMAL', _T("普通复制 (Shift+D)"), _T("生成完全独立的独立副本")),
        ],
        default='INSTANCE'
    )

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
                
            self.copy_type = props.copy_type
                
        return self.execute(context)

    def execute(self, context):
        source_obj = context.active_object
        targets = [obj for obj in context.selected_objects if obj != source_obj]
        
        if not targets:
            self.report({'WARNING'}, _T("请至少选择一个目标物体，最后再加选源物体。"))
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
            if self.copy_type == 'NORMAL' and source_obj.data:
                new_obj.data = source_obj.data.copy()
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
        self.report({'INFO'}, f"{_T('完成！已生成')} {len(created_objects)} {_T('个新物体。')}")
        return {'FINISHED'}

# 4. 原点对齐法向
class M8_OT_AlignOriginToNormal(bpy.types.Operator):
    bl_idname = "m8.align_origin_to_normal"
    bl_label = _T("原点对齐法向")
    bl_description = _T("将物体原点方向对齐到编辑模式下的平均法向")
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

        self.report({'INFO'}, f"{_T('处理完成：')}{count} {_T('个物体已对齐。')}")
        return {'FINISHED'}

class M8_CustomTools_Props(bpy.types.PropertyGroup):
    sort_mode: bpy.props.EnumProperty(
        name=_T("排序方式"),
        items=[
            ('NAME_ASC', _T("名称 (A-Z)"), _T("按材质名称升序排列")),
            ('NAME_DESC', _T("名称 (Z-A)"), _T("按材质名称降序排列")),
            ('COUNT_DESC', _T("面数 (多->少)"), _T("使用面数多的排在前面")),
            ('COUNT_ASC', _T("面数 (少->多)"), _T("使用面数少的排在前面")),
        ],
        default='NAME_ASC'
    )

    remove_unused: bpy.props.BoolProperty(
        name=_T("移除未使用材质"),
        description=_T("移除未分配给任何面的材质槽"),
        default=True
    )

    merge_threshold: bpy.props.FloatProperty(
        name=_T("合并距离"),
        default=0.1,
        min=0.00001,
        description=_T("合并判定的阈值"),
        step=1,
        precision=3
    )

    merge_unit: bpy.props.EnumProperty(
        name=_T("单位"),
        items=[
            ('M', _T("米 (m)"), "Meters"),
            ('CM', _T("厘米 (cm)"), "Centimeters"),
            ('MM', _T("毫米 (mm)"), "Millimeters"),
        ],
        default='M'
    )

    merge_mode: bpy.props.EnumProperty(
        name=_T("合并模式"),
        items=[
            ('CENTER', _T("几何中心"), _T("物体几何中心距离小于合并距离时合并")),
            ('VERTEX', _T("顶点临近"), _T("任意两物体最近顶点距离小于合并距离时合并")),
            ('AABB', _T("包围盒重叠"), _T("物体世界轴向包围盒 (AABB) 相交时合并")),
            ('MATERIAL', _T("相同材质"), _T("合并所有共享相同材质的物体")),
            ('PREFIX', _T("相同前缀"), _T("按命名中的前缀字符归类合并（例：Stone_01.001 -> Stone_01）")),
        ],
        default='CENTER'
    )

    copy_align_mode: bpy.props.EnumProperty(
        name=_T("目标处理"),
        items=[
            ('HIDE', _T("隐藏目标"), _T("隐藏被复制的目标物体")),
            ('REMOVE', _T("删除目标"), _T("删除被复制的目标物体")),
            ('MOVE', _T("移动到集合"), _T("将目标物体移动到 'M8_Backup' 集合中")),
            ('KEEP', _T("保留目标"), _T("保留被复制的目标物体")),
        ],
        default='HIDE'
    )
    copy_type: bpy.props.EnumProperty(
        name=_T("复制类型"),
        items=[
            ('INSTANCE', _T("实例复制 (Alt+D)"), _T("生成与原物体共享网格数据块的关联副本")),
            ('NORMAL', _T("普通复制 (Shift+D)"), _T("生成完全独立的独立副本")),
        ],
        default='INSTANCE'
    )

# 5. 面板类
class VIEW3D_PT_M8_CustomTools(bpy.types.Panel):
    bl_label = _T("M8 常用工具")
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
        col.label(text=_T("材质工具"), icon='MATERIAL')
        
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            col.prop(props, "sort_mode", text="")
            col.prop(props, "remove_unused")
        
        col.operator("m8.sort_materials", icon='SORTALPHA', text=_T("执行排序"))
        
        col.separator()
        col.label(text=_T("物体合并"), icon='GROUP')
        
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            col.prop(props, "merge_mode", text="")
            
            # Show threshold setting only for distance-based modes (CENTER, VERTEX, AABB)
            if props.merge_mode in {'CENTER', 'VERTEX', 'AABB'}:
                row = col.row(align=True)
                row.prop(props, "merge_threshold")
                row.prop(props, "merge_unit", text="")

        col.operator("m8.merge_nearby_objects", icon='MOD_BUILD', text=_T("执行合并"))
        
        col.separator()
        col.label(text=_T("复制与对齐"), icon='DUPLICATE')
        
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.custom_tools
            col.prop(props, "copy_align_mode", text="")
            row = col.row(align=True)
            row.prop(props, "copy_type", expand=True)

        col.operator("m8.batch_copy_align", icon='COPYDOWN', text=_T("批量复制"))
        col.operator("m8.align_origin_to_normal", icon='ORIENTATION_NORMAL', text=_T("原点对齐法向"))
        
