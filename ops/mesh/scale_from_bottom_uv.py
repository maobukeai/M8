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

class MESH_OT_ScaleFromBottomUV(bpy.types.Operator):
    bl_idname = "mesh.scale_from_bottom_uv"
    bl_label = "从底部UV缩放"
    bl_options = {'REGISTER', 'UNDO'}

    scale: bpy.props.FloatProperty(name="缩放系数", description="缩放系数（1.0 不变）", default=1.0, min=0.01, soft_max=3.0)
    uniform: bpy.props.BoolProperty(name="均匀", description="勾选：整体缩放；取消：只在叶片平面内缩放（尽量保持厚度）", default=True)

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and
                context.active_object.type == 'MESH' and
                context.active_object.mode == 'EDIT')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scale")
        layout.prop(self, "uniform")

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        uv_layer = bm.loops.layers.uv.active
        selected_faces = {f for f in bm.faces if f.select}
        if not selected_faces:
            self.report({'WARNING'}, "未选择任何面")
            return {'CANCELLED'}

        islands = _find_face_islands(selected_faces)
        if not islands:
            self.report({'WARNING'}, "未在选择中找到连通岛")
            return {'CANCELLED'}

        scaled_count = 0
        for island in islands:
            vert_uv_data = {}
            for face in island:
                for loop in face.loops:
                    vert = loop.vert
                    v_coord = loop[uv_layer].uv.y if uv_layer else vert.co.y
                    if vert not in vert_uv_data:
                        vert_uv_data[vert] = v_coord
                    else:
                        vert_uv_data[vert] = min(vert_uv_data[vert], v_coord)

            if not vert_uv_data:
                continue

            min_v = min(vert_uv_data.values())
            max_v = max(vert_uv_data.values())
            v_range = max_v - min_v

            all_verts = list(vert_uv_data.keys())
            if v_range < 1e-4:
                pivot = Vector((0.0, 0.0, 0.0))
                for v in all_verts:
                    pivot += v.co
                pivot /= len(all_verts)
            else:
                tolerance = v_range * 0.15
                bottom_verts = [v for v, uv_v in vert_uv_data.items() if uv_v <= min_v + tolerance]
                if not bottom_verts:
                    bottom_verts = all_verts
                pivot = Vector((0.0, 0.0, 0.0))
                for v in bottom_verts:
                    pivot += v.co
                pivot /= len(bottom_verts)

            for vert in all_verts:
                offset = vert.co - pivot
                if self.uniform:
                    vert.co = pivot + offset * self.scale
                else:
                    if uv_layer:
                        tangent, _, normal = _island_uv_tangent_space(island, uv_layer)
                    else:
                        tangent = Vector((1.0, 0.0, 0.0))
                        normal = Vector((0.0, 0.0, 1.0))
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
                    off_t = t * offset.dot(t)
                    off_b = b * offset.dot(b)
                    off_n = n * offset.dot(n)
                    vert.co = pivot + (off_t + off_b) * self.scale + off_n

            scaled_count += 1

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"已从底部UV缩放 {scaled_count} 个岛")
        return {'FINISHED'}
