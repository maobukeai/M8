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

            # 7. 西南 (Bottom-Left): 着色模式切换
            box_sw = pie.box()
            col_sw = box_sw.column(align=True)
            col_sw.scale_y = 1.1
            if context.mode == "EDIT_MESH":
                col_sw.operator("mesh.faces_shade_smooth", text=_T("平滑着色"), icon="SHADING_RENDERED")
                col_sw.operator("mesh.faces_shade_flat", text=_T("平直着色"), icon="SHADING_SOLID")
            else:
                col_sw.operator("object.shade_smooth", text=_T("平滑着色"), icon="SHADING_RENDERED")
                col_sw.operator("object.shade_flat", text=_T("平直着色"), icon="SHADING_SOLID")

            # 8. 东南 (Bottom-Right): 辅助显示与快捷清理
            box_se = pie.box()
            col_se = box_se.column(align=True)
            col_se.scale_y = 1.1
            view = getattr(context, "space_data", None)
            overlay = getattr(view, "overlay", None) if view else None
            if overlay and hasattr(overlay, "show_face_orientation"):
                col_se.prop(overlay, "show_face_orientation", text=_T("面朝向"), icon="FACESEL")
            col_se.operator("m8.flip_normal_transfer", text=_T("反转法向传递"), icon="ARROW_LEFTRIGHT")
            col_se.operator("m8.clear_custom_normals", text=_T("重置自定义法向"), icon="LOOP_BACK")
        except Exception as e:
            try:
                from ...utils.logger import get_logger
                get_logger().error(f"Error drawing normal pie menu: {e}")
            except Exception:
                pass
