import bmesh
import bpy


def _iter_bm_selected_verts(context):
    for obj in context.objects_in_mode:
        if not obj or obj.type != "MESH" or not obj.data:
            continue
        bm = bmesh.from_edit_mesh(obj.data)
        for vert in bm.verts:
            if vert.select:
                yield obj, bm, vert


def _iter_bm_selected_edges(context):
    for obj in context.objects_in_mode:
        if not obj or obj.type != "MESH" or not obj.data:
            continue
        bm = bmesh.from_edit_mesh(obj.data)
        for edge in bm.edges:
            if edge.select:
                yield obj, bm, edge


class M8_OT_VertCrease(bpy.types.Operator):
    bl_idname = "m8.vert_crease"
    bl_label = "顶点折痕"
    bl_options = {"REGISTER", "UNDO"}

    value: bpy.props.FloatProperty(name="Value")

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH":
            return False
        return next(_iter_bm_selected_verts(context), None) is not None

    def execute(self, context):
        bpy.ops.transform.vert_crease(value=-1)
        bpy.ops.transform.vert_crease(value=self.value)
        return {"FINISHED"}


class M8_OT_VertBevelWeight(bpy.types.Operator):
    bl_idname = "m8.vert_bevel_weight"
    bl_label = "顶点倒角权重"
    bl_options = {"REGISTER", "UNDO"}

    value: bpy.props.FloatProperty(name="Value")

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH":
            return False
        return next(_iter_bm_selected_verts(context), None) is not None

    def execute(self, context):
        for obj in context.objects_in_mode:
            if not obj or obj.type != "MESH" or not obj.data:
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            layer = bm.verts.layers.float.get("bevel_weight_vert")
            if layer is None:
                layer = bm.verts.layers.float.new("bevel_weight_vert")
            for vert in bm.verts:
                if vert.select:
                    vert[layer] = self.value
            bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class M8_OT_EdgeCrease(bpy.types.Operator):
    bl_idname = "m8.edge_crease"
    bl_label = "边折痕"
    bl_options = {"REGISTER", "UNDO"}

    value: bpy.props.FloatProperty(name="Value")

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH":
            return False
        return next(_iter_bm_selected_edges(context), None) is not None

    def execute(self, context):
        bpy.ops.transform.edge_crease(value=-1)
        bpy.ops.transform.edge_crease(value=self.value)
        return {"FINISHED"}


class M8_OT_EdgeBevelWeight(bpy.types.Operator):
    bl_idname = "m8.edge_bevel_weight"
    bl_label = "边倒角权重"
    bl_options = {"REGISTER", "UNDO"}

    value: bpy.props.FloatProperty(name="Value")

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH":
            return False
        return next(_iter_bm_selected_edges(context), None) is not None

    def execute(self, context):
        bpy.ops.transform.edge_bevelweight(value=-1)
        bpy.ops.transform.edge_bevelweight(value=self.value)
        return {"FINISHED"}


class M8_OT_ClearAllEdgeProperty(bpy.types.Operator):
    bl_idname = "m8.clear_all_edge_property"
    bl_label = "清除所有边属性"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH":
            return False
        return next(_iter_bm_selected_edges(context), None) is not None

    def execute(self, context):
        bpy.ops.transform.edge_crease("EXEC_DEFAULT", value=-1)
        bpy.ops.transform.edge_bevelweight("EXEC_DEFAULT", value=-1)
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.mesh.mark_sharp(clear=True, use_verts=False)
        bpy.ops.mesh.mark_freestyle_edge(clear=True)
        return {"FINISHED"}

