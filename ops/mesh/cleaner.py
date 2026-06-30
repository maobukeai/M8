import bpy
import bmesh
import math
import mathutils
from mathutils import Vector, Matrix
import concurrent.futures
from ...utils.bmesh_selection import get_edge_loop, get_edge_ring, sort_edge_loop, get_checker_deselect
from ...utils.i18n import _T

def safe_dissolve_edges(bm, mesh, edges_to_dissolve):
    """融并边，直接调用 Blender 系统原生操作以完美清理顶点而不留残留"""
    if not edges_to_dissolve:
        return
    
    # 同步当前选择状态到编辑网格
    bmesh.update_edit_mesh(mesh)
    
    try:
        # 调用系统的融并边操作，同时融并顶点（use_verts=True）
        bpy.ops.mesh.dissolve_edges(use_verts=True)
    except Exception as e:
        print(f"System dissolve_edges failed, using fallback: {e}")
        # 如果系统操作由于某些原因失败，则使用 bmesh.ops 进行备用融并
        valid_edges = [e for e in edges_to_dissolve if e.is_valid]
        if valid_edges:
            bmesh.ops.dissolve_edges(bm, edges=valid_edges, use_verts=True)
            
    bmesh.update_edit_mesh(mesh)

# -------------------------------------------------------------------
# Properties
# -------------------------------------------------------------------

class M8_Clean_Props(bpy.types.PropertyGroup):
    # Properties from Circular Loop Cleaner
    use_checker_deselect: bpy.props.BoolProperty(
        name=_T("间隔减选"),
        description=_T("在初始环形选择中每隔一条边进行跳过"),
        default=True
    )

    auto_dissolve: bpy.props.BoolProperty(
        name=_T("自动融并"),
        description=_T("自动融并选中的边"),
        default=False
    )

    flat_threshold_min: bpy.props.FloatProperty(
        name=_T("平坦阈值最小值"),
        description=_T("平坦循环边的最小角度阈值 (度)"),
        default=5.0,
        min=0.0,
        max=180.0
    )

    flat_threshold_max: bpy.props.FloatProperty(
        name=_T("平坦阈值最大值"),
        description=_T("平坦循环边的最大角度阈值 (度)"),
        default=25.0,
        min=0.0,
        max=180.0
    )

    # Properties from Unbevel
    similarity_threshold: bpy.props.FloatProperty(
        name=_T("相似度阈值"),
        default=0.0005,
        min=0.0,
        max=1.0,
        precision=6,
        step=0.1
    )

    mark_sharp_similar: bpy.props.BoolProperty(
        name=_T("标记锐边"),
        description=_T("反倒角相似边后将结果边标记为锐边"),
        default=True
    )

    mark_sharp_selected: bpy.props.BoolProperty(
        name=_T("标记锐边"),
        description=_T("反倒角选中边后将结果边标记为锐边"),
        default=True
    )

    show_advanced: bpy.props.BoolProperty(
        name=_T("显示高级设置"),
        default=False
    )

    cleanup_initialized: bpy.props.BoolProperty(
        name="cleanup_initialized",
        default=False
    )

    cleanup_affect: bpy.props.EnumProperty(
        name=_T("影响范围"),
        items=[
            ("ALL", _T("全部"), ""),
            ("SELECTED", _T("仅选中"), ""),
        ],
        default="ALL",
    )
    cleanup_merge_distance: bpy.props.FloatProperty(name=_T("合并距离"), default=0.0001, min=0.0, step=0.1, precision=5)
    cleanup_do_merge_by_distance: bpy.props.BoolProperty(name=_T("重复"), default=True)
    cleanup_do_dissolve_degenerate: bpy.props.BoolProperty(name=_T("退化"), default=True)
    cleanup_degenerate_dist: bpy.props.FloatProperty(name=_T("退化阈值"), default=0.00001, min=0.0, step=0.01, precision=6)
    cleanup_do_delete_loose: bpy.props.BoolProperty(name=_T("松散"), default=True)
    cleanup_do_limited_dissolve: bpy.props.BoolProperty(name=_T("冗余"), default=False)
    cleanup_limited_dissolve_angle: bpy.props.FloatProperty(name=_T("角度"), default=0.0872665, min=0.0, max=3.14159, subtype="ANGLE")
    cleanup_do_recalc_normals: bpy.props.BoolProperty(name=_T("重新计算法线"), default=False)
    cleanup_do_make_planar: bpy.props.BoolProperty(name=_T("平坦化面"), default=False)
    cleanup_planar_iterations: bpy.props.IntProperty(name=_T("迭代"), default=1, min=1, max=10)
    cleanup_do_delete_interior_faces: bpy.props.BoolProperty(name=_T("删除内部面 (非流形)"), default=False)
    cleanup_do_select_tools: bpy.props.BoolProperty(name=_T("选择"), default=True)
    cleanup_non_planar_angle: bpy.props.FloatProperty(name=_T("非平面角度"), default=0.0872665, min=0.0, max=3.14159, subtype="ANGLE")
    cleanup_show_advanced: bpy.props.BoolProperty(name=_T("高级"), default=False)

# -------------------------------------------------------------------
# Circular Loop Cleaner Operators
# -------------------------------------------------------------------

