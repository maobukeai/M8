
import bpy
import sys

def log(msg):
    print(f"[DEBUG] {msg}")

def test_toggle_logic():
    log("Starting test...")
    context = bpy.context
    screen = context.screen
    
    # 1. Find a VIEW_3D area
    area = None
    for a in screen.areas:
        if a.type == 'VIEW_3D':
            area = a
            break
            
    if not area:
        log("No VIEW_3D area found!")
        return

    log(f"Found VIEW_3D area: {area}, size: {area.width}x{area.height}")

    # 2. Try split
    old_areas = set(screen.areas)
    split_factor = 0.25
    
    try:
        # Must use override
        with context.temp_override(area=area):
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=split_factor)
        log("Split operation executed.")
    except Exception as e:
        log(f"Split failed: {e}")
        return

    new_areas = set(screen.areas) - old_areas
    if not new_areas:
        log("No new areas detected after split.")
        return
        
    new_area = list(new_areas)[0]
    log(f"New area created: {new_area}")
    
    # 3. Determine top/bottom (simplified)
    # Just use the new area for testing
    target_area = new_area
    
    # 4. Set type
    try:
        log(f"Before change: type={target_area.type}, ui_type={target_area.ui_type}")
        target_area.type = 'FILE_BROWSER'
        target_area.ui_type = 'ASSETS'
        log(f"After change: type={target_area.type}, ui_type={target_area.ui_type}")
    except Exception as e:
        log(f"Failed to set type: {e}")

if __name__ == "__main__":
    try:
        test_toggle_logic()
    except Exception as e:
        log(f"Global error: {e}")
