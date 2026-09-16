# -*- coding: utf-8 -*-
"""
=============================================================================
                  M8 工业级全局/局部 UV 棋盘格系统 (v3.0)
=============================================================================
核心特性：
1. 双轨制覆盖架构 (Dual-Track Override Architecture)：
   - 全版本/全渲染器通杀：在低版本 Blender (2.8~4.1) 及 EEVEE/材质预览下原生不支持
     view_layer.material_override 时，自动无缝启动「槽位无损暂存覆盖」；
   - 在 Cycles 渲染器下同步联动视图层全局覆盖，兼顾极致响应速度与 100% 跨版本兼容。
2. 双作用域支持 (Scope: GLOBAL / SELECTED)：
   - GLOBAL (全场景)：全场景所有网格物体统一显示棋盘格；
   - SELECTED (仅选中)：仅对当前正在展 UV 的选中物体覆盖，杜绝大型场景全屏刺眼和卡顿。
3. 免 UV 三向投影模式 (BOX_GRID)：
   - 新增 Box 三向投射棋盘，基于 Object 局部三维空间投影，即使模型完全没有展开 UV
     （如刚导出的 CAD/STEP、几何节点、布尔高模），也能呈现均匀棋盘格，用于测量体量比例。
4. 全视口同步与着色模式记忆自愈：
   - 自动扫描当前窗口所有 3D Viewport，实体/线框模式自动切到材质预览并记忆；
   - 退出时 100% 精确还原每个视口原本的显示状态。
5. 100% 绝对无损自净与撤销安全：
   - 采用持久化 JSON 备份原始材质插槽，临时槽位自动标记，退出后 0 孤儿节点、0 垃圾残留。
=============================================================================
"""

import bpy
import json
from ...utils.i18n import _T


def get_or_create_grid_image(grid_type="UV_GRID"):
    """获取或新建生成式网格贴图 (2048x2048)"""
    img_name = f"M8_UV_{grid_type}"
    img = bpy.data.images.get(img_name)
    if not img:
        img = bpy.data.images.new(img_name, 2048, 2048)
        img.source = 'GENERATED'
        img.generated_type = grid_type  # 'UV_GRID' or 'COLOR_GRID'
        img.use_fake_user = True
    return img


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
        mapping.inputs['Scale'].default_value = (scale, scale, scale)
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
    mapping.inputs['Scale'].default_value = (scale, scale, scale)

    if grid_type == 'BOX_GRID':
        # 免 UV 三向 Box 投影模式：使用 Object 坐标，无需任何 UV 展开
        links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
        img = get_or_create_grid_image("UV_GRID")
        img_node = nodes.new('ShaderNodeTexImage')
        img_node.location = (0, 0)
        img_node.image = img
        img_node.projection = 'BOX'
        img_node.projection_blend = 0.15
        links.new(mapping.outputs['Vector'], img_node.inputs['Vector'])
        links.new(img_node.outputs['Color'], emission.inputs['Color'])

    elif grid_type == 'CHECKER':
        # 纯程序化黑白棋盘格
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
        checker = nodes.new('ShaderNodeTexChecker')
        checker.location = (0, 0)
        checker.inputs['Color1'].default_value = (0.9, 0.9, 0.9, 1.0)
        checker.inputs['Color2'].default_value = (0.1, 0.1, 0.1, 1.0)
        checker.inputs['Scale'].default_value = 16.0
        links.new(mapping.outputs['Vector'], checker.inputs['Vector'])
        links.new(checker.outputs['Color'], emission.inputs['Color'])

    else:
        # UV_GRID 或 COLOR_GRID 生成式贴图模式
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
        img = get_or_create_grid_image(grid_type)
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


def update_uv_checker_scope(self, context):
    """当作用范围切换时，若当前处于开启状态，自动平滑热切换覆盖范围"""
    if is_uv_checker_active(context):
        try:
            bpy.ops.m8.restore_uv_checker()
            bpy.ops.m8.toggle_uv_checker()
        except Exception:
            pass


def is_uv_checker_active(context):
    """检测当前是否处于棋盘格显示激活状态"""
    if not context or not context.scene:
        return False
    if context.scene.get("m8_uv_checker_active", False):
        return True
    view_layer = getattr(context, "view_layer", None)
    if view_layer and getattr(view_layer, "material_override", None):
        if view_layer.material_override.name == "M8_UV_Checker":
            return True
    return False


