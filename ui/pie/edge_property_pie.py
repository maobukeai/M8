import bpy
from bpy.app.translations import contexts as i18n_contexts


def _draw_edge_overlay_toggles(context, layout):
    overlay = getattr(getattr(context, "space_data", None), "overlay", None)
    if not overlay:
        return
    row = layout.row(align=True)
    row.prop(overlay, "show_edge_crease", text="折痕", toggle=True, expand=True)
    row.prop(overlay, "show_edge_sharp", text="锐边", text_ctxt=i18n_contexts.plural, toggle=True, expand=True)
    row.prop(overlay, "show_edge_bevel_weight", text="倒角权重", toggle=True, expand=True)
    row.prop(overlay, "show_edge_seams", text="缝合边", toggle=True, expand=True)


def _draw_top_block(context, layout):
    column = layout.column(align=True)
    column.scale_y = 1.2
    column.scale_x = 1.2
    column.operator("mesh.set_sharpness_by_angle", text="按角度锐边")
    row = column.row(align=True)
    row.scale_y = 1.2
    ops = row.operator("mesh.mark_sharp", text="从顶点标记锐边")
    ops.use_verts = True
    ops = row.operator("mesh.mark_sharp", text="", icon="PANEL_CLOSE")
    ops.clear = True
    ops.use_verts = True
    row = column.row(align=True)
    row.scale_y = 1.3
    row.operator("mesh.mark_sharp", text="标记锐边")
    row.operator("mesh.mark_sharp", text="", icon="PANEL_CLOSE").clear = True


class VIEW3D_MT_M8EdgePropertyPie(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_m8_edge_property_pie"
    bl_label = "边属性"

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        from ...ops.mesh.edge_property import (
            M8_OT_EdgeCrease,
            M8_OT_EdgeBevelWeight,
            M8_OT_ClearAllEdgeProperty,
            M8_OT_VertCrease,
            M8_OT_VertBevelWeight,
        )

        pie = self.layout.menu_pie()

        pie.operator("mesh.edge_rotate", icon="LOOP_FORWARDS", text="顺时针旋转边").use_ccw = False
        pie.operator("mesh.edge_rotate", icon="LOOP_BACK", text="逆时针旋转边").use_ccw = True
        pie.operator(M8_OT_ClearAllEdgeProperty.bl_idname, icon="TRASH", text="清除所有属性")

        _draw_top_block(context, pie)

        column = pie.column(align=True)
        column.scale_y = 1.2
        column.scale_x = 1.1
        row = column.row(align=True)
        row.operator_context = "INVOKE_DEFAULT"
        row.operator("transform.edge_crease", emboss=True, text="边折痕")
        column.operator_context = "EXEC_DEFAULT"
        row = column.row(align=True)
        for value in (0.25, 0.5, 1):
            row.operator(M8_OT_EdgeCrease.bl_idname, text="{}".format(value)).value = value
        row.operator(M8_OT_EdgeCrease.bl_idname, text="", icon="PANEL_CLOSE").value = -1

        column = pie.column(align=True)
        column.scale_y = 1.2
        column.scale_x = 1.1
        row = column.row(align=True)
        row.operator_context = "INVOKE_DEFAULT"
        row.operator("transform.edge_bevelweight", emboss=True, text="边倒角权重")
        column.operator_context = "EXEC_DEFAULT"
        row = column.row(align=True)
        row.operator(M8_OT_EdgeBevelWeight.bl_idname, text="", icon="PANEL_CLOSE").value = -1
        for value in reversed((0.25, 0.5, 1)):
            row.operator(M8_OT_EdgeBevelWeight.bl_idname, text="{}".format(value)).value = value

        column = pie.column(align=True)
        column.separator(factor=5)
        column.scale_y = 1.2
        column.scale_x = 0.8
        _draw_edge_overlay_toggles(context, column.row(align=True))
        column.separator()
        column.operator_context = "EXEC_DEFAULT"
        row = column.row(align=True)
        for value in (0.25, 0.5, 1):
            row.operator(M8_OT_VertCrease.bl_idname, text="{}".format(value)).value = value
        row.operator(M8_OT_VertCrease.bl_idname, text="", icon="PANEL_CLOSE").value = -1
        row = column.row(align=True)
        row.operator_context = "INVOKE_DEFAULT"
        row.operator("transform.vert_crease", emboss=True, text="顶点折痕")
        column.separator()
        row = column.row(align=True)
        for value in (0.25, 0.5, 1):
            row.operator(M8_OT_VertBevelWeight.bl_idname, text="{}".format(value)).value = value
        row.operator(M8_OT_VertBevelWeight.bl_idname, text="", icon="PANEL_CLOSE").value = 0
        row = column.row(align=True)
        row.operator_context = "INVOKE_DEFAULT"
        row.operator(M8_OT_VertBevelWeight.bl_idname, emboss=True, text="顶点倒角权重")

        column = pie.column(align=True)
        column.scale_x = 1.4
        row = column.row(align=True)
        row.scale_y = 1.4
        ops = row.operator("mesh.mark_seam", text="", icon="PANEL_CLOSE")
        ops.clear = True
        ops = row.operator("mesh.mark_seam", text="标记缝合边")
        ops.clear = False
        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("mesh.mark_freestyle_edge", text="", icon="PANEL_CLOSE").clear = True
        row.operator("mesh.mark_freestyle_edge", text="标记 Freestyle").clear = False

