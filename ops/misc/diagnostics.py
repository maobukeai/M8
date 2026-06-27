from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
import time

import bpy

from ...utils.logger import get_logger


logger = get_logger()

_STALE_PATH_PATTERNS = (
    "Blender\\" + "5.0",
    "Blender\\" + "5.1",
    "scripts" + "\\addons\\M8",
    "C:" + "\\Users",
)
_STALE_PATH_SCAN_TTL = 5.0
_stale_path_scan_cache = {
    "root": None,
    "signature": None,
    "hits": [],
    "meta": {
        "files": 0,
        "duration_ms": 0.0,
        "cached": False,
    },
    "checked_at": 0.0,
}


def _safe_issubclass(cls, base):
    try:
        return issubclass(cls, base)
    except TypeError:
        return False


def _operator_exists(bl_idname):
    if not bl_idname or "." not in bl_idname:
        return False
    namespace, op_name = bl_idname.split(".", 1)
    op_namespace = getattr(bpy.ops, namespace, None)
    return op_namespace is not None and hasattr(op_namespace, op_name)


def _type_registered(cls):
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


def _iter_python_files(root):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _scan_stale_paths(root, return_meta=False):
    root_key = str(root.resolve())
    now = time.monotonic()
    cache = _stale_path_scan_cache
    if cache["root"] == root_key and now - cache.get("checked_at", 0.0) <= _STALE_PATH_SCAN_TTL:
        meta = dict(cache["meta"])
        meta["cached"] = True
        hits = list(cache["hits"])
        return (hits, meta) if return_meta else hits

    started = time.perf_counter()
    files = []
    newest_mtime = 0
    total_size = 0
    for path in _iter_python_files(root):
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(path)
        newest_mtime = max(newest_mtime, getattr(stat, "st_mtime_ns", 0))
        total_size += getattr(stat, "st_size", 0)

    signature = (len(files), newest_mtime, total_size)
    if cache["root"] == root_key and cache["signature"] == signature:
        duration_ms = (time.perf_counter() - started) * 1000.0
        meta = dict(cache["meta"])
        meta.update({"files": len(files), "duration_ms": duration_ms, "cached": True})
        cache["meta"] = dict(meta)
        cache["checked_at"] = now
        hits = list(cache["hits"])
        return (hits, meta) if return_meta else hits

    hits = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in _STALE_PATH_PATTERNS:
            if pattern in text:
                hits.append(str(path.relative_to(root)))
                break
    hits = sorted(hits)
    meta = {
        "files": len(files),
        "duration_ms": (time.perf_counter() - started) * 1000.0,
        "cached": False,
    }
    cache.update(
        {
            "root": root_key,
            "signature": signature,
            "hits": hits,
            "meta": dict(meta),
            "checked_at": now,
        }
    )
    return (hits, meta) if return_meta else hits


def _class_breakdown(classes):
    counts = Counter()
    for cls in classes:
        if _safe_issubclass(cls, bpy.types.Operator):
            counts["operators"] += 1
        elif _safe_issubclass(cls, bpy.types.Panel):
            counts["panels"] += 1
        elif _safe_issubclass(cls, bpy.types.Menu):
            counts["menus"] += 1
        elif _safe_issubclass(cls, bpy.types.PropertyGroup):
            counts["property_groups"] += 1
        elif _safe_issubclass(cls, bpy.types.AddonPreferences):
            counts["preferences"] += 1
        else:
            counts["other"] += 1
    return counts


def _class_reference_duplicates(classes):
    names = {}
    for cls in classes:
        names.setdefault(cls.__name__, []).append(cls)
    return {name: len(items) for name, items in names.items() if len(items) > 1}


