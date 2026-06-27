from __future__ import annotations

from collections import Counter
from datetime import datetime
import time

import bmesh
import bpy

from ...utils.logger import get_logger


logger = get_logger()

DEFAULT_BACKUP_COLLECTION_NAME = "M8_Audit_Backups"
BACKUP_SOURCE_OBJECT_PROP = "m8_backup_of"
BACKUP_SOURCE_MESH_PROP = "m8_backup_source_mesh"
BACKUP_TIME_PROP = "m8_backup_time"


ISSUE_FILTER_ITEMS = [
    ("ALL", "All Issues", "Objects with any scene audit issue"),
    ("TOPOLOGY", "Topology", "Objects with topology issues"),
    ("SAFE_GEOMETRY", "Safe Geometry", "Objects with loose geometry or zero-area faces"),
    ("NON_MANIFOLD", "Non-Manifold", "Objects with non-manifold edges"),
    ("NGONS", "N-gons", "Objects with faces above four vertices"),
    ("MATERIALS", "Materials", "Objects with material slot issues"),
    ("TRANSFORMS", "Transforms", "Objects with unapplied or negative transforms"),
    ("HIGH_POLY", "High Poly", "Objects above the high-poly threshold"),
]


def _object_rotation_is_applied(obj, tolerance):
    if obj.rotation_mode == "QUATERNION":
        return abs(obj.rotation_quaternion.angle) <= tolerance
    if obj.rotation_mode == "AXIS_ANGLE":
        return abs(obj.rotation_axis_angle[0]) <= tolerance
    return all(abs(value) <= tolerance for value in obj.rotation_euler)


def _mesh_objects(context, scope):
    if scope == "SELECTED":
        objects = context.selected_objects
    elif scope == "VISIBLE":
        objects = [obj for obj in context.view_layer.objects if obj.visible_get()]
    else:
        objects = context.scene.objects
    return [obj for obj in dict.fromkeys(objects) if obj and obj.type == "MESH"]


def _material_slot_metrics(obj):
    slot_count = len(obj.material_slots)
    used_indices = {poly.material_index for poly in obj.data.polygons}
    materials = [slot.material for slot in obj.material_slots]
    named_materials = [mat.name for mat in materials if mat]
    duplicates = sum(count - 1 for count in Counter(named_materials).values() if count > 1)
    empty_slots = sum(1 for mat in materials if mat is None)
    unused_slots = sum(1 for index in range(slot_count) if index not in used_indices)
    return {
        "missing_materials": 1 if slot_count == 0 else 0,
        "empty_material_slots": empty_slots,
        "unused_material_slots": unused_slots,
        "duplicate_material_slots": duplicates,
    }


def _mesh_topology_metrics_bmesh(mesh, zero_area_epsilon):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        loose_verts = sum(1 for vert in bm.verts if not vert.link_edges)
        loose_edges = sum(1 for edge in bm.edges if not edge.link_faces)
        non_manifold_edges = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
        zero_area_faces = sum(1 for face in bm.faces if face.calc_area() <= zero_area_epsilon)
        ngons = sum(1 for face in bm.faces if len(face.verts) > 4)
        return {
            "verts": len(bm.verts),
            "edges": len(bm.edges),
            "faces": len(bm.faces),
            "loose_verts": loose_verts,
            "loose_edges": loose_edges,
            "non_manifold_edges": non_manifold_edges,
            "zero_area_faces": zero_area_faces,
            "ngons": ngons,
        }
    finally:
        bm.free()


def _edge_key(vertices):
    v0, v1 = int(vertices[0]), int(vertices[1])
    return (v0, v1) if v0 <= v1 else (v1, v0)


def _mesh_topology_metrics(mesh, zero_area_epsilon):
    try:
        vert_count = len(mesh.vertices)
        edge_count = len(mesh.edges)
        face_count = len(mesh.polygons)

        verts_with_edges = set()
        edge_face_counts = Counter()
        for edge in mesh.edges:
            v0, v1 = int(edge.vertices[0]), int(edge.vertices[1])
            verts_with_edges.add(v0)
            verts_with_edges.add(v1)

        for poly in mesh.polygons:
            for key in poly.edge_keys:
                edge_face_counts[_edge_key(key)] += 1

        loose_edges = 0
        non_manifold_edges = 0
        for edge in mesh.edges:
            face_uses = edge_face_counts.get(_edge_key(edge.vertices), 0)
            if face_uses == 0:
                loose_edges += 1
            if face_uses != 2:
                non_manifold_edges += 1

        zero_area_faces = sum(1 for poly in mesh.polygons if poly.area <= zero_area_epsilon)
        ngons = sum(1 for poly in mesh.polygons if len(poly.vertices) > 4)
        return {
            "verts": vert_count,
            "edges": edge_count,
            "faces": face_count,
            "loose_verts": vert_count - len(verts_with_edges),
            "loose_edges": loose_edges,
            "non_manifold_edges": non_manifold_edges,
            "zero_area_faces": zero_area_faces,
            "ngons": ngons,
        }
    except Exception as exc:
        logger.debug(f"Fast mesh topology scan failed for {getattr(mesh, 'name', '<mesh>')}: {exc}")
        return _mesh_topology_metrics_bmesh(mesh, zero_area_epsilon)


