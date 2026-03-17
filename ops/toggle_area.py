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
        # Default to 30% if not set (though we will set default in prefs)
        close_range = getattr(prefs, "toggle_area_close_range", 30.0) / 100.0
        prefer_lr = getattr(prefs, "toggle_area_prefer_left_right", True)
        toggle_shelf = getattr(prefs, "toggle_area_asset_shelf", True)
        do_top = getattr(prefs, "toggle_area_asset_browser_top", True)
        do_bottom = getattr(prefs, "toggle_area_asset_browser_bottom", True)
        split_factor = getattr(prefs, "toggle_area_split_factor", 0.25)
        wrap_mouse = getattr(prefs, "toggle_area_wrap_mouse", False)
        
        area = context.area
        if not area: return {'CANCELLED'}
        
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
            # Check for Asset Shelf (Blender 4.0+)
            has_shelf = False
            for r in area.regions:
                if r.type == 'ASSET_SHELF':
                    has_shelf = True
                    break
            
            if has_shelf:
                try:
                    # Try specific operator if available, or generic region_toggle
                    # Note: region_toggle might not work if ASSET_SHELF isn't standard in that op
                    # But typically it works if context is correct.
                    # In 4.0, it's often 'ASSET_SHELF'
                    
                    # NOTE: region_toggle relies on context.
                    # We are in invoke, so context should be correct for the area we are in.
                    
                    # However, region_toggle toggles visibility.
                    # We should check if we really want to toggle it.
                    # User says "Toggle Asset Shelf INSTEAD OF Browser".
                    # So if Shelf is available, we use it.
                    
                    # Check if 'ASSET_SHELF' is supported by generic region_toggle
                    # Or use specific property
                    
                    # For Blender 4.0+, area.show_asset_shelf might be a property?
                    # Or area.spaces.active.show_asset_shelf ?
                    
                    # Let's try to access property first for more robustness
                    space = context.space_data
                    if hasattr(space, "show_region_asset_shelf"):
                        space.show_region_asset_shelf = not space.show_region_asset_shelf
                        return True
                    
                    bpy.ops.screen.region_toggle(region_type='ASSET_SHELF')
                    return True
                except:
                    pass
            return False

        def toggle_asset_browser(at_top, mode='TOGGLE'):
            screen = context.screen
            tol = 10
            
            # 1. Check for existing Asset Browser to CLOSE
            for a in screen.areas:
                if a == area: continue
                
                # Check for Asset Browser type
                if a.ui_type != 'ASSETS':
                    continue

                # Check alignment (width)
                if abs(a.x - area.x) > tol or abs(a.width - area.width) > tol:
                    continue
                
                is_candidate = False
                if at_top:
                    # 'a' is above 'area'
                    # a.y should be near area.y + area.height
                    # Also check if they are adjacent
                    if abs(a.y - (area.y + area.height)) < tol:
                        is_candidate = True
                else: # at_bottom
                    # 'a' is below 'area'
                    # a.y + a.height should be near area.y
                    if abs((a.y + a.height) - area.y) < tol:
                        is_candidate = True
                
                if is_candidate:
                    if mode != 'OPEN_ONLY':
                        # Close it
                        with context.temp_override(area=a):
                            bpy.ops.screen.area_close()
                        return True
                    else:
                        # Found one, but we are in OPEN_ONLY mode
                        return False
            
            if mode == 'CLOSE_ONLY':
                return False

            # 2. OPEN new Asset Browser
            # Split area
            
            old_areas = set(screen.areas)
            
            try:
                # Use split factor from prefs
                bpy.ops.screen.area_split(direction='HORIZONTAL', factor=split_factor)
            except:
                return False
                
            new_areas = set(screen.areas) - old_areas
            if not new_areas: return False
            
            new_area = list(new_areas)[0]
            
            # Identify Top and Bottom areas
            # Note: area_split modifies the original area and creates a new one.
            # We must compare their Y coordinates to know which is which.
            
            # Re-fetch the original area object (it might be updated, but reference usually holds)
            # However, safer to just use the two areas we know: 'area' and 'new_area'.
            
            a1 = area
            a2 = new_area
            
            # Determine which is Top and which is Bottom
            if a1.y > a2.y:
                top_area = a1
                bottom_area = a2
            else:
                top_area = a2
                bottom_area = a1
                
            # Assign Asset Browser to the correct area
            if at_top:
                target_area = top_area
            else:
                target_area = bottom_area
            
            target_area.ui_type = 'ASSETS'
            
            if wrap_mouse:
                # Move mouse to center of asset area
                cx = target_area.x + target_area.width / 2
                cy = target_area.y + target_area.height / 2
                context.window.cursor_warp(int(cx), int(cy))
            
            return True

        # Logic Execution
        # Priority:
        # If Prefer LR: Left/Right -> Top/Bottom
        # If Not Prefer LR: Top/Bottom -> Left/Right (Actually User said "Prefer L/R, not D/U", implies L/R > D/U)
        # But if user *unchecks* Prefer LR, maybe they want D/U > L/R? Or just no preference (distance based)?
        # Let's assume if uncheck, check strictly by distance?
        # Or check Top/Bottom first?
        # Let's follow "If prefer_lr: check LR then TB".
        # Else: check TB then LR.
        
        # Also, check area type. Only VIEW_3D supports Asset Browser/Shelf toggle here.
        
        ops_queue = []

        # Helper to decide if we should toggle shelf or browser
        def toggle_shelf_or_browser(is_top_side):
            # 1. Try to CLOSE browser first (High priority cleanup)
            if is_top_side:
                if do_top and toggle_asset_browser(True, mode='CLOSE_ONLY'): return True
            else:
                if do_bottom and toggle_asset_browser(False, mode='CLOSE_ONLY'): return True
            
            # 2. If nothing closed, we want to OPEN something.
            # Check Shelf preference
            if toggle_shelf:
                if toggle_asset_shelf():
                    return True
            
            # 3. If Shelf didn't handle it, Open Browser
            if is_top_side:
                return do_top and toggle_asset_browser(True, mode='OPEN_ONLY')
            else:
                return do_bottom and toggle_asset_browser(False, mode='OPEN_ONLY')

        
        if prefer_lr:
            if is_left: ops_queue.append(toggle_tools)
            if is_right: ops_queue.append(toggle_ui)
            if area.type == 'VIEW_3D':
                if is_bottom: 
                    ops_queue.append(lambda: toggle_shelf_or_browser(False))
                if is_top: 
                    ops_queue.append(lambda: toggle_shelf_or_browser(True))
        else:
            if area.type == 'VIEW_3D':
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
                
        # If nothing matched (e.g. center), maybe do nothing.
        
        return {'CANCELLED'} 
