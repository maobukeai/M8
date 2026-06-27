import bpy
from bpy.app.translations import pgettext_iface as _p


def _tr(text):
    return _p(text)


def _get_active_modifier(obj):
    modifiers = getattr(obj, "modifiers", None)
    if not modifiers:
        return None

    active = getattr(modifiers, "active", None)
    if active:
        return active

    active_index = getattr(modifiers, "active_index", None)
    if active_index is not None and 0 <= active_index < len(modifiers):
        return modifiers[active_index]

    wave_modifiers = [mod for mod in modifiers if getattr(mod, "type", None) == "WAVE"]
    return wave_modifiers[0] if len(wave_modifiers) == 1 else None


def _get_active_wave_modifier(context):
    obj = getattr(context, "active_object", None)
    mod = _get_active_modifier(obj)
    if mod and getattr(mod, "type", None) == "WAVE":
        return obj, mod
    return obj, None


def _prop(layout, data, prop_name, *, text=None, **kwargs):
    if hasattr(data, prop_name):
        if text is None:
            layout.prop(data, prop_name, **kwargs)
        else:
            layout.prop(data, prop_name, text=_tr(text), **kwargs)
        return True
    return False


def _has_any(data, prop_names):
    return any(hasattr(data, prop_name) for prop_name in prop_names)


def _wave_frame_values(mod):
    start = int(getattr(mod, "time_offset", 0))
    lifetime = int(getattr(mod, "lifetime", 0))
    damping = int(getattr(mod, "damping_time", 0))
    stop = start + lifetime
    full_stop = stop + damping
    return start, stop, full_stop


