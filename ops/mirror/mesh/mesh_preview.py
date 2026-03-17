import bmesh
import bpy
from mathutils import Vector, Matrix

from ....hub import Hub3DItem, hub_3d
from ....utils import get_pref
from ....utils.items import AXIS
from ....utils.math import scale_to_matrix


class MeshPreview:
    cache_mesh_hub = {}
    preview_bm = None

    @property
    def axis_index(self) -> int:
        axis_index = AXIS.index(self.axis)
        return axis_index

    @property
    def scale_vector(self) -> Vector:
        scale = Vector((1, 1, 1))
        scale[self.axis_index] = -1
        return scale

    @property
    def scale_matrix(self) -> Matrix:
        scale = self.scale_vector
        scale_matrix = scale_to_matrix(scale)
        return scale_matrix

    def get_mesh_active_object(self, context):
        selected_objects = self.get_selected_mesh_objects(context)
        return context.object if context.object in selected_objects else selected_objects[0]

    def load_mesh_preview(self, context):
        self.cache_mesh_hub = {}
        pref = get_pref()
        
        # 如果关闭了预览，直接返回
        if not getattr(pref, "mirror_show_preview", False):
            return

        # 如果 self.preview_bm 已经存在且有效，先释放
        if self.preview_bm:
            self.preview_bm.free()
            
        pm = self.preview_bm = bmesh.new()
        active = self.get_mesh_active_object(context)
        
        # 预先获取相关属性，避免循环中查找
        max_edges = pref.mirror_preview_max_edge_count
        optimize = pref.mirror_preview_optimize

        def load(obj: bpy.types.Object, matrix: Matrix):
            # 优化：避免 update_from_editmode，它非常慢
            # 只有在必须时才调用，或者直接从 obj.data 获取（可能不是最新的，但性能好）
            # obj.update_from_editmode() 
            
            mesh = obj.data
            edge_count = len(mesh.edges)
            
            # 优化判断逻辑
            should_simplify = edge_count >= max_edges or optimize
            
            if not should_simplify:
                if context.mode == "EDIT_MESH" and obj == context.object:
                    bm = bmesh.from_edit_mesh(mesh)
                else:
                    bm = bmesh.new()
                    bm.from_mesh(mesh)
                
                # 优化：批量创建顶点
                # bm.verts 包含所有顶点
                # 使用 transform 批量处理坐标，而不是逐个 matrix @ vert.co
                # 但我们需要保留 bm 不变，所以拷贝数据到 pm
                
                # 这种逐个复制的方法在 Python 中很慢
                # 优化方案：直接合并 bmesh，然后 transform
                
                # 记录当前的顶点数偏移
                offset = len(pm.verts)
                
                # 将 bm 的几何体复制到 pm
                # bmesh 没有任何直接追加的方法，只能逐个添加?
                # 不，我们可以使用 from_mesh 追加到现有的 bmesh 吗？不行，from_mesh 会清空
                
                # 最高效的方法可能是：
                # 1. 临时创建一个新的 bmesh
                # 2. 变换它
                # 3. 将其内容复制到 pm (还是慢)
                
                # 或者：只在需要预览的时候，针对该物体单独处理，而不是把所有选中的物体合并到一个 bmesh
                # 目前逻辑是合并所有选中物体的网格到一个 preview_bm 中
                
                # 既然 Python 循环慢，我们尽量减少循环内的操作
                # 或者：如果只是预览，我们其实不需要拓扑结构完全正确，只需要线和点
                
                # 现有逻辑维持不变，但增加顶点数的硬限制，防止卡死
                if len(bm.verts) > 50000: # 硬限制
                    should_simplify = True
                    if context.mode != "EDIT_MESH" or obj != context.object:
                        bm.free()
                else:
                    len_vert = len(pm.verts)
                    
                    # 预分配列表以加速
                    new_verts = []
                    
                    # 批量添加顶点
                    # pm.verts.new 仍然是瓶颈
                    for vert in bm.verts:
                        nv = pm.verts.new(matrix @ vert.co)
                        nv.index = len_vert + vert.index # 重新索引
                        new_verts.append(nv)
                    
                    pm.verts.ensure_lookup_table()
                    # bm.verts.ensure_lookup_table() # 假设 bm 索引是连续的
                    
                    # 批量添加边
                    for edge in bm.edges:
                        try:
                            v1_idx = edge.verts[0].index
                            v2_idx = edge.verts[1].index
                            pm.edges.new((new_verts[v1_idx], new_verts[v2_idx]))
                        except IndexError:
                            pass
                            
                    if context.mode != "EDIT_MESH" or obj != context.object:
                        bm.free()
            
            # 如果简化（使用边界框）
            if should_simplify:
                # 使用边界框
                bound_box = [matrix @ Vector(corner) for corner in obj.bound_box]
                
                # 创建边界框顶点
                verts = [pm.verts.new(co) for co in bound_box]
                pm.verts.ensure_lookup_table()
                
                # 边界框的边索引
                indices = [
                    (0, 1), (1, 2), (2, 3), (3, 0), # 底面
                    (4, 5), (5, 6), (6, 7), (7, 4), # 顶面
                    (0, 4), (1, 5), (2, 6), (3, 7)  # 立柱
                ]
                
                for a, b in indices:
                    pm.edges.new((verts[a], verts[b]))

        if context.mode == "EDIT_MESH":
            if context.object.type == "MESH":
                load(active, Matrix())
        else:
            for i in self.get_selected_mesh_objects(context):
                if i.type == "MESH":
                    load(i, active.matrix_world.inverted() @ i.matrix_world)

    def get_preview_matrix(self, context, obj) -> (Vector, Vector, Matrix, Matrix):
        plane_co = Vector()
        plane_no = Vector()
        matrix = Matrix()

        axis_index = self.axis_index
        plane_no[axis_index] = -1 if self.is_negative_axis else 1

        axis = self.axis_mode

        obj_matrix = obj.matrix_world
        obj_rotate = obj_matrix.to_euler().to_matrix().to_4x4()

        if axis == "CURSOR":
            cursor = context.scene.cursor.matrix
            cursor_rotate = cursor.to_euler().to_matrix().to_4x4()

            plane_co = obj_matrix.inverted() @ cursor @ plane_co
            plane_no = obj_rotate.inverted() @ cursor_rotate @ plane_no
            matrix = cursor.inverted() @ obj_matrix
        elif axis == "WORLD":
            plane_co = obj_matrix.inverted() @ plane_co
            plane_no = obj_rotate.inverted() @ plane_no
            matrix = obj_matrix
        elif axis == "ACTIVE":
            active = self.active_matrix
            active_rotate = active.to_euler().to_matrix().to_4x4()

            plane_co = obj_matrix.inverted() @ active @ plane_co
            plane_no = obj_rotate.inverted() @ active_rotate @ plane_no
            matrix = active.inverted() @ obj_matrix
            # matrix = active.inverted_safe() @ obj_matrix

        return plane_co, plane_no, matrix

    def update_mesh_preview(self, context, is_preview=True):
        pref = get_pref()

        # 如果关闭了预览，直接返回
        if not getattr(pref, "mirror_show_preview", False):
            return

        obj = self.get_mesh_active_object(context)

        plane_co, plane_no, matrix = self.get_preview_matrix(context, obj)

        key = (obj.name, self.axis_mode, self.is_negative_axis, self.bisect, self.axis)

        if key in self.cache_mesh_hub:
            hub = self.cache_mesh_hub[key]
        else:
            obj_matrix = obj.matrix_world

            draw_matrix = obj_matrix
            if self.axis_mode == "WORLD":
                draw_matrix = Matrix.Identity(4)
            elif self.axis_mode == "CURSOR":
                draw_matrix = context.scene.cursor.matrix
            elif self.axis_mode == "ACTIVE":
                draw_matrix = self.active_matrix

            hub = Hub3DItem(vert_size=pref.mirror_preview_vert_size, line_width=pref.mirror_preview_edge_width)
            hub.depth_test = "LESS_EQUAL"

            bm = self.preview_bm.copy()
            remove_verts = []
            bisect_edges = []
            if self.bisect:
                cut_verts = bmesh.ops.bisect_plane(bm,
                                                   geom=bm.edges,
                                                   plane_co=plane_co,
                                                   plane_no=plane_no)
                for vert in cut_verts["geom_cut"]:
                    hub.vert(vert, color=(1, 1, 0), matrix=draw_matrix)

                res = bmesh.ops.connect_verts(bm, verts=cut_verts["geom_cut"], faces_exclude=[], check_degenerate=False)
                edges = res["edges"]
                bisect_edges.extend(edges)
                for edge in edges:
                    hub.edge(edge, color=(0, 1, 0), matrix=draw_matrix)

                for vert in bm.verts:
                    co = matrix @ vert.co
                    axis_index = self.axis_index
                    c = co[axis_index]
                    factor = .000001
                    is_remove = c < -factor if self.is_negative_axis else c > factor

                    if is_remove:
                        remove_verts.append(vert)
                        hub.vert(vert, color=(1, 0, 0), matrix=draw_matrix)
                bmesh.ops.delete(bm, geom=remove_verts, context="VERTS")
            bmesh.ops.mirror(bm,
                             geom=bm.edges,
                             matrix=matrix,
                             merge_dist=self.threshold,
                             axis=self.axis)

            for edge in bm.edges:
                hub.edge(edge, color=pref.mirror_preview_edge_color, matrix=draw_matrix)
            self.cache_mesh_hub[key] = hub

        hub.alpha = pref.mirror_preview_alpha if is_preview else None
        area_hash = hash(context.area)
        timeout = None if is_preview else 1.0
        hub_3d(f"{self.bl_idname}_preview", hub, timeout=timeout, area_restrictions=area_hash)