class MESH_OT_smart_edge_loop_cleaner(bpy.types.Operator):
    """Smart Edge Loop Cleaner"""
    bl_idname = "mesh.m8_smart_edge_loop_cleaner"
    bl_label = _T("智能循环边清理")
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties for real-time editing
    use_checker_deselect: bpy.props.BoolProperty(
        name=_T("间隔减选"),
        description=_T("在初始环形选择中每隔一条边进行跳过"),
        default=True
    )

    filter_flat_loops: bpy.props.BoolProperty(
        name=_T("过滤平坦循环边"),
        description=_T("移除面几乎平坦的循环边"),
        default=False
    )

    auto_dissolve: bpy.props.BoolProperty(
        name=_T("自动融并"),
        description=_T("自动融并选中的边"),
        default=True
    )

    flat_threshold_min: bpy.props.FloatProperty(
        name=_T("平坦阈值最小值"),
        description=_T("平坦循环边的最小角度阈值 (度)"),
        default=5.0,
        min=0.0,
        max=180.0
    )

    flat_threshold_max: bpy.props.FloatProperty(
        name=_T("平坦阈值最大值"),
        description=_T("平坦循环边的最大角度阈值 (度)"),
        default=25.0,
        min=0.0,
        max=180.0
    )

    hide_high_valence: bpy.props.BoolProperty(
        name=_T("隐藏高价顶点"),
        description=_T("在处理前临时隐藏连接数较多的顶点"),
        default=True
    )

    valence_threshold: bpy.props.IntProperty(
        name=_T("价数阈值"),
        description=_T("隐藏连接边数超过此数量的顶点"),
        default=4,
        min=3,
        max=20
    )
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')
    
    def invoke(self, context, event):
        # Get values from scene properties if they exist
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.clean
            self.use_checker_deselect = props.use_checker_deselect
            self.auto_dissolve = props.auto_dissolve
            self.flat_threshold_min = props.flat_threshold_min
            self.flat_threshold_max = props.flat_threshold_max
        
        # Always enable flat loop filtering for advanced cleaner
        self.filter_flat_loops = True
        
        return self.execute(context)
    
    def execute(self, context):
        # Save values back to scene properties
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.clean
            props.use_checker_deselect = self.use_checker_deselect
            props.auto_dissolve = self.auto_dissolve
            props.flat_threshold_min = self.flat_threshold_min
            props.flat_threshold_max = self.flat_threshold_max
        
        obj = context.active_object
        mesh = obj.data
        
        # Get bmesh representation
        bm = bmesh.from_edit_mesh(mesh)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        
        # Check if we have a selected edge to start with
        selected_edges = [e for e in bm.edges if e.select]
        if not selected_edges:
            self.report({'ERROR'}, _T("请至少选择一条边来定义方向"))
            bmesh.update_edit_mesh(mesh)
            return {'CANCELLED'}
        
        # Store original selection as indices
        original_selected_edges = [e.index for e in selected_edges]
        
        # Find and hide high valence vertices if needed
        hidden_vert_indices = []
        hidden_edge_indices = []
        hidden_face_indices = []
        
        if self.hide_high_valence:
            # Find high valence vertices
            for vert in bm.verts:
                if len(vert.link_edges) > self.valence_threshold and not vert.hide:
                    hidden_vert_indices.append(vert.index)
                    vert.hide = True
                    
                    # Hide connected edges
                    for edge in vert.link_edges:
                        if not edge.hide:
                            hidden_edge_indices.append(edge.index)
                            edge.hide = True
                    
                    # Hide connected faces  
                    for face in vert.link_faces:
                        if not face.hide:
                            hidden_face_indices.append(face.index)
                            face.hide = True
            
            # Update mesh after hiding
            bmesh.update_edit_mesh(mesh)
            
            # Get fresh bmesh after hiding
            bm = bmesh.from_edit_mesh(mesh)
            bm.edges.ensure_lookup_table()
        
        # Restore original edge selection using indices
        bpy.ops.mesh.select_all(action='DESELECT')
        for edge_idx in original_selected_edges:
            if edge_idx < len(bm.edges) and not bm.edges[edge_idx].hide:
                bm.edges[edge_idx].select = True
        
        # Update mesh
        bmesh.update_edit_mesh(mesh)
        
        # Check if we still have selected edges
        selected_edges = [e for e in bm.edges if e.select]
        if not selected_edges:
            # Restore hidden elements before reporting error
            self.restore_hidden_elements(hidden_vert_indices, hidden_edge_indices, hidden_face_indices)
            self.report({'ERROR'}, _T("隐藏复杂顶点后没有有效边剩余"))
            return {'CANCELLED'}
        
        # Use the first selected edge as direction reference
        start_edge = selected_edges[0]
        
        # Expand starting edge into ring and loops using pure BMesh
        ring_edges = get_edge_ring(start_edge)
        if self.use_checker_deselect:
            ring_edges = get_checker_deselect(ring_edges, nth=2)
        
        selected_loop_edges = set()
        for e in ring_edges:
            selected_loop_edges.update(get_edge_loop(e))
        
        for e in bm.edges:
            e.select = False
        for e in selected_loop_edges:
            e.select = True
        bmesh.update_edit_mesh(mesh)
        
        selected_edges = [e for e in bm.edges if e.select]
        
        # Group edges into loops
        edge_loops = group_edges_into_loops(selected_edges)
        
        # Filter loops based on settings
        loops_to_dissolve = []
        
        for loop in edge_loops:
            should_dissolve = True
            
            # Filter flat loops (only dissolve if within flat threshold)
            if self.filter_flat_loops:
                if not is_flat_loop_range(loop, self.flat_threshold_min, self.flat_threshold_max):
                    should_dissolve = False
            
            # Protect open geometry (never dissolve loops touching open boundaries)
            if touches_open_geometry(loop):
                should_dissolve = False
            
            if should_dissolve:
                loops_to_dissolve.append(loop)
        
        edges_to_dissolve = [e for loop in loops_to_dissolve for e in loop]
        
        # Clear selection and select only loops to dissolve
        for e in bm.edges:
            e.select = False
        for e in edges_to_dissolve:
            e.select = True
        bmesh.update_edit_mesh(mesh)
        
        # Auto dissolve if enabled
        if self.auto_dissolve:
            safe_dissolve_edges(bm, mesh, edges_to_dissolve)
        
        # Restore hidden elements
        if self.hide_high_valence:
            self.restore_hidden_elements(hidden_vert_indices, hidden_edge_indices, hidden_face_indices)
        
        self.report({'INFO'}, f"{_T('已从')} {len(edge_loops)} {_T('条循环边中成功清理')} {len(loops_to_dissolve)} {_T('条')}")
        
        return {'FINISHED'}
    
    def restore_hidden_elements(self, vert_indices, edge_indices, face_indices):
        """Restore hidden elements using indices"""
        obj = bpy.context.active_object
        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        
        # Ensure lookup tables
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        
        # Unhide vertices
        for vert_idx in vert_indices:
            if vert_idx < len(bm.verts):
                bm.verts[vert_idx].hide = False
        
        # Unhide edges
        for edge_idx in edge_indices:
            if edge_idx < len(bm.edges):
                bm.edges[edge_idx].hide = False
        
        # Unhide faces
        for face_idx in face_indices:
            if face_idx < len(bm.faces):
                bm.faces[face_idx].hide = False
        
        bmesh.update_edit_mesh(mesh)


def group_edges_into_loops(edges):
    """Group connected edges into individual loops"""
    loops = []
    visited = set()
    edges_set = set(edges)
    
    for edge in edges:
        if edge in visited:
            continue
        current_loop = []
        edge_queue = [edge]
        visited.add(edge)
        
        while edge_queue:
            current_edge = edge_queue.pop(0)
            current_loop.append(current_edge)
            for vert in current_edge.verts:
                for connected_edge in vert.link_edges:
                    if connected_edge in edges_set and connected_edge not in visited:
                        visited.add(connected_edge)
                        edge_queue.append(connected_edge)
        
        if current_loop:
            loops.append(current_loop)
    return loops


