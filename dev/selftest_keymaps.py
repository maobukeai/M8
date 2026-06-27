"""Keymap smoke tests for the M8 Blender add-on.

Run from Blender, for example:
blender --background --factory-startup --python dev/selftest_keymaps.py
"""

from __future__ import annotations

import importlib
import json
import sys
import traceback
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = ROOT.name
RESULT_PREFIX = "M8_KEYMAP_SELFTEST_RESULT"

SUBDIVISION_KEYS = {
    0: "ZERO",
    1: "ONE",
    2: "TWO",
    3: "THREE",
    4: "FOUR",
}


def _ensure_addon_parent_on_path():
    addon_parent = str(ROOT.parent)
    if addon_parent not in sys.path:
        sys.path.insert(0, addon_parent)


def _enable_addon():
    _ensure_addon_parent_on_path()
    bpy.ops.preferences.addon_enable(module=MODULE_NAME)
    return importlib.import_module(MODULE_NAME)


def _disable_addon():
    if bpy.context.preferences.addons.get(MODULE_NAME):
        bpy.ops.preferences.addon_disable(module=MODULE_NAME)


def _operator_exists(bl_idname):
    if not bl_idname or "." not in bl_idname:
        return False
    namespace, op_name = bl_idname.split(".", 1)
    op_namespace = getattr(bpy.ops, namespace, None)
    return op_namespace is not None and hasattr(op_namespace, op_name)


def _record_check(report, name, ok, detail=None):
    entry = {
        "name": name,
        "ok": bool(ok),
    }
    if detail is not None:
        entry["detail"] = detail
    report["checks"].append(entry)
    if not ok:
        report["failures"].append(entry)


def _sorted_result(result):
    try:
        return sorted(result)
    except Exception:
        return [str(result)]


def _snapshot_kmi(km, kmi):
    snapshot = {
        "keymap": getattr(km, "name", None),
        "idname": getattr(kmi, "idname", None),
        "type": getattr(kmi, "type", None),
        "value": getattr(kmi, "value", None),
        "shift": bool(getattr(kmi, "shift", False)),
        "ctrl": bool(getattr(kmi, "ctrl", False)),
        "alt": bool(getattr(kmi, "alt", False)),
        "oskey": bool(getattr(kmi, "oskey", False)),
        "active": bool(getattr(kmi, "active", False)),
    }
    try:
        if kmi.idname == "m8.subdivision_set":
            snapshot["level"] = int(kmi.properties.level)
        elif kmi.idname == "wm.call_menu_pie":
            snapshot["menu"] = getattr(kmi.properties, "name", None)
    except Exception:
        pass
    return snapshot


def _set_pref(prefs, name, value):
    if prefs is None or not hasattr(prefs, name):
        raise RuntimeError(f"Missing add-on preference: {name}")
    setattr(prefs, name, value)


def _all_active(items):
    return all(bool(kmi.active) for _, _, kmi in items)


def _all_inactive(items):
    return all(not bool(kmi.active) for _, _, kmi in items)


def _get_or_new_keymap(kc, name, space_type):
    km = kc.keymaps.get(name)
    if km is None:
        km = kc.keymaps.new(name=name, space_type=space_type)
    return km


def _add_conflict(created_conflicts, kc, keymap_name, space_type, key_type, *, ctrl=False):
    km = _get_or_new_keymap(kc, keymap_name, space_type)
    kmi = km.keymap_items.new("wm.call_menu", key_type, "PRESS", ctrl=ctrl)
    try:
        kmi.properties.name = "TOPBAR_MT_file"
    except Exception:
        pass
    kmi.active = True
    created_conflicts.append((km, kmi))
    return kmi


def _remove_conflicts(created_conflicts):
    for km, kmi in reversed(created_conflicts):
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    created_conflicts.clear()


def _find_subsurf(obj):
    for mod in reversed(obj.modifiers):
        if mod.type == "SUBSURF":
            return mod
    return None


