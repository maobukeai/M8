import bpy

from ...ops.mesh.switch_mesh_mode import M8_OT_SwitchMeshMode
from ...ops.mesh.switch_uv_mode import M8_OT_SwitchUVMode
from ...ops.mesh.surface_sliding import ui as surface_sliding_ui
from ...ops.mesh.optimization import M8_OT_MeshOptimizationMenu
from ...ops.mesh.draw_texture import M8_OT_DrawSelected, M8_OT_CancelDrawSelected
from ...ops.object.auto_smooth import draw_auto_smooth
from ...ops.object.light_quick_settings import M8_OT_LightQuickSettings
from ...ops.object.camera_quick_settings import M8_OT_CameraQuickSettings
from ...ops.object.select_scene_camera import M8_OT_SelectSceneCamera
from ...ops.object.camera_focus_selected import M8_OT_CameraFocusSelected
from ...ops.object.light_track_to_selected import M8_OT_LightTrackToSelected, M8_OT_LightClearTrackTo
from ...ops.object.text_tools import M8_OT_TextQuickSettings
from ...ops.object.curve_tools import (
    M8_OT_CurveQuickSettings,
    M8_OT_CurveCyclicToggle,
    M8_OT_ObjectConvertToMesh,
)
from ...ops.object.mode_set_remember import M8_OT_ModeSetRemember
from ...ops.object.curve_edit_tools import (
    M8_OT_CurveHandleTypeRemember,
    M8_OT_CurveSwitchDirectionRemember,
    M8_OT_CurveSubdivideRemember,
    M8_OT_CurveSmoothRemember,
)
from ...ops.object.lattice_tools import M8_OT_LatticeMakeRegular
from ...ops.object.switch_mode import M8_OT_SwitchBoneMode
from ...ops.object.switch_image_mode import draw_row_image_mode


def get_pref():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None


def draw_use_transform(context: bpy.types.Context, pie: bpy.types.UILayout):
    tool = context.scene.tool_settings
    column = pie.column(align=True)
    column.scale_y = 1.3
    column.separator()   
    column.separator()
    column.separator()
    column.separator()
    column.separator()
    column.prop(tool, "use_transform_data_origin")
    column.prop(tool, "use_transform_pivot_point_align")
    column.prop(tool, "use_transform_skip_children")

def _get_xray(context: bpy.types.Context) -> bool:
    view = context.space_data
    if view and hasattr(view, "shading") and hasattr(view.shading, "show_xray"):
        return bool(view.shading.show_xray)
    return False

def edit_mesh(context: bpy.types.Context, pie: bpy.types.UILayout):
    tool = context.scene.tool_settings
    view = context.space_data
    overlay = view.overlay if view and hasattr(view, "overlay") else None
    is_xray = _get_xray(context)

    column = pie.column(align=True)
    column.scale_y = 1.3
    row = column.row(align=True)
    row.operator("mesh.flip_normals")
    if overlay and hasattr(overlay, "show_face_orientation"):
        row.prop(overlay, "show_face_orientation", text="", icon="FACESEL")
    column.operator(M8_OT_DrawSelected.bl_idname, icon="TPAINT_HLT")

    col = pie.column(align=True)
    col.scale_y = 1.5
    col.scale_x = 1.1
    surface_sliding_ui(context, col)
    
    col.separator()
    
    # Proportional Edit
    row = col.row(align=True)
    row.prop(tool, "use_proportional_edit", text="衰减", toggle=True, icon="PROP_CON")
    sub = row.row(align=True)
    sub.active = tool.use_proportional_edit
    sub.prop(tool, "proportional_edit_falloff", icon_only=True, text="")

    # Snap
    row = col.row(align=True)
    row.prop(tool, "use_snap", text="吸附", toggle=True, icon="SNAP_ON")
    sub = row.row(align=True)
    sub.active = tool.use_snap
    sub.popover(panel="VIEW3D_PT_snapping", text="", icon="SNAP_PEEL_OBJECT")

    column = pie.column(align=True)
    column.scale_y = 1.3
    column.operator(M8_OT_MeshOptimizationMenu.bl_idname, icon="MOD_REMESH", text="优化")
    if hasattr(tool, "use_mesh_automerge"):
        column.prop(tool, "use_mesh_automerge", text="自动合并顶点")
    column.operator(
        "view3d.toggle_xray",
        icon="XRAY",
        text=("遮挡" if is_xray else "穿透"),
        depress=is_xray
    )


_DIR_NUM = {
    "left": "4",
    "right": "6",
    "down": "2",
    "up": "8",
}


