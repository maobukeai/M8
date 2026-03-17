import bpy
import bmesh
from mathutils import Vector

def _find_face_islands(selected_faces):
    visited = set()
    islands = []
    for face in selected_faces:
        if face in visited:
            continue
        island = set()
        stack = [face]
        while stack:
            f = stack.pop()
            if f in visited or f not in selected_faces:
                continue
            visited.add(f)
            island.add(f)
            for e in f.edges:
                for lf in e.link_faces:
                    if lf not in visited and lf in selected_faces:
                        stack.append(lf)
        if island:
            islands.append(island)
    return islands

def _island_uv_tangent_space(island_faces, uv_layer):
    weighted_tangent = Vector((0.0, 0.0, 0.0))
    weighted_bitangent = Vector((0.0, 0.0, 0.0))
    weighted_normal = Vector((0.0, 0.0, 0.0))

    for face in island_faces:
        if len(face.loops) < 3:
            continue
        area = face.calc_area()
        if area < 1e-7:
            continue

        loops = list(face.loops)[:3]
        p0 = loops[0].vert.co
        p1 = loops[1].vert.co
        p2 = loops[2].vert.co

        uv0 = loops[0][uv_layer].uv
        uv1 = loops[1][uv_layer].uv
        uv2 = loops[2][uv_layer].uv

        e1 = p1 - p0
        e2 = p2 - p0

        du1 = uv1.x - uv0.x
        dv1 = uv1.y - uv0.y
        du2 = uv2.x - uv0.x
        dv2 = uv2.y - uv0.y

        det = du1 * dv2 - du2 * dv1
        if abs(det) < 1e-7:
            continue
        inv_det = 1.0 / det

        tangent = (e1 * dv2 - e2 * dv1) * inv_det
        bitangent = (e2 * du1 - e1 * du2) * inv_det

        weighted_tangent += tangent * area
        weighted_bitangent += bitangent * area
        weighted_normal += face.normal * area

    if weighted_tangent.length > 0:
        weighted_tangent.normalize()
    else:
        weighted_tangent = Vector((1.0, 0.0, 0.0))

    if weighted_bitangent.length > 0:
        weighted_bitangent.normalize()
    else:
        weighted_bitangent = Vector((0.0, 1.0, 0.0))

    if weighted_normal.length > 0:
        weighted_normal.normalize()
    else:
        weighted_normal = Vector((0.0, 0.0, 1.0))

    return weighted_tangent, weighted_bitangent, weighted_normal

def _island_uv_bounds(island_faces, uv_layer):
    min_u, min_v = float('inf'), float('inf')
    max_u, max_v = float('-inf'), float('-inf')
    for face in island_faces:
        for loop in face.loops:
            uv = loop[uv_layer].uv
            min_u = min(min_u, uv.x)
            min_v = min(min_v, uv.y)
            max_u = max(max_u, uv.x)
            max_v = max(max_v, uv.y)
    if min_u == float('inf'):
        return None
    return (min_u, min_v, max_u, max_v)

def _island_center_and_size(island_faces):
    verts = set()
    for face in island_faces:
        for vert in face.verts:
            verts.add(vert)
    if not verts:
        return Vector((0.0, 0.0, 0.0)), 0.1, 0.1

    coords = [v.co for v in verts]
    min_co = Vector((min(v.x for v in coords), min(v.y for v in coords), min(v.z for v in coords)))
    max_co = Vector((max(v.x for v in coords), max(v.y for v in coords), max(v.z for v in coords)))
    center = (min_co + max_co) / 2
    size = max_co - min_co
    dims = sorted([size.x, size.y, size.z], reverse=True)
    width = dims[0] if dims[0] > 1e-4 else 0.1
    height = dims[1] if dims[1] > 1e-4 else 0.1
    return center, width, height

def _island_stem_position(island_faces, uv_layer):
    vert_uv_data = []
    for face in island_faces:
        for loop in face.loops:
            v_coord = loop[uv_layer].uv.y if uv_layer else loop.vert.co.y
            vert_uv_data.append((loop.vert.co.copy(), v_coord))
    if not vert_uv_data:
        return None

    min_v = min(d[1] for d in vert_uv_data)
    max_v = max(d[1] for d in vert_uv_data)
    v_range = max_v - min_v
    if v_range < 1e-4:
        avg = Vector((0.0, 0.0, 0.0))
        for co, _ in vert_uv_data:
            avg += co
        return avg / len(vert_uv_data)

    tolerance = v_range * 0.15
    bottom_verts = [d[0] for d in vert_uv_data if d[1] <= min_v + tolerance]
    if not bottom_verts:
        bottom_verts = [d[0] for d in vert_uv_data]

    stem_pos = Vector((0.0, 0.0, 0.0))
    for co in bottom_verts:
        stem_pos += co
    stem_pos /= len(bottom_verts)
    return stem_pos

def _island_material_index(island_faces):
    material_counts = {}
    for face in island_faces:
        idx = face.material_index
        material_counts[idx] = material_counts.get(idx, 0) + 1
    return max(material_counts, key=material_counts.get) if material_counts else 0

