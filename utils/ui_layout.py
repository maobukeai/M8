import bpy


def operator_draw_object_type_panel(popover, context):
    """绘制活动物体相关的面板"""
    draw_object_property_panel(context, popover.layout)


def draw_object_property_panel(context, layout, panel_name=None):
    """传入Layout绘制相关面板"""
    find = find_draw_class(context, panel_name)
    mix_class = type("Test", (), {"bl_space_type": "PROPERTIES", "layout": layout})
    if find and context.object:
        if context.object.type == "CAMERA":
            with context.temp_override(camera=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "LIGHT":
            with context.temp_override(light=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "ARMATURE":
            with context.temp_override(armature=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "META":
            with context.temp_override(meta_ball=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "LATTICE":
            with context.temp_override(lattice=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "LIGHT_PROBE":
            with context.temp_override(lightprobe=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "SPEAKER":
            with context.temp_override(speaker=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "CURVE":
            with context.temp_override(curve=context.object.data):
                find.draw(mix_class, context)
        elif context.object.type == "EMPTY":
            find.draw(mix_class, context)
        else:
            layout.label(text="draw_popover Error")
    else:
        layout.label(text="draw_popover")


def find_draw_class(context, panel_name=None):
    if panel_name is None:
        in_selected = context.object in context.selected_objects
        if in_selected:
            obj_type = context.object.type
            if obj_type == "LIGHT":
                engine = context.engine
                if engine == "BLENDER_EEVEE_NEXT":
                    panel_name = "DATA_PT_EEVEE_light"
                elif engine == "BLENDER_EEVEE":
                    panel_name = "DATA_PT_EEVEE_light_legacy"
                elif engine == "CYCLES":
                    panel_name = "CYCLES_LIGHT_PT_light"
                elif engine == "BLENDER_WORKBENCH":
                    panel_name = "DATA_PT_light"
            elif obj_type == "CAMERA":
                panel_name = "DATA_PT_lens"
            elif obj_type == "ARMATURE":
                panel_name = "DATA_PT_display"
            elif obj_type == "META":
                panel_name = "DATA_PT_metaball"
            elif obj_type == "EMPTY":
                panel_name = "DATA_PT_empty"
            elif obj_type == "LATTICE":
                panel_name = "DATA_PT_lattice"
            elif obj_type == "LIGHT_PROBE":
                panel_name = "DATA_PT_lightprobe"
            elif obj_type == "SPEAKER":
                panel_name = "DATA_PT_speaker"
            elif obj_type == "CURVE":
                panel_name = "DATA_PT_shape_curve"

    if panel_name is not None:
        find = getattr(bpy.types, panel_name, None)
        if find is not None and context.object:
            if context.object.type == "CAMERA":
                with context.temp_override(camera=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "LIGHT":
                with context.temp_override(light=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "ARMATURE":
                with context.temp_override(armature=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "META":
                with context.temp_override(meta_ball=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "LATTICE":
                with context.temp_override(lattice=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "LIGHT_PROBE":
                with context.temp_override(lightprobe=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "SPEAKER":
                with context.temp_override(speaker=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "CURVE":
                with context.temp_override(curve=context.object.data):
                    if find.poll(context):
                        return find
            elif context.object.type == "EMPTY":
                if find.poll(context):
                    return find
    return None