def _issue_labels(metrics):
    labels = []
    if metrics["unapplied_transform"]:
        labels.append("unapplied transform")
    if metrics["negative_scale"]:
        labels.append("negative scale")
    if metrics["high_poly"]:
        labels.append("high poly")
    for key, label in (
        ("non_manifold_edges", "non-manifold"),
        ("loose_verts", "loose verts"),
        ("loose_edges", "loose edges"),
        ("zero_area_faces", "zero-area faces"),
        ("ngons", "N-gons"),
        ("missing_materials", "no material"),
        ("empty_material_slots", "empty material slots"),
        ("unused_material_slots", "unused material slots"),
        ("duplicate_material_slots", "duplicate materials"),
    ):
        if metrics.get(key, 0):
            labels.append(label)
    return labels


def _object_audit_metrics(
    obj,
    high_poly_threshold,
    zero_area_epsilon=1.0e-12,
    transform_tolerance=0.0001,
    topology_cache=None,
):
    mesh_key = obj.data.as_pointer() if obj.data else 0
    if topology_cache is not None and mesh_key in topology_cache:
        mesh_metrics = topology_cache[mesh_key]
    else:
        mesh_metrics = _mesh_topology_metrics(obj.data, zero_area_epsilon)
        if topology_cache is not None:
            topology_cache[mesh_key] = mesh_metrics
    material_metrics = _material_slot_metrics(obj)
    scale_unapplied = any(abs(value - 1.0) > transform_tolerance for value in obj.scale)
    rotation_unapplied = not _object_rotation_is_applied(obj, transform_tolerance)
    negative_scale = any(value < 0.0 for value in obj.scale)
    return {
        **mesh_metrics,
        **material_metrics,
        "unapplied_transform": 1 if scale_unapplied or rotation_unapplied else 0,
        "negative_scale": 1 if negative_scale else 0,
        "high_poly": 1 if mesh_metrics["faces"] >= high_poly_threshold else 0,
    }


def _metrics_match_filter(metrics, issue_filter):
    if issue_filter == "ALL":
        return bool(_issue_labels(metrics))
    if issue_filter == "TOPOLOGY":
        return any(
            metrics.get(key, 0)
            for key in ("non_manifold_edges", "loose_verts", "loose_edges", "zero_area_faces", "ngons")
        )
    if issue_filter == "SAFE_GEOMETRY":
        return any(metrics.get(key, 0) for key in ("loose_verts", "loose_edges", "zero_area_faces"))
    if issue_filter == "NON_MANIFOLD":
        return bool(metrics.get("non_manifold_edges", 0))
    if issue_filter == "NGONS":
        return bool(metrics.get("ngons", 0))
    if issue_filter == "MATERIALS":
        return any(
            metrics.get(key, 0)
            for key in (
                "missing_materials",
                "empty_material_slots",
                "unused_material_slots",
                "duplicate_material_slots",
            )
        )
    if issue_filter == "TRANSFORMS":
        return bool(metrics.get("unapplied_transform", 0) or metrics.get("negative_scale", 0))
    if issue_filter == "HIGH_POLY":
        return bool(metrics.get("high_poly", 0))
    return False


def collect_scene_audit_report(context, scope="SELECTED", high_poly_threshold=100000):
    started = time.perf_counter()
    objects = _mesh_objects(context, scope)
    topology_cache = {}
    totals = Counter()
    rows = []
    problem_names = []

    for obj in objects:
        metrics = _object_audit_metrics(obj, high_poly_threshold, topology_cache=topology_cache)
        totals.update(metrics)

        labels = _issue_labels(metrics)
        if labels:
            problem_names.append(obj.name)
            rows.append(
                {
                    "name": obj.name,
                    "faces": metrics["faces"],
                    "verts": metrics["verts"],
                    "labels": labels,
                    "metrics": metrics,
                }
            )

    status = "OK"
    if not objects:
        status = "WARNING"
    elif rows:
        status = "WARNING"

    duration_ms = (time.perf_counter() - started) * 1000.0
    details = [
        f"Status: {status}",
        f"Scope: {scope}",
        f"Objects scanned: {len(objects)}",
        f"Unique mesh data scanned: {len(topology_cache)}",
        f"Scan time: {duration_ms:.1f} ms",
        f"Problem objects: {len(rows)}",
        f"Total verts: {totals['verts']}",
        f"Total edges: {totals['edges']}",
        f"Total faces: {totals['faces']}",
        f"Non-manifold edges: {totals['non_manifold_edges']}",
        f"Loose verts: {totals['loose_verts']}",
        f"Loose edges: {totals['loose_edges']}",
        f"Zero-area faces: {totals['zero_area_faces']}",
        f"N-gons: {totals['ngons']}",
        f"Unapplied transform objects: {totals['unapplied_transform']}",
        f"Negative scale objects: {totals['negative_scale']}",
        f"High-poly threshold: {high_poly_threshold}",
        f"High-poly objects: {totals['high_poly']}",
        f"Objects without materials: {totals['missing_materials']}",
        f"Empty material slots: {totals['empty_material_slots']}",
        f"Unused material slots: {totals['unused_material_slots']}",
        f"Duplicate material slots: {totals['duplicate_material_slots']}",
    ]

    if rows:
        details.append("")
        details.append("Problem object sample:")
        for row in rows[:25]:
            details.append(
                f"- {row['name']} ({row['verts']} verts, {row['faces']} faces): "
                + ", ".join(row["labels"])
            )

    summary = (
        f"{status}: {len(objects)} mesh objects scanned, {len(rows)} need attention, "
        f"{totals['non_manifold_edges']} non-manifold edges, {totals['ngons']} N-gons"
    )
    return {
        "status": status,
        "summary": summary,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "details": "\n".join(details),
        "problem_names": problem_names,
        "scope": scope,
        "duration_ms": duration_ms,
        "unique_meshes": len(topology_cache),
    }