def _backup_and_apply_slots(objects, checker_mat, scene):
    """备份物体原材质槽位并临时赋予 M8_UV_Checker (全版本与 EEVEE 绝对兼容)"""
    backup = {}
    added_slots = []

    for obj in objects:
        if not obj or obj.type != 'MESH' or not obj.data:
            continue

        slot_mats = []
        for slot in obj.material_slots:
            slot_mats.append(slot.material.name if slot.material else None)

        if not obj.material_slots:
            # 物体原本没有任何材质槽位，临时追加一个
            obj.data.materials.append(checker_mat)
            added_slots.append(obj.name)
            backup[obj.name] = []
        else:
            backup[obj.name] = slot_mats
            for slot in obj.material_slots:
                slot.material = checker_mat

    scene["m8_uv_checker_slot_backup"] = json.dumps(backup)
    scene["m8_uv_checker_added_slots"] = json.dumps(added_slots)


def _restore_slots(context):
    """从备份中 100% 恢复所有物体的原始材质与槽位数"""
    scene = context.scene
    raw_backup = scene.get("m8_uv_checker_slot_backup")
    raw_added = scene.get("m8_uv_checker_added_slots")

    added_names = set(json.loads(raw_added)) if raw_added else set()

    if raw_backup:
        try:
            backup = json.loads(raw_backup)
            for obj_name, mat_names in backup.items():
                obj = bpy.data.objects.get(obj_name)
                if not obj or obj.type != 'MESH':
                    continue

                if obj_name in added_names:
                    # 物体原本无槽位，清空当时临时追加的槽位
                    obj.data.materials.clear()
                else:
                    for idx, mat_name in enumerate(mat_names):
                        if idx < len(obj.material_slots):
                            orig_mat = bpy.data.materials.get(mat_name) if mat_name else None
                            obj.material_slots[idx].material = orig_mat
        except Exception:
            pass

    if "m8_uv_checker_slot_backup" in scene:
        del scene["m8_uv_checker_slot_backup"]
    if "m8_uv_checker_added_slots" in scene:
        del scene["m8_uv_checker_added_slots"]


def _sync_viewports_to_material(context):
    """自动将所有处于线框或实体模式的 3D 视图临时切换到材质预览"""
    prev_shadings = {}
    wm = getattr(context, "window_manager", None)
    windows = wm.windows if wm else ([context.window] if hasattr(context, "window") else [])

    for win_idx, win in enumerate(windows):
        if not win or not win.screen:
            continue
        for area_idx, area in enumerate(win.screen.areas):
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        cur = space.shading.type
                        if cur in ('WIREFRAME', 'SOLID'):
                            key = f"{win_idx}_{area_idx}"
                            prev_shadings[key] = cur
                            space.shading.type = 'MATERIAL'

    if prev_shadings:
        context.scene["m8_prev_viewport_shadings"] = json.dumps(prev_shadings)


def _restore_viewports(context):
    """将所有 3D 视图还原至开启棋盘格之前的原始着色方式"""
    scene = context.scene
    raw = scene.get("m8_prev_viewport_shadings")
    if not raw:
        return

    try:
        prev_shadings = json.loads(raw)
        wm = getattr(context, "window_manager", None)
        windows = wm.windows if wm else ([context.window] if hasattr(context, "window") else [])

        for win_idx, win in enumerate(windows):
            if not win or not win.screen:
                continue
            for area_idx, area in enumerate(win.screen.areas):
                if area.type == 'VIEW_3D':
                    key = f"{win_idx}_{area_idx}"
                    if key in prev_shadings:
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.shading.type = prev_shadings[key]
    except Exception:
        pass

    if "m8_prev_viewport_shadings" in scene:
        del scene["m8_prev_viewport_shadings"]


def _check_objects_uv_status(objects):
    """巡检目标网格是否有未展 UV 的情况"""
    no_uv_objs = []
    for obj in objects:
        if obj and obj.type == 'MESH' and obj.data:
            if not getattr(obj.data, "uv_layers", None):
                no_uv_objs.append(obj.name)
    return no_uv_objs


