import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
import time
import math
import os

from ...utils.i18n import _T

def _get_prefs():
    root_pkg = ".".join(__package__.split(".")[:3]) if (__package__ or "").startswith("bl_ext") else (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

class M8_OT_InternalScreencast(bpy.types.Operator):
    bl_idname = "m8.internal_screencast"
    bl_label = "Screencast Keys"
    bl_description = _T("屏幕投射按键与鼠标显示 (nutti/Screencast-Keys 复刻版)")

    _handle = None
    _timer = None
    _events = []
    _running = False
    _shader = None
    _img_shader = None
    _texture_cache = {}
    _font_id_cache = {}
    _ripples = []
    _mouse_button_is_down = {}
    _mouse_button_press_time = {}
    _last_operator_name = ""

    @staticmethod
    def _get_font_id(filepath):
        if not filepath or not os.path.isfile(filepath):
            return 0
        cache = M8_OT_InternalScreencast._font_id_cache
        try:
            mtime = os.path.getmtime(filepath)
            if filepath in cache:
                font_id, cached_mtime = cache[filepath]
                if cached_mtime == mtime:
                    return font_id
            font_id = blf.load(filepath)
            cache[filepath] = (font_id, mtime)
            return font_id
        except Exception:
            return 0

    @staticmethod
    def _get_shader():
        if M8_OT_InternalScreencast._shader:
            return M8_OT_InternalScreencast._shader
        try:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        except Exception:
            try:
                shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
            except Exception:
                try:
                    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
                except Exception:
                    return None
        M8_OT_InternalScreencast._shader = shader
        return shader

    @staticmethod
    def _get_image_shader():
        if M8_OT_InternalScreencast._img_shader:
            return M8_OT_InternalScreencast._img_shader
        try:
            shader = gpu.shader.from_builtin('IMAGE')
        except Exception:
            try:
                shader = gpu.shader.from_builtin('2D_IMAGE')
            except Exception:
                shader = None
        M8_OT_InternalScreencast._img_shader = shader
        return shader

    @staticmethod
    def _get_texture(filepath):
        if not filepath or not os.path.isfile(filepath):
            return None
        cache = M8_OT_InternalScreencast._texture_cache
        try:
            mtime = os.path.getmtime(filepath)
            if filepath in cache:
                cached_data = cache[filepath]
                if len(cached_data) == 4 and cached_data[3] == mtime:
                    return cached_data[0], cached_data[1], cached_data[2]
            img = bpy.data.images.load(filepath, check_existing=True)
            tw, th = img.size[0], img.size[1]
            tex = gpu.texture.from_image(img)
            cache[filepath] = (tex, tw, th, mtime)
            return tex, tw, th
        except Exception:
            return None

    @classmethod
    def poll(cls, context):
        return True

    @classmethod
    def stop_running(cls):
        if not cls._running:
            return
        cls._running = False
        if cls._handle:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(cls._handle, 'WINDOW')
            except Exception:
                pass
            cls._handle = None
        if cls._timer:
            for win in bpy.context.window_manager.windows:
                try:
                    bpy.context.window_manager.event_timer_remove(cls._timer)
                    break
                except Exception:
                    pass
            cls._timer = None

    def remove_handlers(self, context):
        if self.__class__._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self.__class__._handle, 'WINDOW')
            self.__class__._handle = None
        if self.__class__._timer:
            try:
                context.window_manager.event_timer_remove(self.__class__._timer)
            except Exception:
                pass
            self.__class__._timer = None

    def invoke(self, context, event):
        prefs = _get_prefs()
        if self.__class__._running:
            self.__class__._running = False
            if prefs and prefs.screencast_enabled:
                prefs.screencast_enabled = False
            self.report({'INFO'}, _T("按键显示已停止"))
            if context.area:
                context.area.tag_redraw()
            return {'FINISHED'}

        self.__class__._running = True
        if prefs and not prefs.screencast_enabled:
            prefs.screencast_enabled = True

        self.__class__._events = []
        self.__class__._mouse_button_is_down = {}
        self.__class__._mouse_button_press_time = {}

        args = (self, context)
        self.__class__._handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
        self.__class__._timer = context.window_manager.event_timer_add(0.03, window=context.window)

        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, _T("按键显示已开启"))
        return {'RUNNING_MODAL'}

    @staticmethod
    def _format_operator_label(op, lang_mode):
        if not op: return ""
        raw_label = getattr(op, "bl_label", "") or getattr(getattr(op, "bl_rna", None), "name", "")
        if not raw_label:
            idname = getattr(op, "bl_idname", "")
            if "_OT_" in idname:
                raw_label = idname.split("_OT_", 1)[1].replace("_", " ").title()
            elif "." in idname:
                raw_label = idname.split(".", 1)[1].replace("_", " ").title()
            else:
                raw_label = idname.replace("_", " ").title()

        if not raw_label: return ""

        translation_map = {
            "Edit Mode": "编辑模式",
            "Object Mode": "物体模式",
            "Pose Mode": "姿态模式",
            "Sculpt Mode": "雕刻模式",
            "Vertex Paint": "顶点绘制",
            "Weight Paint": "权重绘制",
            "Texture Paint": "纹理绘制",
            "Set Object Mode": "切换模式",
            "Call Menu": "调用菜单",
            "Call Pie Menu": "饼菜单",
            "Select": "选择",
            "Select All": "全选",
            "Delete": "删除",
            "Duplicate": "复制",
            "Extrude": "挤出",
            "Bevel": "倒角",
            "Loop Cut and Slide": "环切并滑动",
            "Subdivide": "细分",
            "Move": "移动",
            "Rotate": "旋转",
            "Resize": "缩放",
            "Scale": "缩放",
            "Undo": "撤销",
            "Redo": "重做",
            "Save File": "保存文件",
            "Save As": "另存为",
            # Modeling fallbacks
            "Inset Faces": "内插面",
            "Inset": "内插",
            "Extrude Region": "挤出区域",
            "Extrude Individual": "挤出各个面",
            "Extrude Along Normals": "沿着法线挤出",
            "Loop Subdivide": "环切细分",
            "Bevel Edges": "边角贝塞尔/倒角边",
            "Bevel Vertices": "顶点倒角",
            "Knife Topology Tool": "切刀",
            "Spin": "旋绕",
            "Smooth": "平滑",
            "Edge Slide": "边滑动",
            "Vertex Slide": "顶点滑动",
            "Shrink/Fatten": "法向缩放/收缩/膨胀",
            "Push/Pull": "推/拉",
        }

        cn_text = translation_map.get(raw_label, "")
        if not cn_text:
            for ctx in ("Operator", "UI", "*", None):
                try:
                    translated = bpy.app.translations.pgettext(raw_label, ctx) if ctx else bpy.app.translations.pgettext(raw_label)
                    if translated and translated != raw_label:
                        cn_text = translated
                        break
                except Exception:
                    pass
            
            if not cn_text:
                for ctx in ("Operator", "UI", "*", None):
                    try:
                        translated = bpy.app.translations.pgettext_iface(raw_label, ctx) if ctx else bpy.app.translations.pgettext_iface(raw_label)
                        if translated and translated != raw_label:
                            cn_text = translated
                            break
                    except Exception:
                        pass

        if lang_mode == "ZH":
            return cn_text if cn_text else raw_label
        elif lang_mode == "EN":
            return raw_label
        else:
            if cn_text and cn_text != raw_label:
                return f"{cn_text} / {raw_label}"
            return raw_label

    @classmethod
    def get_active_mouse_buttons(cls, now):
        active = set()
        for btn in ('LEFT', 'RIGHT', 'MIDDLE', 'M4', 'M5'):
            is_down = cls._mouse_button_is_down.get(btn, False)
            t_press = cls._mouse_button_press_time.get(btn, 0)
            elapsed = now - t_press
            if is_down or (elapsed < 0.15):
                active.add(btn)
        return active

    def modal(self, context, event):
        if not self.__class__._running:
            self.remove_handlers(context)
            return {'FINISHED'}

        prefs = _get_prefs()
        if not prefs:
            return {'PASS_THROUGH'}

        mouse_mode = getattr(prefs, "screencast_mouse_display", "ICON")
        now = time.time()

        mb_map = {
            'LEFTMOUSE': 'LEFT',
            'RIGHTMOUSE': 'RIGHT',
            'MIDDLEMOUSE': 'MIDDLE',
            'BUTTON4MOUSE': 'M4',
            'BUTTON5MOUSE': 'M5'
        }

        if event.type in mb_map:
            btn = mb_map[event.type]
            if event.value == 'PRESS':
                self.__class__._mouse_button_is_down[btn] = True
                self.__class__._mouse_button_press_time[btn] = now
                for other_btn in ('LEFT', 'RIGHT', 'MIDDLE'):
                    if other_btn != btn:
                        self.__class__._mouse_button_is_down[other_btn] = False
                if getattr(prefs, "screencast_show_ripples", True):
                    self.__class__._ripples.append({
                        "pos": (event.mouse_region_x, event.mouse_region_y),
                        "time": now,
                        "type": btn
                    })
            elif event.value == 'RELEASE':
                self.__class__._mouse_button_is_down[btn] = False
            elif event.value in {'CLICK', 'DOUBLE_CLICK'}:
                self.__class__._mouse_button_press_time[btn] = now
                if getattr(prefs, "screencast_show_ripples", True):
                    if not self.__class__._ripples or (now - self.__class__._ripples[-1]["time"] > 0.05):
                        self.__class__._ripples.append({
                            "pos": (event.mouse_region_x, event.mouse_region_y),
                            "time": now,
                            "type": btn
                        })
        elif event.type == 'MOUSEMOVE':
            for btn in ('LEFT', 'RIGHT', 'MIDDLE'):
                self.__class__._mouse_button_is_down[btn] = False
        if mouse_mode in {'ICON', 'BOTH'} and context.area:
            context.area.tag_redraw()

        # Update last operator
        if prefs.screencast_show_last_operator:
            try:
                ops = context.window_manager.operators
                if len(ops) > 0:
                    op = ops[-1]
                    if getattr(op, "bl_idname", "") and op.bl_idname != "m8.internal_screencast":
                        lang_mode = getattr(prefs, "screencast_operator_label_mode", "ZH")
                        label = M8_OT_InternalScreencast._format_operator_label(op, lang_mode)
                        if label:
                            self.__class__._last_operator_name = label
            except Exception:
                pass

        if event.value in {'PRESS', 'CLICK', 'DOUBLE_CLICK'}:
            if event.type in {'NONE', 'UNKNOWN', 'TIMER', 'INBETWEEN_MOUSEMOVE', 'WINDOW_DEACTIVATE', 'XR_SESSION_UPDATE', 'MOUSEMOVE'}:
                return {'PASS_THROUGH'}

            is_mouse = event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'BUTTON4MOUSE', 'BUTTON5MOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}

            if is_mouse:
                if mouse_mode in {'NONE', 'ICON'}:
                    return {'PASS_THROUGH'}

            mods = []
            if event.ctrl: mods.append("Ctrl\u200b")
            if event.shift: mods.append("Shift\u200b")
            if event.alt: mods.append("Alt\u200b")
            if event.oskey: mods.append("Cmd\u200b")

            key_text = ""
            if is_mouse:
                mouse_map_text = {
                    'LEFTMOUSE': 'Left Click',
                    'RIGHTMOUSE': 'Right Click',
                    'MIDDLEMOUSE': 'Middle Click',
                    'WHEELUPMOUSE': 'Wheel Up',
                    'WHEELDOWNMOUSE': 'Wheel Down',
                    'BUTTON4MOUSE': 'Mouse 4',
                    'BUTTON5MOUSE': 'Mouse 5',
                }
                key_text = mouse_map_text.get(event.type, event.type)
            else:
                raw = event.type
                if raw in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_ALT', 'RIGHT_ALT', 'OSKEY'}:
                    return {'PASS_THROUGH'}

                special = {
                    'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4', 'FIVE': '5',
                    'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9', 'ZERO': '0',
                    'MINUS': '-', 'PLUS': '+', 'EQUAL': '=', 'SLASH': '/', 'ASTERIX': '*',
                    'LEFT_BRACKET': '[', 'RIGHT_BRACKET': ']', 'COMMA': ',', 'PERIOD': '.',
                    'SEMI_COLON': ';', 'QUOTE': "'", 'BACK_SLASH': '\\', 'ACCENT_GRAVE': '`',
                    'RET': 'Enter', 'SPACE': 'Space', 'ESC': 'Esc', 'TAB': 'Tab',
                    'BACK_SPACE': 'Backspace', 'DEL': 'Delete',
                    'LEFT_ARROW': 'Left', 'RIGHT_ARROW': 'Right', 'UP_ARROW': 'Up', 'DOWN_ARROW': 'Down',
                }
                if raw in special:
                    key_text = special[raw]
                elif raw.startswith('NUMPAD_'):
                    parts = raw.split('_')
                    key_text = f"Num {parts[1].capitalize() if len(parts) > 1 else raw}"
                else:
                    key_text = raw.replace('_', ' ').title()

            key_text += "\u200b"
            full_text = " + ".join(mods + [key_text]) if mods else key_text

            if self.__class__._events:
                last = self.__class__._events[-1]
                if last["text"] == full_text and (now - last["time"] < 1.5):
                    last["count"] += 1
                    last["time"] = now
                    if context.area: context.area.tag_redraw()
                    return {'PASS_THROUGH'}

            self.__class__._events.append({
                "text": full_text,
                "time": now,
                "count": 1,
            })

            limit = prefs.screencast_history_count
            if len(self.__class__._events) > limit:
                self.__class__._events.pop(0)

            if context.area:
                context.area.tag_redraw()

        if event.type == 'TIMER':
            self.__class__._ripples = [r for r in self.__class__._ripples if now - r["time"] < 0.35]
            
            # Auto-release stuck keys if they have been down for more than 0.5s without real release event
            for btn in ('LEFT', 'RIGHT', 'MIDDLE'):
                if self.__class__._mouse_button_is_down.get(btn, False):
                    t_press = self.__class__._mouse_button_press_time.get(btn, 0)
                    if now - t_press > 0.5:
                        self.__class__._mouse_button_is_down[btn] = False
            
            timeout = prefs.screencast_timeout
            new_evs = [e for e in self.__class__._events if now - e["time"] < timeout]
            if (len(new_evs) != len(self.__class__._events)) or self.__class__._ripples:
                self.__class__._events = new_evs
                if context.area: context.area.tag_redraw()

        return {'PASS_THROUGH'}

    @staticmethod
    def draw_rounded_rect(x, y, w, h, r, color):
        shader = M8_OT_InternalScreencast._get_shader()
        if not shader: return
        r = max(0.0, min(float(r), float(min(w, h)) * 0.5))
        pts = []
        seg = 8
        def arc(cx, cy, a0, a1):
            for i in range(seg + 1):
                t = i / seg
                a = a0 + (a1 - a0) * t
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        arc(x + w - r, y + r, -math.pi / 2, 0.0)
        arc(x + w - r, y + h - r, 0.0, math.pi / 2)
        arc(x + r, y + h - r, math.pi / 2, math.pi)
        arc(x + r, y + r, math.pi, math.pi * 3 / 2)

        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": [(x + w / 2, y + h / 2)] + pts + [pts[0]]})
        shader.bind()
        shader.uniform_float("color", color)
        gpu.state.blend_set('ALPHA')
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_ripples(ripples, color):
        if not ripples: return
        shader = M8_OT_InternalScreencast._get_shader()
        if not shader: return
        
        now = time.time()
        gpu.state.blend_set('ALPHA')
        
        for r in ripples:
            elapsed = now - r["time"]
            if elapsed >= 0.35: continue
            t = elapsed / 0.35
            
            # Ease-out cubic animation for natural ripple deceleration
            t_ease = 1.0 - (1.0 - t) ** 3
            radius = 4.0 + 36.0 * t_ease
            alpha = max(0.0, 1.0 - t)
            
            pts = []
            cx, cy = r["pos"]
            seg = 16
            for i in range(seg):
                a = (i / seg) * math.pi * 2
                pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
            
            # Smart color differentiation based on click type
            btn_type = r.get("type", "LEFT")
            if btn_type == "RIGHT":
                btn_color = (1.0, 0.3, 0.3, color[3])
            elif btn_type == "MIDDLE":
                btn_color = (0.2, 0.9, 0.3, color[3])
            else:
                btn_color = color
                
            r_col = (btn_color[0], btn_color[1], btn_color[2], btn_color[3] * alpha)
            batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": pts})
            shader.bind()
            shader.uniform_float("color", r_col)
            batch.draw(shader)
            
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_sleek_vector_mouse(x, y, size, held_buttons, color):
        """Draw ultra-sleek, master-class vector mouse figure."""
        shader = M8_OT_InternalScreencast._get_shader()
        if not shader: return

        w = size * 0.85
        h = size * 1.35
        cx = x + w / 2
        cy = y + h / 2

        base_alpha = color[3] if len(color) > 3 else 1.0
        r = w * 0.44
        seg = 8

        # 1. Dark Solid Body Background Fill
        pts_body = []
        def arc(acx, acy, ar, a0, a1):
            for i in range(seg + 1):
                t = i / seg
                a = a0 + (a1 - a0) * t
                pts_body.append((acx + math.cos(a) * ar, acy + math.sin(a) * ar))

        arc(x + w - r, y + r, r, -math.pi / 2, 0.0)
        arc(x + w - r, y + h - r, r, 0.0, math.pi / 2)
        arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        arc(x + r, y + r, r, math.pi, math.pi * 3 / 2)

        body_bg_col = (0.08, 0.08, 0.08, 0.85 * base_alpha)
        batch_bg = batch_for_shader(shader, 'TRI_FAN', {"pos": [(cx, cy)] + pts_body + [pts_body[0]]})
        shader.bind()
        shader.uniform_float("color", body_bg_col)
        gpu.state.blend_set('ALPHA')
        batch_bg.draw(shader)

        # 2. Smooth Outer Border Line
        col_stroke = [color[0], color[1], color[2], 0.9 * base_alpha]
        batch_stroke = batch_for_shader(shader, 'LINE_LOOP', {"pos": pts_body})
        shader.uniform_float("color", col_stroke)
        batch_stroke.draw(shader)

        split_y = y + h * 0.54
        batch_h = batch_for_shader(shader, 'LINES', {"pos": ((x + 1.5, split_y), (x + w - 1.5, split_y))})
        batch_h.draw(shader)

        batch_v = batch_for_shader(shader, 'LINES', {"pos": ((cx, split_y), (cx, y + h - 1.5))})
        batch_v.draw(shader)

        # 3. Active Button Glow Fills
        fill_col = list(color)
        fill_col[3] = min(1.0, base_alpha * 0.95)

        # Left Button Fill
        if 'LEFT' in held_buttons:
            pts_left = [(cx - 1, split_y + 1)]
            for i in range(seg + 1):
                t = i / seg
                a = (math.pi / 2) + (math.pi / 2) * t
                pts_left.append((x + r + math.cos(a) * (r - 1.5), (y + h - r) + math.sin(a) * (r - 1.5)))
            pts_left.append((x + 1.5, split_y + 1))
            
            batch_l = batch_for_shader(shader, 'TRI_FAN', {"pos": [(x + w*0.25, split_y + (h*0.45)/2)] + pts_left + [pts_left[0]]})
            shader.uniform_float("color", fill_col)
            batch_l.draw(shader)

        # Right Button Fill
        if 'RIGHT' in held_buttons:
            pts_right = [(cx + 1, split_y + 1)]
            for i in range(seg + 1):
                t = i / seg
                a = (math.pi / 2) * (1 - t)
                pts_right.append(((x + w - r) + math.cos(a) * (r - 1.5), (y + h - r) + math.sin(a) * (r - 1.5)))
            pts_right.append((x + w - 1.5, split_y + 1))

            batch_r = batch_for_shader(shader, 'TRI_FAN', {"pos": [(x + w*0.75, split_y + (h*0.45)/2)] + pts_right + [pts_right[0]]})
            shader.uniform_float("color", fill_col)
            batch_r.draw(shader)

        # 4. Scroll Wheel
        wheel_w = w * 0.22
        wheel_h = h * 0.26
        wx = cx - wheel_w / 2
        wy = split_y + 3

        if 'MIDDLE' in held_buttons:
            M8_OT_InternalScreencast.draw_rounded_rect(wx, wy, wheel_w, wheel_h, wheel_w*0.45, fill_col)
        else:
            rw = wheel_w * 0.4
            wheel_pts = []
            def arc_w(acx, acy, a0, a1):
                for i in range(4):
                    t = i / 3
                    a = a0 + (a1 - a0) * t
                    wheel_pts.append((acx + math.cos(a) * rw, acy + math.sin(a) * rw))
            arc_w(wx + wheel_w - rw, wy + rw, -math.pi / 2, 0.0)
            arc_w(wx + wheel_w - rw, wy + wheel_h - rw, 0.0, math.pi / 2)
            arc_w(wx + rw, wy + wheel_h - rw, math.pi / 2, math.pi)
            arc_w(wx + rw, wy + rw, math.pi, math.pi * 3 / 2)

            batch_wm = batch_for_shader(shader, 'LINE_LOOP', {"pos": wheel_pts})
            shader.uniform_float("color", col_stroke)
            batch_wm.draw(shader)

        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_callback_px(self, context):
        try:
            if not M8_OT_InternalScreencast._running:
                return
            prefs = _get_prefs()
            if not prefs:
                return

            now = time.time()
            
            # Prune ripples
            M8_OT_InternalScreencast._ripples = [r for r in M8_OT_InternalScreencast._ripples if now - r["time"] < 0.35]

            # Draw click ripples (Step 4)
            if getattr(prefs, "screencast_show_ripples", True):
                ripple_color = list(getattr(prefs, "screencast_ripple_color", (0.0, 0.6, 1.0, 0.8)))
                M8_OT_InternalScreencast.draw_ripples(M8_OT_InternalScreencast._ripples, ripple_color)

            active_buttons = M8_OT_InternalScreencast.get_active_mouse_buttons(now)

            # Load font dynamically (Step 2)
            font_path = getattr(prefs, "screencast_font_filepath", "")
            font_id = M8_OT_InternalScreencast._get_font_id(font_path)
            font_size = prefs.screencast_font_size
            blf.size(font_id, font_size)

            region = context.region
            width = region.width
            height = region.height

            margin_x = prefs.screencast_offset_x
            margin_y = prefs.screencast_offset_y
            align = prefs.screencast_align
            stack_direction = prefs.screencast_stack_direction

            events = M8_OT_InternalScreencast._events
            last_op = M8_OT_InternalScreencast._last_operator_name if prefs.screencast_show_last_operator else ""

            fg_color = list(prefs.screencast_color)
            bg_color = list(prefs.screencast_bg_color)
            shadow_color = list(getattr(prefs, "screencast_shadow_color", (0, 0, 0, 0.7)))

            display_lines = []
            if last_op:
                display_lines.append(f"[ {last_op} ]")
            
            for e in events:
                txt = e["text"]
                if e["count"] > 1:
                    txt += f" x{e['count']}"
                display_lines.append(txt)

            mouse_mode = getattr(prefs, "screencast_mouse_display", "ICON")
            show_mouse = mouse_mode in {'ICON', 'BOTH'}
            mouse_size = getattr(prefs, "screencast_mouse_size", 30)

            mouse_w = 0
            mouse_h = 0
            is_custom_tex = False
            target_tex_path = ""
            tex_obj = None

            if show_mouse:
                if getattr(prefs, "screencast_use_custom_mouse", False):
                    target_tex_path = prefs.screencast_mouse_img_base
                    if 'LEFT' in active_buttons and prefs.screencast_mouse_img_lmouse:
                        target_tex_path = prefs.screencast_mouse_img_lmouse
                    elif 'RIGHT' in active_buttons and prefs.screencast_mouse_img_rmouse:
                        target_tex_path = prefs.screencast_mouse_img_rmouse
                    elif 'MIDDLE' in active_buttons and prefs.screencast_mouse_img_mmouse:
                        target_tex_path = prefs.screencast_mouse_img_mmouse
                    
                    if target_tex_path:
                        tex_data = M8_OT_InternalScreencast._get_texture(target_tex_path)
                        if tex_data:
                            tex_obj, tw, th = tex_data
                            if th > 0:
                                mouse_h = mouse_size * 1.35
                                mouse_w = mouse_h * (tw / th)
                                is_custom_tex = True
                
                if not is_custom_tex:
                    mouse_h = mouse_size * 1.35
                    mouse_w = mouse_size * 0.85

            layout_mode = getattr(prefs, "screencast_layout_mode", "SIDE")

            box_padding = getattr(prefs, "screencast_box_padding", 10)
            box_radius = getattr(prefs, "screencast_box_radius", 20)
            show_box = getattr(prefs, "screencast_show_box", True)
            show_shadow = getattr(prefs, "screencast_show_shadow", True)

            line_height = font_size + 8

            max_txt_w = 0
            for line in display_lines:
                w = blf.dimensions(font_id, line)[0]
                if w > max_txt_w: max_txt_w = w

            if layout_mode == "SIDE":
                total_content_w = max_txt_w + (mouse_w + 14 if show_mouse and display_lines else (mouse_w if show_mouse else 0))
                total_content_h = max(len(display_lines) * line_height, mouse_h) if display_lines else mouse_h
            else:
                total_content_w = max(max_txt_w, mouse_w)
                if show_mouse and display_lines:
                    total_content_h = len(display_lines) * line_height + 10 + mouse_h
                else:
                    total_content_h = len(display_lines) * line_height if display_lines else mouse_h

            if total_content_w <= 0 and not show_mouse:
                return

            if align == 'LEFT':
                base_x = margin_x
            elif align == 'RIGHT':
                base_x = width - margin_x - total_content_w - box_padding * 2
            else:
                base_x = (width - total_content_w) / 2

            if stack_direction == "DOWN":
                base_y = height - margin_y - total_content_h - box_padding * 2
            else:
                base_y = margin_y

            # Draw Background Box (Image or Rounded Rect)
            if show_box and (display_lines or show_mouse):
                box_x = base_x - box_padding
                box_y = base_y - box_padding
                box_w = total_content_w + box_padding * 2
                box_h = total_content_h + box_padding * 2

                drawn_bg_img = False
                bg_img_path = getattr(prefs, "screencast_bg_image", "")
                bg_alpha = getattr(prefs, "screencast_bg_image_alpha", 1.0)
                if bg_img_path:
                    img_shader = M8_OT_InternalScreencast._get_image_shader()
                    tex_data = M8_OT_InternalScreencast._get_texture(bg_img_path)
                    if img_shader and tex_data:
                        tex = tex_data[0]
                        batch = batch_for_shader(img_shader, 'TRI_FAN', {
                            "pos": ((box_x, box_y), (box_x + box_w, box_y), (box_x + box_w, box_y + box_h), (box_x, box_y + box_h)),
                            "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1))
                        })
                        img_shader.bind()
                        img_shader.uniform_sampler("image", tex)
                        try:
                            img_shader.uniform_float("color", (1.0, 1.0, 1.0, bg_alpha))
                        except Exception:
                            pass
                        gpu.state.blend_set('ALPHA')
                        batch.draw(img_shader)
                        gpu.state.blend_set('NONE')
                        drawn_bg_img = True

                if not drawn_bg_img:
                    M8_OT_InternalScreencast.draw_rounded_rect(box_x, box_y, box_w, box_h, box_radius, bg_color)

            # Draw Mouse (Custom Texture or Sleek Vector)
            if show_mouse:
                if layout_mode == "SIDE":
                    mx = base_x
                    my = base_y + (total_content_h - mouse_h) / 2
                else: # ABOVE or BELOW
                    if align == 'LEFT':
                        mx = base_x
                    elif align == 'RIGHT':
                        mx = base_x + total_content_w - mouse_w
                    else: # CENTER
                        mx = base_x + (total_content_w - mouse_w) / 2

                if layout_mode == "SIDE":
                    pass # already set
                elif layout_mode == "ABOVE":
                    my = base_y
                else: # BELOW
                    my = base_y + total_content_h - mouse_h
                
                drawn_custom = False
                if is_custom_tex and tex_obj:
                    img_shader = M8_OT_InternalScreencast._get_image_shader()
                    if img_shader:
                        batch = batch_for_shader(img_shader, 'TRI_FAN', {
                            "pos": ((mx, my), (mx + mouse_w, my), (mx + mouse_w, my + mouse_h), (mx, my + mouse_h)),
                            "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1))
                        })
                        img_shader.bind()
                        img_shader.uniform_sampler("image", tex_obj)
                        try:
                            img_shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
                        except Exception:
                            pass
                        gpu.state.blend_set('ALPHA')
                        batch.draw(img_shader)
                        gpu.state.blend_set('NONE')
                        drawn_custom = True

                if not drawn_custom:
                    M8_OT_InternalScreencast.draw_sleek_vector_mouse(mx, my, mouse_size, active_buttons, fg_color)

            # Draw Text Lines
            if display_lines:
                if layout_mode == "SIDE":
                    text_x = base_x + (mouse_w + 14 if show_mouse else 0)
                    if stack_direction == "DOWN":
                        curr_y = base_y + total_content_h - font_size
                        step = -line_height
                    else:
                        curr_y = base_y + 4
                        step = line_height
                else: # ABOVE or BELOW
                    if align == 'LEFT':
                        text_x = base_x
                    elif align == 'RIGHT':
                        text_x = base_x + total_content_w - max_txt_w
                    else: # CENTER
                        text_x = base_x + (total_content_w - max_txt_w) / 2

                if layout_mode == "ABOVE":
                    if stack_direction == "DOWN":
                        curr_y = base_y + total_content_h - font_size
                        step = -line_height
                    else:
                        curr_y = base_y + (mouse_h + 10 if show_mouse else 4)
                        step = line_height
                elif layout_mode == "BELOW":
                    if stack_direction == "DOWN":
                        text_h = len(display_lines) * line_height
                        curr_y = base_y + text_h - font_size
                        step = -line_height
                    else:
                        curr_y = base_y + 4
                        step = line_height

                for line in display_lines:
                    if show_shadow:
                        blf.color(font_id, *shadow_color)
                        blf.position(font_id, text_x + 1.5, curr_y - 1.5, 0)
                        blf.draw(font_id, line)

                    blf.color(font_id, *fg_color)
                    blf.position(font_id, text_x, curr_y, 0)
                    blf.draw(font_id, line)

                    curr_y += step
        except Exception as e:
            import traceback
            print(f"[M8 Screencast Error] {e}")
            traceback.print_exc()