def _make_mesh_object():
    mesh = bpy.data.meshes.new("M8_KeymapSmoke_Mesh")
    mesh.from_pydata(
        [
            (-1, -1, -1),
            (1, -1, -1),
            (1, 1, -1),
            (-1, 1, -1),
            (-1, -1, 1),
            (1, -1, 1),
            (1, 1, 1),
            (-1, 1, 1),
        ],
        [],
        [
            (0, 1, 2, 3),
            (4, 7, 6, 5),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (3, 7, 4, 0),
        ],
    )
    mesh.update()
    obj = bpy.data.objects.new("M8_KeymapSmoke_Object", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def _remove_mesh_object(obj):
    mesh = getattr(obj, "data", None)
    try:
        bpy.data.objects.remove(obj, do_unlink=True)
    except Exception:
        pass
    if mesh and mesh.users == 0:
        try:
            bpy.data.meshes.remove(mesh)
        except Exception:
            pass


def _smoke_subdivision_operator(report):
    obj = _make_mesh_object()
    try:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

        level_results = {}
        for level in range(5):
            result = bpy.ops.m8.subdivision_set(level=level)
            subsurf = _find_subsurf(obj)
            level_results[level] = {
                "result": _sorted_result(result),
                "levels": getattr(subsurf, "levels", None),
                "render_levels": getattr(subsurf, "render_levels", None),
                "has_modifier": subsurf is not None,
            }

        result = bpy.ops.m8.subdivision_set(level=0)
        subsurf = _find_subsurf(obj)
        level_results["reset_0"] = {
            "result": _sorted_result(result),
            "levels": getattr(subsurf, "levels", None),
            "render_levels": getattr(subsurf, "render_levels", None),
            "has_modifier": subsurf is not None,
        }
        report["subdivision_operator"] = level_results

        _record_check(
            report,
            "subdivision_operator_ctrl_0_no_modifier",
            level_results[0]["result"] == ["FINISHED"] and not level_results[0]["has_modifier"],
            level_results[0],
        )
        for level in range(1, 5):
            _record_check(
                report,
                f"subdivision_operator_level_{level}",
                level_results[level]["result"] == ["FINISHED"]
                and level_results[level]["levels"] == level
                and level_results[level]["render_levels"] >= level,
                level_results[level],
            )
        _record_check(
            report,
            "subdivision_operator_reset_existing_modifier_to_0",
            level_results["reset_0"]["result"] == ["FINISHED"]
            and level_results["reset_0"]["levels"] == 0,
            level_results["reset_0"],
        )
    finally:
        _remove_mesh_object(obj)


def _try_toggle_area_ui_smoke(report):
    report["toggle_area_ui_invoke"] = {
        "status": "skipped",
        "reason": "background mode has no interactive area",
    }
    if bpy.app.background:
        return

    window = bpy.context.window
    screen = getattr(window, "screen", None) if window else None
    if not screen:
        report["toggle_area_ui_invoke"]["reason"] = "no active screen"
        return

    area = next((area for area in screen.areas if area.type == "VIEW_3D"), None)
    if area is None:
        report["toggle_area_ui_invoke"]["reason"] = "no VIEW_3D area"
        return

    region = next((region for region in area.regions if region.type == "WINDOW"), None)
    event = type(
        "M8KeymapSmokeEvent",
        (),
        {
            "mouse_x": int(area.x + 5),
            "mouse_y": int(area.y + max(5, area.height // 2)),
        },
    )()

    toggle_area_module = importlib.import_module(f"{MODULE_NAME}.ops.misc.toggle_area")
    operator = toggle_area_module.M8_OT_ToggleArea()
    override = {
        "window": window,
        "screen": screen,
        "area": area,
    }
    if region:
        override["region"] = region

    with bpy.context.temp_override(**override):
        result = operator.invoke(bpy.context, event)
        if "FINISHED" in result:
            try:
                operator.invoke(bpy.context, event)
            except Exception:
                pass

    report["toggle_area_ui_invoke"] = {
        "status": "ran",
        "result": _sorted_result(result),
        "area": {
            "type": area.type,
            "width": area.width,
            "height": area.height,
        },
    }
    _record_check(
        report,
        "toggle_area_ui_invoke_returns_status",
        bool(result) and all(item in {"FINISHED", "CANCELLED", "RUNNING_MODAL", "PASS_THROUGH"} for item in result),
        report["toggle_area_ui_invoke"],
    )


def run():
    report = {
        "root": str(ROOT),
        "module": MODULE_NAME,
        "registered": False,
        "unregistered": False,
        "checks": [],
        "failures": [],
        "keymaps": {},
        "preferences": {},
        "conflicts": {},
    }

    created_conflicts = []
    original_prefs = {}
    was_enabled = bool(bpy.context.preferences.addons.get(MODULE_NAME))

    try:
        _enable_addon()
        report["registered"] = True

        keymap_helpers = importlib.import_module(f"{MODULE_NAME}.property.keymap_helpers")
        keymap_manager = importlib.import_module(f"{MODULE_NAME}.property.keymap_manager")
        constants = importlib.import_module(f"{MODULE_NAME}.property.keymap_constants")

        prefs = keymap_helpers._get_addon_prefs()
        report["preferences"]["available"] = prefs is not None
        _record_check(report, "addon_preferences_available", prefs is not None)
        if prefs is None:
            return report

        for name in (
            "activate_toggle_area",
            "activate_subdivision_shortcuts",
            "auto_exclusive_shift_s_include_user",
        ):
            original_prefs[name] = getattr(prefs, name)

        _set_pref(prefs, "auto_exclusive_shift_s_include_user", True)
        _set_pref(prefs, "activate_toggle_area", True)
        _set_pref(prefs, "activate_subdivision_shortcuts", True)
        keymap_manager.register_keymaps()
        keymap_manager.update_keymaps(prefs, bpy.context)

        addon_keymaps = getattr(keymap_helpers, "addon_keymaps", [])
        report["keymaps"]["addon_count"] = len(addon_keymaps)
        _record_check(report, "addon_keymaps_registered", len(addon_keymaps) > 0, len(addon_keymaps))

        toggle_items = keymap_helpers._find_toggle_area_keymap_items()
        report["keymaps"]["toggle_area"] = [
            _snapshot_kmi(km, kmi)
            for _, km, kmi in toggle_items
        ]
        expected_toggle_keymaps = {name for name, _ in constants.TOGGLE_AREA_KEYMAP_BINDINGS}
        actual_toggle_keymaps = {km.name for _, km, _ in toggle_items}
        _record_check(
            report,
            "toggle_area_operator_registered",
            _operator_exists(constants.TOGGLE_AREA_OP_ID),
            constants.TOGGLE_AREA_OP_ID,
        )
        _record_check(
            report,
            "toggle_area_t_keymaps_present",
            expected_toggle_keymaps.issubset(actual_toggle_keymaps),
            {
                "expected": sorted(expected_toggle_keymaps),
                "actual": sorted(actual_toggle_keymaps),
            },
        )
        _record_check(
            report,
            "toggle_area_t_keymaps_shape",
            all(
                kmi.idname == constants.TOGGLE_AREA_OP_ID
                and kmi.type == "T"
                and kmi.value == "PRESS"
                and not kmi.shift
                and not kmi.ctrl
                and not kmi.alt
                for _, _, kmi in toggle_items
            ),
            report["keymaps"]["toggle_area"],
        )

        subdivision_items = keymap_helpers._find_subdivision_keymap_items()
        report["keymaps"]["subdivision"] = [
            _snapshot_kmi(km, kmi)
            for _, km, kmi in subdivision_items
        ]
        expected_subdivision_pairs = {
            (keymap_name, level)
            for keymap_name, _ in constants.SUBDIVISION_KEYMAP_BINDINGS
            for level in SUBDIVISION_KEYS
        }
        actual_subdivision_pairs = {
            (km.name, int(kmi.properties.level))
            for _, km, kmi in subdivision_items
        }
        _record_check(
            report,
            "subdivision_operator_registered",
            _operator_exists("m8.subdivision_set"),
            "m8.subdivision_set",
        )
        _record_check(
            report,
            "subdivision_ctrl_0_to_4_keymaps_present",
            expected_subdivision_pairs.issubset(actual_subdivision_pairs),
            {
                "expected": sorted(expected_subdivision_pairs),
                "actual": sorted(actual_subdivision_pairs),
            },
        )
        _record_check(
            report,
            "subdivision_ctrl_0_to_4_keymaps_shape",
            all(
                kmi.idname == "m8.subdivision_set"
                and kmi.type == SUBDIVISION_KEYS[int(kmi.properties.level)]
                and kmi.value == "PRESS"
                and kmi.ctrl
                and not kmi.shift
                and not kmi.alt
                for _, _, kmi in subdivision_items
            ),
            report["keymaps"]["subdivision"],
        )

        _smoke_subdivision_operator(report)
        _try_toggle_area_ui_smoke(report)

        _set_pref(prefs, "activate_toggle_area", False)
        toggle_items = keymap_helpers._find_toggle_area_keymap_items()
        report["preferences"]["toggle_area_off_active"] = [bool(kmi.active) for _, _, kmi in toggle_items]
        _record_check(
            report,
            "pref_toggle_area_off_disables_keymaps",
            toggle_items and _all_inactive(toggle_items),
            report["preferences"]["toggle_area_off_active"],
        )
        _set_pref(prefs, "activate_toggle_area", True)
        toggle_items = keymap_helpers._find_toggle_area_keymap_items()
        report["preferences"]["toggle_area_on_active"] = [bool(kmi.active) for _, _, kmi in toggle_items]
        _record_check(
            report,
            "pref_toggle_area_on_enables_keymaps",
            toggle_items and _all_active(toggle_items),
            report["preferences"]["toggle_area_on_active"],
        )

        _set_pref(prefs, "activate_subdivision_shortcuts", False)
        subdivision_items = keymap_helpers._find_subdivision_keymap_items()
        report["preferences"]["subdivision_off_active"] = [bool(kmi.active) for _, _, kmi in subdivision_items]
        _record_check(
            report,
            "pref_subdivision_off_disables_keymaps",
            subdivision_items and _all_inactive(subdivision_items),
            report["preferences"]["subdivision_off_active"],
        )
        _set_pref(prefs, "activate_subdivision_shortcuts", True)
        subdivision_items = keymap_helpers._find_subdivision_keymap_items()
        report["preferences"]["subdivision_on_active"] = [bool(kmi.active) for _, _, kmi in subdivision_items]
        _record_check(
            report,
            "pref_subdivision_on_enables_keymaps",
            subdivision_items and _all_active(subdivision_items),
            report["preferences"]["subdivision_on_active"],
        )

        wm = bpy.context.window_manager
        user_kc = wm.keyconfigs.user if wm and wm.keyconfigs else None
        _record_check(report, "user_keyconfig_available", user_kc is not None)
        if user_kc is not None:
            t_conflict = _add_conflict(
                created_conflicts,
                user_kc,
                "3D View",
                "VIEW_3D",
                "T",
            )
            result = bpy.ops.size_tool.exclusive_toggle_area_hotkey()
            report["conflicts"]["toggle_area_exclusive_result"] = _sorted_result(result)
            report["conflicts"]["toggle_area_disabled"] = not bool(t_conflict.active)
            _record_check(
                report,
                "exclusive_toggle_area_disables_user_conflict",
                "FINISHED" in result and not bool(t_conflict.active),
                report["conflicts"]["toggle_area_exclusive_result"],
            )
            result = bpy.ops.size_tool.restore_toggle_area_conflicts()
            report["conflicts"]["toggle_area_restore_result"] = _sorted_result(result)
            report["conflicts"]["toggle_area_restored"] = bool(t_conflict.active)
            _record_check(
                report,
                "restore_toggle_area_restores_user_conflict",
                "FINISHED" in result and bool(t_conflict.active),
                report["conflicts"]["toggle_area_restore_result"],
            )

            subdivision_conflicts = [
                _add_conflict(
                    created_conflicts,
                    user_kc,
                    "Object Mode",
                    "EMPTY",
                    key_type,
                    ctrl=True,
                )
                for key_type in SUBDIVISION_KEYS.values()
            ]
            result = bpy.ops.size_tool.exclusive_subdivision_hotkey()
            report["conflicts"]["subdivision_exclusive_result"] = _sorted_result(result)
            report["conflicts"]["subdivision_disabled"] = [
                not bool(kmi.active) for kmi in subdivision_conflicts
            ]
            _record_check(
                report,
                "exclusive_subdivision_disables_user_conflicts",
                "FINISHED" in result and all(not bool(kmi.active) for kmi in subdivision_conflicts),
                report["conflicts"]["subdivision_exclusive_result"],
            )
            result = bpy.ops.size_tool.restore_subdivision_conflicts()
            report["conflicts"]["subdivision_restore_result"] = _sorted_result(result)
            report["conflicts"]["subdivision_restored"] = [
                bool(kmi.active) for kmi in subdivision_conflicts
            ]
            _record_check(
                report,
                "restore_subdivision_restores_user_conflicts",
                "FINISHED" in result and all(bool(kmi.active) for kmi in subdivision_conflicts),
                report["conflicts"]["subdivision_restore_result"],
            )
    finally:
        _remove_conflicts(created_conflicts)
        try:
            prefs = importlib.import_module(f"{MODULE_NAME}.property.keymap_helpers")._get_addon_prefs()
            if prefs is not None:
                for name, value in original_prefs.items():
                    try:
                        setattr(prefs, name, value)
                    except Exception:
                        pass
        except Exception:
            pass
        if not was_enabled:
            try:
                _disable_addon()
                report["unregistered"] = True
            except Exception as exc:
                report["unregister_error"] = str(exc)
        else:
            report["unregistered"] = False

    return report


if __name__ == "__main__":
    try:
        result = run()
    except SystemExit:
        raise
    except Exception as exc:
        result = {
            "fatal": str(exc),
            "traceback": traceback.format_exc(),
        }
    print(RESULT_PREFIX + " " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result.get("fatal") or result.get("failures"):
        raise SystemExit(1)