def _mesh_select_depress(context: bpy.types.Context, mode: str) -> bool:
    if context.mode != "EDIT_MESH":
        return False
    msm = context.scene.tool_settings.mesh_select_mode
    if mode == "VERT":
        return bool(msm[0])
    if mode == "EDGE":
        return bool(msm[1])
    if mode == "FACE":
        return bool(msm[2])
    return False


def draw_switch_view_3d_mode_operator(context: bpy.types.Context, pie: bpy.types.UILayout, pref, direction: str):
    mode = getattr(pref, f"switch_mode_{direction}")
    num = _DIR_NUM.get(direction, "")

    if mode == "SWITCH_MODE":
        is_object = context.mode == "OBJECT"
        target = "EDIT" if is_object else "OBJECT"
        text = ("编辑模式" if is_object else "物体模式")
        icon = "EDITMODE_HLT" if is_object else "OBJECT_DATAMODE"
        pie.operator("object.mode_set", text=f"{text} {num}".strip(), icon=icon).mode = target
        return

    label_map = {"VERT": "顶点", "EDGE": "边", "FACE": "面"}
    icon_map = {"VERT": "VERTEXSEL", "EDGE": "EDGESEL", "FACE": "FACESEL"}
    text = f"{label_map.get(mode, mode)} {num}".strip()
    icon = icon_map.get(mode, "NONE")
    ops = pie.operator(
        M8_OT_SwitchMeshMode.bl_idname,
        text=text,
        icon=icon,
        depress=_mesh_select_depress(context, mode),
    )
    ops.select_mode = {mode}


def draw_switch_image_mode_operator(context: bpy.types.Context, pie: bpy.types.UILayout, pref, direction: str, override_mode: str = None):
    tool_settings = context.tool_settings
    if override_mode:
        mode = override_mode
    else:
        mode = getattr(pref, f"switch_mode_{direction}")
    num = _DIR_NUM.get(direction, "")

    if mode == "SWITCH_MODE":
        is_edit_mesh = context.mode == "EDIT_MESH"
        if context.area.ui_type == 'UV' or context.area.type == 'IMAGE_EDITOR':
             text = ("物体模式" if is_edit_mesh else "编辑UV")
        else:
             text = ("物体模式" if is_edit_mesh else "编辑模式")
        
        icon = "OBJECT_DATAMODE" if is_edit_mesh else "EDITMODE_HLT"
        target = "OBJECT" if is_edit_mesh else "EDIT"
        pie.operator("object.mode_set", text=f"{text} {num}".strip(), icon=icon).mode = target
        return

    label_map = {"VERT": "顶点", "EDGE": "边", "FACE": "面"}
    uv_map = {"VERT": "VERTEX", "EDGE": "EDGE", "FACE": "FACE"}
    uv_type = uv_map.get(mode, "VERTEX")

    is_sync = tool_settings.use_uv_select_sync
    depress = False
    if context.mode == "EDIT_MESH":
        if is_sync:
            depress = _mesh_select_depress(context, mode)
        else:
            depress = (uv_type == tool_settings.uv_select_mode[:])

    icon = {"VERT": "UV_VERTEXSEL", "EDGE": "UV_EDGESEL", "FACE": "UV_FACESEL"}.get(mode, "UV_VERTEXSEL")
    ops = pie.operator(
        M8_OT_SwitchUVMode.bl_idname,
        text=f"{label_map.get(mode, mode)} {num}".strip(),
        icon=icon,
        depress=depress,
    )
    ops.uv_mode = uv_type if not is_sync else mode


def draw_switch_bone_mode_operator(context: bpy.types.Context, pie: bpy.types.UILayout, pref, direction: str):
    active = context.active_object
    data = context.object.data
    om = active.mode
    mode = getattr(pref, f"switch_bone_mode_{direction}")
    
    if mode == "EDIT_OR_OBJECT":
        text, icon, mode = (
            ("物体模式", "OBJECT_DATAMODE", "OBJECT") 
            if om == "EDIT" or om not in ("EDIT", "OBJECT") else 
            ("编辑模式", "EDITMODE_HLT", "EDIT")
        )
        ops = pie.operator("object.mode_set", text=text, icon=icon)
        ops.mode = mode
        ops.toggle = True
    elif mode == "POSE":
        pie.operator(M8_OT_SwitchBoneMode.bl_idname,
                        text="姿态模式",
                        icon="POSE_HLT",
                        depress=context.mode == "POSE")
    elif mode == "EDIT":
        if om == "POSE":
            ops = pie.operator("object.mode_set", text="编辑模式", icon="EDITMODE_HLT")
            ops.mode = "EDIT"
            ops.toggle = True
        else:
            pie.separator()
    elif mode == "BONE_POSITION":
        is_pose = data.pose_position == "POSE"
        text, icon, value = ("切换到静置", "POSE_HLT", "REST") if is_pose else (
            "切换到姿态", "ARMATURE_DATA", "POSE",)
        ops = pie.operator("wm.context_set_enum", text=text, icon=icon)
        ops.data_path = "object.data.pose_position"
        ops.value = value
    elif mode == "VIEW_SELECTED":
        pie.operator("view3d.view_selected", text="聚焦", icon="VIEWZOOM")
    elif mode == "TOGGLE_XRAY":
        pie.prop(active, "show_in_front", text="前台显示", icon="XRAY")
    elif mode == "TOGGLE_NAMES":
        pie.prop(data, "show_names", text="显示名称", icon="SORTALPHA")
    elif mode == "TOGGLE_AXES":
        pie.prop(data, "show_axes", text="显示轴向", icon="AXIS_SIDE")
    else:
        pie.label(text=f"Invalid mode {mode}")


