import bpy

def _mesh_select_ui_args(context):
    from bpy.app.translations import pgettext_iface
    if context.mode == "EDIT_MESH":
        select_mode = context.scene.tool_settings.mesh_select_mode[:]
        if select_mode == (True, False, False):
            return {"text": pgettext_iface("To Vert"), "icon": "VERTEXSEL"}
        if select_mode == (False, True, False):
            return {"text": pgettext_iface("To Edge"), "icon": "EDGESEL"}
        if select_mode == (False, False, True):
            return {"text": pgettext_iface("To Face"), "icon": "FACESEL"}
        return {"text": pgettext_iface("To Select"), "icon": "RESTRICT_SELECT_OFF"}
    return {"text": pgettext_iface("To Select"), "icon": "RESTRICT_SELECT_OFF"}

class VIEW3D_MT_SizeToolTransformPie(bpy.types.Menu):
    bl_label = "光标和原点"
    bl_idname = "VIEW3D_MT_size_tool_transform_pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        if context.mode in {"EDIT_MESH", "EDIT_CURVE"}:
            pie.operator("m8.mp7_cursor_to_select_smart", **_mesh_select_ui_args(context))
            pie.operator("view3d.snap_selected_to_cursor", text="到游标", icon="RESTRICT_SELECT_OFF").use_offset = False

            col = pie.column(align=True)
            col.separator(factor=2)
            col.ui_units_y = -20
            col.scale_y = 1.5
            col.scale_x = 1.2

            row = col.split(factor=0.35)
            row.separator()
            row.label(text="物体原点")

            sp = col.split(align=True)
            if context.mode == "EDIT_CURVE":
                sp.operator("m8.mp7_origin_to_active_smart", text="到曲线", icon="CURVE_DATA")
                sp.operator("m8.mp7_origin_to_cursor_smart", text="到游标", icon="ORIENTATION_CURSOR")
            else:
                sp.operator("m8.mp7_origin_to_active_smart", **_mesh_select_ui_args(context))
                sp.operator("m8.mp7_origin_to_cursor_smart", text="到游标", icon="ORIENTATION_CURSOR")

            pie.separator()
            pie.operator("view3d.snap_cursor_to_center", text="到原点", icon="WORLD")
            pie.operator("view3d.snap_selected_to_cursor", text="到游标，偏移", icon="PIVOT_CURSOR").use_offset = True
            pie.separator()
            return

        # 1. West (Left) - 4
        pie.operator("view3d.snap_cursor_to_selected", text="到所选", icon='RESTRICT_SELECT_OFF')
        # 2. East (Right) - 6
        pie.operator("view3d.snap_selected_to_cursor", text="到游标", icon='PIVOT_CURSOR')
        
        # 3. South (Bottom)
        col = pie.column(align=True)
        col.label(text="物体原点", icon='OBJECT_ORIGIN')
        sub = col.box().column(align=True)
        sub.scale_y = 1.30
        
        # Row 1
        row = sub.row(align=True)
        row.scale_y = 1.15
        op = row.operator("object.origin_set", text="到几何中心", icon='OBJECT_ORIGIN')
        op.type = 'ORIGIN_GEOMETRY'
        try:
            op.center = 'BOUNDS'
        except Exception:
            pass
        row.operator("object.origin_set", text="到游标", icon='PIVOT_CURSOR').type = 'ORIGIN_CURSOR'
        
        # Row 2
        row = sub.row(align=True)
        row.scale_y = 1.15
        row.operator("object.origin_to_active", text="到活动", icon='RESTRICT_SELECT_OFF')
        row.operator("object.quick_origin", text="到底部", icon='TRIA_DOWN').type = 'BOTTOM'

        sub.separator()
        row = sub.row(align=True)
        row.scale_y = 1.15
        op = row.operator("object.freeze_transforms_maya", text="冻结所有变换", icon='FREEZE')
        op.freeze_location = True
        op.freeze_rotation = True
        op.freeze_scale = True
        
        # 4. North (Top)
        pie.separator()
        
        # 5. North-West (Top-Left) - 7
        pie.operator("view3d.snap_cursor_to_center", text="到原点", icon='WORLD')
        
        # 6. North-East (Top-Right) - 9
        op = pie.operator("view3d.snap_selected_to_cursor", text="到游标 (偏移)", icon='PIVOT_CURSOR')
        op.use_offset = True

        # 7. South-West (Bottom-Left) - 1
        pie.separator()

        # 8. South-East (Bottom-Right) - 3
        pie.separator()

class VIEW3D_MT_SizeToolObjectOrigin(bpy.types.Menu):
    bl_label = "物体原点"
    bl_idname = "VIEW3D_MT_size_tool_object_origin"

    def draw(self, context):
        layout = self.layout
        layout.label(text="物体原点", icon='OBJECT_ORIGIN')
        
        col = layout.column(align=True)
        
        # Row 1
        row = col.row(align=True)
        op = row.operator("object.origin_set", text="到几何中心", icon='CENTER_ONLY')
        op.type = 'ORIGIN_GEOMETRY'
        try:
            op.center = 'BOUNDS'
        except Exception:
            pass
        row.operator("object.origin_set", text="到游标", icon='PIVOT_CURSOR').type = 'ORIGIN_CURSOR'

        # Row 2
        row = col.row(align=True)
        row.operator("object.origin_to_active", text="到活动", icon='OBJECT_ACTIVE')
        row.operator("object.quick_origin", text="到底部", icon='ALIGN_BOTTOM').type = 'BOTTOM'