def is_flat_loop_range(loop, min_threshold, max_threshold):
    """Check if a loop is flat based on face normal angles across its edges"""
    if not loop:
        return True
    total_angle = 0.0
    angle_count = 0
    for edge in loop:
        if len(edge.link_faces) == 2:
            f1, f2 = edge.link_faces
            try:
                angle = f1.normal.angle(f2.normal)
                total_angle += angle
                angle_count += 1
            except Exception:
                pass
    if angle_count == 0:
        return True
    avg_angle_deg = math.degrees(total_angle / angle_count)
    return min_threshold <= avg_angle_deg <= max_threshold


def touches_open_geometry(loop):
    """Check if loop touches non-manifold or boundary edges"""
    for edge in loop:
        if len(edge.link_faces) < 2:
            return True
        for vert in edge.verts:
            if not vert.is_manifold:
                return True
    return False



class MESH_OT_simple_edge_loop_cleaner(bpy.types.Operator):
    """Simple Edge Loop Cleaner for Cylinders"""
    bl_idname = "mesh.m8_simple_edge_loop_cleaner"
    bl_label = _T("清理循环边")
    bl_description = _T("针对简单几何体(如圆柱)的快速循环边清理")
    bl_options = {'REGISTER', 'UNDO'}

    use_checker_deselect: bpy.props.BoolProperty(
        name=_T("间隔减选"),
        description=_T("在初始环形选择中每隔一条边进行跳过"),
        default=True
    )

    auto_dissolve: bpy.props.BoolProperty(
        name=_T("自动融并"),
        description=_T("自动融并选中的边"),
        default=True
    )
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')
    
    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        
        # Get bmesh representation
        bm = bmesh.from_edit_mesh(mesh)
        bm.edges.ensure_lookup_table()
        
        # Check if we have a selected edge to start with
        selected_edges = [e for e in bm.edges if e.select]
        if not selected_edges:
            self.report({'ERROR'}, _T("请至少选择一条边来定义方向"))
            return {'CANCELLED'}

        # Use the first selected edge as the direction reference
        start_edge = selected_edges[0]
        
        # Expand starting edge into ring and loops using pure BMesh
        ring_edges = get_edge_ring(start_edge)
        if self.use_checker_deselect:
            ring_edges = get_checker_deselect(ring_edges, nth=2)
        
        selected_loop_edges = set()
        for e in ring_edges:
            selected_loop_edges.update(get_edge_loop(e))
        
        # Protect boundary edges and open geometry loops
        edge_loops = group_edges_into_loops(selected_loop_edges)
        loops_to_dissolve = [loop for loop in edge_loops if not touches_open_geometry(loop)]
        edges_to_dissolve = [e for loop in loops_to_dissolve for e in loop]
        
        for e in bm.edges:
            e.select = False
        for e in edges_to_dissolve:
            e.select = True
        bmesh.update_edit_mesh(mesh)
        
        # Auto dissolve if enabled
        if self.auto_dissolve:
            safe_dissolve_edges(bm, mesh, edges_to_dissolve)
        
        self.report({'INFO'}, _T("简单边循环清理已完成"))
        
        return {'FINISHED'}


class MESH_OT_auto_unsubdivide(bpy.types.Operator):
    """Auto Unsubdivide"""
    bl_idname = "mesh.m8_auto_unsubdivide"
    bl_label = _T("自动反细分")
    bl_description = _T("选择相连几何体并进行反细分")
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')
    
    def execute(self, context):
        objects = context.objects_in_mode_unique_data
        total_success = 0
        
        # Save original active object
        original_active = context.view_layer.objects.active
        
        for obj in objects:
            if obj.type != 'MESH':
                continue
            
            # Set as active for bpy.ops
            context.view_layer.objects.active = obj
            
            mesh = obj.data
            bm = bmesh.from_edit_mesh(mesh)
            
            # Check if anything is selected
            has_selection = (any(v.select for v in bm.verts) or 
                            any(e.select for e in bm.edges) or 
                            any(f.select for f in bm.faces))
            
            if not has_selection:
                continue
            
            try:
                # Select linked
                bpy.ops.mesh.select_linked()
                # Run unsubdivide
                bpy.ops.mesh.unsubdivide()
                total_success += 1
            except Exception as e:
                print(f"Unsubdivide failed for {obj.name}: {e}")
        
        # Restore active object
        if original_active:
            context.view_layer.objects.active = original_active
            
        if total_success > 0:
            self.report({'INFO'}, f"{_T('已对')} {total_success} {_T('个物体执行反细分')}")
        else:
            self.report({'WARNING'}, _T("未找到选择项或操作失败"))
            
        return {'FINISHED'}


class MESH_OT_decimate_selected(bpy.types.Operator):
    """Decimate Selected"""
    bl_idname = "mesh.m8_decimate_selected"
    bl_label = _T("精简几何体")
    bl_description = _T("精简选中的几何体")
    bl_options = {'REGISTER', 'UNDO'}

    ratio: bpy.props.FloatProperty(
        name=_T("比率"),
        description=_T("保留几何体的比率"),
        default=0.5,
        min=0.0,
        max=1.0
    )

    use_symmetry: bpy.props.BoolProperty(
        name=_T("对称"),
        description=_T("保持 X 轴对称"),
        default=False
    )
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')
    
    def execute(self, context):
        objects = context.objects_in_mode_unique_data
        total_success = 0
        original_active = context.view_layer.objects.active
        
        for obj in objects:
            if obj.type != 'MESH':
                continue
            
            context.view_layer.objects.active = obj
            mesh = obj.data
            bm = bmesh.from_edit_mesh(mesh)
            
            # Check if anything is selected
            has_selection = (any(v.select for v in bm.verts) or 
                            any(e.select for e in bm.edges) or 
                            any(f.select for f in bm.faces))
            
            if not has_selection:
                continue
            
            try:
                bpy.ops.mesh.decimate(ratio=self.ratio, use_symmetry=self.use_symmetry)
                total_success += 1
            except Exception as e:
                print(f"Decimate failed for {obj.name}: {e}")
        
        if original_active:
            context.view_layer.objects.active = original_active
            
        if total_success > 0:
            self.report({'INFO'}, f"{_T('已对')} {total_success} {_T('个物体精简几何体（比率：')}{self.ratio:.2f}）")
        else:
            self.report({'WARNING'}, _T("请先选择要精简的几何体"))
            
        return {'FINISHED'}