def draw_common_view_ops(pie):
    pie.operator("view3d.view_selected", text="聚焦", icon="VIEWZOOM")
    pie.operator("view3d.localview", text="局部视图", icon="HIDE_OFF")


def draw_extrude_bevel_props(pie, data):
    if hasattr(data, "extrude"):
        pie.prop(data, "extrude", text="挤出")
    else:
        pie.separator()
    if hasattr(data, "bevel_depth"):
        pie.prop(data, "bevel_depth", text="倒角")
    else:
        pie.separator()


def draw_node_editor_ops(context: bpy.types.Context, pie: bpy.types.UILayout):
    # 1. Left
    col = pie.column(align=True)
    col.scale_y = 1.3
    col.operator("node.view_selected", text="聚焦", icon="VIEWZOOM")
    col.separator()
    col.separator()

    # 2. Right
    col = pie.column(align=True)
    col.scale_y = 1.3
    col.operator("node.mute_toggle", text="禁用/启用", icon="CHECKBOX_DEHLT")
    col.operator("node.join", text="加入框", icon="NODE_SEL")
    col.operator("node.parent_clear", text="移出框", icon="UNLINKED")

    # 3. Bottom
    pie.operator("node.join", text="加入框", icon="NODE_SEL")

    # 4. Top
    active_node = context.active_node
    is_group_selected = False
    if active_node and getattr(active_node, "type", "") == "GROUP":
        is_group_selected = True

    is_inside_group = False
    space = context.space_data
    if hasattr(space, "path") and len(space.path) > 0:
        is_inside_group = True
    elif hasattr(space, "edit_tree") and hasattr(space, "node_tree") and space.edit_tree != space.node_tree:
        is_inside_group = True

    if is_group_selected:
        pie.operator("node.group_edit", text="编辑组", icon="NODETREE")
    elif is_inside_group:
        pie.operator("node.tree_path_parent", text="退出组", icon="FILE_PARENT")
    else:
        pie.operator("node.group_edit", text="编辑组", icon="NODETREE")

    # 5. Top Left
    pie.operator("node.group_make", text="成组", icon="NODETREE")

    # 6. Top Right
    pie.operator("node.group_ungroup", text="解组", icon="X")

    # 7. Bottom Left
    col = pie.column(align=True)
    col.scale_y = 1.3
    col.operator("wm.call_menu", text="搜索添加", icon="ADD").name = "NODE_MT_add"
    col.operator("node.group_make", text="打组", icon="NODE_MATERIAL")

    # 8. Bottom Right
    col = pie.column(align=True)
    col.scale_y = 1.3
    col.operator("node.view_all", text="查看全部", icon="VIEWZOOM")
    col.operator("node.backimage_fit", text="重置节点", icon="LOOP_BACK")


