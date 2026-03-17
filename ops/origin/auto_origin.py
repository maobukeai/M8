import bpy
from bpy.app.handlers import persistent
from mathutils import Vector, Matrix
import time
from ...utils import CAGE_TAG_KEY, get_backup_suffix, is_size_cage

_known_ptrs = set()
_op_cache_len = 0
_last_add_op_time = 0.0
_pending_add_op_time = 0.0
_pending_process_queue = set()
_timer_registered = False

def _get_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    if not bpy.context or not getattr(bpy.context, "preferences", None):
        return None
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

def _prefs_enabled():
    prefs = _get_addon_prefs()
    if not prefs:
        return True, True
    enabled = bool(getattr(prefs, "auto_new_object_origin_bottom", False))
    snap_floor = bool(getattr(prefs, "auto_new_object_snap_to_floor", True))
    return enabled, snap_floor

def _should_skip_object(obj):
    if not obj:
        return True
    if obj.get("_m8_auto_origin_done"):
        return True
    if obj.name.endswith(get_backup_suffix()):
        return True
    if obj.get(CAGE_TAG_KEY) or is_size_cage(obj):
        return True
    if obj.library:
        return True
    if not getattr(obj, "bound_box", None):
        return True
    # Support more types than just MESH
    if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
        return True
    return False

def _process_object_instantly(obj, snap_floor=True):
    if not obj or not obj.data:
        return False
        
    # Handle multi-user data
    if getattr(obj.data, "users", 1) > 1:
        # For non-mesh objects, copying data might be different or unnecessary?
        # But to be safe and avoid affecting other instances, we copy.
        try:
            obj.data = obj.data.copy()
        except Exception:
            pass

    mw = obj.matrix_world.copy()
    bbox = [mw @ Vector(v) for v in obj.bound_box]
    if not bbox:
        return False
        
    min_z = min(v.z for v in bbox)
    center = sum(bbox, Vector((0.0, 0.0, 0.0))) / 8.0
    bottom_center_world = Vector((center.x, center.y, min_z))
    target_world = bottom_center_world.copy()
    if snap_floor:
        target_world.z = 0.0

    basis = mw.to_3x3()
    try:
        world_offset = bottom_center_world - mw.translation
        local_offset = basis.inverted() @ world_offset
        
        # transform() is available on Object or Data?
        # MESH/CURVE/SURFACE/META/FONT data usually have transform()
        if hasattr(obj.data, "transform"):
            obj.data.transform(Matrix.Translation(-local_offset))
            obj.data.update()
            mw.translation = target_world
            obj.matrix_world = mw
        else:
            return False
    except Exception:
        return False
    return True

def _rebuild_known_ptrs():
    _known_ptrs.clear()
    try:
        for obj in bpy.data.objects:
            try:
                _known_ptrs.add(obj.as_pointer())
            except Exception:
                pass
    except Exception:
        pass

def _update_add_op_from_history(wm):
    global _op_cache_len, _last_add_op_time, _pending_add_op_time
    try:
        ops = getattr(wm, "operators", None)
        if not ops:
            _op_cache_len = 0
            return
        n = len(ops)
        if n <= _op_cache_len:
            _op_cache_len = n
            return
        start = _op_cache_len
        _op_cache_len = n
        for i in range(n - 1, start - 1, -1):
            try:
                idname = ops[i].bl_idname
            except Exception:
                continue
            if idname and idname.endswith("_add"):
                _last_add_op_time = time.monotonic()
                _pending_add_op_time = _last_add_op_time
                return
    except Exception:
        return

def _process_queue_timer():
    global _timer_registered
    if not _pending_process_queue:
        _timer_registered = False
        return None
    
    # Process all pending objects
    enabled, snap_floor = _prefs_enabled()
    if enabled:
        # Copy set to avoid modification during iteration
        for name in list(_pending_process_queue):
            _delayed_process_objects([name], snap_floor)
            
    _pending_process_queue.clear()
    _timer_registered = False
    return None

def _delayed_process_objects(object_names, snap_floor):
    if not object_names:
        return None
    
    # Re-fetch objects by name to ensure validity and get original ID
    # Note: Using bpy.data.objects[name] gets the original object, not evaluated
    processed_any = False
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
            
        # Double check validity just in case
        if _should_skip_object(obj):
            continue
            
        if _process_object_instantly(obj, snap_floor=snap_floor):
            processed_any = True
            try:
                _known_ptrs.add(obj.as_pointer())
            except Exception:
                pass
                
    return None

def _handle_depsgraph(depsgraph):
    global _pending_add_op_time, _timer_registered
    enabled, _snap_floor = _prefs_enabled()
    if not enabled or not depsgraph:
        return

    try:
        ctx = bpy.context
        wm = getattr(ctx, "window_manager", None) if ctx else None
        if wm:
            _update_add_op_from_history(wm)
        if not _pending_add_op_time:
            return
        if time.monotonic() - _pending_add_op_time > 2.0:
            return
            
        candidates_found = False
        for update in getattr(depsgraph, "updates", []):
            obj = getattr(update, "id", None)
            if isinstance(obj, bpy.types.Object):
                # Only process if we haven't seen it
                if obj.as_pointer() not in _known_ptrs:
                    if not _should_skip_object(obj):
                        _pending_process_queue.add(obj.name)
                        candidates_found = True
                        try:
                            # Mark as processed immediately to avoid re-queueing
                            # Real processing happens in timer
                            _known_ptrs.add(obj.as_pointer())
                            obj["_m8_auto_origin_done"] = 1
                        except Exception:
                            pass

        if candidates_found and not _timer_registered:
            bpy.app.timers.register(_process_queue_timer, first_interval=0.01)
            _timer_registered = True
            
        _pending_add_op_time = 0.0
    except Exception:
        pass

@persistent
def depsgraph_update_post(_scene=None, depsgraph=None, *args):
    _handle_depsgraph(depsgraph)

def register():
    if depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)
    if load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_post_handler)
    _rebuild_known_ptrs()

def unregister():
    if depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)
    if load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post_handler)

@persistent
def load_post_handler(_scene=None, _depsgraph=None):
    global _op_cache_len, _last_add_op_time, _pending_add_op_time
    _op_cache_len = 0
    _last_add_op_time = 0.0
    _pending_add_op_time = 0.0
    _rebuild_known_ptrs()
