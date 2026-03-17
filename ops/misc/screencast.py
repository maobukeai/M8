import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
import time
import os
import math

def _get_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

class M8_OT_InternalScreencast(bpy.types.Operator):
    bl_idname = "m8.internal_screencast"
    bl_label = "M8 Screencast"
    bl_description = "Internal full-featured screencast keys"
    
    _handle = None
    _timer = None
    # _events: list of dicts:
    # {
    #   "text": str, 
    #   "timestamp": float, 
    #   "type": "MOUSE" | "KEY" | "OP", 
    #   "mouse_button": "LEFT"|"RIGHT"|"MIDDLE" (optional),
    #   "modifiers": ["Ctrl", "Shift"...]
    # }
    _events = [] 
    _running = False
    _shader = None
    _active_modifiers = set() # Track held modifiers

    @staticmethod
    def _get_shader():
        if M8_OT_InternalScreencast._shader:
            return M8_OT_InternalScreencast._shader
        try:
            # Blender 4.0+
            shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        except Exception:
            try:
                # Blender < 4.0
                shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            except Exception:
                # 备用方案
                shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        M8_OT_InternalScreencast._shader = shader
        return shader

    @classmethod
    def poll(cls, context):
        return True

    def modal(self, context, event):
        if not self.__class__._running:
            self.remove_handlers(context)
            return {'FINISHED'}

        prefs = _get_prefs()
        if not prefs: return {'PASS_THROUGH'}

        # Update active modifiers (use canonical uppercase to avoid any UI translation)
        current_mods = set()
        if event.ctrl: current_mods.add("CTRL")
        if event.shift: current_mods.add("SHIFT")
        if event.alt: current_mods.add("ALT")
        if event.oskey: current_mods.add("CMD")
        self.__class__._active_modifiers = current_mods

        # Capture Logic
        if event.value in {'PRESS', 'CLICK', 'DOUBLE_CLICK'}:
            
            # 1. Filter junk
            if event.type in {'NONE', 'UNKNOWN', 'TIMER', 'INBETWEEN_MOUSEMOVE', 'WINDOW_DEACTIVATE', 'XR_SESSION_UPDATE'}:
                return {'PASS_THROUGH'}
            
            # Silent Mode: Filter rapid scroll/move if needed
            # (not fully implemented but placeholder logic is here)

            # 2. Identify Type
            is_mouse = event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'BUTTON4MOUSE', 'BUTTON5MOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
            
            if is_mouse and not prefs.screencast_show_mouse:
                return {'PASS_THROUGH'}

            # 3. Construct Event Data
            new_event = {
                "timestamp": time.time(),
                "modifiers": list(current_mods),
                "count": 1
            }

            if is_mouse:
                new_event["type"] = "MOUSE"
                mapping = {
                    'LEFTMOUSE': 'LEFT', 'RIGHTMOUSE': 'RIGHT', 'MIDDLEMOUSE': 'MIDDLE',
                    'BUTTON4MOUSE': 'M4', 'BUTTON5MOUSE': 'M5',
                    'WHEELUPMOUSE': 'WHEEL_UP', 'WHEELDOWNMOUSE': 'WHEEL_DOWN'
                }
                new_event["text"] = mapping.get(event.type, event.type)
                new_event["mouse_button"] = new_event["text"] # For icon drawing
            else:
                new_event["type"] = "KEY"
                raw_type = event.type
                text = raw_type
                
                # --- Comprehensive Key Mapping ---
                # Use canonical key labels (uppercase) or Symbols
                special_keys = {
                    'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4', 'FIVE': '5',
                    'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9', 'ZERO': '0',
                    'MINUS': '-', 'PLUS': '+', 'EQUAL': '=', 'SLASH': '/', 'ASTERIX': '*', 
                    'LEFT_BRACKET': '[', 'RIGHT_BRACKET': ']', 
                    'COMMA': ',', 'PERIOD': '.', 'SEMI_COLON': ';', 'QUOTE': "'", 'BACK_SLASH': '\\',
                    'ACCENT_GRAVE': '`',
                    'TAB': 'TAB', 'RET': 'ENTER', 'SPACE': 'SPACE', 'ESC': 'ESC',
                    'BACK_SPACE': 'BACK', 'DEL': 'DEL', 'INSERT': 'INS', 'HOME': 'HOME', 'END': 'END',
                    'PAGE_UP': 'PGUP', 'PAGE_DOWN': 'PGDN',
                    'LEFT_ARROW': 'LEFT', 'RIGHT_ARROW': 'RIGHT', 'UP_ARROW': 'UP', 'DOWN_ARROW': 'DOWN',
                    'NUMPAD_1': 'Num 1', 'NUMPAD_2': 'Num 2', 'NUMPAD_3': 'Num 3',
                    'NUMPAD_4': 'Num 4', 'NUMPAD_5': 'Num 5', 'NUMPAD_6': 'Num 6',
                    'NUMPAD_7': 'Num 7', 'NUMPAD_8': 'Num 8', 'NUMPAD_9': 'Num 9',
                    'NUMPAD_0': 'Num 0', 'NUMPAD_PERIOD': 'Num .', 'NUMPAD_ENTER': 'Num Enter',
                    'NUMPAD_PLUS': 'Num +', 'NUMPAD_MINUS': 'Num -', 'NUMPAD_ASTERIX': 'Num *', 'NUMPAD_SLASH': 'Num /',
                    'PAUSE': 'PAUSE', 'CAPS_LOCK': 'CAPS', 'SCROLL_LOCK': 'SCROLL', 'NUM_LOCK': 'NUMLOCK',
                    'PRINTSCREEN': 'PRTSC',
                    'MEDIA_PLAY': 'Media Play', 'MEDIA_STOP': 'Media Stop', 'MEDIA_FIRST': 'Media First', 'MEDIA_LAST': 'Media Last',
                }
                
                # Modifier keys (show by themselves when tapped)
                modifier_key_map = {
                    "LEFT_CTRL": "CTRL", "RIGHT_CTRL": "CTRL", "CTRL": "CTRL",
                    "LEFT_SHIFT": "SHIFT", "RIGHT_SHIFT": "SHIFT", "SHIFT": "SHIFT",
                    "LEFT_ALT": "ALT", "RIGHT_ALT": "ALT", "ALT": "ALT",
                    "OSKEY": "CMD",
                }

                # F-Keys (F1-F24)
                if raw_type.startswith('F') and raw_type[1:].isdigit():
                    text = raw_type
                
                # Check mapping
                if raw_type in special_keys:
                    text = special_keys[raw_type]
                elif len(raw_type) == 1 and raw_type.isalpha():
                    text = raw_type # Keep uppercase for single letters
                elif raw_type in modifier_key_map:
                    text = modifier_key_map[raw_type]
                    # Logic: if this is a modifier press, don't show modifiers list (avoid "CTRL + CTRL")
                    new_event["modifiers"] = [] 
                else:
                    text = raw_type
                
                new_event["text"] = text

            # 4. Merge Logic (Double click / Repetition / Retroactive Cleanup)
            if self.__class__._events:
                last = self.__class__._events[-1]
                
                # Check match for increment
                mods_match = set(last["modifiers"]) == set(new_event["modifiers"])
                text_match = last["text"] == new_event["text"]
                
                if mods_match and text_match:
                    last["count"] += 1
                    last["timestamp"] = new_event["timestamp"] # Update time to keep it alive
                    context.area.tag_redraw()
                    return {'PASS_THROUGH'}
                
                # Retroactive Modifier Cleanup
                # If last event was a pure modifier (e.g. "CTRL") and new event is a combo that INCLUDES that modifier (e.g. "CTRL + C")
                # and happens quickly, we remove the standalone modifier display to keep it clean.
                # Only apply if last event count is 1 (user didn't tap Ctrl multiple times intentionally)
                if last.get("count", 1) == 1 and last["type"] == "KEY":
                    # Check if last text is a modifier
                    last_mod_name = last["text"] # e.g. "CTRL"
                    # Check if this modifier is in new_event's modifiers list
                    # new_event modifiers are "CTRL", "SHIFT" etc (canonical)
                    if last_mod_name in new_event["modifiers"]:
                        # Also check timing? If too slow, maybe user wanted to show "CTRL"... then "C".
                        # Let's say < 0.8s is "combo setup".
                        if (new_event["timestamp"] - last["timestamp"]) < 0.8:
                            self.__class__._events.pop()

            self.__class__._events.append(new_event)
            
            # Limit history
            limit = prefs.screencast_history_count
            if len(self.__class__._events) > limit:
                self.__class__._events.pop(0)
                
            context.area.tag_redraw()
            
        # Capture Last Operator
        if prefs.screencast_show_last_operator:
             # This is tricky in modal. We can check window_manager.operators[-1]
             # But it updates asynchronously.
             # We can check in draw callback or timer.
             pass

        if event.type == 'TIMER':
            # Cleanup old events
            timeout = prefs.screencast_timeout
            now = time.time()
            new_events = [e for e in self.__class__._events if now - e["timestamp"] < timeout]
            
            if len(new_events) != len(self.__class__._events):
                self.__class__._events = new_events
                context.area.tag_redraw()

        return {'PASS_THROUGH'}

    @staticmethod
    def _draw_entry_animation(x, y, w, h, age, enabled):
        # Return modified (x, y, w, h, alpha_mult)
        if not enabled or age > 0.2:
            return x, y, w, h, 1.0
        
        # Simple pop-in scale
        t = age / 0.2 # 0.0 to 1.0
        # Ease out back
        # s = 1.0 + 2.70158 * pow(t - 1.0, 3) + 1.70158 * pow(t - 1.0, 2)
        # Simpler: easeOutCubic
        t -= 1.0
        scale = t * t * t + 1.0
        
        cx = x + w/2
        cy = y + h/2
        nw = w * scale
        nh = h * scale
        nx = cx - nw/2
        ny = cy - nh/2
        
        return nx, ny, nw, nh, min(1.0, age * 5.0)

    def remove_handlers(self, context):
        if self.__class__._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self.__class__._handle, 'WINDOW')
            self.__class__._handle = None
        if self.__class__._timer:
            context.window_manager.event_timer_remove(self.__class__._timer)
            self.__class__._timer = None

    def invoke(self, context, event):
        prefs = _get_prefs()
        if self.__class__._running:
            self.__class__._running = False
            # Sync Prefs (Avoid recursive update call if possible, or just set it)
            if prefs and prefs.screencast_enabled:
                prefs.screencast_enabled = False
            self.report({'INFO'}, "Screencast Stopped")
            if context.area: context.area.tag_redraw()
            return {'FINISHED'}

        self.__class__._running = True
        # Sync Prefs
        if prefs and not prefs.screencast_enabled:
            prefs.screencast_enabled = True
            
        self.__class__._events = []
        self.__class__._active_modifiers = set()
        
        args = (self, context)
        self.__class__._handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
        self.__class__._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "Screencast Started")
        return {'RUNNING_MODAL'}

    @staticmethod
    def draw_bg_box(x, y, width, height, color):
        if not M8_OT_InternalScreencast._shader:
            M8_OT_InternalScreencast._get_shader()
        
        batch = batch_for_shader(M8_OT_InternalScreencast._shader, 'TRIS', {
            "pos": ((x, y), (x + width, y), (x, y + height), (x + width, y + height))
        }, indices=((0, 1, 2), (2, 1, 3)))
        
        M8_OT_InternalScreencast._shader.bind()
        M8_OT_InternalScreencast._shader.uniform_float("color", color)
        gpu.state.blend_set('ALPHA')
        batch.draw(M8_OT_InternalScreencast._shader)
        gpu.state.blend_set('NONE')

    @staticmethod
    def _rounded_rect_points(x, y, w, h, r, segments=6):
        r = max(0.0, min(float(r), float(min(w, h)) * 0.5))
        if r <= 0.0:
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        pts = []
        def arc(cx, cy, a0, a1):
            for i in range(segments + 1):
                t = i / segments
                a = a0 + (a1 - a0) * t
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        arc(x + w - r, y + r, -math.pi / 2, 0.0)
        arc(x + w - r, y + h - r, 0.0, math.pi / 2)
        arc(x + r, y + h - r, math.pi / 2, math.pi)
        arc(x + r, y + r, math.pi, math.pi * 3 / 2)
        return pts

    @staticmethod
    def draw_keycap(x, y, w, h, r, bg, outline, shadow=True):
        if not M8_OT_InternalScreencast._shader:
            M8_OT_InternalScreencast._get_shader()
        
        # 1. Main Shadow (Drop Shadow)
        if shadow:
            shadow_col = (0.0, 0.0, 0.0, min(0.35, bg[3] if len(bg) > 3 else 0.35))
            pts_s = M8_OT_InternalScreencast._rounded_rect_points(x + 2, y - 2, w, h, r)
            batch_s = batch_for_shader(M8_OT_InternalScreencast._shader, 'TRI_FAN', {"pos": [(x + w / 2, y + h / 2)] + pts_s})
            M8_OT_InternalScreencast._shader.bind()
            M8_OT_InternalScreencast._shader.uniform_float("color", shadow_col)
            gpu.state.blend_set('ALPHA')
            batch_s.draw(M8_OT_InternalScreencast._shader)
            gpu.state.blend_set('NONE')

        # 2. Keycap Gradient Body
        # We simulate gradient by drawing a slightly lighter top half and darker bottom half over base color
        # Or just use base color and draw highlights/shadows
        pts = M8_OT_InternalScreencast._rounded_rect_points(x, y, w, h, r)
        batch_f = batch_for_shader(M8_OT_InternalScreencast._shader, 'TRI_FAN', {"pos": [(x + w / 2, y + h / 2)] + pts})
        
        M8_OT_InternalScreencast._shader.bind()
        M8_OT_InternalScreencast._shader.uniform_float("color", bg)
        gpu.state.blend_set('ALPHA')
        batch_f.draw(M8_OT_InternalScreencast._shader)
        
        # Simulate Vertical Gradient (Lighter Top)
        # Draw a rect on top half with subtle white fade?
        # Actually standard shader 'SMOOTH_COLOR' allows vertex colors. 
        # But switching shaders is expensive in loop. Let's stick to simple overlays.
        
        # Draw top highlight (Gloss)
        gloss_col = (1, 1, 1, 0.08 * bg[3]) # Very subtle white
        pts_g = M8_OT_InternalScreencast._rounded_rect_points(x + 2, y + h*0.5, w - 4, h*0.4, r - 2)
        if len(pts_g) > 2:
             batch_g = batch_for_shader(M8_OT_InternalScreencast._shader, 'TRI_FAN', {"pos": [(x + w/2, y + h*0.7)] + pts_g})
             M8_OT_InternalScreencast._shader.uniform_float("color", gloss_col)
             batch_g.draw(M8_OT_InternalScreencast._shader)

        gpu.state.blend_set('NONE')

        # 3. Outline / Stroke
        if outline and outline[3] > 0:
            batch_o = batch_for_shader(M8_OT_InternalScreencast._shader, 'LINE_LOOP', {"pos": pts})
            M8_OT_InternalScreencast._shader.bind()
            M8_OT_InternalScreencast._shader.uniform_float("color", outline)
            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(1.0)
            batch_o.draw(M8_OT_InternalScreencast._shader)
            gpu.state.blend_set('NONE')

    @staticmethod
    def draw_mouse_icon(x, y, size, button, color):
        if not M8_OT_InternalScreencast._shader:
            M8_OT_InternalScreencast._get_shader()
            
        w = size * 0.65
        h = size * 1.0
        
        # Better Mouse Shape (Rounded Top, Flat-ish Bottom)
        # Using rounded rect points for body
        r = w * 0.4
        pts_body = M8_OT_InternalScreencast._rounded_rect_points(x, y, w, h, r)
        
        batch_body = batch_for_shader(M8_OT_InternalScreencast._shader, 'LINE_LOOP', {"pos": pts_body})
        
        # Split line (Button separator)
        split_y = y + h * 0.6
        batch_split_h = batch_for_shader(M8_OT_InternalScreencast._shader, 'LINES', {
            "pos": ((x, split_y), (x+w, split_y))
        })
        batch_split_v = batch_for_shader(M8_OT_InternalScreencast._shader, 'LINES', {
            "pos": ((x+w*0.5, split_y), (x+w*0.5, y+h))
        })
        
        M8_OT_InternalScreencast._shader.bind()
        M8_OT_InternalScreencast._shader.uniform_float("color", color)
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(1.5)
        
        batch_body.draw(M8_OT_InternalScreencast._shader)
        batch_split_h.draw(M8_OT_InternalScreencast._shader)
        batch_split_v.draw(M8_OT_InternalScreencast._shader)
        
        # Fill Active Button
        fill_color = list(color)
        fill_color[3] *= 0.6
        M8_OT_InternalScreencast._shader.uniform_float("color", fill_color)
        
        # We need to construct fill shapes carefully to match rounded top
        # For simplicity, we can use a clipping rect or just draw approximated polys
        # Let's draw simple rects for buttons, they will overlap outline but look okay at small size
        # Or better: use the top part of rounded rect logic
        
        fill_verts = []
        cx = x + w*0.5
        top = y + h
        
        if 'LEFT' in button:
            # Top-Left quadrant
            # It's roughly a rectangle with rounded top-left
            # Let's just fill the rect area, it's small enough
            fill_verts = [(x, split_y), (cx, split_y), (cx, top), (x, top)] 
            # This will bleed out of rounded corners. 
            # Improving: simple triangle fan for top-left
            pass
        elif 'RIGHT' in button:
            fill_verts = [(cx, split_y), (x+w, split_y), (x+w, top), (cx, top)]
        elif 'MIDDLE' in button:
             # Wheel
             wy_start = split_y - h*0.1
             wy_end = split_y + h*0.2
             fill_verts = [(cx-w*0.15, wy_start), (cx+w*0.15, wy_start), (cx+w*0.15, wy_end), (cx-w*0.15, wy_end)]
             
        if fill_verts:
            batch_fill = batch_for_shader(M8_OT_InternalScreencast._shader, 'TRI_FAN', {"pos": fill_verts})
            batch_fill.draw(M8_OT_InternalScreencast._shader)

        # Wheel Scroll Indicators
        if 'WHEEL' in button:
            # Draw arrow up or down above mouse?
            pass

        gpu.state.blend_set('NONE')
        gpu.state.line_width_set(1.0)

    @staticmethod
    def _mods_ordered(mods):
        # Optional: Use symbols if enabled
        prefs = _get_prefs()
        use_symbols = getattr(prefs, "screencast_use_symbols", False)
        
        # Map
        symbol_map = {
            "CTRL": "⌃", 
            "SHIFT": "⇧", 
            "ALT": "⌥", 
            "CMD": "⌘"
        }
        
        order = {"CTRL": 0, "SHIFT": 1, "ALT": 2, "CMD": 3, "⌃": 0, "⇧": 1, "⌥": 2, "⌘": 3}
        
        res = []
        for m in mods:
            m_clean = m.strip().replace("\u200B", "")
            if use_symbols and m_clean in symbol_map:
                res.append(symbol_map[m_clean])
            else:
                res.append(m)
                
        return sorted(res, key=lambda m: order.get(m.strip().replace("\u200B", ""), 99))

    @staticmethod
    def draw_gear_icon(x, y, size, color):
        if not M8_OT_InternalScreencast._shader:
            M8_OT_InternalScreencast._get_shader()
        
        cx, cy = x + size/2, y + size/2
        r_outer = size * 0.45
        r_inner = size * 0.35
        num_teeth = 8
        
        verts = []
        import math
        for i in range(num_teeth * 2):
            angle = (i / (num_teeth * 2)) * math.pi * 2
            r = r_outer if i % 2 == 0 else r_inner
            verts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
            
        batch = batch_for_shader(M8_OT_InternalScreencast._shader, 'TRI_FAN', {"pos": [(cx, cy)] + verts + [verts[0]]})
        M8_OT_InternalScreencast._shader.bind()
        M8_OT_InternalScreencast._shader.uniform_float("color", color)
        gpu.state.blend_set('ALPHA')
        batch.draw(M8_OT_InternalScreencast._shader)
        
        # Draw hole (simple circle)
        hole_verts = []
        r_hole = size * 0.15
        for i in range(12):
            angle = (i / 12) * math.pi * 2
            hole_verts.append((cx + math.cos(angle) * r_hole, cy + math.sin(angle) * r_hole))
            
        batch_hole = batch_for_shader(M8_OT_InternalScreencast._shader, 'TRI_FAN', {"pos": hole_verts})
        # Use a dark color for hole or just blend? 
        # Actually standard shader doesn't support subtraction easily without stencil.
        # We can draw the hole with alpha 0 but that won't punch through.
        # Let's draw it with a semi-transparent dark color to look like a hole.
        hole_col = (0, 0, 0, 0.4 * color[3])
        M8_OT_InternalScreencast._shader.uniform_float("color", hole_col)
        batch_hole.draw(M8_OT_InternalScreencast._shader)
        
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_callback_px(self, context):
        if not M8_OT_InternalScreencast._running: return
        events = M8_OT_InternalScreencast._events

        prefs = _get_prefs()
        if not prefs: return

        font_id = 0
        font_size = prefs.screencast_font_size
        blf.size(font_id, font_size)
        
        region = context.region
        width = region.width
        height = region.height # Need full height for layout
        
        margin_x = prefs.screencast_offset_x
        margin_y = prefs.screencast_offset_y
        align = prefs.screencast_align
        stack_direction = getattr(prefs, "screencast_stack_direction", "UP")
        entry_anim = getattr(prefs, "screencast_entry_animation", True)
        
        # Calculate Start Y
        if stack_direction == "DOWN":
            # From Top Down
            start_y = height - margin_y - (font_size * 2) # Initial offset
        else:
            # From Bottom Up
            start_y = margin_y
            
        y = start_y
        padding = 8
        line_height = font_size + padding * 2
        
        now = time.time()
        timeout = prefs.screencast_timeout

        style = getattr(prefs, "screencast_style", "KEYCAPS")
        # Enhance keycap style: gradient/bevel simulation
        cap_bg = list(getattr(prefs, "screencast_cap_bg_color", prefs.screencast_bg_color))
        cap_outline = list(getattr(prefs, "screencast_cap_outline_color", (1, 1, 1, 0.15)))
        cap_radius = int(getattr(prefs, "screencast_cap_radius", 8))
        cap_gap = int(getattr(prefs, "screencast_cap_gap", 6))
        cap_shadow = bool(getattr(prefs, "screencast_cap_shadow", True))
        cap_upper = bool(getattr(prefs, "screencast_cap_uppercase", True))

        def draw_keycaps_row(tokens, alpha, y_pos, bg_override=None):
            token_sizes = []
            total_w = 0.0
            h = font_size + padding * 2
            for tok in tokens:
                kind = tok["kind"]
                if kind == "MOUSE":
                    w = font_size * 1.8
                elif kind == "ICON_GEAR":
                    w = font_size * 1.5
                else:
                    label = tok["label"]
                    # If symbols enabled, some labels might be symbols already.
                    # Don't uppercase symbols.
                    if cap_upper and not bool(tok.get("no_upper", False)) and not any(c in label for c in "⌃⇧⌥⌘"):
                        label = label.upper()
                    
                    # Fix label for drawing (strip zero-width spaces if any left, though we prefer normal spaces now)
                    draw_label = label.replace("\u200B", "")
                    tok["draw_label"] = draw_label
                    
                    w = blf.dimensions(font_id, draw_label)[0] + padding * 2
                token_sizes.append((tok, w))
                total_w += w
            total_w += cap_gap * max(0, len(tokens) - 1)
            if align == 'LEFT':
                x = margin_x
            elif align == 'RIGHT':
                x = width - margin_x - total_w
            else:
                x = (width - total_w) / 2
            
            # Draw Loop
            for tok, w in token_sizes:
                # Apply Entry Animation if needed (only for main keys, not operator usually, or handle outside)
                # But here we are inside draw_row.
                # Let's assume animation applies to the whole row's alpha, or per key?
                # Usually per-row age.
                # Here we only have alpha passed in.
                
                # Apply animation transform
                # We need 'age' here. But draw_keycaps_row is generic.
                # Let's just draw static here, caller handles position/alpha.
                
                bgc = list(bg_override if bg_override is not None else cap_bg)
                bgc[3] *= alpha
                ol = list(cap_outline)
                ol[3] *= alpha
                
                # Draw Keycap Body
                M8_OT_InternalScreencast.draw_keycap(x, y_pos, w, h, cap_radius, bgc, ol, shadow=cap_shadow)
                
                # Draw "Bevel" Highlight (top edge)
                if style == "KEYCAPS":
                    # Simple highlight line at top
                    highlight_col = (1, 1, 1, 0.1 * alpha)
                    pts_h = [(x + cap_radius, y_pos + h - 2), (x + w - cap_radius, y_pos + h - 2)]
                    # Use simple line
                    batch_h = batch_for_shader(M8_OT_InternalScreencast._shader, 'LINES', {"pos": pts_h})
                    M8_OT_InternalScreencast._shader.uniform_float("color", highlight_col)
                    batch_h.draw(M8_OT_InternalScreencast._shader)
                    
                    # Bottom shadow/thickness
                    shadow_col = (0, 0, 0, 0.2 * alpha)
                    pts_b = [(x + cap_radius, y_pos + 2), (x + w - cap_radius, y_pos + 2)]
                    batch_b = batch_for_shader(M8_OT_InternalScreencast._shader, 'LINES', {"pos": pts_b})
                    M8_OT_InternalScreencast._shader.uniform_float("color", shadow_col)
                    batch_b.draw(M8_OT_InternalScreencast._shader)

                fg = list(prefs.screencast_color)
                fg[3] *= alpha
                
                if tok["kind"] == "MOUSE":
                    M8_OT_InternalScreencast.draw_mouse_icon(x + (w - font_size) / 2, y_pos + (h - font_size) / 2, font_size, tok["label"], fg)
                elif tok["kind"] == "ICON_GEAR":
                    M8_OT_InternalScreencast.draw_gear_icon(x + (w - font_size) / 2, y_pos + (h - font_size) / 2, font_size, fg)
                else:
                    label = tok.get("draw_label", tok["label"])
                    tw = blf.dimensions(font_id, label)[0]
                    blf.color(font_id, *fg)
                    blf.position(font_id, x + (w - tw) / 2, y_pos + padding + font_size * 0.2, 0)
                    blf.draw(font_id, label)
                x += w + cap_gap
            return h

        def _prettify_operator_label(label, idname):
            label = (label or "").strip()
            if not label:
                idname = (idname or "").strip()
                if "_OT_" in idname:
                    label = idname.split("_OT_", 1)[1].replace("_", " ").title()
                elif "." in idname:
                    label = idname.split(".", 1)[1].replace("_", " ").title()
                else:
                    label = idname.replace("_", " ").title()
            if label.isupper():
                label = label.title()
            def _try_translate(label_text, op_idname):
                idname_map = {
                    "OBJECT_OT_editmode_toggle": "切换编辑模式",
                    "OBJECT_OT_mode_set": "切换模式",
                    "OBJECT_OT_delete": "删除物体",
                    "OBJECT_OT_duplicate_move": "复制并移动",
                    "OBJECT_OT_origin_set": "设置原点",
                    "OBJECT_OT_shade_smooth": "平滑着色",
                    "OBJECT_OT_shade_flat": "平直着色",
                    "OBJECT_OT_modifier_add": "添加修改器",
                    "OBJECT_OT_subdivision_set": "设置细分",
                    "MESH_OT_select_mode": "切换选择模式",
                    "MESH_OT_select_all": "全选",
                    "MESH_OT_select_more": "扩展选择",
                    "MESH_OT_select_less": "收缩选择",
                    "MESH_OT_select_linked": "选择相连元素",
                    "MESH_OT_extrude_region_move": "挤出",
                    "MESH_OT_extrude_faces_move": "挤出面",
                    "MESH_OT_extrude_edges_move": "挤出边",
                    "MESH_OT_inset": "内插面",
                    "MESH_OT_loopcut_slide": "环切",
                    "MESH_OT_bevel": "倒角",
                    "MESH_OT_subdivide": "细分",
                    "MESH_OT_merge": "合并",
                    "MESH_OT_delete": "删除",
                    "MESH_OT_duplicate_move": "复制",
                    "MESH_OT_knife_tool": "切割",
                    "MESH_OT_fill": "填充",
                    "MESH_OT_face_make_f2": "F2填充",
                    "TRANSFORM_OT_translate": "移动",
                    "TRANSFORM_OT_rotate": "旋转",
                    "TRANSFORM_OT_resize": "缩放",
                    "TRANSFORM_OT_snap_type": "吸附设置",
                    "VIEW3D_OT_view_selected": "聚焦所选",
                    "VIEW3D_OT_view_all": "显示全部",
                    "VIEW3D_OT_view_axis": "切换视角",
                    "VIEW3D_OT_view_orbit": "旋转视图",
                    "VIEW3D_OT_view_pan": "平移视图",
                    "VIEW3D_OT_zoom": "缩放视图",
                    "VIEW3D_OT_toggle_xray": "透视模式",
                    "WM_OT_save_mainfile": "保存",
                    "WM_OT_save_as_mainfile": "另存为",
                    "WM_OT_open_mainfile": "打开文件",
                    "WM_OT_redraw_timer": "刷新",
                    "ED_OT_undo": "撤销",
                    "ED_OT_redo": "重做",
                    "SCREEN_OT_screen_full_area": "全屏",
                    "SCREEN_OT_region_quadview": "四视图",
                }
                if op_idname in idname_map:
                    return idname_map[op_idname]
                try:
                    translated = bpy.app.translations.pgettext_iface(label_text)
                    if translated and translated != label_text:
                        return translated
                except Exception:
                    pass
                token_map = {
                    "Switch": "切换", "Mode": "模式", "Mesh": "网格", "Select": "选择", "Edit": "编辑", "Object": "物体",
                    "Toggle": "切换", "Move": "移动", "Rotate": "旋转", "Scale": "缩放", "Extrude": "挤出", "Loop": "环",
                    "Cut": "切", "Slide": "滑动", "Bevel": "倒角", "Delete": "删除", "Subdivide": "细分", "Merge": "合并",
                    "View": "视图", "Selected": "所选", "All": "全部", "Save": "保存", "Open": "打开", "Undo": "撤销",
                    "Redo": "重做", "Duplicate": "复制", "Linked": "关联", "Origin": "原点", "Set": "设置", "Shade": "着色",
                    "Smooth": "平滑", "Flat": "平直", "Modifier": "修改器", "Add": "添加", "Remove": "移除", "Apply": "应用",
                    "Snap": "吸附", "Type": "类型", "Cursor": "游标", "Grid": "网格", "Selection": "选中项", "Active": "活动项",
                    "Hide": "隐藏", "Reveal": "显示", "Separate": "分离", "Join": "合并", "Parent": "父级", "Group": "集合",
                    "Collection": "集合", "New": "新建", "Clear": "清除", "Rest": "重置", "Pose": "姿态", "Bone": "骨骼",
                    "Weight": "权重", "Paint": "绘制", "Texture": "纹理", "Image": "图像", "Node": "节点", "Render": "渲染",
                    "Animation": "动画", "Keyframe": "关键帧", "Insert": "插入", "Axis": "轴向", "Orbit": "轨道", "Pan": "平移",
                    "Zoom": "缩放", "Walk": "飞行", "Fly": "飞行", "Navigation": "导航", "Center": "中心", "Frame": "帧",
                }
                parts = []
                # Simple CamelCase/Space split
                temp = label_text.replace("/", " ").replace("_", " ").replace("-", " ")
                for word in temp.split(" "):
                    if not word: continue
                    # Handle CamelCase inside word? usually idname processing does this.
                    # Just check dict
                    if word in token_map:
                        parts.append(token_map[word])
                    else:
                        parts.append(word)
                
                # Heuristic: if we translated at least one significant word, return joined
                # But English structure is Verb-Object, Chinese is often Verb-Object too but sometimes Modifier-Noun.
                # Simple join is "Okay" for screencast hints.
                if any(p in token_map.values() for p in parts):
                    return "".join(parts)
                
                return ""

            try:
                mode = getattr(prefs, "screencast_operator_label_mode", "ZH")
                if mode == "ZH":
                    cn = _try_translate(label, idname)
                    if cn:
                        label = cn
                elif mode == "BOTH":
                    cn = _try_translate(label, idname)
                    if cn and cn != label:
                        label = f"{cn} / {label}"
            except Exception:
                pass
            return label

        if prefs.screencast_show_last_operator:
            try:
                if len(context.window_manager.operators) > 0:
                    op = context.window_manager.operators[-1]
                    if getattr(op, "bl_idname", "") and op.bl_idname != "M8_OT_internal_screencast":
                        raw_label = getattr(op, "bl_label", "") or getattr(getattr(op, "bl_rna", None), "name", "") or ""
                        op_label = _prettify_operator_label(raw_label, op.bl_idname)
                        
                        # New "Notification Banner" style for operator
                        # Instead of separate keycaps, we draw one unified banner
                        
                        # We construct one single token, but we draw it manually or use draw_keycaps_row with special background?
                        # Let's use draw_keycaps_row but force it to be one big pill if we merge tokens?
                        # No, simpler to just modify how we pass tokens.
                        
                        # We want: [ GEAR ICON | Text ] as one single block
                        # To do this with current system, we can just treat it as one token if we can draw icon inside text? No.
                        # Let's use a special "BANNER" kind.
                        
                        op_tokens = [
                            {"kind": "ICON_GEAR", "label": "OP"},
                            {"kind": "TEXT", "label": op_label, "no_upper": True},
                        ]
                        
                        # If we want a unified banner, we should merge them visually.
                        # We can set gap to 0 and remove inner radius? 
                        # Or just draw a custom background for the whole row first.
                        
                        # Let's calculate total width first
                        total_w = 0
                        sizes = []
                        for tok in op_tokens:
                            if tok["kind"] == "ICON_GEAR": w = font_size * 1.5
                            else: w = blf.dimensions(font_id, tok["label"])[0] + padding * 2
                            sizes.append(w)
                            total_w += w
                        
                        # Gap between icon and text
                        banner_gap = 4
                        total_w += banner_gap
                        
                        h = font_size + padding * 2
                        
                        # Position
                        if align == 'LEFT': x = margin_x
                        elif align == 'RIGHT': x = width - margin_x - total_w
                        else: x = (width - total_w) / 2
                        
                        # Draw Banner Background
                        banner_bg = (0.1, 0.1, 0.1, 0.85) # Darker, opaque
                        banner_outline = (1, 1, 1, 0.2)
                        M8_OT_InternalScreencast.draw_keycap(x, y, total_w, h, cap_radius, banner_bg, banner_outline, shadow=True)
                        
                        # Draw Content
                        curr_x = x
                        
                        # Icon
                        fg = list(prefs.screencast_color)
                        # Maybe slightly dimmer for icon?
                        
                        M8_OT_InternalScreencast.draw_gear_icon(curr_x + (sizes[0] - font_size)/2, y + (h - font_size)/2, font_size, fg)
                        curr_x += sizes[0] + banner_gap
                        
                        # Text
                        lbl = op_label
                        tw = blf.dimensions(font_id, lbl)[0]
                        # Center text vertically
                        blf.color(font_id, *fg)
                        # Left align text after icon?
                        blf.position(font_id, curr_x, y + padding + font_size * 0.2, 0)
                        blf.draw(font_id, lbl)
                        
                        # Increment Y (handle stack direction)
                        if stack_direction == "DOWN":
                            y -= (h + 5)
                        else:
                            y += h + 5
            except Exception:
                pass

        # Keycaps Loop
        for evt in events:
            mods = M8_OT_InternalScreencast._mods_ordered(evt.get("modifiers", []))
            count = int(evt.get("count", 1) or 1)
            is_mouse = (evt.get("type") == "MOUSE")
            mouse_btn = evt.get("mouse_button", "")
            key_text = evt.get("text", "")
            age = now - evt["timestamp"]
            
            # Alpha
            alpha = 1.0
            if age > (timeout - 0.5):
                alpha = (timeout - age) * 2.0
                if alpha < 0: alpha = 0
            
            # Entry Animation
            # Apply transform logic before drawing
            anim_x, anim_y, anim_w, anim_h, anim_alpha = x, y, 0, 0, alpha # w,h determined inside row draw
            
            # Since draw_keycaps_row handles layout, we can only pass alpha override effectively
            # or we need to transform the whole context.
            # But BLF position is absolute.
            
            # Let's simplify: pass 'age' to draw_keycaps_row and handle per-token animation?
            # Or just alpha.
            if entry_anim and age < 0.2:
                # Scale up effect: alpha fade in
                alpha = min(alpha, age * 5.0)

            tokens = [{"kind": "TEXT", "label": m} for m in mods]
            if is_mouse:
                if mouse_btn in {"LEFT", "RIGHT", "MIDDLE"}:
                    tokens.append({"kind": "MOUSE", "label": mouse_btn})
                else:
                    tokens.append({"kind": "TEXT", "label": mouse_btn})
            else:
                if key_text:
                    # Smart Number Merge
                    # If this is part of a number sequence, we might want to display it differently?
                    # No, the merging is done in event capture. Here we just display "12."
                    tokens.append({"kind": "TEXT", "label": key_text})
            
            h = draw_keycaps_row(tokens, alpha, y)
            
            if stack_direction == "DOWN":
                y -= (h + 5)
            else:
                y += h + 5

def register():
    bpy.utils.register_class(M8_OT_InternalScreencast)
    
    # Auto-start check on registration (startup)
    # We can't access prefs directly here easily because context might not be ready.
    # But we can use a timer to check shortly after load.
    def auto_start_screencast():
        try:
            prefs = bpy.context.preferences.addons[__name__.split('.')[0]].preferences
            if prefs.screencast_enabled and not M8_OT_InternalScreencast._running:
                # We need to run it in a window context.
                # Find a 3D view?
                # Actually, operator is INVOKE_DEFAULT which might need context.
                # But we can override.
                for win in bpy.context.window_manager.windows:
                    for area in win.screen.areas:
                        if area.type == 'VIEW_3D':
                            with bpy.context.temp_override(window=win, area=area):
                                bpy.ops.m8.internal_screencast('INVOKE_DEFAULT')
                            return
        except Exception:
            pass

    bpy.app.timers.register(auto_start_screencast, first_interval=1.0)

def unregister():
    bpy.utils.unregister_class(M8_OT_InternalScreencast)