class VIEW3D_MT_M8SwitchModePie(bpy.types.Menu):
    bl_label = "切换模式"
    bl_idname = "VIEW3D_MT_m8_switch_mode_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pref = get_pref()
        obj = context.active_object

        if not pref:
            return

        if context.area.type == "NODE_EDITOR":
            draw_node_editor_ops(context, pie)
            return

        if context.area.type == "IMAGE_EDITOR" or context.area.ui_type == "UV":
            # Fixed mapping for Image/UV Editor
            mapping = {
                "left": "VERT",
                "right": "FACE",
                "down": "EDGE",
                "up": "SWITCH_MODE"
            }
            for direction in ("left", "right", "down", "up"):
                draw_switch_image_mode_operator(context, pie, pref, direction, override_mode=mapping.get(direction))
            
            # 5. Top Left
            row = pie.row(align=False)
            draw_row_image_mode(context, row, is_row=True)
            
            sub = row.row(align=True)
            sub.scale_x = 1.5
            sub.scale_y = 1.4
            sub.prop(context.scene.tool_settings, "use_uv_select_sync", text="", icon="UV_SYNC_SELECT")

            # 6. Top Right
            pie.separator()
            # 7. Bottom Left
            pie.separator()
            # 8. Bottom Right
            pie.separator()
            return

        if not obj:
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            return

        if obj.type == "MESH":
            for direction in ("left", "right", "down", "up"):
                draw_switch_view_3d_mode_operator(context, pie, pref, direction)

            row = pie.row(align=True)
            row.scale_x = 1.7
            row.scale_y = 1.5

            om = obj.mode
            mode_list = [
                ("VERTEX_PAINT", "VPAINT_HLT"),
                ("WEIGHT_PAINT", "WPAINT_HLT"),
                ("TEXTURE_PAINT", "TPAINT_HLT"),
                ("SCULPT", "SCULPTMODE_HLT"),
                ("EDIT", "EDITMODE_HLT") if om == "OBJECT" else ("OBJECT", "OBJECT_DATAMODE"),
            ]
            if len(obj.particle_systems):
                mode_list.insert(-2, ("PARTICLE_EDIT", "PARTICLEMODE"))

            for (m, icon) in mode_list:
                r = row.row(align=True)
                ops = r.operator(M8_OT_ModeSetRemember.bl_idname, text="", icon=icon, depress=(m == om))
                ops.mode = m

            if om == "OBJECT":
                draw_auto_smooth(context, pie)
                pie.separator()
                draw_use_transform(context, pie)
            elif om == "EDIT":
                edit_mesh(context, pie)
            elif om == "TEXTURE_PAINT":
                data = obj.data
                column = pie.column(align=True)
                column.scale_y = 1.3
                if hasattr(data, "use_paint_mask"):
                    column.prop(data, "use_paint_mask", text="", icon="FACESEL")
                column.operator(M8_OT_CancelDrawSelected.bl_idname, icon="EDITMODE_HLT")
                pie.separator()
                pie.separator()
            elif om in {"VERTEX_PAINT", "WEIGHT_PAINT"}:
                data = obj.data
                column = pie.column(align=True)
                column.scale_y = 1.3
                if hasattr(data, "use_paint_mask"):
                    column.prop(data, "use_paint_mask", text="", icon="FACESEL")
                if hasattr(data, "use_paint_mask_vertex"):
                    column.prop(data, "use_paint_mask_vertex", text="", icon="VERTEXSEL")
                pie.separator()
                pie.separator()
            else:
                pie.separator()
                pie.separator()
                pie.separator()
            return

        if obj.type == "LIGHT":
            light = obj.data
            pie.prop(light, "energy", text="能量")

            if getattr(light, "type", "") == "SUN" and hasattr(light, "angle"):
                pie.prop(light, "angle", text="角度")
            elif getattr(light, "type", "") in {"POINT", "SPOT"} and hasattr(light, "shadow_soft_size"):
                pie.prop(light, "shadow_soft_size", text="半径")
            elif getattr(light, "type", "") == "AREA" and hasattr(light, "size"):
                pie.prop(light, "size", text="尺寸")
            else:
                pie.separator()

            pie.operator(M8_OT_LightTrackToSelected.bl_idname, text="对准选中", icon="CON_TRACKTO")
            pie.operator(M8_OT_LightQuickSettings.bl_idname, text="灯光设置", icon="LIGHT_DATA")

            if hasattr(light, "use_shadow"):
                pie.prop(light, "use_shadow", text="投影")
            else:
                pie.separator()

            draw_common_view_ops(pie)
            pie.operator(M8_OT_LightClearTrackTo.bl_idname, text="清除对准", icon="X")
            return

        if obj.type == "CAMERA":
            cam = obj.data
            pie.prop(cam, "lens", text="焦距")

            try:
                pie.prop(context.scene.view_settings, "exposure", text="曝光")
            except Exception:
                pie.separator()

            pie.operator(M8_OT_CameraFocusSelected.bl_idname, text="对焦到选中", icon="TRACKING_FORWARDS")
            pie.operator(M8_OT_CameraQuickSettings.bl_idname, text="相机设置", icon="PREFERENCES")

            pie.operator("view3d.view_camera", text="查看摄像机", icon="CAMERA_DATA")
            
            if context.space_data and context.space_data.type == 'VIEW_3D':
                pie.prop(context.space_data, "lock_camera", text="锁定相机到视图", icon="LOCKVIEW_ON")
            else:
                pie.separator()

            pie.operator(M8_OT_SelectSceneCamera.bl_idname, text="设为活动摄像机", icon="OUTLINER_OB_CAMERA")
            pie.operator("view3d.localview", text="局部视图", icon="HIDE_OFF")
            return

        if obj.type == "LATTICE":
            data = obj.data
            is_object = context.mode == "OBJECT"

            pie.operator("view3d.view_selected", text="聚焦", icon="VIEWZOOM")

            if hasattr(data, "use_outside"):
                pie.prop(data, "use_outside", text="外部影响")
            else:
                pie.separator()

            pie.operator(M8_OT_LatticeMakeRegular.bl_idname, text="重置形状", icon="MESH_GRID")

            ops = pie.operator(M8_OT_ModeSetRemember.bl_idname, text=("编辑模式" if is_object else "物体模式"), icon=("EDITMODE_HLT" if is_object else "OBJECT_DATAMODE"))
            ops.mode = ("EDIT" if is_object else "OBJECT")

            pie.operator("view3d.localview", text="局部视图", icon="HIDE_OFF")
            
            pie.separator()
            
            pie.prop(data, "points_u", text="分辨率 U")

            col = pie.column(align=True)
            col.prop(data, "points_v", text="分辨率 V")
            col.prop(data, "points_w", text="分辨率 W")
            return

        if obj.type == "FONT":
            data = obj.data
            is_object = context.mode == "OBJECT"

            # 1. Left (Original Top)
            if context.mode == "EDIT_TEXT":
                pie.operator("wm.call_menu_pie", text="编辑工具 4", icon="TOOL_SETTINGS").name = "VIEW3D_MT_m8_text_edit_pie"
            else:
                pie.separator()

            # 2. Right
            pie.operator(M8_OT_TextQuickSettings.bl_idname, text="文字设置 6", icon="FONT_DATA")

            # 3. Bottom
            pie.operator("wm.call_menu_pie", text="转换 2", icon="MESH_DATA").name = "VIEW3D_MT_m8_curve_convert_pie"

            # 4. Top (Original Left - Toggle Mode)
            ops = pie.operator(M8_OT_ModeSetRemember.bl_idname, text=("编辑文字 8" if is_object else "物体模式 8"), icon=("EDITMODE_HLT" if is_object else "OBJECT_DATAMODE"))
            ops.mode = ("EDIT" if is_object else "OBJECT")

            draw_common_view_ops(pie)
            draw_extrude_bevel_props(pie, data)
            return

        if obj.type == "META":
            data = obj.data
            is_object = context.mode == "OBJECT"

            # 1. Left (Original Top)
            pie.operator("view3d.view_selected", text="聚焦 4", icon="VIEWZOOM")

            # 2. Right
            # 融球没有很多特殊的 operator，主要是属性设置
            # 这里放阈值属性比较合适
            pie.prop(data, "threshold", text="阈值 6")

            # 3. Bottom
            # 复用曲线的转换菜单（因为都是 M8_OT_ObjectConvertToMesh）
            pie.operator("wm.call_menu_pie", text="转换 2", icon="MESH_DATA").name = "VIEW3D_MT_m8_curve_convert_pie"

            # 4. Top (Original Left - Toggle Mode)
            ops = pie.operator(M8_OT_ModeSetRemember.bl_idname, text=("编辑模式 8" if is_object else "物体模式 8"), icon=("EDITMODE_HLT" if is_object else "OBJECT_DATAMODE"))
            ops.mode = ("EDIT" if is_object else "OBJECT")

            # 5. Top Left
            # 这里已经有了左侧的聚焦，所以不需要 draw_common_view_ops 里的聚焦
            # 只需手动添加局部视图即可
            pie.operator("view3d.localview", text="局部视图", icon="HIDE_OFF")
            
            # 6. Top Right
            pie.separator()
            # 7. Bottom Left
            pie.separator()
            # 8. Bottom Right
            pie.separator()
            
            # 融球特有的分辨率设置
            col = pie.column(align=True)
            col.prop(data, "resolution", text="视图分辨率")
            col.prop(data, "render_resolution", text="渲染分辨率")
            return

        if obj.type in {"CURVE", "SURFACE"}:
            data = obj.data
            is_object = context.mode == "OBJECT"

            # 1. Left (Original Top)
            if context.mode == "EDIT_CURVE":
                pie.operator("wm.call_menu_pie", text="编辑工具 4", icon="TOOL_SETTINGS").name = "VIEW3D_MT_m8_curve_edit_pie"
            else:
                pie.operator(M8_OT_CurveCyclicToggle.bl_idname, text="切换闭合 4", icon="RECOVER_LAST")

            # 2. Right
            pie.operator(M8_OT_CurveQuickSettings.bl_idname, text="曲线设置 6", icon="CURVE_DATA")

            # 3. Bottom
            pie.operator("wm.call_menu_pie", text="转换 2", icon="MESH_DATA").name = "VIEW3D_MT_m8_curve_convert_pie"

            # 4. Top (Original Left - Toggle Mode)
            ops = pie.operator(M8_OT_ModeSetRemember.bl_idname, text=("编辑模式 8" if is_object else "物体模式 8"), icon=("EDITMODE_HLT" if is_object else "OBJECT_DATAMODE"))
            ops.mode = ("EDIT" if is_object else "OBJECT")

            draw_common_view_ops(pie)
            draw_extrude_bevel_props(pie, data)
            return

        if obj.type == "CURVES":
            is_object = context.mode == "OBJECT"
            # 1. Left
            pie.operator("view3d.view_selected", text="聚焦", icon="VIEWZOOM")
            # 2. Right
            op = pie.operator(M8_OT_ObjectConvertToMesh.bl_idname, text="转网格(保留)", icon="MESH_DATA")
            op.keep_original = True
            # 3. Bottom
            op = pie.operator(M8_OT_ObjectConvertToMesh.bl_idname, text="转网格(替换)", icon="OUTLINER_OB_MESH")
            op.keep_original = False
            # 4. Top (Toggle)
            pie.operator("object.mode_set", text=("雕刻曲线" if is_object else "物体模式"), icon=("SCULPTMODE_HLT" if is_object else "OBJECT_DATAMODE")).mode = ("SCULPT_CURVES" if is_object else "OBJECT")
            
            pie.operator("view3d.localview", text="局部视图", icon="HIDE_OFF")
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            return

        if obj.type == "ARMATURE":
            draw_switch_bone_mode_operator(context, pie, pref, "left")

            is_pose = context.mode == "POSE"
            pie.operator(
                M8_OT_SwitchBoneMode.bl_idname,
                text=("物体模式 6" if is_pose else "姿态模式 6"),
                icon=("OBJECT_DATAMODE" if is_pose else "POSE_HLT"),
                depress=is_pose,
            )

            draw_switch_bone_mode_operator(context, pie, pref, "down")

            om = obj.mode
            is_edit = om == "EDIT"
            ops = pie.operator(
                "object.mode_set",
                text=("物体模式 8" if is_edit else "编辑模式 8"),
                icon=("OBJECT_DATAMODE" if is_edit else "EDITMODE_HLT"),
            )
            ops.mode = ("OBJECT" if is_edit else "EDIT")
            ops.toggle = True

            data = obj.data
            row = pie.row(align=True)
            row.scale_x = 1.3
            row.scale_y = 1.3
            row.prop(obj, "show_in_front", text="", icon="XRAY")
            row.prop(data, "show_names", text="", icon="SORTALPHA")
            row.prop(data, "show_axes", text="", icon="AXIS_SIDE")
            row.prop(data, "display_type", text="")

            pie.separator()
            pie.separator()
            pie.separator()
            return

        if obj.type == "EMPTY":
            is_image = obj.empty_display_type == "IMAGE"

            # 1. Left
            pie.operator("view3d.view_selected", text="聚焦", icon="VIEWZOOM")

            # 2. Right
            col = pie.column(align=True)
            col.prop(obj, "empty_display_size", text="尺寸")
            if is_image:
                col.prop(obj, "empty_image_offset", text="偏移")

            # 3. Bottom
            pie.operator("wm.call_menu_pie", text="切换类型", icon="EMPTY_DATA").name = "VIEW3D_MT_m8_empty_type_pie"

            # 4. Top
            pie.prop(obj, "show_in_front", text="前台显示", icon="XRAY")

            # 5. Top Left
            pie.operator("view3d.localview", text="局部视图", icon="HIDE_OFF")

            # 6. Top Right
            if is_image:
                col = pie.column(align=True)
                col.prop(obj, "empty_image_depth", text="深度")
                col.prop(obj, "empty_image_side", text="侧面")
            else:
                pie.separator()

            # 7. Bottom Left
            col = pie.column(align=True)
            col.prop(obj, "show_name", text="显示名称", icon="SORTALPHA")
            col.prop(obj, "show_bounds", text="显示边界", icon="BBOX")
            
            # 8. Bottom Right
            if is_image:
                col = pie.column(align=True)
                
                row = col.row(align=True)
                row.prop(obj, "use_empty_image_alpha", text="透明度", icon="RESTRICT_VIEW_OFF")
                if obj.use_empty_image_alpha:
                     row.prop(obj, "color", index=3, text="", slider=True)
                
                row = col.row(align=True)
                row.prop(obj, "show_empty_image_orthographic", text="正交", toggle=True)
                row.prop(obj, "show_empty_image_perspective", text="透视", toggle=True)
            else:
                pie.separator()

            return

        if obj.type in {"GPENCIL", "GREASEPENCIL"}:
            data = obj.data
            is_object = context.mode == "OBJECT"
            is_edit = context.mode == "EDIT_GPENCIL" or context.mode == "EDIT_GREASEPENCIL"
            is_sculpt = context.mode == "SCULPT_GPENCIL" or context.mode == "SCULPT_GREASEPENCIL"
            is_draw = context.mode == "PAINT_GPENCIL" or context.mode == "PAINT_GREASEPENCIL"
            is_weight = context.mode == "WEIGHT_GPENCIL" or context.mode == "WEIGHT_GREASEPENCIL"
            is_vertex = context.mode == "VERTEX_GPENCIL" or context.mode == "VERTEX_GREASEPENCIL"

            # 1. Left (4): Draw Mode / Object Mode
            ops = pie.operator("object.mode_set", text=("绘制模式 4" if not is_draw else "物体模式 4"), icon=("GREASEPENCIL" if not is_draw else "OBJECT_DATAMODE"))
            ops.mode = ("PAINT_GPENCIL" if not is_draw else "OBJECT") if obj.type == "GPENCIL" else ("PAINT_GREASEPENCIL" if not is_draw else "OBJECT")

            # 2. Right (6): Sculpt Mode / Object Mode
            ops = pie.operator("object.mode_set", text=("雕刻模式 6" if not is_sculpt else "物体模式 6"), icon=("SCULPTMODE_HLT" if not is_sculpt else "OBJECT_DATAMODE"))
            ops.mode = ("SCULPT_GPENCIL" if not is_sculpt else "OBJECT") if obj.type == "GPENCIL" else ("SCULPT_GREASEPENCIL" if not is_sculpt else "OBJECT")

            # 3. Bottom (2): Weight Paint / Vertex Paint
            # 这里可以放权重绘制或者顶点绘制，或者不做设置
            # 暂时放权重绘制
            ops = pie.operator("object.mode_set", text=("权重绘制 2" if not is_weight else "物体模式 2"), icon=("WPAINT_HLT" if not is_weight else "OBJECT_DATAMODE"))
            ops.mode = ("WEIGHT_GPENCIL" if not is_weight else "OBJECT") if obj.type == "GPENCIL" else ("WEIGHT_GREASEPENCIL" if not is_weight else "OBJECT")

            # 4. Top (8): Edit Mode / Object Mode
            ops = pie.operator("object.mode_set", text=("编辑模式 8" if not is_edit else "物体模式 8"), icon=("EDITMODE_HLT" if not is_edit else "OBJECT_DATAMODE"))
            ops.mode = ("EDIT_GPENCIL" if not is_edit else "OBJECT") if obj.type == "GPENCIL" else ("EDIT_GREASEPENCIL" if not is_edit else "OBJECT")

            # 5. Top Left: Local View
            pie.operator("view3d.localview", text="局部视图", icon="HIDE_OFF")
            
            # 6. Top Right
            pie.separator()
            
            # 7. Bottom Left
            # 常用属性：笔触深度顺序 (2D/3D)
            if hasattr(data, "stroke_depth_order"):
                pie.prop(data, "stroke_depth_order", text="")
            else:
                pie.separator()

            # 8. Bottom Right
            # 常用属性：洋葱皮
            if hasattr(data, "use_onion_skinning"):
                pie.prop(data, "use_onion_skinning", text="", icon="ONIONSKIN_ON")
            else:
                pie.separator()

            return

        # Default Fallback
        # 1. Left
        pie.separator()
        # 2. Right
        pie.separator()
        # 3. Bottom
        pie.separator()
        # 4. Top (Toggle)
        is_object = context.mode == "OBJECT"
        pie.operator("object.mode_set", text=("编辑模式" if is_object else "物体模式"), icon=("EDITMODE_HLT" if is_object else "OBJECT_DATAMODE")).mode = ("EDIT" if is_object else "OBJECT")
        
        pie.separator()
        pie.separator()
        pie.separator()
        pie.separator()