def store_scene_audit_report(context, report):
    wm_state = getattr(getattr(context, "window_manager", None), "m8", None)
    if not wm_state:
        return False
    wm_state.scene_audit_status = report["status"]
    wm_state.scene_audit_summary = report["summary"]
    wm_state.scene_audit_checked_at = report["checked_at"]
    wm_state.scene_audit_details = report["details"]
    wm_state.scene_audit_problem_objects = "\n".join(report["problem_names"])
    wm_state.scene_audit_last_scope = report.get("scope", "SELECTED")
    return True


def _ensure_object_mode(context):
    if context.mode == "OBJECT":
        return True
    try:
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="OBJECT")
            return True
    except Exception:
        pass
    return context.mode == "OBJECT"


def _cleanup_mesh_geometry(mesh, zero_area_epsilon=1.0e-12):
    bm = bmesh.new()
    removed = Counter()
    changed = False
    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()

        zero_faces = [face for face in bm.faces if face.calc_area() <= zero_area_epsilon]
        for face in zero_faces:
            try:
                bm.faces.remove(face)
                removed["zero_area_faces"] += 1
                changed = True
            except ValueError:
                pass

        bm.edges.ensure_lookup_table()
        loose_edges = [edge for edge in bm.edges if not edge.link_faces]
        for edge in loose_edges:
            try:
                bm.edges.remove(edge)
                removed["loose_edges"] += 1
                changed = True
            except ValueError:
                pass

        bm.verts.ensure_lookup_table()
        loose_verts = [vert for vert in bm.verts if not vert.link_edges]
        for vert in loose_verts:
            try:
                bm.verts.remove(vert)
                removed["loose_verts"] += 1
                changed = True
            except ValueError:
                pass

        if changed:
            bm.to_mesh(mesh)
            mesh.update()
    finally:
        bm.free()
    return removed


def _cleanup_material_slots(obj):
    mesh = obj.data
    old_materials = [slot.material for slot in obj.material_slots]
    old_poly_indices = [poly.material_index for poly in mesh.polygons]
    used_indices = {index for index in old_poly_indices if 0 <= index < len(old_materials)}
    old_to_new = {}
    new_materials = []
    material_to_new = {}
    removed = Counter()

    for index, mat in enumerate(old_materials):
        if mat is None:
            removed["empty_material_slots"] += 1
            continue
        if index not in used_indices:
            removed["unused_material_slots"] += 1
            continue

        key = mat.as_pointer()
        if key in material_to_new:
            old_to_new[index] = material_to_new[key]
            removed["duplicate_material_slots"] += 1
            continue

        new_index = len(new_materials)
        material_to_new[key] = new_index
        old_to_new[index] = new_index
        new_materials.append(mat)

    if (
        removed["empty_material_slots"] == 0
        and removed["unused_material_slots"] == 0
        and removed["duplicate_material_slots"] == 0
    ):
        return removed

    mesh.materials.clear()
    for mat in new_materials:
        mesh.materials.append(mat)

    fallback_index = 0
    for poly, old_index in zip(mesh.polygons, old_poly_indices):
        poly.material_index = old_to_new.get(old_index, fallback_index)
    mesh.update()
    return removed


def _backup_collection(context, collection_name):
    collection_name = (collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip() or DEFAULT_BACKUP_COLLECTION_NAME
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)

    scene_children = context.scene.collection.children
    if collection.name not in [child.name for child in scene_children]:
        scene_children.link(collection)
    return collection


def _backup_object_for_safe_fix(context, obj, collection_name, timestamp):
    collection = _backup_collection(context, collection_name)
    backup = obj.copy()
    backup.data = obj.data.copy()
    backup.animation_data_clear()
    backup.name = f"{obj.name}_M8AuditBackup_{timestamp}"
    backup.data.name = f"{obj.data.name}_M8AuditBackup_{timestamp}"
    backup.hide_viewport = True
    backup.hide_render = True
    backup[BACKUP_SOURCE_OBJECT_PROP] = obj.name
    backup[BACKUP_SOURCE_MESH_PROP] = obj.data.name
    backup[BACKUP_TIME_PROP] = timestamp
    collection.objects.link(backup)
    return backup


def _is_scene_audit_backup(obj):
    return bool(
        obj
        and obj.type == "MESH"
        and obj.data
        and obj.get(BACKUP_SOURCE_OBJECT_PROP)
        and obj.get(BACKUP_TIME_PROP)
    )


