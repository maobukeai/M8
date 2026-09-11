import bpy
from ...utils.i18n import _T


def build_or_update_uv_checker_material(scale=2.0, grid_type="UV_GRID"):
    """创建或更新全局 UV 棋盘格材质与着色器节点"""
    mat_name = "M8_UV_Checker"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(mat_name)

    mat.use_fake_user = True
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True

    # 优化：若材质节点已存在且网格类型未变，仅需更新 Mapping 缩放，避免重复重建节点树
    current_grid_type = mat.get("m8_grid_type")
    mapping = mat.node_tree.nodes.get("M8_Mapping") if mat.node_tree else None
    if mapping and current_grid_type == grid_type and len(mat.node_tree.nodes) >= 4:
        mapping.inputs['Scale'].default_value = (scale, scale, 1.0)
        if grid_type == 'CHECKER':
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_CHECKER':
                    n.inputs['Scale'].default_value = 16.0
        return mat

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)

    emission = nodes.new('ShaderNodeEmission')
    emission.location = (200, 0)
    emission.inputs['Strength'].default_value = 1.0
    links.new(emission.outputs['Emission'], output.inputs['Surface'])

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-400, 0)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.name = "M8_Mapping"
    mapping.location = (-200, 0)
    mapping.inputs['Scale'].default_value = (scale, scale, 1.0)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    if grid_type == 'CHECKER':
        checker = nodes.new('ShaderNodeTexChecker')
        checker.location = (0, 0)
        checker.inputs['Color1'].default_value = (0.9, 0.9, 0.9, 1.0)
        checker.inputs['Color2'].default_value = (0.1, 0.1, 0.1, 1.0)
        checker.inputs['Scale'].default_value = 16.0
        links.new(mapping.outputs['Vector'], checker.inputs['Vector'])
        links.new(checker.outputs['Color'], emission.inputs['Color'])
    else:
        img_name = f"M8_UV_{grid_type}"
        img = bpy.data.images.get(img_name)
        if not img:
            img = bpy.data.images.new(img_name, 2048, 2048)
            img.source = 'GENERATED'
            img.generated_type = grid_type  # 'UV_GRID' or 'COLOR_GRID'
            img.use_fake_user = True
        img_node = nodes.new('ShaderNodeTexImage')
        img_node.location = (0, 0)
        img_node.image = img
        img_node.extension = 'REPEAT'
        links.new(mapping.outputs['Vector'], img_node.inputs['Vector'])
        links.new(img_node.outputs['Color'], emission.inputs['Color'])

    mat["m8_grid_type"] = grid_type
    return mat


def update_uv_checker_material(self, context):
    """当棋盘格缩放或类型更改时，实时更新材质节点并重绘视图"""
    mat_name = "M8_UV_Checker"
    if mat_name in bpy.data.materials:
        scale = getattr(self, "uv_checker_scale", 2.0)
        grid_type = getattr(self, "uv_checker_type", "UV_GRID")
        build_or_update_uv_checker_material(scale=scale, grid_type=grid_type)
        if context and hasattr(context, "window_manager") and context.window_manager:
            for window in context.window_manager.windows:
                if window.screen:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()


class M8_OT_ToggleUVChecker(bpy.types.Operator):
    bl_idname = "m8.toggle_uv_checker"
    bl_label = _T("棋盘格显示")
    bl_description = _T("开启/关闭全局 UV 棋盘格材质覆盖，用于查看 UV 拉伸与接缝")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        view_layer = context.view_layer
        current_override = getattr(view_layer, "material_override", None)
        is_active = bool(current_override and current_override.name == "M8_UV_Checker")

        if is_active:
            # 关闭棋盘格，恢复原本的覆盖材质（或无）
            prev_mat_name = context.scene.get("m8_prev_material_override")
            if prev_mat_name and prev_mat_name in bpy.data.materials and prev_mat_name != "M8_UV_Checker":
                view_layer.material_override = bpy.data.materials[prev_mat_name]
            else:
                view_layer.material_override = None

            # 恢复之前的着色方式
            prev_shading = context.scene.get("m8_prev_shading_type")
            space = context.space_data if context.space_data and context.space_data.type == 'VIEW_3D' else None
            if space and prev_shading:
                space.shading.type = prev_shading
                context.scene["m8_prev_shading_type"] = None

            self.report({'INFO'}, _T("已关闭 UV 棋盘格显示"))
        else:
            # 开启棋盘格
            if current_override and current_override.name != "M8_UV_Checker":
                context.scene["m8_prev_material_override"] = current_override.name
            else:
                context.scene["m8_prev_material_override"] = ""

            scale = 2.0
            grid_type = "UV_GRID"
            if hasattr(context.scene, "m8"):
                scale = getattr(context.scene.m8, "uv_checker_scale", 2.0)
                grid_type = getattr(context.scene.m8, "uv_checker_type", "UV_GRID")

            mat = build_or_update_uv_checker_material(scale=scale, grid_type=grid_type)
            view_layer.material_override = mat

            # 若当前为线框或实体模式，自动切换到材质预览以便直观显示
            space = context.space_data if context.space_data and context.space_data.type == 'VIEW_3D' else None
            if space:
                current_shading = space.shading.type
                if current_shading in ('WIREFRAME', 'SOLID'):
                    context.scene["m8_prev_shading_type"] = current_shading
                    space.shading.type = 'MATERIAL'

            self.report({'INFO'}, _T("已开启 UV 棋盘格显示"))

        return {'FINISHED'}
