# -*- coding: utf-8 -*-
"""
M8 法向饼菜单 (Normal Pie Menu)
在编辑模式下快速修正法向、消除黑斑拉扯、传递法向、应用或清理法向修改器。
"""

import bpy
from ...utils.i18n import _T

class VIEW3D_MT_M8NormalPie(bpy.types.Menu):
    bl_label = _T("法向工具")
    bl_idname = "VIEW3D_MT_m8_normal_pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        try:
            # 1. 西 (Left): 平面轮廓拍平
            op_planar = pie.operator("m8.smart_normal_transfer", text=_T("平面拍平传递"), icon="MOD_NORMALEDIT")
            op_planar.mode = "PLANAR"

            # 2. 东 (Right): 圆柱曲面拟合
            op_cyl = pie.operator("m8.smart_normal_transfer", text=_T("圆柱拟合传递"), icon="MESH_CYLINDER")
            op_cyl.mode = "CYLINDER"

            # 3. 南 (Bottom): 提取面平滑
            op_smooth = pie.operator("m8.smart_normal_transfer", text=_T("提取平滑传递"), icon="MOD_SMOOTH")
            op_smooth.mode = "SMOOTH_EXTRACT"

            # 4. 北 (Top): 智能法向 (AUTO) - 主推项，手势往上一甩即智能修正
            op_auto = pie.operator("m8.smart_normal_transfer", text=_T("智能法向 (AUTO)"), icon="AUTO")
            op_auto.mode = "AUTO"

            # 5. 西北 (Top-Left): 应用所有法向修改器并清理辅助体
            pie.operator("m8.apply_normal_transfer", text=_T("应用并固化法向"), icon="CHECKMARK")

            # 6. 东北 (Top-Right): 清理法向修改器
            pie.operator("m8.clear_normal_transfer", text=_T("清除法向传递"), icon="TRASH")

            # 7. 西南 (Bottom-Left): 着色模式与高级工具入口
            box_sw = pie.box()
            col_sw = box_sw.column(align=True)
            col_sw.scale_y = 1.05
            if context.mode == "EDIT_MESH":
                col_sw.operator("mesh.faces_shade_smooth", text=_T("平滑着色"), icon="SHADING_RENDERED")
                col_sw.operator("mesh.faces_shade_flat", text=_T("平直着色"), icon="SHADING_SOLID")
            else:
                col_sw.operator("object.shade_smooth", text=_T("平滑着色"), icon="SHADING_RENDERED")
                col_sw.operator("object.shade_flat", text=_T("平直着色"), icon="SHADING_SOLID")
            col_sw.menu("VIEW3D_MT_m8_normal_direct_tools_menu", text=_T("更多法向工具..."), icon="DOWNARROW_HLT")

            # 8. 东南 (Bottom-Right): 常用控制与历史暂存入口
            box_se = pie.box()
            col_se = box_se.column(align=True)
            col_se.scale_y = 1.05
            col_se.operator("m8.flip_normal_transfer", text=_T("反转法向"), icon="ARROW_LEFTRIGHT")
            col_se.operator("m8.clear_custom_normals", text=_T("重置自定义法向"), icon="LOOP_BACK")
            col_se.menu("VIEW3D_MT_m8_normal_history_menu", text=_T("暂存与快照..."), icon="DOWNARROW_HLT")
        except Exception as e:
            try:
                from ...utils.logger import get_logger
                get_logger().error(f"Error drawing normal pie menu: {e}")
            except Exception:
                pass


class VIEW3D_MT_M8NormalDirectToolsMenu(bpy.types.Menu):
    bl_label = _T("更多法向工具")
    bl_idname = "VIEW3D_MT_m8_normal_direct_tools_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("m8.flatten_normals", text=_T("选区法向拍平"), icon="MOD_NORMALEDIT")
        layout.operator("m8.average_normals", text=_T("法向平均化"), icon="MOD_SMOOTH")
        layout.operator("m8.align_normals_to_axis", text=_T("法向轴向对齐"), icon="SNAP_INCREMENT")
        layout.operator("m8.point_normals_to_cursor", text=_T("法向指向游标"), icon="PIVOT_CURSOR")
        layout.operator("m8.transfer_from_target", text=_T("从目标物体吸取"), icon="EYEDROPPER")
        layout.separator()
        layout.operator("m8.toggle_split_normals", text=_T("显示法向连线"), icon="NORMALS_FACE")


class VIEW3D_MT_M8NormalHistoryMenu(bpy.types.Menu):
    bl_label = _T("暂存与快照")
    bl_idname = "VIEW3D_MT_m8_normal_history_menu"

    def draw(self, context):
        layout = self.layout
        obj_act = context.active_object or context.edit_object
        has_stash = False
        if obj_act and obj_act.type == "MESH":
            stash_name = obj_act.get("_m8_normal_stash_name")
            if stash_name and stash_name in bpy.data.objects:
                has_stash = True
            elif f"_M8_Stash_{obj_act.name}" in bpy.data.objects:
                has_stash = True

        has_snapshot = bool(obj_act and obj_act.type == "MESH" and "_M8_Normal_Snapshot" in obj_act.data.attributes)

        layout.label(text=_T("几何暂存 (跨拓扑):"), icon="DUPLICATE")
        layout.operator("m8.create_geometry_stash", text=_T("暂存几何体 (Stash)"), icon="DUPLICATE")
        row_stash = layout.row(align=True)
        row_stash.enabled = has_stash
        row_stash.operator("m8.transfer_from_stash", text=_T("从暂存体恢复法向"), icon="MOD_DATA_TRANSFER")
        if has_stash:
            layout.operator("m8.clear_geometry_stash", text=_T("清除暂存"), icon="PANEL_CLOSE")

        layout.separator()
        layout.label(text=_T("法向快照 (同拓扑):"), icon="FILE_TICK")
        layout.operator("m8.save_normal_snapshot", text=_T("保存法向快照"), icon="FILE_TICK")
        row_snap = layout.row(align=True)
        row_snap.enabled = has_snapshot
        row_snap.operator("m8.restore_normal_snapshot", text=_T("还原法向快照"), icon="RECOVER_LAST")
        if has_snapshot:
            layout.operator("m8.clear_normal_snapshot", text=_T("清除法向快照"), icon="TRASH")