class VIEW3D_MT_M8CurveConvertPie(bpy.types.Menu):
    bl_label = "曲线转换"
    bl_idname = "VIEW3D_MT_m8_curve_convert_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        op = pie.operator(M8_OT_ObjectConvertToMesh.bl_idname, text="转网格(保留)", icon="MESH_DATA")
        op.keep_original = True
        op = pie.operator(M8_OT_ObjectConvertToMesh.bl_idname, text="转网格(替换)", icon="OUTLINER_OB_MESH")
        op.keep_original = False
        pie.separator()
        pie.separator()
        pie.separator()
        pie.separator()
        pie.separator()
        pie.separator()


class VIEW3D_MT_M8CurveEditPie(bpy.types.Menu):
    bl_label = "曲线编辑"
    bl_idname = "VIEW3D_MT_m8_curve_edit_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        wm = context.window_manager
        last_handle = getattr(wm, "m8_last_curve_handle_type", "AUTOMATIC")
        last_action = getattr(wm, "m8_last_curve_edit_action", "")

        ops = pie.operator(M8_OT_CurveHandleTypeRemember.bl_idname, text="手柄:Auto", icon="HANDLE_AUTO", depress=(last_handle == "AUTOMATIC"))
        ops.handle_type = "AUTOMATIC"
        ops = pie.operator(M8_OT_CurveHandleTypeRemember.bl_idname, text="手柄:Align", icon="HANDLE_ALIGNED", depress=(last_handle == "ALIGNED"))
        ops.handle_type = "ALIGNED"
        ops = pie.operator(M8_OT_CurveHandleTypeRemember.bl_idname, text="手柄:Vector", icon="HANDLE_VECTOR", depress=(last_handle == "VECTOR"))
        ops.handle_type = "VECTOR"
        ops = pie.operator(M8_OT_CurveHandleTypeRemember.bl_idname, text="手柄:Free", icon="HANDLE_FREE", depress=(last_handle == "FREE_ALIGN"))
        ops.handle_type = "FREE_ALIGN"

        pie.operator(M8_OT_CurveSwitchDirectionRemember.bl_idname, text="反转方向", icon="FILE_REFRESH", depress=(last_action == "SWITCH_DIRECTION"))
        ops = pie.operator(M8_OT_CurveSubdivideRemember.bl_idname, text="细分", icon="SUBDIVIDE_EDGES", depress=(last_action == "SUBDIVIDE"))
        ops.number_cuts = 1
        pie.operator(M8_OT_CurveSmoothRemember.bl_idname, text="平滑", icon="SMOOTHCURVE", depress=(last_action == "SMOOTH"))
        pie.operator(M8_OT_CurveCyclicToggle.bl_idname, text="切换闭合", icon="RECOVER_LAST")


 