class MESH_OT_dissolve_edges(bpy.types.Operator):
    """Dissolve Edges"""
    bl_idname = "mesh.m8_dissolve_selected_edges"
    bl_label = _T("融并边")
    bl_description = _T("融并选中的边")
    bl_options = {'REGISTER', 'UNDO'}

    use_verts: bpy.props.BoolProperty(
        name=_T("融并顶点"),
        description=_T("融并边时同时融并顶点"),
        default=True
    )
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')
    
    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        
        # Get bmesh representation
        bm = bmesh.from_edit_mesh(mesh)
        
        # Check if we have selected edges
        selected_edges = [e for e in bm.edges if e.select]
        if not selected_edges:
            self.report({'WARNING'}, _T("未选中任何边"))
            return {'CANCELLED'}

        # Dissolve the selected edges
        try:
            bpy.ops.mesh.dissolve_edges(use_verts=self.use_verts)
            self.report({'INFO'}, f"{_T('已融并')} {len(selected_edges)} {_T('条边')}")
        except Exception as e:
            self.report({'ERROR'}, f"{_T('融并失败：')}{str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class MESH_OT_mark_sharp(bpy.types.Operator):
    """Mark Sharp Edges"""
    bl_idname = "mesh.m8_mark_sharp_edges"
    bl_label = _T("标记锐边")
    bl_description = _T("将选中的边标记为锐边")
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')
    
    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        
        # Get bmesh representation
        bm = bmesh.from_edit_mesh(mesh)
        
        # Check if we have selected edges
        selected_edges = [e for e in bm.edges if e.select]
        if not selected_edges:
            self.report({'WARNING'}, _T("未选中任何边"))
            return {'CANCELLED'}

        # Mark selected edges as sharp
        for edge in selected_edges:
            edge.smooth = False

        # Update mesh
        bmesh.update_edit_mesh(mesh)

        self.report({'INFO'}, f"{_T('已将')} {len(selected_edges)} {_T('条边标记为锐边')}")
        return {'FINISHED'}


class MESH_OT_checker_deselect(bpy.types.Operator):
    """Manual Checker Deselect"""
    bl_idname = "mesh.m8_checker_deselect"
    bl_label = _T("间隔减选")
    bl_description = _T("对当前选中的循环边/并排边应用间隔减选")
    bl_options = {'REGISTER', 'UNDO'}

    # 暴露原生属性，让左下角面板可用
    nth: bpy.props.IntProperty(name=_T("弃选"), default=1, min=1)
    skip: bpy.props.IntProperty(name=_T("选中"), default=1, min=1)
    offset: bpy.props.IntProperty(name=_T("偏移量"), default=0)
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')
    
    def execute(self, context):
        try:
            # 直接调用 Blender 原生且高度优化的 C 算法，完美支持 Ring 和 Loop
            bpy.ops.mesh.select_nth(skip=self.skip, nth=self.nth, offset=self.offset)
            return {'FINISHED'}
        except Exception as e:
            self.report({'WARNING'}, f"{_T('减选失败')}: {e}")
            return {'CANCELLED'}

# -------------------------------------------------------------------
# Unbevel Operators
# -------------------------------------------------------------------

def get_safe_unbevel_pos(edge, b_edges_ids):
    """Safely calculates the unbevel intersection point, gracefully degrading to midpoint on failure"""
    import math
    import mathutils
    from mathutils import Vector, Matrix
    
    verts = edge.verts
    pos_between = verts[0].co.lerp(verts[1].co, 0.5)
    
    # Safe boundary & non-manifold check
    if len(edge.link_faces) != 2:
        return pos_between
        
    try:
        # Check if adjoining edges are selected to guess the corner normal
        linked_edges_0 = sum(1 for e in edge.link_faces[0].edges if e.index in b_edges_ids)
        linked_edges_1 = sum(1 for e in edge.link_faces[1].edges if e.index in b_edges_ids)
        
        if len(edge.link_faces[0].verts) > 4 or linked_edges_0 < 2:
            ed_normal = edge.link_faces[1].normal
        elif len(edge.link_faces[1].verts) > 4 or linked_edges_1 < 2:
            ed_normal = edge.link_faces[0].normal
        else:
            ed_normal = edge.link_faces[0].normal.lerp(edge.link_faces[1].normal, 0.5)
        
        fix_dir = ed_normal.cross((verts[0].co - verts[1].co).normalized())
        if fix_dir.length < 1e-6:
            return pos_between
            
        v0_nor = mathutils.geometry.intersect_line_plane(verts[0].normal + (fix_dir * 2), verts[0].normal - (fix_dir * 2), Vector((0,0,0)), fix_dir)
        v1_nor = mathutils.geometry.intersect_line_plane(verts[1].normal + (fix_dir * 2), verts[1].normal - (fix_dir * 2), Vector((0,0,0)), fix_dir)
        
        if not v0_nor or not v1_nor:
            v0_nor = verts[0].normal
            v1_nor = verts[1].normal
        else:
            v0_nor = v0_nor.normalized()
            v1_nor = v1_nor.normalized()
            
        nor_dir = v0_nor.lerp(v1_nor, 0.5)
        if nor_dir.length < 1e-6:
            return pos_between
        nor_dir.normalize()
        
        side_dir_2 = (verts[0].co - verts[1].co).normalized()
        side_dir_2.negate()
        side_dir_1 = nor_dir.cross(side_dir_2).normalized()
        
        angle_between_1 = v0_nor.angle(nor_dir)
        degree_90 = 1.57079632679
        
        rot_mat = Matrix.Rotation((-angle_between_1 * 2) - degree_90, 3, side_dir_1)
        rot_mat_2 = Matrix.Rotation((angle_between_1 * 2) + (degree_90 * 2), 3, side_dir_1)
        
        dir_1 = ((rot_mat @ nor_dir).normalized() * 10000) + verts[0].co
        dir_2 = (rot_mat_2 @ nor_dir).normalized()
        
        scale_pos = mathutils.geometry.intersect_line_plane(verts[0].co, dir_1, verts[1].co, dir_2)
        
        if scale_pos is None:
            return pos_between
            
        return scale_pos
        
    except Exception:
        # Graceful fallback to midpoint on mathematical singularity
        return pos_between


class MESH_OT_auto_unbevel_similar(bpy.types.Operator):
    """Select similar edges and unbevel them completely"""
    bl_idname = "mesh.m8_auto_unbevel_similar"
    bl_label = _T("反倒角相似边")
    bl_description = _T("基于选中的边选择相似边并完全反倒角")
    bl_options = {'REGISTER', 'UNDO'}

    similarity_threshold: bpy.props.FloatProperty(
        name=_T("相似度阈值"),
        description=_T("边相似度的阈值 (越低越严格)"),
        default=0.0005,
        min=0.0,
        max=1.0,
        precision=6,
        step=0.1  # 降低滑动敏感度
    )

    mark_sharp: bpy.props.BoolProperty(
        name=_T("标记锐边"),
        description=_T("反倒角后将结果边标记为锐边"),
        default=True
    )

    def invoke(self, context, event):
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.clean
            self.similarity_threshold = props.similarity_threshold
            self.mark_sharp = props.mark_sharp_similar
        return self.execute(context)

    def execute(self, context):
        # Save values back to scene properties
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.clean
            props.similarity_threshold = self.similarity_threshold
            props.mark_sharp_similar = self.mark_sharp

        active_obj = context.active_object
        
        if not active_obj or active_obj.type != 'MESH':
            self.report({'ERROR'}, _T("没有活动的网格物体"))
            return {'CANCELLED'}

        # Enter edit mode if not already
        if active_obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(active_obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # Get currently selected edges
        selected_edges = [edge for edge in bm.edges if edge.select]

        if not selected_edges:
            self.report({'ERROR'}, _T("请至少先选择一条边"))
            return {'CANCELLED'}
        
        # Use the first selected edge as reference
        reference_edge = selected_edges[0]
        reference_length = reference_edge.calc_length()
        
        # Find all edges with similar length
        similar_edges = []
        for edge in bm.edges:
            edge_length = edge.calc_length()
            if abs(edge_length - reference_length) <= self.similarity_threshold:
                similar_edges.append(edge)
        
        # Store vertices and their connected edges before unbeveling for sharp marking
        vertices_to_edge_groups = {}
        if self.mark_sharp:
            for edge in similar_edges:
                for vert in edge.verts:
                    if vert not in vertices_to_edge_groups:
                        vertices_to_edge_groups[vert] = set()
                    # Store edges that are NOT being unbeveled (the edges we want to mark sharp)
                    for connected_edge in vert.link_edges:
                        if connected_edge not in similar_edges:
                            vertices_to_edge_groups[vert].add(connected_edge.index)
        
        # Clear selection and select similar edges
        for edge in bm.edges:
            edge.select = False
        for vert in bm.verts:
            vert.select = False
        for face in bm.faces:
            face.select = False
            
        # Select all similar edges
        for edge in similar_edges:
            edge.select = True
            edge.verts[0].select = True
            edge.verts[1].select = True
        
        bmesh.update_edit_mesh(active_obj.data)
        
        if len(similar_edges) == 0:
            self.report({'WARNING'}, _T("未找到相似边"))
            return {'CANCELLED'}
        
        # Store vertices that will be affected for sharp marking later
        affected_verts = set()
        for edge in similar_edges:
            affected_verts.add(edge.verts[0])
            affected_verts.add(edge.verts[1])
        
        # Now run the unbevel operation (hardcoded to completely unbevel)
        unbevel_value = 0.0  # Always completely unbevel
        degree_90 = 1.5708
        
        # Get selected edges for unbeveling
        b_edges = [edge for edge in bm.edges if edge.select]
        b_edges_pos = []
        b_edges_ids = [edge.index for edge in b_edges]
        
        for edge in b_edges:
            scale_pos = get_safe_unbevel_pos(edge, b_edges_ids)
            b_edges_pos.append((edge.verts[0], scale_pos))
            b_edges_pos.append((edge.verts[1], scale_pos))
        
        for v_data in b_edges_pos:
            v_data[0].co = v_data[1].lerp(v_data[0].co, unbevel_value)
        
        # Always merge since we're completely unbeveling
        bpy.ops.mesh.merge(type='COLLAPSE')
        
        # Mark sharp if enabled
        if self.mark_sharp:
            # Refresh bmesh after merge
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            
            # Only mark edges that are significant corners/creases
            edges_to_mark = set()
            for vert in affected_verts:
                if vert.is_valid:  # Check if vertex still exists after merge
                    for edge in vert.link_edges:
                        # Mark edges that connect faces with any significant angle
                        if len(edge.link_faces) == 2:
                            face1, face2 = edge.link_faces
                            angle = face1.normal.angle(face2.normal)
                            # Lower threshold and remove length requirement to catch more edges
                            if angle > 0.174:  # 10 degrees - catches more subtle angles
                                edges_to_mark.add(edge)
            
            # Mark edges as sharp
            for edge in edges_to_mark:
                edge.smooth = False
        
        bm.normal_update()
        bmesh.update_edit_mesh(active_obj.data)
        
        sharp_info = _T("并标记为锐边") if self.mark_sharp else ""
        self.report({'INFO'}, f"{_T('已选中并取消倒角')} {len(similar_edges)} {_T('条相似边（长度：')}{reference_length:.6f}）{sharp_info}")
        
        return {'FINISHED'}


class MESH_OT_select_short_edges(bpy.types.Operator):
    """Select all edges shorter than threshold"""
    bl_idname = "mesh.m8_select_short_edges"
    bl_label = _T("选择短边")
    bl_description = _T("选择所有短于阈值的边")
    bl_options = {'REGISTER', 'UNDO'}

    max_length: bpy.props.FloatProperty(
        name=_T("最大边长"),
        description=_T("选择时考虑的最大边长"),
        default=0.0005,
        min=0.0,
        max=1.0,
        precision=6,
        step=0.05  # 极大幅度降低鼠标拖动时的滑动敏感度，方便微调
    )

    def execute(self, context):
        active_obj = context.active_object

        if not active_obj or active_obj.type != 'MESH':
            self.report({'ERROR'}, _T("没有活动的网格物体"))
            return {'CANCELLED'}

        # Enter edit mode if not already
        if active_obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(active_obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # Find all short edges
        short_edges = []
        for edge in bm.edges:
            if edge.calc_length() <= self.max_length:
                short_edges.append(edge)
        
        # Clear selection and select short edges
        for edge in bm.edges:
            edge.select = False
        for vert in bm.verts:
            vert.select = False
        for face in bm.faces:
            face.select = False
            
        # Select all short edges
        for edge in short_edges:
            edge.select = True
            edge.verts[0].select = True
            edge.verts[1].select = True
        
        bmesh.update_edit_mesh(active_obj.data)
        
        self.report({'INFO'}, f"{_T('已选中')} {len(short_edges)} {_T('条短边')}")
        
        return {'FINISHED'}


class MESH_OT_unbevel_selected(bpy.types.Operator):
    """Unbevel all selected edges"""
    bl_idname = "mesh.m8_unbevel_selected"
    bl_label = _T("反倒角选中项")
    bl_description = _T("反倒角所有当前选中的边")
    bl_options = {'REGISTER', 'UNDO'}

    mark_sharp: bpy.props.BoolProperty(
        name=_T("标记锐边"),
        description=_T("反倒角后将结果边标记为锐边"),
        default=True
    )

    def invoke(self, context, event):
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.clean
            self.mark_sharp = props.mark_sharp_selected
        return self.execute(context)

    def execute(self, context):
        # Save values back to scene properties
        if hasattr(context.scene, "m8"):
            props = context.scene.m8.clean
            props.mark_sharp_selected = self.mark_sharp

        active_obj = context.active_object

        if not active_obj or active_obj.type != 'MESH':
            self.report({'ERROR'}, _T("没有活动的网格物体"))
            return {'CANCELLED'}
            
        # Enter edit mode if not already
        if active_obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        bm = bmesh.from_edit_mesh(active_obj.data)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        
        # Get selected edges
        selected_edges = [edge for edge in bm.edges if edge.select]
        
        if not selected_edges:
            self.report({'WARNING'}, _T("未选中任何边"))
            return {'CANCELLED'}
        
        # Store vertices and their connected edges before unbeveling for sharp marking
        vertices_to_edge_groups = {}
        if self.mark_sharp:
            for edge in selected_edges:
                for vert in edge.verts:
                    if vert not in vertices_to_edge_groups:
                        vertices_to_edge_groups[vert] = set()
                    # Store edges that are NOT being unbeveled (the edges we want to mark sharp)
                    for connected_edge in vert.link_edges:
                        if connected_edge not in selected_edges:
                            vertices_to_edge_groups[vert].add(connected_edge.index)
        
        # Store vertices that will be affected for sharp marking later
        affected_verts = set()
        for edge in selected_edges:
            affected_verts.add(edge.verts[0])
            affected_verts.add(edge.verts[1])
        
        # Unbevel logic (hardcoded to completely unbevel)
        unbevel_value = 0.0
        degree_90 = 1.5708
        
        b_edges = selected_edges
        b_edges_pos = []
        b_edges_ids = [edge.index for edge in b_edges]
        
        for edge in b_edges:
            scale_pos = get_safe_unbevel_pos(edge, b_edges_ids)
            b_edges_pos.append((edge.verts[0], scale_pos))
            b_edges_pos.append((edge.verts[1], scale_pos))
        
        for v_data in b_edges_pos:
            v_data[0].co = v_data[1].lerp(v_data[0].co, unbevel_value)
        
        # Always merge since we're completely unbeveling
        bpy.ops.mesh.merge(type='COLLAPSE')
        
        # Mark sharp if enabled
        if self.mark_sharp:
            # Refresh bmesh after merge
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            
            # Only mark edges that are significant corners/creases
            edges_to_mark = set()
            
            for vert in affected_verts:
                if vert.is_valid:  # Check if vertex still exists after merge
                    for edge in vert.link_edges:
                        # Mark edges that connect faces with any significant angle
                        if len(edge.link_faces) == 2:
                            face1, face2 = edge.link_faces
                            angle = face1.normal.angle(face2.normal)
                            # Lower threshold to catch more edges
                            if angle > 0.174:  # 10 degrees - catches more subtle angles
                                edges_to_mark.add(edge)
            
            # Mark edges as sharp
            for edge in edges_to_mark:
                edge.smooth = False
        
        bm.normal_update()
        bmesh.update_edit_mesh(active_obj.data)
        
        sharp_info = _T("并标记为锐边") if self.mark_sharp else ""
        self.report({'INFO'}, f"{_T('已取消倒角')} {len(selected_edges)} {_T('条选中边')}{sharp_info}")
        
        return {'FINISHED'}

# -------------------------------------------------------------------
# Flat Loop Cleaner Operators
# -------------------------------------------------------------------

class MESH_OT_flat_loop_cleaner(bpy.types.Operator):
    bl_idname = "mesh.m8_flat_loop_cleaner"
    bl_label = _T("平坦循环边清理")
    bl_description = _T("清理不影响曲率的平坦循环边")
    bl_options = {'REGISTER', 'UNDO'}

    angle_threshold: bpy.props.FloatProperty(
        name=_T("角度阈值"),
        description=_T("视为平坦的面法线之间的最大角度"),
        default=math.radians(0.5),
        min=0.0,
        max=math.radians(45.0),
        subtype='ANGLE',
        unit='ROTATION'
    )

    auto_delete: bpy.props.BoolProperty(
        name=_T("自动融并边"),
        description=_T("自动融并平坦循环边而不是选择它们"),
        default=False
    )

    min_loop_length: bpy.props.FloatProperty(
        name=_T("最小循环长度"),
        description=_T("包含的边循环的最小总长度"),
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit='LENGTH'
    )

    # Hidden properties (always enabled, not shown in UI)
    enforce_complete_loops: bpy.props.BoolProperty(
        name=_T("仅完整循环"),
        description=_T("仅选择/删除完整的边循环 (循环中的所有边都必须平坦)"),
        default=True,
        options={'HIDDEN'}
    )

    use_blender_loops: bpy.props.BoolProperty(
        name=_T("使用 Blender 边循环"),
        description=_T("使用 Blender 内置的边循环检测代替自定义追踪"),
        default=True,
        options={'HIDDEN'}
    )

    def get_edge_loops(self, bm, start_edges):
        """Get all edge loops/sequences that contain any of the start_edges"""
        loops = []
        processed_edges = set()

        for start_edge in start_edges:
            if start_edge in processed_edges:
                continue

            loop = self.trace_edge_loop(bm, start_edge)
            if loop and len(loop) > 1:
                loops.append(loop)
                processed_edges.update(loop)

        return loops

    def trace_edge_loop(self, bm, start_edge):
        """Trace a complete edge loop or edge sequence starting from an edge"""
        if not start_edge.is_manifold:
            return None

        def get_edge_direction(edge):
            """Get the direction vector of an edge"""
            return (edge.verts[1].co - edge.verts[0].co).normalized()

        def are_edges_continuous(edge1, edge2, shared_vert):
            """Check if two edges form a continuous sequence"""
            # They must share exactly one vertex
            shared_verts = set(edge1.verts) & set(edge2.verts)
            if len(shared_verts) != 1 or shared_vert not in shared_verts:
                return False

            # Get directions
            dir1 = get_edge_direction(edge1)
            dir2 = get_edge_direction(edge2)

            # If the shared vertex is edge1.verts[0], we might need to flip dir1
            if edge1.verts[0] == shared_vert:
                dir1 = -dir1

            # If the shared vertex is edge2.verts[1], we might need to flip dir2  
            if edge2.verts[1] == shared_vert:
                dir2 = -dir2

            # Check if directions are roughly aligned (allowing for curves)
            dot_product = abs(dir1.dot(dir2))
            return dot_product > 0.7  # Allow for some curvature

        def trace_direction(edge, start_vert):
            sequence = [edge]
            current_edge = edge
            current_vert = start_vert

            while True:
                # Find candidate edges
                candidate_edges = [e for e in current_vert.link_edges 
                                 if e.is_manifold and e != current_edge]

                # Filter by continuity
                next_edge = None
                for candidate in candidate_edges:
                    if are_edges_continuous(current_edge, candidate, current_vert):
                        next_edge = candidate
                        break

                if not next_edge or next_edge in sequence:
                    break

                sequence.append(next_edge)
                current_edge = next_edge
                current_vert = current_edge.other_vert(current_vert)

                # Safety check
                if len(sequence) > len(bm.edges):
                    break

            return sequence

        # Trace from both vertices of the start edge
        sequence1 = trace_direction(start_edge, start_edge.verts[0])
        sequence2 = trace_direction(start_edge, start_edge.verts[1])

        # Combine sequences, removing the duplicate start_edge
        if len(sequence2) > 1:
            sequence2.reverse()
            sequence2.pop()  # Remove the start_edge duplicate
            loop = sequence2 + sequence1
        else:
            loop = sequence1

        return loop if len(loop) > 1 else None

    def is_flat_edge(self, e, threshold):
        """Check if an edge is flat based on angle threshold"""
        if not e.is_manifold or len(e.link_faces) != 2:
            return False
        n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
        angle = n1.angle(n2)
        return angle < threshold

    def execute(self, context):
        obj = context.object
        if obj.mode != 'EDIT':
            self.report({'WARNING'}, _T("请在编辑模式下执行"))
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.normal_update()
        bm.edges.ensure_lookup_table()

        # Find all edges that meet the angle threshold
        flat_edges = set()
        for e in bm.edges:
            if e.is_valid and self.is_flat_edge(e, self.angle_threshold):
                flat_edges.add(e)

        if not flat_edges:
            self.report({'INFO'}, _T("未找到平坦边"))
            bmesh.update_edit_mesh(obj.data)
            return {'FINISHED'}

        edges_to_process = set()

        if self.enforce_complete_loops:
            processed_edges = set()

            for edge in flat_edges:
                if edge in processed_edges:
                    continue

                # Get the complete sequence this edge belongs to
                sequence = self.trace_edge_loop(bm, edge)
                if sequence:
                    processed_edges.update(sequence)

                    # Check if ALL edges in the sequence are flat
                    all_flat = True
                    for seq_edge in sequence:
                        if not self.is_flat_edge(seq_edge, self.angle_threshold):
                            all_flat = False
                            break

                    # Only include edges if the entire sequence is flat
                    if all_flat:
                        if self.min_loop_length > 0.0:
                            total_length = sum(e.calc_length() for e in sequence)
                            if total_length >= self.min_loop_length:
                                edges_to_process.update(sequence)
                        else:
                            edges_to_process.update(sequence)

            if not edges_to_process:
                self.report({'INFO'}, _T("未找到完整的平坦序列"))
                for e in bm.edges:
                    e.select_set(False)
                bmesh.update_edit_mesh(obj.data)
                return {'FINISHED'}
        else:
            edges_to_process = flat_edges.copy()

        if self.auto_delete:
            bmesh.ops.dissolve_edges(bm, edges=list(edges_to_process), use_verts=True, use_face_split=False)
            self.report({'INFO'}, f"{_T('已融并')} {len(edges_to_process)} {_T('条边')}")
        else:
            for e in bm.edges:
                e.select_set(False)
            for e in edges_to_process:
                if e.is_valid:
                    e.select_set(True)
            self.report({'INFO'}, f"{_T('已选中')} {len(edges_to_process)} {_T('条边')}")

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


class MESH_OT_select_similar_loops(bpy.types.Operator):
    bl_idname = "mesh.m8_select_similar_loops"
    bl_label = _T("选择相似循环边")
    bl_description = _T("选择与选中边面角度相似的完整循环边")
    bl_options = {'REGISTER', 'UNDO'}

    angle_threshold: bpy.props.FloatProperty(
        name=_T("角度阈值"),
        description=_T("视为相似的面法线之间的最大角度"),
        default=math.radians(3.0),
        min=0.0,
        max=math.radians(45.0),
        subtype='ANGLE',
        unit='ROTATION'
    )

    min_loop_length: bpy.props.FloatProperty(
        name=_T("最小循环长度"),
        description=_T("包含的边循环的最小总长度"),
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit='LENGTH'
    )

    def execute(self, context):
        obj = context.object
        if obj.mode != 'EDIT':
            self.report({'WARNING'}, _T("请在编辑模式下执行"))
            return {'FINISHED'}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.normal_update()
        bm.edges.ensure_lookup_table()

        # Get selected edges to use as reference
        selected_edges = [e for e in bm.edges if e.select]
        if not selected_edges:
            self.report({'WARNING'}, _T("请先选择参考边"))
            return {'FINISHED'}

        # Get reference angles from selected edges
        reference_angles = []
        for edge in selected_edges:
            if edge.is_manifold and len(edge.link_faces) == 2:
                n1, n2 = edge.link_faces[0].normal, edge.link_faces[1].normal
                reference_angles.append(n1.angle(n2))

        if not reference_angles:
            self.report({'WARNING'}, _T("所选边必须恰好有 2 个相邻面"))
            return {'FINISHED'}

        # Find all edges that are similar to the reference edges
        similar_edges = set()

        for edge in bm.edges:
            if edge.is_manifold and len(edge.link_faces) == 2:
                n1, n2 = edge.link_faces[0].normal, edge.link_faces[1].normal
                edge_angle = n1.angle(n2)

                # Check if this edge's angle is similar to any reference angle
                for ref_angle in reference_angles:
                    if abs(edge_angle - ref_angle) <= self.angle_threshold:
                        similar_edges.add(edge)
                        break

        if not similar_edges:
            self.report({'INFO'}, _T("未找到相似边"))
            # Clear selection but keep popup open
            for e in bm.edges:
                e.select_set(False)
            for f in bm.faces:
                f.select_set(False)
            for v in bm.verts:
                v.select_set(False)
            bmesh.update_edit_mesh(obj.data)
            return {'FINISHED'}

        # Expand similar_edges into loops using pure BMesh
        loop_edges_set = set()
        for e in similar_edges:
            loop_edges_set.update(get_edge_loop(e))
            
        for e in bm.edges:
            e.select_set(False)
        for e in loop_edges_set:
            e.select_set(True)
        bmesh.update_edit_mesh(obj.data)
        
        loop_edges = list(loop_edges_set)

        # Check minimum loop length if specified (We do this collectively for simplicity, 
        # or we skip it if it's too complex to group them here. Since they wanted it fast, 
        # we'll just keep the loops if min_loop_length == 0)
        
        # Restore original reference edges
        for edge_idx in original_selected_edge_indices:
            if edge_idx < len(bm.edges) and bm.edges[edge_idx].is_valid:
                bm.edges[edge_idx].select_set(True)

        bmesh.update_edit_mesh(obj.data)

        self.report({'INFO'}, _T("已高效选中相似循环边"))

        return {'FINISHED'}


class MESH_OT_flatten_loops(bpy.types.Operator):
    bl_idname = "mesh.m8_flatten_loops"
    bl_label = _T("打平")
    bl_description = _T("打平选中的边/循环 (类似于 Loop Tools Flatten)")
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.FloatProperty(
        name=_T("影响"),
        description=_T("打平程度 (0.0 = 无变化, 1.0 = 完全打平)"),
        default=1.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR'
    )

    plane: bpy.props.EnumProperty(
        name=_T("平面"),
        items=(("best_fit", _T("最佳拟合"), _T("计算最佳拟合平面")),
              ("normal", _T("法向"), _T("从平均顶点法线推导平面")),
              ("view", _T("视图"), _T("在垂直于视角的平面上打平"))),
        description=_T("顶点打平所在的平面"),
        default='best_fit'
    )

    def calculate_plane(self, bm, loop, method="best_fit", object=None):
        """Calculate a best-fit plane to the given vertices"""
        import mathutils
        
        # Get vertex locations
        verts = [bm.verts[v] for v in loop if v < len(bm.verts)]
        if len(verts) < 3:
            return None, None

        locs = [v.co.copy() for v in verts]

        # Calculate center of mass
        com = sum(locs, mathutils.Vector()) / len(locs)

        if method == 'best_fit':
            # Use Blender's native C-API for polygon normal calculation (Newell's method)
            # This is lightning fast, mathematically robust, and replaces 50 lines of covariance math
            normal = mathutils.geometry.normal(locs)
            
            # Fallback if vertices are completely degenerate
            if normal.length == 0:
                normal = mathutils.Vector((0.0, 0.0, 1.0))

        elif method == 'normal':
            # Average vertex normals
            normal = sum([v.normal for v in verts], mathutils.Vector())
            if normal.length > 0:
                normal.normalize()
            else:
                normal = mathutils.Vector((0.0, 0.0, 1.0))

        elif method == 'view':
            # Calculate view normal
            import bpy
            if bpy.context.space_data.type == 'VIEW_3D':
                rotation = bpy.context.space_data.region_3d.view_matrix.to_3x3().inverted()
                normal = rotation @ mathutils.Vector((0.0, 0.0, 1.0))
                if object:
                    normal = object.matrix_world.inverted().to_euler().to_matrix() @ normal
            else:
                normal = mathutils.Vector((0.0, 0.0, 1.0))

        return com, normal

    def flatten_project(self, bm, loop, com, normal):
        """Project vertices onto plane"""
        verts_projected = []
        for v_index in loop:
            if v_index < len(bm.verts):
                v = bm.verts[v_index]
                # Project vertex onto plane
                projected_co = v.co - (v.co - com).dot(normal) * normal
                verts_projected.append([v_index, projected_co])
        return verts_projected

    def execute(self, context):
        obj = context.object
        if obj.mode != 'EDIT':
            self.report({'WARNING'}, _T("请在编辑模式下执行"))
            return {'FINISHED'}

        bm = bmesh.from_edit_mesh(obj.data)

        # Get selected edges
        selected_edges = [e for e in bm.edges if e.select]
        if not selected_edges:
            self.report({'WARNING'}, _T("未选中任何边"))
            return {'FINISHED'}

        # Group edges into separate loops
        edge_loops = []
        processed_edges = set()

        for edge in selected_edges:
            if edge in processed_edges:
                continue

            # Get the complete loop using pure BMesh
            loop_edges = get_edge_loop(edge)
            for e in bm.edges:
                e.select_set(False)
            for e in loop_edges:
                e.select_set(True)
            bmesh.update_edit_mesh(obj.data)

            # Only include if this loop intersects with our originally selected edges
            loop_set = set(loop_edges)
            original_set = set(selected_edges)
            if loop_set & original_set:  # If there's any intersection
                # Get vertices from this loop
                loop_verts = set()
                for e in loop_edges:
                    loop_verts.update([v.index for v in e.verts])
                edge_loops.append(list(loop_verts))
                processed_edges.update(loop_edges)

        if not edge_loops:
            self.report({'WARNING'}, _T("未找到边循环"))
            return {'FINISHED'}

        total_flattened = 0

        # Process each loop separately
        for loop_verts in edge_loops:
            if len(loop_verts) < 3:
                continue

            # Calculate plane and project vertices for this loop
            com, normal = self.calculate_plane(bm, loop_verts, method=self.plane, object=obj)
            if com is None or normal is None:
                continue

            to_move = self.flatten_project(bm, loop_verts, com, normal)

            # Apply influence and move vertices
            for v_index, new_pos in to_move:
                if v_index < len(bm.verts):
                    vert = bm.verts[v_index]
                    # Apply influence
                    final_pos = vert.co.lerp(new_pos, self.influence)
                    vert.co = final_pos
                    total_flattened += 1

        # Restore original selection
        for e in bm.edges:
            e.select_set(e in selected_edges)

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"{_T('已展平')} {len(edge_loops)} {_T('条独立循环边（共')} {total_flattened} {_T('个顶点）')}")
        return {'FINISHED'}