def _keymap_diagnostics(addon_keymaps):
    seen = {}
    duplicate_items = []
    broken_items = []

    for entry in addon_keymaps:
        if not isinstance(entry, (tuple, list)) or len(entry) < 2:
            continue
        keymap, keymap_item = entry[0], entry[1]
        idname = getattr(keymap_item, "idname", "")
        event_key = (
            getattr(keymap, "name", ""),
            idname,
            getattr(keymap_item, "type", ""),
            getattr(keymap_item, "value", ""),
            bool(getattr(keymap_item, "ctrl", False)),
            bool(getattr(keymap_item, "alt", False)),
            bool(getattr(keymap_item, "shift", False)),
            bool(getattr(keymap_item, "oskey", False)),
        )
        if event_key in seen:
            duplicate_items.append(f"{event_key[0]}:{event_key[1]}:{event_key[2]}")
        else:
            seen[event_key] = keymap_item

        if idname and not _operator_exists(idname):
            broken_items.append(f"{getattr(keymap, 'name', '')}:{idname}")

    return sorted(set(duplicate_items)), sorted(set(broken_items))


def collect_health_report():
    from ... import registration
    from ...property import keymap_helpers
    from ...ui import icons as m8_icons

    root = Path(__file__).resolve().parents[2]
    classes = list(getattr(registration, "CLASSES", []))
    registration_errors = [
        getattr(cls, "__name__", str(cls))
        for cls in getattr(registration, "_registration_errors", [])
    ]

    missing_operators = []
    missing_types = []
    bl_idnames = {}
    class_counts = _class_breakdown(classes)
    duplicate_class_refs = _class_reference_duplicates(classes)

    for cls in classes:
        bl_idname = getattr(cls, "bl_idname", None)
        if bl_idname:
            bl_idnames.setdefault(bl_idname, []).append(cls.__name__)

        if _safe_issubclass(cls, bpy.types.Operator):
            if not _operator_exists(bl_idname):
                missing_operators.append(f"{cls.__name__}:{bl_idname}")
        elif (
            _safe_issubclass(cls, bpy.types.Panel)
            or _safe_issubclass(cls, bpy.types.Menu)
            or _safe_issubclass(cls, bpy.types.PropertyGroup)
            or _safe_issubclass(cls, bpy.types.AddonPreferences)
        ):
            if not _type_registered(cls):
                missing_types.append(cls.__name__)

    duplicate_bl_idnames = {
        bl_idname: names
        for bl_idname, names in bl_idnames.items()
        if len(names) > 1
    }

    keymap_count = len(getattr(keymap_helpers, "addon_keymaps", []))
    duplicate_keymaps, broken_keymaps = _keymap_diagnostics(getattr(keymap_helpers, "addon_keymaps", []))
    state_properties = {
        "Scene.m8": hasattr(bpy.types.Scene, "m8"),
        "WindowManager.m8": hasattr(bpy.types.WindowManager, "m8"),
        "Object.m8": hasattr(bpy.types.Object, "m8"),
    }
    icon_cache_ready = getattr(m8_icons, "_preview_collection", None) is not None
    stale_paths, stale_scan_meta = _scan_stale_paths(root, return_meta=True)

    status = "OK"
    if registration_errors or missing_operators or missing_types or duplicate_bl_idnames or broken_keymaps:
        status = "ERROR"
    elif keymap_count == 0 or not all(state_properties.values()) or stale_paths or duplicate_keymaps:
        status = "WARNING"

    details = [
        f"Status: {status}",
        f"Root: {root}",
        f"Classes: {len(classes)}",
        (
            "Class breakdown: "
            f"{class_counts['operators']} operators, {class_counts['panels']} panels, "
            f"{class_counts['menus']} menus, {class_counts['property_groups']} property groups, "
            f"{class_counts['preferences']} preferences, {class_counts['other']} other"
        ),
        f"Duplicate class refs: {len(duplicate_class_refs)}",
        f"Registration errors: {len(registration_errors)}",
        f"Missing operators: {len(missing_operators)}",
        f"Missing UI/types: {len(missing_types)}",
        f"Duplicate bl_idnames: {len(duplicate_bl_idnames)}",
        f"Keymaps: {keymap_count}",
        f"Duplicate keymap items: {len(duplicate_keymaps)}",
        f"Broken keymap operators: {len(broken_keymaps)}",
        "State: " + ", ".join(f"{name}={value}" for name, value in state_properties.items()),
        f"Icon previews ready: {icon_cache_ready}",
        f"Stale hard-coded paths: {len(stale_paths)}",
        (
            "Stale path scan: "
            f"{stale_scan_meta['files']} files, "
            f"{stale_scan_meta['duration_ms']:.1f} ms, "
            f"{'cached' if stale_scan_meta['cached'] else 'fresh'}"
        ),
    ]
    if duplicate_class_refs:
        pairs = [f"{name} x{count}" for name, count in duplicate_class_refs.items()]
        details.append("Duplicate class refs list: " + ", ".join(pairs[:12]))
    if registration_errors:
        details.append("Registration errors list: " + ", ".join(registration_errors[:12]))
    if missing_operators:
        details.append("Missing operators list: " + ", ".join(missing_operators[:12]))
    if missing_types:
        details.append("Missing types list: " + ", ".join(missing_types[:12]))
    if duplicate_bl_idnames:
        pairs = [f"{key} -> {', '.join(value)}" for key, value in duplicate_bl_idnames.items()]
        details.append("Duplicate bl_idnames list: " + " | ".join(pairs[:8]))
    if duplicate_keymaps:
        details.append("Duplicate keymap items list: " + ", ".join(duplicate_keymaps[:12]))
    if broken_keymaps:
        details.append("Broken keymap operators list: " + ", ".join(broken_keymaps[:12]))
    if stale_paths:
        details.append("Stale path files: " + ", ".join(stale_paths[:12]))

    return {
        "status": status,
        "summary": (
            f"{status}: {len(classes)} classes, {keymap_count} keymaps, "
            f"{len(missing_operators)} missing ops, {len(missing_types)} missing types"
        ),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "details": "\n".join(details),
    }


