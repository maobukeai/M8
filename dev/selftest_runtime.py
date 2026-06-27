"""Runtime smoke test for the M8 Blender add-on.

Run from Blender, for example:
blender --background --factory-startup --python dev/selftest_runtime.py
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = ROOT.name


def _load_addon_package():
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]

    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to create import spec for {ROOT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _operator_exists(bl_idname):
    if not bl_idname or "." not in bl_idname:
        return False
    namespace, op_name = bl_idname.split(".", 1)
    op_namespace = getattr(bpy.ops, namespace, None)
    return op_namespace is not None and hasattr(op_namespace, op_name)


def _type_exists(cls):
    if getattr(cls, "is_registered", False):
        return True
    try:
        if getattr(cls, "bl_rna", None) is not None:
            return True
    except Exception:
        pass

    for base in (
        bpy.types.Panel,
        bpy.types.Menu,
        bpy.types.PropertyGroup,
        bpy.types.AddonPreferences,
    ):
        if not _safe_issubclass(cls, base):
            continue
        lookup = getattr(base, "bl_rna_get_subclass_py", None)
        if lookup is None:
            continue
        for identifier in (getattr(cls, "bl_idname", None), cls.__name__):
            if not identifier:
                continue
            try:
                if lookup(identifier) is not None:
                    return True
            except Exception:
                pass
    return False


def _safe_issubclass(cls, base):
    try:
        return issubclass(cls, base)
    except TypeError:
        return False


def run():
    report = {
        "root": str(ROOT),
        "module": MODULE_NAME,
        "registered": False,
        "registration_errors": [],
        "missing_operators": [],
        "missing_types": [],
        "duplicate_bl_idnames": [],
        "keymaps": 0,
        "state_properties": {},
        "health_check_result": None,
        "full_system_check_result": None,
        "full_system_copy_result": None,
        "full_system_status": None,
        "full_system_summary": None,
        "health_status": None,
        "health_summary": None,
        "selection_snapshot_save_result": None,
        "selection_snapshot_add_result": None,
        "selection_snapshot_remove_result": None,
        "selection_snapshot_restore_result": None,
        "selection_snapshot_clear_result": None,
        "selection_snapshot_restored": None,
        "wave_quick_set_result": None,
        "wave_loop_result": None,
        "wave_speed_after_shrink": None,
        "wave_loop_values": None,
        "scene_audit_result": None,
        "scene_audit_status": None,
        "scene_audit_summary": None,
        "scene_audit_fix_result": None,
        "scene_audit_post_fix_summary": None,
        "scene_audit_backup_count": None,
        "scene_audit_latest_restore_result": None,
        "scene_audit_latest_restore_summary": None,
        "scene_audit_counts_after_latest_restore": None,
        "scene_audit_select_backups_result": None,
        "scene_audit_selected_restore_result": None,
        "scene_audit_selected_restore_summary": None,
        "scene_audit_counts_after_selected_restore": None,
        "scene_audit_backup_refresh_result": None,
        "scene_audit_backup_summary": None,
        "scene_audit_backup_count_before_prune": None,
        "scene_audit_backup_prune_result": None,
        "scene_audit_backup_manage_summary": None,
        "scene_audit_backup_count_after_prune": None,
        "unregistered": False,
    }

    addon = _load_addon_package()
    addon.register()
    report["registered"] = True

    registration = importlib.import_module(f"{MODULE_NAME}.registration")
    classes = list(getattr(registration, "CLASSES", []))
    report["registration_errors"] = [
        getattr(cls, "__name__", str(cls))
        for cls in getattr(registration, "_registration_errors", [])
    ]

    seen_bl_idnames = {}
    for cls in classes:
        bl_idname = getattr(cls, "bl_idname", None)
        if bl_idname:
            seen_bl_idnames.setdefault(bl_idname, []).append(cls.__name__)

        if _safe_issubclass(cls, bpy.types.Operator):
            if not _operator_exists(bl_idname):
                report["missing_operators"].append(f"{cls.__name__}:{bl_idname}")
        elif (
            _safe_issubclass(cls, bpy.types.Panel)
            or _safe_issubclass(cls, bpy.types.Menu)
            or _safe_issubclass(cls, bpy.types.PropertyGroup)
            or _safe_issubclass(cls, bpy.types.AddonPreferences)
        ):
            if not _type_exists(cls):
                report["missing_types"].append(cls.__name__)

    report["duplicate_bl_idnames"] = [
        {"bl_idname": bl_idname, "classes": names}
        for bl_idname, names in seen_bl_idnames.items()
        if len(names) > 1
    ]

    keymap_helpers = importlib.import_module(f"{MODULE_NAME}.property.keymap_helpers")
    report["keymaps"] = len(getattr(keymap_helpers, "addon_keymaps", []))
    report["state_properties"] = {
        "Scene.m8": hasattr(bpy.types.Scene, "m8"),
        "WindowManager.m8": hasattr(bpy.types.WindowManager, "m8"),
        "Object.m8": hasattr(bpy.types.Object, "m8"),
    }

    try:
        report["health_check_result"] = sorted(bpy.ops.m8.run_health_check())
        wm_state = getattr(bpy.context.window_manager, "m8", None)
        report["health_status"] = getattr(wm_state, "health_status", None)
        report["health_summary"] = getattr(wm_state, "health_summary", None)
        report["full_system_check_result"] = sorted(
            bpy.ops.m8.run_full_system_check(scene_scope="VISIBLE")
        )
        report["full_system_copy_result"] = sorted(bpy.ops.m8.copy_full_system_report())
        report["full_system_status"] = getattr(wm_state, "full_check_status", None)
        report["full_system_summary"] = getattr(wm_state, "full_check_summary", None)
    except Exception as exc:
        report["health_check_result"] = f"ERROR: {exc}"

    try:
        sel_mesh_a = bpy.data.meshes.new("M8_Selftest_Selection_A_Mesh")
        sel_mesh_a.from_pydata([(0, 0, 0), (0.25, 0, 0), (0, 0.25, 0)], [], [(0, 1, 2)])
        sel_mesh_a.update()
        sel_mesh_b = bpy.data.meshes.new("M8_Selftest_Selection_B_Mesh")
        sel_mesh_b.from_pydata([(1, 0, 0), (1.25, 0, 0), (1, 0.25, 0)], [], [(0, 1, 2)])
        sel_mesh_b.update()
        sel_obj_a = bpy.data.objects.new("M8_Selftest_Selection_A", sel_mesh_a)
        sel_obj_b = bpy.data.objects.new("M8_Selftest_Selection_B", sel_mesh_b)
        bpy.context.collection.objects.link(sel_obj_a)
        bpy.context.collection.objects.link(sel_obj_b)

        bpy.ops.object.select_all(action="DESELECT")
        sel_obj_a.select_set(True)
        bpy.context.view_layer.objects.active = sel_obj_a
        report["selection_snapshot_save_result"] = sorted(bpy.ops.m8.save_selection_snapshot())

        bpy.ops.object.select_all(action="DESELECT")
        sel_obj_b.select_set(True)
        bpy.context.view_layer.objects.active = sel_obj_b
        report["selection_snapshot_add_result"] = sorted(bpy.ops.m8.add_selection_to_snapshot())

        bpy.ops.object.select_all(action="DESELECT")
        sel_obj_a.select_set(True)
        bpy.context.view_layer.objects.active = sel_obj_a
        report["selection_snapshot_remove_result"] = sorted(bpy.ops.m8.remove_selection_from_snapshot())

        bpy.ops.object.select_all(action="DESELECT")
        report["selection_snapshot_restore_result"] = sorted(bpy.ops.m8.restore_selection_snapshot())
        report["selection_snapshot_restored"] = sorted(obj.name for obj in bpy.context.selected_objects)
        report["selection_snapshot_clear_result"] = sorted(bpy.ops.m8.clear_selection_snapshot())

        bpy.data.objects.remove(sel_obj_a, do_unlink=True)
        bpy.data.objects.remove(sel_obj_b, do_unlink=True)
        bpy.data.meshes.remove(sel_mesh_a)
        bpy.data.meshes.remove(sel_mesh_b)
    except Exception as exc:
        report["selection_snapshot_save_result"] = f"ERROR: {exc}"

    try:
        wave_mesh = bpy.data.meshes.new("M8_Selftest_Wave_Mesh")
        wave_mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        wave_mesh.update()
        wave_obj = bpy.data.objects.new("M8_Selftest_Wave_Object", wave_mesh)
        bpy.context.collection.objects.link(wave_obj)
        bpy.context.view_layer.objects.active = wave_obj
        bpy.ops.object.select_all(action="DESELECT")
        wave_obj.select_set(True)
        wave_mod = wave_obj.modifiers.new("M8_Selftest_Wave", "WAVE")
        wave_mod.speed = 0.4
        report["wave_quick_set_result"] = sorted(
            bpy.ops.m8.wave_quick_set(action="SHRINK", modifier_name=wave_mod.name)
        )
        report["wave_speed_after_shrink"] = wave_mod.speed
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = 24
        report["wave_loop_result"] = sorted(
            bpy.ops.m8.wave_set_loop_animation(modifier_name=wave_mod.name)
        )
        report["wave_loop_values"] = {
            "time_offset": int(getattr(wave_mod, "time_offset", 0)),
            "lifetime": int(getattr(wave_mod, "lifetime", 0)),
            "damping_time": int(getattr(wave_mod, "damping_time", 0)),
            "use_cyclic": bool(getattr(wave_mod, "use_cyclic", False)),
        }
        bpy.data.objects.remove(wave_obj, do_unlink=True)
        bpy.data.meshes.remove(wave_mesh)
    except Exception as exc:
        report["wave_quick_set_result"] = f"ERROR: {exc}"

    try:
        mesh = bpy.data.meshes.new("M8_Selftest_Mesh")
        mesh.from_pydata(
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 0, 0)],
            [(2, 3)],
            [(0, 1, 2)],
        )
        mat = bpy.data.materials.new("M8_Selftest_Material")
        unused_mat = bpy.data.materials.new("M8_Selftest_Unused_Material")
        mesh.materials.append(mat)
        mesh.materials.append(mat)
        mesh.materials.append(unused_mat)
        mesh.polygons[0].material_index = 1
        mesh.update()
        obj = bpy.data.objects.new("M8_Selftest_Object", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        report["scene_audit_result"] = sorted(
            bpy.ops.m8.run_scene_audit(scope="SELECTED", high_poly_threshold=100)
        )
        wm_state = getattr(bpy.context.window_manager, "m8", None)
        report["scene_audit_status"] = getattr(wm_state, "scene_audit_status", None)
        report["scene_audit_summary"] = getattr(wm_state, "scene_audit_summary", None)
        report["scene_audit_fix_result"] = sorted(
            bpy.ops.m8.fix_scene_audit_safe_issues(scope="SELECTED")
        )
        report["scene_audit_post_fix_summary"] = getattr(wm_state, "scene_audit_summary", None)
        backup_collection = bpy.data.collections.get("M8_Audit_Backups")
        backup_objects = list(backup_collection.objects) if backup_collection else []
        report["scene_audit_backup_count"] = len(backup_objects)
        report["scene_audit_latest_restore_result"] = sorted(
            bpy.ops.m8.restore_scene_audit_latest_backups(rescan=False)
        )
        report["scene_audit_latest_restore_summary"] = getattr(
            wm_state, "scene_audit_last_restore_summary", None
        )
        report["scene_audit_counts_after_latest_restore"] = {
            "verts": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "materials": len(obj.material_slots),
        }
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.m8.fix_scene_audit_safe_issues(scope="SELECTED", rescan=False)
        report["scene_audit_select_backups_result"] = sorted(
            bpy.ops.m8.select_scene_audit_backups()
        )
        report["scene_audit_selected_restore_result"] = sorted(
            bpy.ops.m8.restore_scene_audit_selected_backups(rescan=False)
        )
        report["scene_audit_selected_restore_summary"] = getattr(
            wm_state, "scene_audit_last_restore_summary", None
        )
        report["scene_audit_counts_after_selected_restore"] = {
            "verts": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "materials": len(obj.material_slots),
        }
        report["scene_audit_backup_refresh_result"] = sorted(
            bpy.ops.m8.refresh_scene_audit_backups()
        )
        report["scene_audit_backup_summary"] = getattr(
            wm_state, "scene_audit_backup_summary", None
        )
        report["scene_audit_backup_count_before_prune"] = getattr(
            wm_state, "scene_audit_backup_count", None
        )
        report["scene_audit_backup_prune_result"] = sorted(
            bpy.ops.m8.prune_scene_audit_backups(keep_per_source=1)
        )
        report["scene_audit_backup_manage_summary"] = getattr(
            wm_state, "scene_audit_last_backup_manage_summary", None
        )
        report["scene_audit_backup_count_after_prune"] = getattr(
            wm_state, "scene_audit_backup_count", None
        )
        backup_collection = bpy.data.collections.get("M8_Audit_Backups")
        backup_objects = list(backup_collection.objects) if backup_collection else []
        for backup in backup_objects:
            backup_data = backup.data
            bpy.data.objects.remove(backup, do_unlink=True)
            if backup_data and backup_data.users == 0:
                bpy.data.meshes.remove(backup_data)
        if backup_collection and not backup_collection.objects:
            bpy.data.collections.remove(backup_collection)
        bpy.data.objects.remove(obj, do_unlink=True)
        for mesh_data in list(bpy.data.meshes):
            if mesh_data.name.startswith("M8_Selftest") and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data)
        for material in list(bpy.data.materials):
            if material.name.startswith("M8_Selftest") and material.users == 0:
                bpy.data.materials.remove(material)
    except Exception as exc:
        report["scene_audit_result"] = f"ERROR: {exc}"

    addon.unregister()
    report["unregistered"] = True
    return report


if __name__ == "__main__":
    try:
        result = run()
    except Exception as exc:
        result = {
            "fatal": str(exc),
            "traceback": traceback.format_exc(),
        }
    print("M8_SELFTEST_RESULT " + json.dumps(result, ensure_ascii=False, sort_keys=True))