class VIEW3D_MT_M8EmptyTypePie(bpy.types.Menu):
    bl_label = "空物体类型"
    bl_idname = "VIEW3D_MT_m8_empty_type_pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        obj = context.object
        
        # 1. Left - 十字
        pie.prop_enum(obj, "empty_display_type", "PLAIN_AXES", text="十字", icon="EMPTY_AXIS")
        # 2. Right - 箭头
        pie.prop_enum(obj, "empty_display_type", "ARROWS", text="箭头", icon="EMPTY_ARROWS")
        # 3. Bottom - 单箭头
        pie.prop_enum(obj, "empty_display_type", "SINGLE_ARROW", text="单箭头", icon="EMPTY_SINGLE_ARROW")
        # 4. Top - 图片
        pie.prop_enum(obj, "empty_display_type", "IMAGE", text="图片", icon="IMAGE_DATA")
        # 5. Top Left - 立方体
        pie.prop_enum(obj, "empty_display_type", "CUBE", text="立方体", icon="CUBE")
        # 6. Top Right - 球体
        pie.prop_enum(obj, "empty_display_type", "SPHERE", text="球体", icon="SPHERE")
        # 7. Bottom Left - 锥体
        pie.prop_enum(obj, "empty_display_type", "CONE", text="锥体", icon="CONE")
        # 8. Bottom Right - 圆环
        pie.prop_enum(obj, "empty_display_type", "CIRCLE", text="圆环", icon="MESH_CIRCLE")


class VIEW3D_MT_M8TextEditPie(bpy.types.Menu):
    bl_label = "文字编辑"
    bl_idname = "VIEW3D_MT_m8_text_edit_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator("font.text_copy", text="复制", icon="COPYDOWN")
        pie.operator("font.text_paste", text="粘贴", icon="PASTEDOWN")
        pie.operator("font.text_cut", text="剪切", icon="CUT")
        pie.operator("font.delete", text="删除", icon="X")
        pie.operator("font.select_all", text="全选", icon="SELECT_SET")
        pie.operator("font.line_break", text="换行", icon="SORTBYEXT")
        pie.separator()
        pie.separator()