class M8_OT_WaveSetLoopAnimation(bpy.types.Operator):
    bl_idname = "m8.wave_set_loop_animation"
    bl_label = "设置循环动画"
    bl_description = "设置循环动画"
    bl_options = {"REGISTER", "UNDO"}

    modifier_name: bpy.props.StringProperty(options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return _get_active_wave_modifier(context)[1] is not None

    def execute(self, context):
        obj, mod = _get_active_wave_modifier(context)
        if not obj or not mod:
            return {"CANCELLED"}

        if self.modifier_name and mod.name != self.modifier_name:
            found = obj.modifiers.get(self.modifier_name)
            if not found or found.type != "WAVE":
                return {"CANCELLED"}
            mod = found

        scene = context.scene
        frame_start = int(getattr(scene, "frame_start", 1))
        frame_end = int(getattr(scene, "frame_end", frame_start))
        frame_count = max(1, frame_end - frame_start + 1)

        if hasattr(mod, "time_offset"):
            mod.time_offset = frame_start
        if hasattr(mod, "lifetime"):
            mod.lifetime = frame_count
        if hasattr(mod, "damping_time"):
            mod.damping_time = 0
        if hasattr(mod, "use_cyclic"):
            mod.use_cyclic = True

        self.report({"INFO"}, f"已设置循环动画（{frame_start}-{frame_end}，共 {frame_count} 帧）")
        return {"FINISHED"}


class M8_OT_WaveQuickSet(bpy.types.Operator):
    bl_idname = "m8.wave_quick_set"
    bl_label = "波形修改"
    bl_description = "调整波形修改器"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=[
            ("DIFFUSION", "Diffusion", ""),
            ("SHRINK", "Shrink", ""),
            ("FRAME_ZERO", "Frame Zero", ""),
            ("FRAME_STOP", "Frame Stop", ""),
            ("FULL_STOP", "Full stop frame", ""),
        ],
        options={"HIDDEN"},
    )
    modifier_name: bpy.props.StringProperty(options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return _get_active_wave_modifier(context)[1] is not None

    def execute(self, context):
        obj, mod = _get_active_wave_modifier(context)
        if not obj or not mod:
            return {"CANCELLED"}

        if self.modifier_name and mod.name != self.modifier_name:
            found = obj.modifiers.get(self.modifier_name)
            if not found or found.type != "WAVE":
                return {"CANCELLED"}
            mod = found

        if self.action in {"DIFFUSION", "SHRINK"}:
            speed = getattr(mod, "speed", 0.25)
            speed = abs(speed) if abs(speed) > 0.00001 else 0.25
            mod.speed = speed if self.action == "DIFFUSION" else -speed
            self.report({"INFO"}, f"已{'设置扩散' if self.action == 'DIFFUSION' else '设置收缩'}（速度 {mod.speed:.2f}）")
            return {"FINISHED"}

        current = int(getattr(context.scene, "frame_current", 1))
        offset = int(getattr(mod, "time_offset", current))

        if self.action == "FRAME_ZERO" and hasattr(mod, "time_offset"):
            mod.time_offset = current
            self.report({"INFO"}, f"已设置起始帧为 {current}")
        elif self.action == "FRAME_STOP" and hasattr(mod, "lifetime"):
            mod.lifetime = max(1, current - offset)
            self.report({"INFO"}, f"已设置停止帧为 {current}（持续 {mod.lifetime} 帧）")
        elif self.action == "FULL_STOP" and hasattr(mod, "damping_time"):
            lifetime = int(getattr(mod, "lifetime", 0))
            mod.damping_time = max(0, current - offset - lifetime)
            self.report({"INFO"}, f"已设置完全停止（阻尼 {mod.damping_time}）")
        else:
            return {"CANCELLED"}

        return {"FINISHED"}


class VIEW3D_PT_M8_WaveHelper(bpy.types.Panel):
    bl_label = ""
    bl_idname = "VIEW3D_PT_m8_wave_helper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "m8"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return _get_active_wave_modifier(context)[1] is not None

    def draw_header(self, context):
        self.layout.label(text=_tr("WaveHelper"), icon="MOD_WAVE")

    def draw(self, context):
        layout = self.layout
        obj, mod = _get_active_wave_modifier(context)
        if not obj or not mod:
            layout.label(text=_tr("When the active object's activity modifier is the wave modifier it will be displayed in the N panel"), icon="INFO")
            return

        layout.use_property_split = True
        layout.use_property_decorate = False

        header = layout.row(align=True)
        header.prop(mod, "name", text="")

        toggles = header.row(align=True)
        toggles.use_property_split = False
        toggles.use_property_decorate = False
        if hasattr(mod, "show_viewport"):
            toggles.prop(mod, "show_viewport", text="", icon="RESTRICT_VIEW_OFF")
        if hasattr(mod, "show_render"):
            toggles.prop(mod, "show_render", text="", icon="RESTRICT_RENDER_OFF")
        if hasattr(mod, "show_in_editmode"):
            toggles.prop(mod, "show_in_editmode", text="", icon="EDITMODE_HLT")

        box = layout.box()
        box.label(text=_tr("Motion"), icon="MOD_WAVE")
        col = box.column(align=True)
        _prop(col, mod, "height")
        _prop(col, mod, "width", text="宽度")
        _prop(col, mod, "narrowness", text="波间距")
        _prop(col, mod, "speed", text="频率")

        row = box.row(align=True)
        row.use_property_split = False
        row.use_property_decorate = False
        op = row.operator("m8.wave_quick_set", text=_tr("Diffusion"), icon="TRIA_RIGHT")
        op.action = "DIFFUSION"
        op.modifier_name = mod.name
        op = row.operator("m8.wave_quick_set", text=_tr("Shrink"), icon="TRIA_LEFT")
        op.action = "SHRINK"
        op.modifier_name = mod.name

        box = layout.box()
        box.label(text=_tr("Direction"), icon="ORIENTATION_GLOBAL")
        row = box.row(align=True)
        row.use_property_split = False
        row.use_property_decorate = False
        _prop(row, mod, "use_x", toggle=True)
        _prop(row, mod, "use_y", toggle=True)
        col = box.column(align=True)
        _prop(col, mod, "start_position_x")
        _prop(col, mod, "start_position_y")

        box = layout.box()
        box.label(text=_tr("Falloff"), icon="SMOOTHCURVE")
        col = box.column(align=True)
        _prop(col, mod, "falloff_radius")
        _prop(col, mod, "vertex_group", text="顶点组")
        if hasattr(mod, "use_normal"):
            col.prop(mod, "use_normal", text=_tr("Along Normals"))

        if getattr(mod, "use_normal", False):
            row = col.row(align=True)
            row.use_property_split = False
            row.use_property_decorate = False
            _prop(row, mod, "use_normal_x", toggle=True)
            _prop(row, mod, "use_normal_y", toggle=True)
            _prop(row, mod, "use_normal_z", toggle=True)

        if _has_any(mod, ("texture", "texture_coords", "texture_coords_object", "uv_layer")):
            box = layout.box()
            box.label(text=_tr("Texture"), icon="TEXTURE")
            col = box.column(align=True)
            _prop(col, mod, "texture")
            _prop(col, mod, "texture_coords")
            texture_coords = getattr(mod, "texture_coords", "")
            if texture_coords == "OBJECT":
                _prop(col, mod, "texture_coords_object")
            elif texture_coords == "UV":
                _prop(col, mod, "uv_layer")

        box = layout.box()
        box.label(text=_tr("Animation"), icon="TIME")
        col = box.column(align=True)
        if hasattr(mod, "time_offset"):
            col.prop(mod, "time_offset", text=_tr("Offset"))
        if hasattr(mod, "lifetime"):
            col.prop(mod, "lifetime", text=_tr("Frame Stop"))
        if hasattr(mod, "damping_time"):
            col.prop(mod, "damping_time", text=_tr("Damping"))
        if hasattr(mod, "use_cyclic"):
            col.prop(mod, "use_cyclic")

        if _has_any(mod, ("time_offset", "lifetime", "damping_time")):
            start, stop, full_stop = _wave_frame_values(mod)
            info = box.column(align=True)
            info.use_property_split = False
            info.label(text=f"{_tr('Frame Start')}: {start}")
            info.label(text=f"{_tr('Frame End')}: {stop}")
            info.label(text=f"{_tr('Full stop frame')}: {full_stop}")

        row = box.row(align=True)
        row.use_property_split = False
        row.use_property_decorate = False
        op = row.operator("m8.wave_quick_set", text=_tr("Frame Zero"), icon="KEYINGSET")
        op.action = "FRAME_ZERO"
        op.modifier_name = mod.name
        op = row.operator("m8.wave_quick_set", text=_tr("Frame Stop"), icon="KEYINGSET")
        op.action = "FRAME_STOP"
        op.modifier_name = mod.name
        op = row.operator("m8.wave_quick_set", text=_tr("Full stop frame"), icon="KEYINGSET")
        op.action = "FULL_STOP"
        op.modifier_name = mod.name

        op = box.operator("m8.wave_set_loop_animation", text=_tr("Set loop animation"), icon="FILE_REFRESH")
        op.modifier_name = mod.name