def _scene_audit_backups_from_collection(collection_name):
    collection_name = (collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip() or DEFAULT_BACKUP_COLLECTION_NAME
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        return []
    return [obj for obj in collection.objects if _is_scene_audit_backup(obj)]


def _backup_sort_key(backup):
    return (str(backup.get(BACKUP_TIME_PROP, "")), backup.name)


def _latest_backups_by_source(backups):
    latest = {}
    for backup in backups:
        source_name = str(backup.get(BACKUP_SOURCE_OBJECT_PROP, "")).strip()
        if not source_name:
            continue
        current = latest.get(source_name)
        if current is None or _backup_sort_key(backup) > _backup_sort_key(current):
            latest[source_name] = backup
    return [latest[source_name] for source_name in sorted(latest)]


def _backups_by_source(backups):
    grouped = {}
    for backup in backups:
        source_name = str(backup.get(BACKUP_SOURCE_OBJECT_PROP, "")).strip()
        if not source_name:
            source_name = "<missing source marker>"
        grouped.setdefault(source_name, []).append(backup)
    for source_backups in grouped.values():
        source_backups.sort(key=_backup_sort_key, reverse=True)
    return grouped


def collect_scene_audit_backup_report(collection_name=DEFAULT_BACKUP_COLLECTION_NAME):
    collection_name = (collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip() or DEFAULT_BACKUP_COLLECTION_NAME
    backups = sorted(_scene_audit_backups_from_collection(collection_name), key=_backup_sort_key, reverse=True)
    grouped = _backups_by_source(backups)
    missing_sources = [
        backup
        for backup in backups
        if not bpy.data.objects.get(str(backup.get(BACKUP_SOURCE_OBJECT_PROP, "")).strip())
    ]

    total_verts = sum(len(backup.data.vertices) for backup in backups if backup.data)
    total_faces = sum(len(backup.data.polygons) for backup in backups if backup.data)
    latest_time = str(backups[0].get(BACKUP_TIME_PROP, "")) if backups else ""

    status = "OK"
    if not backups:
        status = "WARNING"
    elif missing_sources:
        status = "WARNING"

    details = [
        f"Status: {status}",
        f"Backup collection: {collection_name}",
        f"Backups: {len(backups)}",
        f"Source objects: {len(grouped)}",
        f"Missing source objects: {len(missing_sources)}",
        f"Total backup verts: {total_verts}",
        f"Total backup faces: {total_faces}",
    ]
    if latest_time:
        details.append(f"Latest backup: {latest_time}")

    if backups:
        details.append("")
        details.append("Latest backup sample:")
        for backup in backups[:25]:
            source_name = str(backup.get(BACKUP_SOURCE_OBJECT_PROP, "")).strip()
            source_exists = bool(bpy.data.objects.get(source_name))
            source_state = "source ok" if source_exists else "missing source"
            details.append(
                f"- {backup.get(BACKUP_TIME_PROP, '')} | {source_name} -> {backup.name} "
                f"({len(backup.data.vertices)} verts, {len(backup.data.polygons)} faces, {source_state})"
            )

    summary = (
        f"{status}: {len(backups)} backups for {len(grouped)} objects, "
        f"{len(missing_sources)} missing sources"
    )
    return {
        "status": status,
        "summary": summary,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "details": "\n".join(details),
        "backup_count": len(backups),
        "source_count": len(grouped),
        "missing_source_count": len(missing_sources),
        "collection_name": collection_name,
    }


def store_scene_audit_backup_report(context, report):
    wm_state = getattr(getattr(context, "window_manager", None), "m8", None)
    if not wm_state:
        return False
    wm_state.scene_audit_backup_status = report["status"]
    wm_state.scene_audit_backup_summary = report["summary"]
    wm_state.scene_audit_backup_checked_at = report["checked_at"]
    wm_state.scene_audit_backup_details = report["details"]
    wm_state.scene_audit_backup_count = report["backup_count"]
    wm_state.scene_audit_backup_source_count = report["source_count"]
    wm_state.scene_audit_backup_missing_source_count = report["missing_source_count"]
    wm_state.scene_audit_backup_collection_name = report["collection_name"]
    return True


def _prune_old_backups(backups, keep_per_source=1):
    keep_per_source = max(0, int(keep_per_source))
    grouped = _backups_by_source(backups)
    to_remove = []
    kept = []
    for source_backups in grouped.values():
        kept.extend(source_backups[:keep_per_source])
        to_remove.extend(source_backups[keep_per_source:])

    for backup in to_remove:
        _remove_backup_object(backup)
    return kept, to_remove


def _restore_backup_to_source(backup):
    source_name = str(backup.get(BACKUP_SOURCE_OBJECT_PROP, "")).strip()
    if not source_name:
        return None, f"{backup.name}: missing source object marker"

    target = bpy.data.objects.get(source_name)
    if target is None:
        return None, f"{backup.name}: source object '{source_name}' no longer exists"
    if target.type != "MESH":
        return None, f"{backup.name}: source object '{source_name}' is not a mesh"
    if backup.data is None:
        return None, f"{backup.name}: backup mesh data is missing"

    restored_mesh = backup.data.copy()
    source_mesh_name = str(backup.get(BACKUP_SOURCE_MESH_PROP, "")).strip()
    if source_mesh_name:
        restored_mesh.name = f"{source_mesh_name}_M8Restored"
    target.data = restored_mesh
    target.update_tag()
    return target, ""


def _remove_backup_object(backup):
    mesh = backup.data
    bpy.data.objects.remove(backup, do_unlink=True)
    if mesh and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def _select_objects(context, objects):
    if not objects:
        return
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_viewport = False
        obj.hide_set(False)
        obj.select_set(True)
    context.view_layer.objects.active = objects[0]


def _restore_backup_objects(context, backups, delete_backups=False):
    restored_targets = []
    skipped = []

    for backup in backups:
        target, reason = _restore_backup_to_source(backup)
        if target is None:
            skipped.append(reason)
            continue
        restored_targets.append(target)
        if delete_backups:
            _remove_backup_object(backup)

    unique_targets = list(dict.fromkeys(restored_targets))
    if unique_targets:
        _select_objects(context, unique_targets)

    summary = f"Restored {len(restored_targets)}/{len(backups)} backups"
    if skipped:
        summary += f", {len(skipped)} skipped"
    return unique_targets, skipped, summary


def _append_fix_history(wm_state, line, max_lines=8):
    existing = getattr(wm_state, "scene_audit_fix_history", "") if wm_state else ""
    lines = [line] + [item for item in existing.splitlines() if item]
    wm_state.scene_audit_fix_history = "\n".join(lines[:max_lines])


class M8_OT_RunSceneAudit(bpy.types.Operator):
    bl_idname = "m8.run_scene_audit"
    bl_label = "运行 M8 场景审计"
    bl_description = "扫描网格物体的拓扑、变换、材质和密度问题"
    bl_options = {"REGISTER"}

    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("SELECTED", "Selected", "Scan selected mesh objects"),
            ("VISIBLE", "Visible", "Scan visible mesh objects in the current view layer"),
            ("ALL", "Scene", "Scan all mesh objects in the scene"),
        ],
        default="SELECTED",
        options={"SKIP_SAVE"},
    )
    high_poly_threshold: bpy.props.IntProperty(
        name="High Poly Threshold",
        default=100000,
        min=100,
        soft_max=1000000,
        options={"SKIP_SAVE"},
    )
    copy_to_clipboard: bpy.props.BoolProperty(
        name="Copy Report",
        default=False,
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        try:
            threshold = int(self.high_poly_threshold)
            wm_state = getattr(context.window_manager, "m8", None)
            if wm_state:
                wm_state.scene_audit_high_poly_threshold = threshold
            report = collect_scene_audit_report(context, self.scope, threshold)
            store_scene_audit_report(context, report)
            if self.copy_to_clipboard:
                context.window_manager.clipboard = report["details"]
            level = "WARNING" if report["status"] == "WARNING" else "INFO"
            self.report({level}, report["summary"])
            return {"FINISHED"}
        except Exception as exc:
            logger.error(f"M8 scene audit failed: {exc}", exc_info=True)
            self.report({"ERROR"}, f"M8 scene audit failed: {exc}")
            return {"CANCELLED"}


class M8_OT_CopySceneAuditReport(bpy.types.Operator):
    bl_idname = "m8.copy_scene_audit_report"
    bl_label = "复制 M8 场景审计报告"
    bl_description = "将最新的 M8 场景审计报告复制到剪贴板"
    bl_options = {"REGISTER"}

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        details = getattr(wm_state, "scene_audit_details", "") if wm_state else ""
        if not details:
            threshold = getattr(wm_state, "scene_audit_high_poly_threshold", 100000) if wm_state else 100000
            report = collect_scene_audit_report(context, "SELECTED", threshold)
            store_scene_audit_report(context, report)
            details = report["details"]
        context.window_manager.clipboard = details
        self.report({"INFO"}, "已复制 M8 场景审计报告")
        return {"FINISHED"}


class M8_OT_SelectSceneAuditIssueObjects(bpy.types.Operator):
    bl_idname = "m8.select_scene_audit_issue_objects"
    bl_label = "选择 M8 场景审计问题物体"
    bl_description = "重新扫描并选择匹配特定 M8 场景审计问题类型的物体"
    bl_options = {"REGISTER", "UNDO"}

    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("SELECTED", "Selected", "Scan selected mesh objects"),
            ("VISIBLE", "Visible", "Scan visible mesh objects in the current view layer"),
            ("ALL", "Scene", "Scan all mesh objects in the scene"),
        ],
        default="SELECTED",
        options={"SKIP_SAVE"},
    )
    issue_filter: bpy.props.EnumProperty(
        name="Issue",
        items=ISSUE_FILTER_ITEMS,
        default="ALL",
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        threshold = getattr(wm_state, "scene_audit_high_poly_threshold", 100000) if wm_state else 100000
        objects = _mesh_objects(context, self.scope)
        topology_cache = {}
        matches = [
            obj
            for obj in objects
            if _metrics_match_filter(
                _object_audit_metrics(obj, threshold, topology_cache=topology_cache),
                self.issue_filter,
            )
        ]

        if not matches:
            self.report({"WARNING"}, "没有匹配所选问题类型的物体")
            return {"CANCELLED"}

        bpy.ops.object.select_all(action="DESELECT")
        for obj in matches:
            obj.select_set(True)
        context.view_layer.objects.active = matches[0]
        self.report({"INFO"}, f"Selected {len(matches)} objects")
        return {"FINISHED"}


class M8_OT_FixSceneAuditSafeIssues(bpy.types.Operator):
    bl_idname = "m8.fix_scene_audit_safe_issues"
    bl_label = "修复 M8 场景审计安全问题"
    bl_description = "移除松散几何体、零面积面以及未使用/空/重复的材质槽"
    bl_options = {"REGISTER", "UNDO"}

    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("SELECTED", "Selected", "Fix selected mesh objects"),
            ("VISIBLE", "Visible", "Fix visible mesh objects in the current view layer"),
            ("ALL", "Scene", "Fix all mesh objects in the scene"),
        ],
        default="SELECTED",
        options={"SKIP_SAVE"},
    )
    fix_geometry: bpy.props.BoolProperty(name="Geometry", default=True, options={"SKIP_SAVE"})
    fix_materials: bpy.props.BoolProperty(name="Materials", default=True, options={"SKIP_SAVE"})
    rescan: bpy.props.BoolProperty(name="Rescan", default=True, options={"SKIP_SAVE"})
    make_backup: bpy.props.BoolProperty(name="Backup", default=True, options={"SKIP_SAVE"})
    backup_collection_name: bpy.props.StringProperty(
        name="Backup Collection",
        default="M8_Audit_Backups",
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        if not _ensure_object_mode(context):
            self.report({"ERROR"}, "执行安全修复前请切换到物体模式")
            return {"CANCELLED"}

        objects = _mesh_objects(context, self.scope)
        if not objects:
            self.report({"WARNING"}, "没有可修复的网格物体")
            return {"CANCELLED"}

        wm_state = getattr(context.window_manager, "m8", None)
        threshold = getattr(wm_state, "scene_audit_high_poly_threshold", 100000) if wm_state else 100000
        backup_name = (self.backup_collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip()
        backup_name = backup_name or DEFAULT_BACKUP_COLLECTION_NAME
        if wm_state:
            if backup_name == DEFAULT_BACKUP_COLLECTION_NAME:
                backup_name = getattr(wm_state, "scene_audit_backup_collection_name", backup_name)
            wm_state.scene_audit_make_backup = bool(self.make_backup)
            wm_state.scene_audit_backup_collection_name = backup_name

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        removed = Counter()
        changed_objects = 0
        backup_count = 0
        for obj in objects:
            before = sum(removed.values())
            metrics = _object_audit_metrics(obj, threshold)
            should_backup = self.make_backup and (
                (self.fix_geometry and _metrics_match_filter(metrics, "SAFE_GEOMETRY"))
                or (self.fix_materials and _metrics_match_filter(metrics, "MATERIALS"))
            )
            if should_backup:
                _backup_object_for_safe_fix(context, obj, backup_name, timestamp)
                backup_count += 1

            if self.fix_geometry:
                removed.update(_cleanup_mesh_geometry(obj.data))
            if self.fix_materials:
                removed.update(_cleanup_material_slots(obj))
            if sum(removed.values()) > before:
                changed_objects += 1

        summary = (
            f"Fixed {changed_objects}/{len(objects)} objects: "
            f"{removed['loose_verts']} loose verts, {removed['loose_edges']} loose edges, "
            f"{removed['zero_area_faces']} zero-area faces, "
            f"{removed['empty_material_slots']} empty slots, "
            f"{removed['unused_material_slots']} unused slots, "
            f"{removed['duplicate_material_slots']} duplicate slots, "
            f"{backup_count} backups"
        )

        if wm_state:
            wm_state.scene_audit_last_fix_summary = summary
            _append_fix_history(wm_state, f"{datetime.now().strftime('%H:%M:%S')} {summary}")

        if self.rescan:
            report = collect_scene_audit_report(context, self.scope, threshold)
            store_scene_audit_report(context, report)
        if self.make_backup:
            backup_report = collect_scene_audit_backup_report(backup_name)
            store_scene_audit_backup_report(context, backup_report)

        self.report({"INFO"}, summary)
        return {"FINISHED"}


class M8_OT_SelectSceneAuditBackups(bpy.types.Operator):
    bl_idname = "m8.select_scene_audit_backups"
    bl_label = "选择 M8 场景审计备份"
    bl_description = "显示并选择 M8 场景审计备份物体"
    bl_options = {"REGISTER", "UNDO"}

    backup_collection_name: bpy.props.StringProperty(
        name="Backup Collection",
        default=DEFAULT_BACKUP_COLLECTION_NAME,
        options={"SKIP_SAVE"},
    )
    reveal: bpy.props.BoolProperty(name="Reveal", default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        backup_name = (self.backup_collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip()
        backup_name = backup_name or DEFAULT_BACKUP_COLLECTION_NAME
        if wm_state and backup_name == DEFAULT_BACKUP_COLLECTION_NAME:
            backup_name = getattr(wm_state, "scene_audit_backup_collection_name", backup_name)

        backups = sorted(_scene_audit_backups_from_collection(backup_name), key=_backup_sort_key, reverse=True)
        if not backups:
            self.report({"WARNING"}, f"No M8 scene audit backups found in '{backup_name}'")
            return {"CANCELLED"}

        bpy.ops.object.select_all(action="DESELECT")
        for backup in backups:
            if self.reveal:
                backup.hide_viewport = False
                backup.hide_set(False)
            backup.select_set(True)
        context.view_layer.objects.active = backups[0]

        self.report({"INFO"}, f"Selected {len(backups)} M8 backup objects")
        return {"FINISHED"}


class M8_OT_RestoreSceneAuditSelectedBackups(bpy.types.Operator):
    bl_idname = "m8.restore_scene_audit_selected_backups"
    bl_label = "恢复选中的 M8 场景审计备份"
    bl_description = "从选中的 M8 场景审计备份恢复原始网格物体"
    bl_options = {"REGISTER", "UNDO"}

    delete_backups: bpy.props.BoolProperty(
        name="Delete Backups After Restore",
        default=False,
        options={"SKIP_SAVE"},
    )
    rescan: bpy.props.BoolProperty(name="Rescan", default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        if not _ensure_object_mode(context):
            self.report({"ERROR"}, "恢复备份前请切换到物体模式")
            return {"CANCELLED"}

        backups = sorted(
            [obj for obj in context.selected_objects if _is_scene_audit_backup(obj)],
            key=_backup_sort_key,
        )
        if not backups:
            self.report({"WARNING"}, "请先选择一个或多个 M8 场景审计备份物体")
            return {"CANCELLED"}

        restored, skipped, summary = _restore_backup_objects(context, backups, self.delete_backups)
        if not restored:
            self.report({"WARNING"}, summary)
            return {"CANCELLED"}

        wm_state = getattr(context.window_manager, "m8", None)
        if wm_state:
            wm_state.scene_audit_last_restore_summary = summary
            _append_fix_history(wm_state, f"{datetime.now().strftime('%H:%M:%S')} {summary}")
            if self.rescan:
                threshold = getattr(wm_state, "scene_audit_high_poly_threshold", 100000)
                report = collect_scene_audit_report(context, "SELECTED", threshold)
                store_scene_audit_report(context, report)
            backup_report = collect_scene_audit_backup_report(
                getattr(wm_state, "scene_audit_backup_collection_name", DEFAULT_BACKUP_COLLECTION_NAME)
            )
            store_scene_audit_backup_report(context, backup_report)

        level = "WARNING" if skipped else "INFO"
        self.report({level}, summary)
        return {"FINISHED"}


class M8_OT_RestoreSceneAuditLatestBackups(bpy.types.Operator):
    bl_idname = "m8.restore_scene_audit_latest_backups"
    bl_label = "恢复最新的 M8 场景审计备份"
    bl_description = "从每个源网格物体的最新 M8 场景审计备份中恢复"
    bl_options = {"REGISTER", "UNDO"}

    backup_collection_name: bpy.props.StringProperty(
        name="Backup Collection",
        default=DEFAULT_BACKUP_COLLECTION_NAME,
        options={"SKIP_SAVE"},
    )
    delete_backups: bpy.props.BoolProperty(
        name="Delete Backups After Restore",
        default=False,
        options={"SKIP_SAVE"},
    )
    rescan: bpy.props.BoolProperty(name="Rescan", default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        if not _ensure_object_mode(context):
            self.report({"ERROR"}, "恢复备份前请切换到物体模式")
            return {"CANCELLED"}

        wm_state = getattr(context.window_manager, "m8", None)
        backup_name = (self.backup_collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip()
        backup_name = backup_name or DEFAULT_BACKUP_COLLECTION_NAME
        if wm_state and backup_name == DEFAULT_BACKUP_COLLECTION_NAME:
            backup_name = getattr(wm_state, "scene_audit_backup_collection_name", backup_name)

        backups = _scene_audit_backups_from_collection(backup_name)
        latest_backups = _latest_backups_by_source(backups)
        if not latest_backups:
            self.report({"WARNING"}, f"No M8 scene audit backups found in '{backup_name}'")
            return {"CANCELLED"}

        restored, skipped, summary = _restore_backup_objects(context, latest_backups, self.delete_backups)
        if not restored:
            self.report({"WARNING"}, summary)
            return {"CANCELLED"}

        if wm_state:
            wm_state.scene_audit_last_restore_summary = summary
            _append_fix_history(wm_state, f"{datetime.now().strftime('%H:%M:%S')} {summary}")
            if self.rescan:
                threshold = getattr(wm_state, "scene_audit_high_poly_threshold", 100000)
                report = collect_scene_audit_report(context, "SELECTED", threshold)
                store_scene_audit_report(context, report)
            backup_report = collect_scene_audit_backup_report(backup_name)
            store_scene_audit_backup_report(context, backup_report)

        level = "WARNING" if skipped else "INFO"
        self.report({level}, summary)
        return {"FINISHED"}


class M8_OT_RefreshSceneAuditBackups(bpy.types.Operator):
    bl_idname = "m8.refresh_scene_audit_backups"
    bl_label = "刷新 M8 场景审计备份"
    bl_description = "刷新 M8 场景审计备份清单"
    bl_options = {"REGISTER"}

    backup_collection_name: bpy.props.StringProperty(
        name="Backup Collection",
        default=DEFAULT_BACKUP_COLLECTION_NAME,
        options={"SKIP_SAVE"},
    )
    copy_to_clipboard: bpy.props.BoolProperty(
        name="Copy Report",
        default=False,
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        backup_name = (self.backup_collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip()
        backup_name = backup_name or DEFAULT_BACKUP_COLLECTION_NAME
        if wm_state and backup_name == DEFAULT_BACKUP_COLLECTION_NAME:
            backup_name = getattr(wm_state, "scene_audit_backup_collection_name", backup_name)

        report = collect_scene_audit_backup_report(backup_name)
        store_scene_audit_backup_report(context, report)
        if self.copy_to_clipboard:
            context.window_manager.clipboard = report["details"]

        level = "WARNING" if report["status"] == "WARNING" else "INFO"
        self.report({level}, report["summary"])
        return {"FINISHED"}


class M8_OT_CopySceneAuditBackupReport(bpy.types.Operator):
    bl_idname = "m8.copy_scene_audit_backup_report"
    bl_label = "复制 M8 场景审计备份报告"
    bl_description = "将最新的 M8 场景审计备份清单复制到剪贴板"
    bl_options = {"REGISTER"}

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        details = getattr(wm_state, "scene_audit_backup_details", "") if wm_state else ""
        if not details:
            backup_name = (
                getattr(wm_state, "scene_audit_backup_collection_name", DEFAULT_BACKUP_COLLECTION_NAME)
                if wm_state
                else DEFAULT_BACKUP_COLLECTION_NAME
            )
            report = collect_scene_audit_backup_report(backup_name)
            store_scene_audit_backup_report(context, report)
            details = report["details"]
        context.window_manager.clipboard = details
        self.report({"INFO"}, "已复制 M8 场景审计备份报告")
        return {"FINISHED"}


class M8_OT_PruneSceneAuditBackups(bpy.types.Operator):
    bl_idname = "m8.prune_scene_audit_backups"
    bl_label = "清理 M8 场景审计备份"
    bl_description = "删除较早的 M8 场景审计备份，每个源物体仅保留最新的若干份"
    bl_options = {"REGISTER", "UNDO"}

    backup_collection_name: bpy.props.StringProperty(
        name="备份集合",
        default=DEFAULT_BACKUP_COLLECTION_NAME,
        options={"SKIP_SAVE"},
    )
    keep_per_source: bpy.props.IntProperty(
        name="每个源物体保留份数",
        default=2,
        min=1,
        soft_max=10,
        options={"SKIP_SAVE"},
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if not _ensure_object_mode(context):
            self.report({"ERROR"}, "清理备份前请切换到物体模式")
            return {"CANCELLED"}

        wm_state = getattr(context.window_manager, "m8", None)
        backup_name = (self.backup_collection_name or DEFAULT_BACKUP_COLLECTION_NAME).strip()
        backup_name = backup_name or DEFAULT_BACKUP_COLLECTION_NAME
        if wm_state and backup_name == DEFAULT_BACKUP_COLLECTION_NAME:
            backup_name = getattr(wm_state, "scene_audit_backup_collection_name", backup_name)

        backups = _scene_audit_backups_from_collection(backup_name)
        if not backups:
            self.report({"WARNING"}, f"在 '{backup_name}' 中未找到 M8 场景审计备份")
            return {"CANCELLED"}

        kept, removed = _prune_old_backups(backups, self.keep_per_source)
        summary = f"已清理 {len(removed)} 个旧备份，保留 {len(kept)} 个"
        report = collect_scene_audit_backup_report(backup_name)
        store_scene_audit_backup_report(context, report)

        if wm_state:
            wm_state.scene_audit_backup_keep_per_source = int(self.keep_per_source)
            wm_state.scene_audit_last_backup_manage_summary = summary
            _append_fix_history(wm_state, f"{datetime.now().strftime('%H:%M:%S')} {summary}")

        self.report({"INFO"}, summary)
        return {"FINISHED"}


class M8_OT_SelectSceneAuditProblemObjects(bpy.types.Operator):
    bl_idname = "m8.select_scene_audit_problem_objects"
    bl_label = "选择 M8 场景审计问题物体"
    bl_description = "选择最新的 M8 场景审计报告中列出的物体"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        wm_state = getattr(context.window_manager, "m8", None)
        names_text = getattr(wm_state, "scene_audit_problem_objects", "") if wm_state else ""
        names = [name for name in names_text.splitlines() if name]
        if not names:
            self.report({"WARNING"}, "最新的场景审计中没有问题物体")
            return {"CANCELLED"}

        selected = []
        bpy.ops.object.select_all(action="DESELECT")
        for name in names:
            obj = bpy.data.objects.get(name)
            if obj:
                obj.select_set(True)
                selected.append(obj)
        if selected:
            context.view_layer.objects.active = selected[0]
            self.report({"INFO"}, f"已选中 {len(selected)} 个问题物体")
            return {"FINISHED"}

        self.report({"WARNING"}, "问题物体已不存在")
        return {"CANCELLED"}