def _create_plane_in_bmesh(bm, uv_layer, center, tangent, normal, width, height, uv_bounds, material_index, *, stem_extension=0.0, stem_position=None):
    t = tangent.normalized()
    n = normal.normalized()
    t = t - n * t.dot(n)
    if t.length > 1e-4:
        t.normalize()
    else:
        if abs(n.z) < 0.9:
            t = n.cross(Vector((0.0, 0.0, 1.0))).normalized()
        else:
            t = n.cross(Vector((1.0, 0.0, 0.0))).normalized()
    b = n.cross(t).normalized()

    hw = width / 2.0
    if stem_position is not None:
        base = stem_position
        v1 = bm.verts.new(base + t * (-hw) + b * (-stem_extension))
        v2 = bm.verts.new(base + t * (hw) + b * (-stem_extension))
        v3 = bm.verts.new(base + t * (hw) + b * height)
        v4 = bm.verts.new(base + t * (-hw) + b * height)
    else:
        hh = height / 2.0
        v1 = bm.verts.new(center + t * (-hw) + b * (-hh - stem_extension))
        v2 = bm.verts.new(center + t * (hw) + b * (-hh - stem_extension))
        v3 = bm.verts.new(center + t * (hw) + b * (hh))
        v4 = bm.verts.new(center + t * (-hw) + b * (hh))

    try:
        face = bm.faces.new([v1, v2, v3, v4])
    except ValueError:
        return None

    face.material_index = material_index
    if uv_bounds and uv_layer:
        min_u, min_v, max_u, max_v = uv_bounds
        uvs = [(min_u, min_v), (max_u, min_v), (max_u, max_v), (min_u, max_v)]
        for i, loop in enumerate(face.loops):
            loop[uv_layer].uv = uvs[i]
    return face

class MESH_OT_LeavesToPlanes(bpy.types.Operator):
    bl_idname = "mesh.leaves_to_planes"
    bl_label = "叶片转面片"
    bl_options = {'REGISTER', 'UNDO'}

    scope: bpy.props.EnumProperty(
        name="范围",
        description="处理范围",
        items=[
            ('SELECTED', "仅选择", "只处理当前已选中的面"),
            ('ALL', "全网格", "处理整个网格的所有面"),
        ],
        default='SELECTED',
    )
    stem_extension: bpy.props.FloatProperty(name="茎部延伸", description="向叶柄方向延伸面片底边（本地单位）", default=0.0, min=0.0, soft_max=1.0, unit='LENGTH')
    anchor_to_stem: bpy.props.BoolProperty(name="锚定到叶柄", description="让面片底边对齐叶柄位置（更容易保持连接）", default=True)
    face_count_threshold: bpy.props.IntProperty(name="面数阈值", description="只转换面数小于此值的岛（防止误转枝干）", default=50, min=3)

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and
                context.active_object.type == 'MESH' and
                context.active_object.mode == 'EDIT')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scope")
        layout.prop(self, "anchor_to_stem")
        layout.prop(self, "stem_extension")
        layout.prop(self, "face_count_threshold")

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        uv_layer = bm.loops.layers.uv.active
        if self.scope == 'ALL':
            pool_faces = set(bm.faces)
        else:
            pool_faces = {f for f in bm.faces if f.select}
            if not pool_faces:
                self.report({'WARNING'}, "未选择任何面")
                return {'CANCELLED'}

        islands = _find_face_islands(pool_faces)
        if not islands:
            self.report({'WARNING'}, "未找到连通岛")
            return {'CANCELLED'}

        # 过滤面数过多的岛（可能是枝干）
        valid_islands = []
        skipped_count = 0
        for island in islands:
            if len(island) <= self.face_count_threshold:
                valid_islands.append(island)
            else:
                skipped_count += 1
        
        if not valid_islands:
            self.report({'WARNING'}, f"选中的岛面数均超过阈值 ({self.face_count_threshold})，未转换")
            return {'CANCELLED'}

        created_count = 0
        for island in valid_islands:
            if uv_layer:
                tangent, _, normal = _island_uv_tangent_space(island, uv_layer)
                uv_bounds = _island_uv_bounds(island, uv_layer)
            else:
                tangent = Vector((1.0, 0.0, 0.0))
                normal = Vector((0.0, 0.0, 1.0))
                uv_bounds = None

            center, width, height = _island_center_and_size(island)
            material_index = _island_material_index(island)

            stem_position = None
            if self.anchor_to_stem and uv_layer:
                stem_position = _island_stem_position(island, uv_layer)

            for face in list(island):
                bm.faces.remove(face)

            new_face = _create_plane_in_bmesh(
                bm,
                uv_layer,
                center,
                tangent,
                normal,
                width,
                height,
                uv_bounds,
                material_index,
                stem_extension=self.stem_extension,
                stem_position=stem_position,
            )
            if new_face:
                new_face.select = True
                for v in new_face.verts:
                    v.select = True
                for e in new_face.edges:
                    e.select = True
                created_count += 1

        verts_to_remove = [v for v in bm.verts if not v.link_faces]
        for v in verts_to_remove:
            bm.verts.remove(v)

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"已将 {len(islands)} 个岛转换为 {created_count} 个面片")
        return {'FINISHED'}