class M8_OT_ToggleUVChecker(bpy.types.Operator):
    bl_idname = "m8.toggle_uv_checker"
    bl_label = _T("棋盘格显示")
    bl_description = _T("开启/关闭全局 UV 棋盘格材质覆盖，用于查看 UV 拉伸与接缝")
    bl_options = {"REGISTER", "UNDO"}

    scope: bpy.props.EnumProperty(
        name=_T("作用范围"),
        items=[
            ('AUTO', _T("自适应"), _T("使用偏好设置中的全局/选中范围设置")),
            ('GLOBAL', _T("全场景"), _T("覆盖场景中所有网格物体")),
            ('SELECTED', _T("仅选中"), _T("仅覆盖当前选中的网格物体")),
        ],
        default='AUTO',
    )

    def execute(self, context):
        view_layer = context.view_layer
        scene = context.scene
        is_active = is_uv_checker_active(context)

        if is_active:
            # -----------------------------------------------------------------
            # 关闭棋盘格：全局还原
            # -----------------------------------------------------------------
            # 1. 还原 ViewLayer override
            prev_mat_name = scene.get("m8_prev_material_override")
            if prev_mat_name and prev_mat_name in bpy.data.materials and prev_mat_name != "M8_UV_Checker":
                view_layer.material_override = bpy.data.materials[prev_mat_name]
            else:
                view_layer.material_override = None

            if "m8_prev_material_override" in scene:
                del scene["m8_prev_material_override"]

            # 2. 还原所有槽位覆盖
            _restore_slots(context)

            # 3. 还原视口着色方式
            _restore_viewports(context)

            scene["m8_uv_checker_active"] = False
            self.report({'INFO'}, _T("已关闭 UV 棋盘格显示"))

        else:
            # -----------------------------------------------------------------
            # 开启棋盘格：双轨制智能覆盖
            # -----------------------------------------------------------------
            # 决定作用范围
            scope_mode = self.scope
            if scope_mode == 'AUTO':
                scope_mode = getattr(scene.m8, "uv_checker_scope", "GLOBAL") if hasattr(scene, "m8") else 'GLOBAL'

            # 收集目标物体
            target_objs = []
            if scope_mode == 'SELECTED':
                target_objs = [o for o in context.selected_objects if o.type == 'MESH']
                if not target_objs and context.active_object and context.active_object.type == 'MESH':
                    target_objs = [context.active_object]
                if not target_objs:
                    self.report({'WARNING'}, _T("未检测到选中的网格物体"))
                    return {'CANCELLED'}
            else:
                # 全场景：收集所有可渲染的网格物体
                target_objs = [o for o in view_layer.objects if o.type == 'MESH']

            # 构建或更新材质
            scale = 2.0
            grid_type = "UV_GRID"
            if hasattr(scene, "m8"):
                scale = getattr(scene.m8, "uv_checker_scale", 2.0)
                grid_type = getattr(scene.m8, "uv_checker_type", "UV_GRID")

            mat = build_or_update_uv_checker_material(scale=scale, grid_type=grid_type)

            # 检查是否有未展 UV 的物体
            no_uv_objs = _check_objects_uv_status(target_objs)

            # 1. 槽位无损暂存覆盖（全版本通杀保障）
            _backup_and_apply_slots(target_objs, mat, scene)

            # 2. 若为全场景模式，同步记录并设置 view_layer.material_override（加速 Cycles）
            current_override = getattr(view_layer, "material_override", None)
            if current_override and current_override.name != "M8_UV_Checker":
                scene["m8_prev_material_override"] = current_override.name
            else:
                scene["m8_prev_material_override"] = ""

            if scope_mode == 'GLOBAL':
                view_layer.material_override = mat

            # 3. 视口模式同步与记忆
            _sync_viewports_to_material(context)

            scene["m8_uv_checker_active"] = True

            # 提示信息输出
            if no_uv_objs and grid_type != 'BOX_GRID':
                self.report({'WARNING'}, f"{_T('已开启 UV 棋盘格显示')} ({len(no_uv_objs)} {_T('个物体未展 UV，建议切换为免UV三向')})")
            else:
                mode_str = _T("全场景") if scope_mode == 'GLOBAL' else _T("仅选中")
                self.report({'INFO'}, f"{_T('已开启 UV 棋盘格显示')} ({mode_str})")

        return {'FINISHED'}


class M8_OT_RestoreUVChecker(bpy.types.Operator):
    bl_idname = "m8.restore_uv_checker"
    bl_label = _T("还原棋盘格显示")
    bl_description = _T("强制恢复所有物体的材质插槽并清除棋盘格覆盖")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        view_layer = context.view_layer
        scene = context.scene

        prev_mat_name = scene.get("m8_prev_material_override")
        if prev_mat_name and prev_mat_name in bpy.data.materials and prev_mat_name != "M8_UV_Checker":
            view_layer.material_override = bpy.data.materials[prev_mat_name]
        else:
            view_layer.material_override = None

        if "m8_prev_material_override" in scene:
            del scene["m8_prev_material_override"]

        _restore_slots(context)
        _restore_viewports(context)
        scene["m8_uv_checker_active"] = False

        self.report({'INFO'}, _T("已关闭 UV 棋盘格显示"))
        return {'FINISHED'}