def store_health_report(context, report):
    wm_state = getattr(getattr(context, "window_manager", None), "m8", None)
    if not wm_state:
        return False
    wm_state.health_status = report["status"]
    wm_state.health_summary = report["summary"]
    wm_state.health_checked_at = report["checked_at"]
    wm_state.health_details = report["details"]
    return True


def store_full_system_report(context, report):
    wm_state = getattr(getattr(context, "window_manager", None), "m8", None)
    if not wm_state:
        return False
    wm_state.full_check_status = report["status"]
    wm_state.full_check_summary = report["summary"]
    wm_state.full_check_checked_at = report["checked_at"]
    wm_state.full_check_details = report["details"]
    return True


def collect_full_system_report(context, scene_scope="VISIBLE", high_poly_threshold=100000):
    from .scene_audit import (
        DEFAULT_BACKUP_COLLECTION_NAME,
        collect_scene_audit_backup_report,
        collect_scene_audit_report,
        store_scene_audit_backup_report,
        store_scene_audit_report,
    )

    health_report = collect_health_report()
    store_health_report(context, health_report)

    scene_report = collect_scene_audit_report(
        context,
        scene_scope,
        int(high_poly_threshold),
    )
    store_scene_audit_report(context, scene_report)

    wm_state = getattr(context.window_manager, "m8", None)
    backup_name = (
        getattr(wm_state, "scene_audit_backup_collection_name", DEFAULT_BACKUP_COLLECTION_NAME)
        if wm_state
        else DEFAULT_BACKUP_COLLECTION_NAME
    )
    backup_report = collect_scene_audit_backup_report(backup_name)
    store_scene_audit_backup_report(context, backup_report)

    statuses = [health_report["status"], scene_report["status"], backup_report["status"]]
    status = "ERROR" if "ERROR" in statuses else "WARNING" if "WARNING" in statuses else "OK"
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details = "\n\n".join(
        (
            f"Status: {status}",
            f"Checked at: {checked_at}",
            f"Scene scope: {scene_scope}",
            "",
            "[Health]\n" + health_report["details"],
            "[Scene Audit]\n" + scene_report["details"],
            "[Backups]\n" + backup_report["details"],
        )
    )
    summary = (
        f"Full check {status}: health {health_report['status']}, "
        f"scene {scene_report['status']}, backups {backup_report['status']}"
    )
    return {
        "status": status,
        "summary": summary,
        "checked_at": checked_at,
        "details": details,
        "health": health_report,
        "scene_audit": scene_report,
        "backups": backup_report,
    }


