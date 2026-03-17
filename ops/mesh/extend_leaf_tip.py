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

class MESH_OT_ExtendLeafTip(bpy.types.Operator):
    bl_idname = "mesh.extend_leaf_tip"
    bl_label = "延长叶尖"
    bl_options = {'REGISTER', 'UNDO'}

    extension: bpy.props.FloatProperty(name="延伸量", description="沿叶片方向延伸叶尖（本地单位）", default=0.002, soft_min=-1.0, soft_max=1.0, unit='LENGTH')

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and
                context.active_object.type == 'MESH' and
                context.active_object.mode == 'EDIT')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "extension")

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

        extended_count = 0
        for island in islands:
            vert_uv_data = {}
            for face in island:
                for loop in face.loops:
                    vert = loop.vert
                    v_coord = loop[uv_layer].uv.y if uv_layer else vert.co.y
                    if vert not in vert_uv_data:
                        vert_uv_data[vert] = v_coord
                    else:
                        vert_uv_data[vert] = max(vert_uv_data[vert], v_coord)

            if not vert_uv_data:
                continue

            min_v = min(vert_uv_data.values())
            max_v = max(vert_uv_data.values())
            v_range = max_v - min_v
            if v_range < 1e-4:
                continue

            tolerance = v_range * 0.15
            bottom_verts = [v for v, uv_v in vert_uv_data.items() if uv_v <= min_v + tolerance]
            top_verts = [v for v, uv_v in vert_uv_data.items() if uv_v >= max_v - tolerance]
            if not bottom_verts or not top_verts:
                continue

            stem_center = Vector((0.0, 0.0, 0.0))
            for v in bottom_verts:
                stem_center += v.co
            stem_center /= len(bottom_verts)

            tip_center = Vector((0.0, 0.0, 0.0))
            for v in top_verts:
                tip_center += v.co
            tip_center /= len(top_verts)

            leaf_direction = tip_center - stem_center
            if leaf_direction.length < 1e-4:
                continue
            leaf_direction.normalize()

            for vert, uv_v in vert_uv_data.items():
                t = (uv_v - min_v) / v_range
                vert.co += leaf_direction * self.extension * t

            extended_count += 1

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"已延长 {extended_count} 个叶片的叶尖")
        return {'FINISHED'}
