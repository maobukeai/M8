import bpy
from ...utils.i18n import _T

class VIEW3D_MT_M8ShadingPie(bpy.types.Menu):
    bl_label = _T("着色方式")
    bl_idname = "VIEW3D_MT_m8_shading_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        view = context.space_data
        shading = getattr(view, "shading", None) if view else None
        overlay = getattr(view, "overlay", None) if view else None
        render = getattr(context.scene, "render", None) if context.scene else None

        if not shading:
            for _ in range(8):
                pie.separator()
            return

        pie.prop_enum(shading, "type", "WIREFRAME", text=_T("线框"), icon="SHADING_WIRE")
        pie.prop_enum(shading, "type", "SOLID", text=_T("实体"), icon="SHADING_SOLID")
        pie.prop_enum(shading, "type", "MATERIAL", text=_T("材质预览"), icon="SHADING_TEXTURE")
        pie.prop_enum(shading, "type", "RENDERED", text=_T("渲染"), icon="SHADING_RENDERED")

        box = pie.box()
        col = box.column(align=True)
        col.label(text=_T("辅助显示"))
        if overlay and hasattr(overlay, "show_face_orientation"):
            col.prop(overlay, "show_face_orientation", text=_T("面朝向"), icon="FACESEL")
        if overlay and hasattr(overlay, "show_wireframes"):
            col.prop(overlay, "show_wireframes", text=_T("线框叠加"), icon="MOD_WIREFRAME")
        if overlay and hasattr(overlay, "show_stats"):
            col.prop(overlay, "show_stats", text=_T("统计信息"), icon="INFO")

        box = pie.box()
        col = box.column(align=True)
        col.label(text=_T("视图控制"))
        if shading.type == "WIREFRAME" and hasattr(shading, "show_xray_wireframe"):
            col.prop(shading, "show_xray_wireframe", text=_T("透视模式"), icon="XRAY")
        elif hasattr(shading, "show_xray"):
            col.prop(shading, "show_xray", text=_T("透视模式"), icon="XRAY")

        box = pie.box()
        col = box.column(align=True)
        col.label(text=_T("显示设置"))
        if shading.type == "RENDERED" and render:
            try:
                engine_prop = render.bl_rna.properties.get("engine") if hasattr(render, "bl_rna") else None
                engine_ids = []
                if engine_prop:
                    for item in engine_prop.enum_items:
                        if item.identifier:
                            engine_ids.append(item.identifier)

                eevee_id = None
                if "BLENDER_EEVEE" in engine_ids:
                    eevee_id = "BLENDER_EEVEE"
                elif "BLENDER_EEVEE_NEXT" in engine_ids:
                    eevee_id = "BLENDER_EEVEE_NEXT"

                cycles_available = "CYCLES" in engine_ids
                eevee_available = bool(eevee_id)

                if cycles_available and eevee_available:
                    if render.engine == "CYCLES":
                        target_engine = eevee_id
                        target_text = "Eevee"
                    elif render.engine == eevee_id:
                        target_engine = "CYCLES"
                        target_text = "Cycles"
                    else:
                        target_engine = "CYCLES"
                        target_text = "Cycles"
                    op = col.operator("wm.context_set_enum", text=_T("切换: ") + target_text, icon="SHADING_RENDERED")
                    op.data_path = "scene.render.engine"
                    op.value = target_engine
                elif cycles_available and render.engine != "CYCLES":
                    op = col.operator("wm.context_set_enum", text=_T("切换: Cycles"), icon="SHADING_RENDERED")
                    op.data_path = "scene.render.engine"
                    op.value = "CYCLES"
                if engine_ids:
                    col.prop(render, "engine", text=_T("渲染器"))
                elif hasattr(col, "label"):
                    col.label(text=_T("未检测到可用渲染引擎"), icon="INFO")
            except Exception:
                pass
        if render and hasattr(render, "film_transparent"):
            col.prop(render, "film_transparent", text=_T("背景透明"))

        # UV 棋盘格显示 (方便查看 UV 拉伸)
        is_checker_on = bool(
            getattr(context.view_layer, "material_override", None) and
            context.view_layer.material_override.name == "M8_UV_Checker"
        )
        row = col.row(align=True)
        row.operator(
            "m8.toggle_uv_checker",
            text=_T("棋盘格显示"),
            icon="CHECKBOX_HLT" if is_checker_on else "CHECKBOX_DEHLT",
            depress=is_checker_on,
        )
        if is_checker_on and hasattr(context.scene, "m8"):
            sub_col = col.box().column(align=True)
            split = sub_col.split(factor=0.5, align=True)
            row_a = split.row(align=True)
            row_b = split.row(align=True)
            row_a.prop(context.scene.m8, "uv_checker_scale", text=_T("缩放"))
            row_b.prop(context.scene.m8, "uv_checker_type", text="")

        box = pie.box()
        col = box.column(align=True)
        col.label(text=_T("材质管理"), icon="MATERIAL")

        obj = context.active_object
        is_mesh = bool(obj and obj.type == "MESH")
        is_edit = (context.mode == "EDIT_MESH")
        act_mat = obj.active_material if (is_mesh and hasattr(obj, "active_material")) else None

        # 检查是否有外部全局覆盖材质（且非 M8 UV 棋盘格）
        view_layer = getattr(context, "view_layer", None)
        curr_override = getattr(view_layer, "material_override", None) if view_layer else None
        if curr_override and curr_override.name != "M8_UV_Checker":
            row_ov = col.row(align=True)
            row_ov.alert = True
            op_ov = row_ov.operator("wm.context_set_id", text=_T("清除全局覆盖"), icon="X")
            op_ov.data_path = "view_layer.material_override"
            op_ov.value = ""

        if is_mesh:
            # 1. 材质名 / 切换 + 独立副本 + 新建
            row = col.row(align=True)
            if act_mat:
                row.prop(obj, "active_material", text="", icon="MATERIAL_DATA")
                users = act_mat.users
                if users > 1:
                    sub_r = row.row(align=True)
                    sub_r.alert = True
                    sub_r.operator("m8.material_make_single_user", text=f"{users}", icon="DUPLICATE")
                else:
                    sub_r = row.row(align=True)
                    sub_r.enabled = False
                    sub_r.operator("m8.material_make_single_user", text="", icon="DUPLICATE")
            else:
                row.label(text=_T("未指定材质"), icon="SHADING_TEXTURE")

            row.operator("m8.material_new", text="", icon="ADD")

            col.separator()

            # 2. 模式联动核心操作
            if is_edit:
                row_assign = col.row(align=True)
                row_assign.scale_y = 1.15
                row_assign.operator("object.material_slot_assign", text=_T("指定到所选面"), icon="CHECKMARK")
                row_assign.operator("mesh.select_material", text=_T("选同面"), icon="RESTRICT_SELECT_OFF")
            else:
                row_sync = col.row(align=True)
                row_sync.scale_y = 1.15
                has_multisel = len(context.selected_objects) > 1
                row_sync.enabled = bool(act_mat and has_multisel)
                row_sync.operator("m8.material_link_to_selected", text=_T("赋予至选中物体"), icon="LINKED")

            # 3. 辅助管理工具
            row_tools = col.row(align=True)
            if not is_edit:
                op_sel = row_tools.operator("m8.select_same_material", text=_T("选择同材质"), icon="RESTRICT_SELECT_OFF")
                op_sel.enabled = bool(act_mat)
            row_tools.operator("m8.material_clean_slots", text=_T("清理空槽"), icon="BRUSH_DATA")
            if act_mat:
                row_tools.operator("object.material_slot_remove", text="", icon="TRASH")
        else:
            col.label(text=_T("未选中网格物体"), icon="INFO")
