import bpy
from ...utils import SNAP_MATRIX_WORLD_KEY, SNAP_SIZE_KEY, get_backup_suffix, is_size_cage
from ...utils.i18n import _T

class VIEW3D_PT_SizeAdjustPanel(bpy.types.Panel):
    bl_label = ""
    bl_idname = "VIEW3D_PT_size_expert"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm8'
    bl_order = 10
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text=_T("尺寸专家工具 Pro"))

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']
        cage_children = [o for o in getattr(obj, "children", []) if getattr(o, "type", None) == 'MESH'] if obj and is_size_cage(obj) else []
        backup_suffix = get_backup_suffix()
        is_backup = bool(obj and obj.name.endswith(backup_suffix))

        row = layout.row(align=True)
        row.operator("scene.switch_unit", text="MM").unit_type = 'MM'
        row.operator("scene.switch_unit", text="CM").unit_type = 'CM'
        row.operator("scene.switch_unit", text="M").unit_type = 'M'

        layout.separator()
        row = layout.row(align=True)
        row.operator("object.toggle_backup_visibility", icon='HIDE_OFF')
        row.prop(context.scene, "size_tool_padding", text=_T("内边距"))
        row.operator("scene.reset_size_tool_padding", text=_T("重置"))
        layout.operator("object.create_size_cage", icon='MOD_WIREFRAME')

        if not obj:
            return

        if is_backup:
            box = layout.box()
            box.label(text=_T("备用调节盒:"), icon='FILE_BACKUP')
            row = box.row(align=True)
            row.operator("object.activate_backup_cage", icon='CHECKMARK')
            row.operator("object.delete_backup_cages", icon='TRASH')
            return

        if is_size_cage(obj):
            box = layout.box()
            box.label(text=_T("调节盒控制中:"), icon='OBJECT_DATA')
            box.prop(obj, "dimensions", text="")
            box.operator("object.auto_adjust_z", icon='CON_SIZELIMIT')
            layout.separator()
            layout.operator("object.update_size_snapshot", icon='FILE_TICK')
            layout.separator()
            row = layout.row(align=True)
            row.operator("object.finish_detach", icon='CHECKMARK')
            row.operator("object.finish_and_clean", icon='CHECKMARK')
            row = layout.row(align=True)
            row.operator("object.finish_archive_cage", icon='FILE_BACKUP').bake = False
            row.operator("object.finish_archive_cage", icon='FILE_BACKUP', text=_T("完成(保留盒/烘焙)")).bake = True
            return

        candidates = selected_meshes or cage_children or [obj]
        has_snapshot = any((SNAP_MATRIX_WORLD_KEY in o.keys() or SNAP_SIZE_KEY in o.keys()) for o in candidates)

        layout.separator()
        row = layout.row()
        row.enabled = has_snapshot
        row.operator("object.restore_from_snapshot", icon='LOOP_BACK', text=_T("还原(重建盒)")).rebuild_cage = True
        row = layout.row()
        row.enabled = has_snapshot
        row.operator("object.restore_from_snapshot", icon='RECOVER_LAST', text=_T("仅还原(不重建盒)")).rebuild_cage = False
        row = layout.row(align=True)
        row.enabled = has_snapshot
        row.operator("object.select_size_snapshot_group", icon='RESTRICT_SELECT_OFF')
        row.operator("object.clear_size_snapshot", icon='TRASH')

        if not has_snapshot:
            layout.label(text=_T("未检测到快照：请先创建调节盒再尝试还原"))

class VIEW3D_PT_SizeToolToolboxPanel(bpy.types.Panel):
    bl_label = ""
    bl_idname = "VIEW3D_PT_size_tool_toolbox"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm8'
    bl_order = 11
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text=_T("工具箱"))

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text=_T("变换辅助"), icon='TRANSFORM_ORIGINS')
        row = box.row(align=True)
        row.operator("object.quick_origin", text=_T("原点到底部")).type = 'BOTTOM'
        row.operator("object.quick_origin", text=_T("原点到中心")).type = 'CENTER'
        row = box.row(align=True)
        row.operator("object.snap_to_floor", text=_T("一键落地"), icon='RESTRICT_SELECT_OFF')
        row.operator("object.quick_origin", text=_T("原点到(0,0,0)")).type = 'ORIGIN'

        box = layout.box()
        box.label(text=_T("冻结变换"), icon='FREEZE')
        row = box.row()
        row.enabled = any(o.type == 'MESH' for o in context.selected_objects)
        row.operator("object.freeze_transforms_maya", text=_T("自定义..."))
        row = box.row(align=True)
        row.enabled = any(o.type == 'MESH' for o in context.selected_objects)
        op = row.operator("object.freeze_transforms_maya", text=_T("全部"))
        op.freeze_location = True
        op.freeze_rotation = True
        op.freeze_scale = True
        op = row.operator("object.freeze_transforms_maya", text=_T("仅位置"))
        op.freeze_location = True
        op.freeze_rotation = False
        op.freeze_scale = False
        op = row.operator("object.freeze_transforms_maya", text=_T("仅旋转"))
        op.freeze_location = False
        op.freeze_rotation = True
        op.freeze_scale = False
        op = row.operator("object.freeze_transforms_maya", text=_T("仅缩放"))
        op.freeze_location = False
        op.freeze_rotation = False
        op.freeze_scale = True

        box = layout.box()
        box.label(text=_T("叶片转面片"), icon='MESH_GRID')
        box.enabled = (context.active_object is not None and context.active_object.type == 'MESH' and context.mode == 'EDIT_MESH')
        box.operator("mesh.leaves_to_planes", text=_T("转换..."))
        row = box.row(align=True)
        row.operator("mesh.scale_from_bottom_uv", text=_T("从底部UV缩放..."))
        row.operator("mesh.extend_leaf_tip", text=_T("延长叶尖..."))

        box = layout.box()
        box.label(text=_T("随机选择岛"), icon='RESTRICT_SELECT_OFF')
        box.enabled = (context.active_object is not None and context.active_object.type == 'MESH' and context.mode == 'EDIT_MESH')
        
        col = box.column(align=True)
        col.operator("mesh.select_random_islands", text=_T("随机选择..."))
        
        row = col.row(align=True)
        op = row.operator("mesh.select_random_islands", text=_T("反选岛"))
        op.action = 'DESELECT'
        op.scope = 'ALL'
        op.percentage = 100.0
