import bpy


class VIEW3D_MT_M8MeshOptimizationPie(bpy.types.Menu):
    bl_label = "优化"
    bl_idname = "VIEW3D_MT_m8_mesh_optimization_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()

        op = pie.operator("m8.mesh_merge_by_distance", text="合并(小)", icon="AUTOMERGE_ON")
        op.distance = 0.0001

        pie.operator("m8.mesh_limited_dissolve", text="有限融并", icon="MOD_DECIM")

        pie.operator("m8.mesh_delete_loose", text="删除游离", icon="X")

        op = pie.operator("m8.mesh_recalc_normals", text="重算法线(外)", icon="NORMALS_FACE")
        op.inside = False

        pie.operator("mesh.select_non_manifold", text="非流形", icon="SELECT_SET")

        op = pie.operator("m8.mesh_recalc_normals", text="重算法线(内)", icon="NORMALS_FACE")
        op.inside = True

        pie.operator("mesh.tris_convert_to_quads", text="三角转四边", icon="MOD_TRIANGULATE")

        op = pie.operator("m8.mesh_merge_by_distance", text="合并(大)", icon="AUTOMERGE_OFF")
        op.distance = 0.001


class M8_OT_MeshOptimizationMenu(bpy.types.Operator):
    bl_idname = "m8.mesh_optimization_menu"
    bl_label = "优化"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def invoke(self, context, event):
        bpy.ops.wm.call_menu_pie(name=VIEW3D_MT_M8MeshOptimizationPie.bl_idname)
        return {"FINISHED"}


class M8_OT_MeshMergeByDistance(bpy.types.Operator):
    bl_idname = "m8.mesh_merge_by_distance"
    bl_label = "Merge by Distance"
    bl_options = {"REGISTER", "UNDO"}

    distance: bpy.props.FloatProperty(name="Distance", default=0.0001, min=0.0, soft_max=0.1, precision=6)

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def execute(self, context):
        try:
            bpy.ops.mesh.merge_by_distance(distance=self.distance)
        except Exception:
            # Fallback or just fail silently if op is not available (unlikely in 4.4)
            return {"CANCELLED"}
        return {"FINISHED"}


class M8_OT_MeshDeleteLoose(bpy.types.Operator):
    bl_idname = "m8.mesh_delete_loose"
    bl_label = "Delete Loose"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def execute(self, context):
        try:
            bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=True)
            return {"FINISHED"}
        except Exception:
            return {"CANCELLED"}


class M8_OT_MeshRecalcNormals(bpy.types.Operator):
    bl_idname = "m8.mesh_recalc_normals"
    bl_label = "Recalculate Normals"
    bl_options = {"REGISTER", "UNDO"}

    inside: bpy.props.BoolProperty(name="Inside", default=False)

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def execute(self, context):
        try:
            bpy.ops.mesh.normals_make_consistent(inside=self.inside)
            return {"FINISHED"}
        except Exception:
            return {"CANCELLED"}


class M8_OT_MeshLimitedDissolve(bpy.types.Operator):
    bl_idname = "m8.mesh_limited_dissolve"
    bl_label = "Limited Dissolve"
    bl_options = {"REGISTER", "UNDO"}

    angle_limit: bpy.props.FloatProperty(name="Angle Limit", default=0.0872665, min=0.0, soft_max=3.14159, subtype="ANGLE")

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def execute(self, context):
        try:
            bpy.ops.mesh.dissolve_limited(angle_limit=self.angle_limit)
            return {"FINISHED"}
        except Exception:
            return {"CANCELLED"}


class M8_OT_SmartDissolve(bpy.types.Operator):
    bl_idname = "m8.smart_dissolve"
    bl_label = "智能融并"
    bl_description = "根据当前选择模式智能融并点、线或面"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.mode == "EDIT_MESH" and context.object and context.object.type == "MESH")

    def execute(self, context):
        select_mode = context.tool_settings.mesh_select_mode
        # (Vertex, Edge, Face)
        
        try:
            if select_mode[2]: # Face
                bpy.ops.mesh.dissolve_faces()
            elif select_mode[1]: # Edge
                bpy.ops.mesh.dissolve_edges()
            elif select_mode[0]: # Vertex
                bpy.ops.mesh.dissolve_verts()
            else:
                # Should not happen in standard edit mode usually
                return {'CANCELLED'}
        except Exception as e:
            self.report({'WARNING'}, f"融并失败: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