class M8_OT_RunHealthCheck(bpy.types.Operator):
    bl_idname = "m8.run_health_check"
    bl_label = "运行 M8 健康检查"
    bl_description = "检查 M8 注册、快捷键、状态属性、图标及失效路径"
    bl_options = {"REGISTER"}

    copy_to_clipboard: bpy.props.BoolProperty(
        name="复制报告",
        default=False,
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        try:
            report = collect_health_report()
            store_health_report(context, report)
            if self.copy_to_clipboard:
                context.window_manager.clipboard = report["details"]
            level = {"OK": "INFO", "WARNING": "WARNING", "ERROR": "ERROR"}.get(report["status"], "INFO")
            self.report({level}, report["summary"])
            return {"FINISHED"}
        except Exception as exc:
            logger.error(f"M8 health check failed: {exc}", exc_info=True)
            self.report({"ERROR"}, f"M8 健康检查失败：{exc}")
            return {"CANCELLED"}


class M8_OT_CopyHealthReport(bpy.types.Operator):
    bl_idname = "m8.copy_health_report"
    bl_label = "复制 M8 健康报告"
    bl_description = "将最新的 M8 健康报告复制到剪贴板"
    bl_options = {"REGISTER"}

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        details = getattr(wm_state, "health_details", "") if wm_state else ""
        if not details:
            report = collect_health_report()
            store_health_report(context, report)
            details = report["details"]
        context.window_manager.clipboard = details
        self.report({"INFO"}, "已复制 M8 健康报告")
        return {"FINISHED"}


class M8_OT_RunFullSystemCheck(bpy.types.Operator):
    bl_idname = "m8.run_full_system_check"
    bl_label = "运行 M8 全系统检查"
    bl_description = "一次性运行 M8 健康、场景审计及备份清单检查"
    bl_options = {"REGISTER"}

    scene_scope: bpy.props.EnumProperty(
        name="场景范围",
        items=[
            ("SELECTED", "已选中", "审计选中的网格物体"),
            ("VISIBLE", "可见", "审计可见的网格物体"),
            ("ALL", "场景", "审计场景中所有网格物体"),
        ],
        default="VISIBLE",
        options={"SKIP_SAVE"},
    )
    high_poly_threshold: bpy.props.IntProperty(
        name="高面数阈值",
        default=100000,
        min=100,
        soft_max=1000000,
        options={"SKIP_SAVE"},
    )
    copy_to_clipboard: bpy.props.BoolProperty(
        name="复制报告",
        default=False,
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        try:
            report = collect_full_system_report(
                context,
                self.scene_scope,
                int(self.high_poly_threshold),
            )
            store_full_system_report(context, report)
            if self.copy_to_clipboard:
                context.window_manager.clipboard = report["details"]

            level = {"OK": "INFO", "WARNING": "WARNING", "ERROR": "ERROR"}.get(report["status"], "INFO")
            self.report({level}, report["summary"])
            return {"FINISHED"}
        except Exception as exc:
            logger.error(f"M8 full system check failed: {exc}", exc_info=True)
            self.report({"ERROR"}, f"M8 全系统检查失败：{exc}")
            return {"CANCELLED"}


class M8_OT_CopyFullSystemReport(bpy.types.Operator):
    bl_idname = "m8.copy_full_system_report"
    bl_label = "复制 M8 全系统报告"
    bl_description = "将最新的 M8 全系统报告复制到剪贴板"
    bl_options = {"REGISTER"}

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        details = getattr(wm_state, "full_check_details", "") if wm_state else ""
        if not details:
            threshold = getattr(wm_state, "scene_audit_high_poly_threshold", 100000) if wm_state else 100000
            report = collect_full_system_report(context, "VISIBLE", threshold)
            store_full_system_report(context, report)
            details = report["details"]
        context.window_manager.clipboard = details
        self.report({"INFO"}, "已复制 M8 全系统报告")
        return {"FINISHED"}
