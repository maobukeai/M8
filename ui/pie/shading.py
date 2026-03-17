import bpy

class VIEW3D_MT_M8ShadingPie(bpy.types.Menu):
    bl_label = "着色方式"
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

        pie.prop_enum(shading, "type", "WIREFRAME", text="线框", icon="SHADING_WIRE")
        pie.prop_enum(shading, "type", "SOLID", text="实体", icon="SHADING_SOLID")
        pie.prop_enum(shading, "type", "MATERIAL", text="材质预览", icon="SHADING_TEXTURE")
        pie.prop_enum(shading, "type", "RENDERED", text="渲染", icon="SHADING_RENDERED")

        box = pie.box()
        col = box.column(align=True)
        col.label(text="辅助显示")
        if overlay and hasattr(overlay, "show_face_orientation"):
            col.prop(overlay, "show_face_orientation", text="面朝向", icon="FACESEL")
        if overlay and hasattr(overlay, "show_wireframes"):
            col.prop(overlay, "show_wireframes", text="线框叠加", icon="MOD_WIREFRAME")
        if overlay and hasattr(overlay, "show_stats"):
            col.prop(overlay, "show_stats", text="统计信息", icon="INFO")

        box = pie.box()
        col = box.column(align=True)
        col.label(text="视图控制")
        if shading.type == "WIREFRAME" and hasattr(shading, "show_xray_wireframe"):
            col.prop(shading, "show_xray_wireframe", text="透视模式", icon="XRAY")
        elif hasattr(shading, "show_xray"):
            col.prop(shading, "show_xray", text="透视模式", icon="XRAY")

        box = pie.box()
        col = box.column(align=True)
        col.label(text="显示设置")
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
                    op = col.operator("wm.context_set_enum", text=f"切换: {target_text}", icon="SHADING_RENDERED")
                    op.data_path = "scene.render.engine"
                    op.value = target_engine
                elif cycles_available and render.engine != "CYCLES":
                    op = col.operator("wm.context_set_enum", text="切换: Cycles", icon="SHADING_RENDERED")
                    op.data_path = "scene.render.engine"
                    op.value = "CYCLES"
                if engine_ids:
                    col.prop(render, "engine", text="渲染器")
                elif hasattr(col, "label"):
                    col.label(text="未检测到可用渲染引擎", icon="INFO")
            except Exception:
                pass
        if render and hasattr(render, "film_transparent"):
            col.prop(render, "film_transparent", text="背景透明")

        box = pie.box()
        col = box.column(align=True)
        col.label(text="材质管理")
        if hasattr(context.view_layer, "material_override"):
            col.prop(context.view_layer, "material_override", text="")
            if context.view_layer.material_override:
                op = col.operator("wm.context_set_value", text="清除覆盖", icon="X")
                op.data_path = "view_layer.material_override"
                op.value = "None"
        else:
            col.label(text="无覆盖属性", icon="ERROR")
