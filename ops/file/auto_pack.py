import bpy
from bpy.app.handlers import persistent


def _get_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    prefs = getattr(bpy.context, "preferences", None)
    addon = prefs.addons.get(root_pkg) if prefs else None
    return addon.preferences if addon else None


def _find_operator_override_context():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return {"window": window, "area": area, "region": region}
    except Exception:
        return None
    return None


def _packed_name_set(collection):
    packed = set()
    for item in list(collection):
        try:
            pf = getattr(item, "packed_file", None)
            if pf is not None:
                filepath = getattr(pf, "filepath", "") or ""
                packed.add(filepath or item.name)
                continue

            pfs = getattr(item, "packed_files", None)
            if pfs:
                for pfi in list(pfs):
                    filepath = getattr(pfi, "filepath", "") or ""
                    packed.add(filepath or item.name)
        except Exception:
            continue
    return packed


def _get_pack_stats():
    return {
        "images": _packed_name_set(getattr(bpy.data, "images", [])),
        "sounds": _packed_name_set(getattr(bpy.data, "sounds", [])),
        "fonts": _packed_name_set(getattr(bpy.data, "fonts", [])),
        "movieclips": _packed_name_set(getattr(bpy.data, "movieclips", [])),
    }


def _is_enabled():
    prefs = _get_addon_prefs()
    if not prefs:
        return False, False
    auto_pack = bool(getattr(prefs, "auto_pack_resources_on_save", False))
    auto_purge = bool(getattr(prefs, "auto_purge_unused_materials_on_save", False))
    return auto_pack, auto_purge


def _is_safe_orphan_id(id_block):
    try:
        if getattr(id_block, "library", None):
            return False
        if getattr(id_block, "use_fake_user", False):
            return False
        if getattr(id_block, "asset_data", None) is not None:
            return False
        return getattr(id_block, "users", 0) == 0
    except Exception:
        return False


def _remove_orphans_from_collection(data_collection):
    removed = 0
    for id_block in list(data_collection):
        if _is_safe_orphan_id(id_block):
            try:
                data_collection.remove(id_block)
                removed += 1
            except Exception:
                pass
    return removed


def _purge_orphans_keep_assets(max_passes=6):
    total_removed = 0
    passes = int(max_passes)
    for _ in range(passes):
        removed = 0
        removed += _remove_orphans_from_collection(getattr(bpy.data, "meshes", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "materials", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "images", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "node_groups", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "actions", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "armatures", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "curves", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "collections", []))
        removed += _remove_orphans_from_collection(getattr(bpy.data, "objects", []))
        total_removed += removed
        if removed == 0:
            break
    return total_removed


@persistent
def save_pre(_dummy=None, *args, **kwargs):
    auto_pack, auto_purge = _is_enabled()
    if not (auto_pack or auto_purge):
        return

    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return

    summary = {
        "purged_orphans": 0,
        "purged_materials": 0,
        "packed_added": {},
        "packed_total": {},
        "packed_added_samples": {},
        "packed_added_full": {},
    }

    if auto_purge:
        try:
            summary["purged_orphans"] = int(_purge_orphans_keep_assets())
        except Exception:
            pass

    if auto_pack:
        try:
            before = _get_pack_stats()
            override = _find_operator_override_context()
            if override:
                with bpy.context.temp_override(**override):
                    bpy.ops.file.pack_all()
            else:
                bpy.ops.file.pack_all()
            after = _get_pack_stats()
            added_full = {k: sorted(list(after[k] - before[k])) for k in after.keys()}
            summary["packed_added_full"] = added_full
            summary["packed_added"] = {k: len(v) for k, v in added_full.items()}
            summary["packed_total"] = {k: len(after[k]) for k in after.keys()}
            def _sample(xs):
                out = []
                for x in xs[:6]:
                    try:
                        out.append(bpy.path.basename(x))
                    except Exception:
                        out.append(str(x))
                return out
            summary["packed_added_samples"] = {k: _sample(v) for k, v in added_full.items()}
        except Exception:
            pass

    try:
        wm["_m8_last_auto_pack_summary"] = summary
    except Exception:
        pass


@persistent
def save_post(_dummy=None, *args, **kwargs):
    auto_pack, auto_purge = _is_enabled()
    if not (auto_pack or auto_purge):
        return

    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return

    summary = None
    try:
        summary = wm.get("_m8_last_auto_pack_summary", None)
    except Exception:
        summary = None

    if not summary:
        return

    def _notify():
        override = _find_operator_override_context()
        try:
            if override:
                with bpy.context.temp_override(**override):
                    bpy.ops.m8.show_save_report('INVOKE_DEFAULT', source="AUTO")
            else:
                bpy.ops.m8.show_save_report('INVOKE_DEFAULT', source="AUTO")
        except Exception:
            return None
        return None

    try:
        bpy.app.timers.register(_notify, first_interval=0.01)
    except Exception:
        pass


def register():
    if save_pre not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(save_pre)
    if save_post not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(save_post)


def unregister():
    if save_pre in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(save_pre)
    if save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(save_post)
