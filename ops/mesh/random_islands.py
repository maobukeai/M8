import bpy
import bmesh
import random

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

class MESH_OT_SelectRandomIslands(bpy.types.Operator):
    bl_idname = "mesh.select_random_islands"
    bl_label = "随机选择岛"
    bl_description = "按比例随机选择网格岛（连通面片块）"
    bl_options = {'REGISTER', 'UNDO'}

    scope: bpy.props.EnumProperty(
        name="范围",
        description="从哪里抽取岛进行随机",
        items=[
            ('ALL', "全网格", "基于整个网格的岛"),
            ('SELECTED', "当前选择", "只基于当前已选中的面"),
        ],
        default='ALL',
    )
    percentage: bpy.props.FloatProperty(
        name="比例",
        description="要随机选择的岛比例",
        default=50.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE',
    )
    use_count: bpy.props.BoolProperty(
        name="按数量",
        description="使用固定数量而不是百分比",
        default=False,
    )
    count: bpy.props.IntProperty(
        name="数量",
        description="要随机选择的岛数量",
        default=1,
        min=1,
    )
    seed: bpy.props.IntProperty(
        name="随机种子",
        description="随机种子（相同种子会得到相同结果）",
        default=0,
        min=0,
    )
    action: bpy.props.EnumProperty(
        name="动作",
        description="对随机出的岛做什么",
        items=[
            ('SELECT', "选择", "选择随机出的岛"),
            ('DESELECT', "取消选择", "对随机出的岛取消选择"),
        ],
        default='SELECT',
    )
    extend: bpy.props.BoolProperty(
        name="追加选择",
        description="在当前选择基础上追加，而不是替换",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        if self.seed == 0:
            self.seed = random.randint(0, 1000000)
        return context.window_manager.invoke_props_popup(self, event)

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)

        if self.scope == 'SELECTED':
            pool_faces = {f for f in bm.faces if f.select}
            if not pool_faces:
                self.report({'WARNING'}, "当前选择中没有面")
                return {'CANCELLED'}
        else:
            pool_faces = set(bm.faces)

        islands = _find_face_islands(pool_faces)
        if not islands:
            self.report({'WARNING'}, "未找到任何岛")
            return {'CANCELLED'}

        if self.action == 'SELECT' and not self.extend:
            for f in bm.faces:
                f.select = False
            for e in bm.edges:
                e.select = False
            for v in bm.verts:
                v.select = False

        random.seed(self.seed)
        
        if self.use_count:
            num_to_select = self.count
        else:
            num_to_select = int(len(islands) * (self.percentage / 100.0))
            
        selected_islands = random.sample(islands, min(num_to_select, len(islands)))
        for island in selected_islands:
            for face in island:
                face.select = (self.action == 'SELECT')
                for vert in face.verts:
                    vert.select = (self.action == 'SELECT')
                for edge in face.edges:
                    edge.select = (self.action == 'SELECT')

        bmesh.update_edit_mesh(obj.data)
        if self.action == 'SELECT':
            self.report({'INFO'}, f"已选择 {len(selected_islands)}/{len(islands)} 个岛")
        else:
            self.report({'INFO'}, f"已取消选择 {len(selected_islands)}/{len(islands)} 个岛")
        return {'FINISHED'}
