import bpy

class M8_OT_ToggleArea(bpy.types.Operator):
    bl_idname = "m8.toggle_area"
    bl_label = "Toggle Area"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        from ..property.preferences import _get_addon_prefs
        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        # Get settings
        close_range = getattr(prefs, "toggle_area_close_range", 30.0) / 100.0
        prefer_lr = getattr(prefs, "toggle_area_prefer_left_right", True)
        toggle_shelf = getattr(prefs, "toggle_area_asset_shelf", True)
        do_top = getattr(prefs, "toggle_area_asset_browser_top", True)
        do_bottom = getattr(prefs, "toggle_area_asset_browser_bottom", True)
        split_factor = getattr(prefs, "toggle_area_split_factor", 0.25)
        wrap_mouse = getattr(prefs, "toggle_area_wrap_mouse", False)
        
        area = context.area
        if not area: return {'CANCELLED'}
        
        # Check area size to prevent operation in Timeline/Header
        if area.height < 100:
            self.report({'WARNING'}, f"区域太小 (高度{area.height}px)，请在主视图内操作")
            return {'CANCELLED'}

        # Calculate mouse relative position
        mx = event.mouse_x - area.x
        my = event.mouse_y - area.y
        w = area.width
        h = area.height
        
        if w <= 0 or h <= 0: return {'CANCELLED'}
        
        nx = mx / w
        ny = my / h
        
        # Determine zones
        is_left = nx < close_range
        is_right = nx > (1.0 - close_range)
        is_bottom = ny < close_range
        is_top = ny > (1.0 - close_range)
        
        # Functions
        def toggle_tools():
            try:
                bpy.ops.screen.region_toggle(region_type='TOOLS')
                return True
            except: return False

        def toggle_ui():
            try:
                bpy.ops.screen.region_toggle(region_type='UI')
                return True
            except: return False

        def toggle_asset_shelf():
            if not toggle_shelf: return False
            try:
                space = context.space_data
                if hasattr(space, "show_region_asset_shelf"):
                    space.show_region_asset_shelf = not space.show_region_asset_shelf
                    return True
            except Exception:
                pass
            return False

        def toggle_asset_browser(at_top, mode='TOGGLE'):
            screen = context.screen
            tol = 10
            
            # 1. Check for existing Asset Browser to CLOSE
            for a in screen.areas:
                if a == area: continue
                if a.ui_type != 'ASSETS':
                    continue
                if abs(a.x - area.x) > tol or abs(a.width - area.width) > tol:
                    continue
                
                is_candidate = False
                if at_top:
                    if abs(a.y - (area.y + area.height)) < tol:
                        is_candidate = True
                else:
                    if abs((a.y + a.height) - area.y) < tol:
                        is_candidate = True
                
                if is_candidate:
                    if mode != 'OPEN_ONLY':
                        try:
                            with context.temp_override(area=a):
                                bpy.ops.screen.area_close()
                            return True
                        except Exception as e:
                            print(f"M8 ToggleArea: Close failed: {e}")
                            return False
                    else:
                        return False
            
            if mode == 'CLOSE_ONLY':
                return False

            # 2. OPEN new Asset Browser
            # HORIZONTAL split factor 是"下方区域"占整体的比例。
            # at_top=True 时我们希望新建的上方区域占 split_factor（较小），
            # 所以对原区域来说下方保留 1-split_factor，上方新区域为 split_factor。
            # at_top=False 时新建区域在下方，factor=split_factor 直接对应。
            effective_factor = (1.0 - split_factor) if at_top else split_factor

            old_areas = set(screen.areas)
            try:
                bpy.ops.screen.area_split(direction='HORIZONTAL', factor=effective_factor)
            except Exception as e:
                self.report({'WARNING'}, f"分割区域失败: {e}")
                return False
                
            new_areas = set(screen.areas) - old_areas
            if not new_areas: return False
            
            new_area = list(new_areas)[0]
            
            a1 = area
            a2 = new_area
            top_area    = a1 if a1.y > a2.y else a2
            bottom_area = a2 if a1.y > a2.y else a1
                
            target_area = top_area if at_top else bottom_area
            
            try:
                target_area.type = 'FILE_BROWSER'
                target_area.ui_type = 'ASSETS'
            except Exception as e:
                self.report({'WARNING'}, f"设置资产浏览器失败: {e}")
            
            if wrap_mouse:
                cx = target_area.x + target_area.width / 2
                cy = target_area.y + target_area.height / 2
                context.window.cursor_warp(int(cx), int(cy))
            
            return True


        # Logic Execution
        ops_queue = []

        # Helper to decide if we should toggle shelf or browser
        def toggle_shelf_or_browser(is_top_side):
            # 1. Try to CLOSE browser first
            if is_top_side:
                if do_top and toggle_asset_browser(True, mode='CLOSE_ONLY'): return True
            else:
                if do_bottom and toggle_asset_browser(False, mode='CLOSE_ONLY'): return True
            
            # 2. Check Shelf preference
            # Note: For Blender 4.x, if shelf toggle fails or not available, we should continue.
            # However, if 'toggle_shelf' is True, but 'toggle_asset_shelf()' returns False,
            # we might want to ensure we fallback to browser if shelf didn't toggle.
            
            if toggle_shelf:
                # If shelf toggled successfully, return True.
                # If it failed (e.g. no shelf region in 4.4), continue to browser.
                if toggle_asset_shelf():
                    return True
            
            # 3. Open Browser
            if is_top_side:
                return do_top and toggle_asset_browser(True, mode='OPEN_ONLY')
            else:
                return do_bottom and toggle_asset_browser(False, mode='OPEN_ONLY')

        
        if prefer_lr:
            if is_left: ops_queue.append(toggle_tools)
            if is_right: ops_queue.append(toggle_ui)
            if is_bottom: 
                ops_queue.append(lambda: toggle_shelf_or_browser(False))
            if is_top: 
                ops_queue.append(lambda: toggle_shelf_or_browser(True))
        else:
            if is_bottom:
                ops_queue.append(lambda: toggle_shelf_or_browser(False))
            if is_top:
                ops_queue.append(lambda: toggle_shelf_or_browser(True))
            if is_left: ops_queue.append(toggle_tools)
            if is_right: ops_queue.append(toggle_ui)
            
        # Execute first valid
        for op in ops_queue:
            if op():
                return {'FINISHED'}
        
        # Fallback: toggle Toolbar
        if toggle_tools():
            return {'FINISHED'}
                
        return {'CANCELLED'}
