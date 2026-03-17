import bpy
import bmesh
from mathutils import Matrix, Vector

from ...utils import ensure_object_mode, call_object_op_with_selection


def _call_op_or_none(op, *args, **kwargs):
    try:
        if hasattr(op, "poll") and not op.poll():
            return None
        return op(*args, **kwargs)
    except Exception:
        return None


def _is_cancelled(result) -> bool:
    try:
        return isinstance(result, set) and "CANCELLED" in result
    except Exception:
        return False


def _matrix_location(matrix: Matrix) -> Matrix:
    return Matrix.Translation(matrix.translation)


def _matrix_rotation(matrix: Matrix) -> Matrix:
    return matrix.to_euler().to_matrix().to_4x4()


def _matrix_scale(matrix: Matrix) -> Matrix:
    s = matrix.to_scale()
    return Matrix.Diagonal(Vector((s.x, s.y, s.z, 1.0)))


def _compose_target_matrix(source: Matrix, target: Matrix, only_location: bool, only_rotation: bool) -> Matrix:
    a_loc = _matrix_location(source)
    a_rot = _matrix_rotation(source)
    a_sca = _matrix_scale(source)

    b_loc = _matrix_location(target)
    b_rot = _matrix_rotation(target)

    if only_location:
        return b_loc @ a_rot @ a_sca
    if only_rotation:
        return a_loc @ b_rot @ a_sca
    return b_loc @ b_rot @ a_sca


def _normalize(v: Vector) -> Vector:
    try:
        if v.length == 0:
            return v
        return v.normalized()
    except Exception:
        return v


def _cursor_matrix_from_axes_location(x: Vector, y: Vector, z: Vector, loc: Vector) -> Matrix:
    m = Matrix.Identity(4)
    m.col[0].xyz = x
    m.col[1].xyz = y
    m.col[2].xyz = z
    m.translation = loc
    return m


def _apply_axis_continuity(context, x: Vector, y: Vector, z: Vector) -> tuple[Vector, Vector, Vector]:
    wm = getattr(context, "window_manager", None)
    if not wm:
        return x, y, z
    try:
        prev = getattr(wm, "m8_cursor_z_axis", None)
        if prev is None:
            return x, y, z
        prev_v = Vector((prev[0], prev[1], prev[2]))
        if prev_v.length == 0:
            return x, y, z
        if z.dot(prev_v) < 0:
            return -x, -y, -z
    except Exception:
        return x, y, z
    return x, y, z


def _store_axis_continuity(context, z: Vector) -> None:
    wm = getattr(context, "window_manager", None)
    if not wm:
        return
    try:
        setattr(wm, "m8_cursor_z_axis", (float(z.x), float(z.y), float(z.z)))
    except Exception:
        pass


def _apply_matrix_continuity(context, m: Matrix | None) -> Matrix | None:
    if m is None:
        return None
    try:
        x = Vector(m.col[0].xyz)
        y = Vector(m.col[1].xyz)
        z = Vector(m.col[2].xyz)
        x, y, z = _apply_axis_continuity(context, x, y, z)
        m.col[0].xyz = x
        m.col[1].xyz = y
        m.col[2].xyz = z
        _store_axis_continuity(context, z)
        return m
    except Exception:
        return m


def _make_orthonormal_axes(z_axis: Vector, x_hint: Vector) -> tuple[Vector, Vector, Vector]:
    z = _normalize(z_axis)
    xh = _normalize(x_hint)
    if z.length == 0:
        z = Vector((0.0, 0.0, 1.0))
    if xh.length == 0 or abs(z.dot(xh)) > 0.999:
        xh = Vector((1.0, 0.0, 0.0)) if abs(z.dot(Vector((1.0, 0.0, 0.0)))) < 0.999 else Vector((0.0, 1.0, 0.0))
    y = _normalize(z.cross(xh))
    x = _normalize(y.cross(z))
    return x, y, z


def _selected_verts_min_max_world(bm, obj_mat: Matrix) -> tuple[Vector, Vector] | None:
    min_v = None
    max_v = None
    for v in bm.verts:
        if not v.select:
            continue
        co = obj_mat @ v.co
        if min_v is None:
            min_v = co.copy()
            max_v = co.copy()
        else:
            min_v.x = min(min_v.x, co.x)
            min_v.y = min(min_v.y, co.y)
            min_v.z = min(min_v.z, co.z)
            max_v.x = max(max_v.x, co.x)
            max_v.y = max(max_v.y, co.y)
            max_v.z = max(max_v.z, co.z)
    if min_v is None or max_v is None:
        return None
    return min_v, max_v


def _mesh_active_element_matrix_or_none(obj) -> Matrix | None:
    if not obj or obj.type != "MESH" or not getattr(obj, "data", None):
        return None
    try:
        bm = bmesh.from_edit_mesh(obj.data)
    except Exception:
        return None
    obj_mat = obj.matrix_world.copy()
    active = bm.select_history.active

    if isinstance(active, bmesh.types.BMFace):
        verts = active.verts[:]
        if not verts:
            return None
        loc_local = Vector()
        for v in verts:
            loc_local += v.co
        loc_local /= len(verts)
        loc = obj_mat @ loc_local
        z_axis = (obj_mat.to_3x3() @ active.normal).normalized()
        x_hint = obj_mat.to_3x3() @ (verts[1].co - verts[0].co)
        x, y, z = _make_orthonormal_axes(z_axis, x_hint)
        return _cursor_matrix_from_axes_location(x, y, z, loc)

    if isinstance(active, bmesh.types.BMEdge):
        a, b = active.verts[0], active.verts[1]
        loc = obj_mat @ ((a.co + b.co) / 2.0)
        x_hint = obj_mat.to_3x3() @ (b.co - a.co)
        z_axis = Vector((0.0, 0.0, 1.0))
        if active.link_faces:
            n = Vector()
            for f in active.link_faces:
                n += f.normal
            if n.length != 0:
                z_axis = obj_mat.to_3x3() @ (n / len(active.link_faces))
        else:
            z_axis = obj_mat.to_3x3() @ Vector((0.0, 0.0, 1.0))
        x, y, z = _make_orthonormal_axes(z_axis, x_hint)
        return _cursor_matrix_from_axes_location(x, y, z, loc)

    if isinstance(active, bmesh.types.BMVert):
        loc = obj_mat @ active.co
        z_axis = obj_mat.to_3x3() @ active.normal
        x_hint = Vector()
        if active.link_edges:
            e = active.link_edges[0]
            other = e.verts[0] if e.verts[0] != active else e.verts[1]
            x_hint = obj_mat.to_3x3() @ (other.co - active.co)
        x, y, z = _make_orthonormal_axes(z_axis, x_hint)
        return _cursor_matrix_from_axes_location(x, y, z, loc)

    return None


def _mesh_selected_center_or_none(obj) -> Vector | None:
    if not obj or obj.type != "MESH" or not getattr(obj, "data", None):
        return None
    try:
        bm = bmesh.from_edit_mesh(obj.data)
    except Exception:
        return None
    mm = _selected_verts_min_max_world(bm, obj.matrix_world.copy())
    if not mm:
        return None
    min_v, max_v = mm[0], mm[1]
    return (max_v + min_v) / 2.0


def _editmode_mesh_cursor_to_select_matrix(context) -> Matrix | None:
    objs = _editmode_objects(context)
    if not objs:
        return None

    active_obj = context.active_object if context.active_object in objs else objs[0]
    base = _apply_matrix_continuity(context, _mesh_active_element_matrix_or_none(active_obj))
    centers = []
    for o in objs:
        c = _mesh_selected_center_or_none(o)
        if c is not None:
            centers.append(c)
    if not centers:
        return base

    avg = Vector()
    for c in centers:
        avg += c
    avg /= len(centers)

    if base is not None:
        base.translation = avg
        return _apply_matrix_continuity(context, base)

    obj_mat = active_obj.matrix_world.copy()
    z_axis = obj_mat.to_3x3() @ Vector((0.0, 0.0, 1.0))
    x, y, z = _make_orthonormal_axes(z_axis, obj_mat.to_3x3() @ Vector((1.0, 0.0, 0.0)))
    return _apply_matrix_continuity(context, _cursor_matrix_from_axes_location(x, y, z, avg))


def _editmode_curve_cursor_to_select_matrix(context) -> Matrix | None:
    obj = context.edit_object or context.active_object
    if not obj or obj.type != "CURVE" or not getattr(obj, "data", None):
        return None

    loc_local = Vector()
    count = 0
    tangent_local = Vector()
    tangent_count = 0
    selected_local_points = []
    for spline in obj.data.splines:
        for bp in getattr(spline, "bezier_points", []):
            if getattr(bp, "select_control_point", False) or getattr(bp, "select_left_handle", False) or getattr(bp, "select_right_handle", False):
                loc_local += bp.co
                count += 1
                selected_local_points.append(bp.co.copy())
                th = (bp.handle_right - bp.handle_left)
                if th.length != 0:
                    tangent_local += th
                    tangent_count += 1
        for p in getattr(spline, "points", []):
            if getattr(p, "select", False):
                try:
                    loc_local += Vector((p.co.x, p.co.y, p.co.z))
                except Exception:
                    loc_local += Vector(p.co[:3])
                count += 1
                try:
                    selected_local_points.append(Vector((p.co.x, p.co.y, p.co.z)))
                except Exception:
                    selected_local_points.append(Vector(p.co[:3]))
        if getattr(spline, "points", None) and len(spline.points) >= 2:
            sp = spline.points
            for i in range(1, len(sp)):
                if getattr(sp[i - 1], "select", False) and getattr(sp[i], "select", False):
                    try:
                        a = Vector((sp[i - 1].co.x, sp[i - 1].co.y, sp[i - 1].co.z))
                        b = Vector((sp[i].co.x, sp[i].co.y, sp[i].co.z))
                    except Exception:
                        a = Vector(sp[i - 1].co[:3])
                        b = Vector(sp[i].co[:3])
                    d = (b - a)
                    if d.length != 0:
                        tangent_local += d
                        tangent_count += 1
    if count == 0:
        return None
    loc_local /= count

    obj_mat = obj.matrix_world.copy()
    loc = obj_mat @ loc_local
    z_axis = None

    if len(selected_local_points) >= 3:
        center_local = Vector()
        for p in selected_local_points:
            center_local += p
        center_local /= len(selected_local_points)
        acc = Vector()
        for i in range(1, len(selected_local_points)):
            a = selected_local_points[i - 1] - center_local
            b = selected_local_points[i] - center_local
            c = a.cross(b)
            if c.length != 0:
                acc += c
        if acc.length != 0:
            z_axis = (obj_mat.to_3x3() @ acc).normalized()

    if z_axis is None:
        rd = getattr(context, "region_data", None)
        if rd and hasattr(rd, "view_matrix"):
            try:
                z_axis = (-rd.view_matrix.inverted().col[2].xyz).normalized()
            except Exception:
                z_axis = None

    if z_axis is None:
        z_axis = (obj_mat.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()

    x_hint = obj_mat.to_3x3() @ Vector((1.0, 0.0, 0.0))
    if tangent_count:
        x_hint = obj_mat.to_3x3() @ (tangent_local / tangent_count)
    x, y, z = _make_orthonormal_axes(z_axis, x_hint)
    return _apply_matrix_continuity(context, _cursor_matrix_from_axes_location(x, y, z, loc))


def _editmode_cursor_to_select_matrix(context) -> Matrix | None:
    if getattr(context, "mode", "") == "EDIT_MESH":
        return _editmode_mesh_cursor_to_select_matrix(context)
    if getattr(context, "mode", "") == "EDIT_CURVE":
        return _editmode_curve_cursor_to_select_matrix(context)
    return None


def _editmode_origin_set_from_matrix(context, objects, target_matrix: Matrix, only_location: bool, only_rotation: bool) -> bool:
    if not objects:
        return False
    changed_any = False
    for obj in objects:
        if not obj or not getattr(obj, "data", None):
            continue
        if obj.type != "MESH":
            continue
        try:
            om = obj.matrix_world.copy()
            tm = _compose_target_matrix(om, target_matrix, only_location, only_rotation)
            transform_matrix = tm.inverted() @ om

            bm = bmesh.from_edit_mesh(obj.data)
            bm.transform(transform_matrix)
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=False)
            obj.matrix_world = tm
            changed_any = True
        except Exception:
            continue
    if changed_any:
        try:
            context.view_layer.update()
        except Exception:
            pass
    return changed_any


def _editmode_curve_objects(context):
    objs = []
    for attr in ("objects_in_mode_unique_data", "objects_in_mode"):
        value = getattr(context, attr, None)
        if value:
            objs = list(value)
            break
    if not objs and getattr(context, "edit_object", None):
        objs = [context.edit_object]
    if not objs and getattr(context, "active_object", None):
        objs = [context.active_object]
    return [o for o in objs if o and o.type == "CURVE" and getattr(o, "data", None)]


def _editmode_curve_origin_set_from_matrix(context, objects, target_matrix: Matrix, only_location: bool, only_rotation: bool) -> bool:
    if not objects:
        return False
    changed_any = False
    for obj in objects:
        if not obj or obj.type != "CURVE" or not getattr(obj, "data", None):
            continue
        try:
            om = obj.matrix_world.copy()
            tm = _compose_target_matrix(om, target_matrix, only_location, only_rotation)
            transform_matrix = tm.inverted() @ om

            for spline in obj.data.splines:
                for point in getattr(spline, "points", []):
                    co = point.co.copy()
                    new_co = transform_matrix @ Vector((co.x, co.y, co.z))
                    point.co = Vector((*new_co, co.w))
                for b_point in getattr(spline, "bezier_points", []):
                    b_point.co = transform_matrix @ b_point.co
                    b_point.handle_left = transform_matrix @ b_point.handle_left
                    b_point.handle_right = transform_matrix @ b_point.handle_right

            obj.matrix_world = tm
            changed_any = True
        except Exception:
            continue
    if changed_any:
        try:
            context.view_layer.update()
        except Exception:
            pass
    return changed_any


def _editmode_objects(context):
    objs = []
    for attr in ("objects_in_mode_unique_data", "objects_in_mode"):
        value = getattr(context, attr, None)
        if value:
            objs = list(value)
            break
    if not objs and getattr(context, "active_object", None):
        objs = [context.active_object]
    return [o for o in objs if o and o.type == "MESH" and getattr(o, "data", None)]


def _restore_mode(context, original_mode: str):
    if not context.active_object:
        return
    mode = "OBJECT"
    if original_mode.startswith("EDIT"):
        mode = "EDIT"
    elif original_mode == "POSE":
        mode = "POSE"
    _call_op_or_none(bpy.ops.object.mode_set, mode=mode)


def _snap_cursor_to_selected_or_none():
    if hasattr(bpy.ops, "view3d") and hasattr(bpy.ops.view3d, "snap_cursor_to_selected"):
        return _call_op_or_none(bpy.ops.view3d.snap_cursor_to_selected, "EXEC_DEFAULT")
    return None


class M8_OT_MP7CursorToSelectSmart(bpy.types.Operator):
    bl_idname = "m8.mp7_cursor_to_select_smart"
    bl_label = "到所选"
    bl_description = "优先使用 MP7Tools 的到所选/活动元素；失败时回退到 Blender 的到所选"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        result = None
        if hasattr(bpy.ops, "m8") and hasattr(bpy.ops.m8, "cursor_to_select"):
            result = _call_op_or_none(bpy.ops.m8.cursor_to_select, "INVOKE_DEFAULT")
        if result is not None and not _is_cancelled(result):
            return result

        if getattr(context, "mode", "") in {"EDIT_MESH", "EDIT_CURVE"}:
            m = _editmode_cursor_to_select_matrix(context)
            if m is not None:
                try:
                    context.scene.cursor.matrix = m
                    self.report({"INFO"}, "已回退到编辑模式原地设置：游标到所选")
                    return {"FINISHED"}
                except Exception:
                    pass

        fallback = _call_op_or_none(bpy.ops.view3d.snap_cursor_to_selected, "INVOKE_DEFAULT")
        if fallback is not None:
            self.report({"INFO"}, "已回退到 Blender 原生：游标到所选")
        return fallback if fallback is not None else {"CANCELLED"}


class M8_OT_MP7OriginToActiveSmart(bpy.types.Operator):
    bl_idname = "m8.mp7_origin_to_active_smart"
    bl_label = "到活动"
    bl_description = "设置原点到活动元素。Alt:仅位置；Ctrl:仅旋转。失败时回退为“原点到所选/游标”"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        if event.ctrl and event.alt:
            self.report({"WARNING"}, "Ctrl 与 Alt 同时按下无法解析")
            return {"CANCELLED"}
        result = None
        if hasattr(bpy.ops, "m8") and hasattr(bpy.ops.m8, "origin_to_active"):
            result = _call_op_or_none(bpy.ops.m8.origin_to_active, "INVOKE_DEFAULT")
        if result is not None and not _is_cancelled(result):
            return result

        original_mode = context.mode
        only_location = bool(event.alt) and not bool(event.ctrl)
        only_rotation = bool(event.ctrl) and not bool(event.alt)
        if original_mode == "EDIT_MESH":
            objects = _editmode_objects(context)
            if objects:
                target = _editmode_mesh_cursor_to_select_matrix(context)
                if target is not None:
                    ok = _editmode_origin_set_from_matrix(
                        context,
                        objects,
                        target,
                        only_location=only_location,
                        only_rotation=only_rotation,
                    )
                    if ok:
                        msg = "已回退到编辑模式原地设置：原点到所选"
                        if only_rotation:
                            msg += "；Ctrl 仅旋转已尽量等效"
                        self.report({"INFO"}, msg)
                        return {"FINISHED"}

        if original_mode == "EDIT_CURVE":
            objects = _editmode_curve_objects(context)
            if objects:
                target = _editmode_curve_cursor_to_select_matrix(context)
                if target is not None:
                    ok = _editmode_curve_origin_set_from_matrix(
                        context,
                        objects,
                        target,
                        only_location=only_location,
                        only_rotation=only_rotation,
                    )
                    if ok:
                        msg = "已回退到编辑模式原地设置：原点到曲线所选"
                        if only_rotation:
                            msg += "；Ctrl 仅旋转已尽量等效"
                        self.report({"INFO"}, msg)
                        return {"FINISHED"}

        objects = list(context.selected_objects)
        active_object = context.view_layer.objects.active or (objects[0] if objects else None)
        if not active_object:
            return {"CANCELLED"}

        _snap_cursor_to_selected_or_none()

        ensure_object_mode(context)
        fallback = call_object_op_with_selection(
            context,
            bpy.ops.object.origin_set,
            active_object=active_object,
            selected_objects=objects if objects else [active_object],
            type="ORIGIN_CURSOR",
        )
        _restore_mode(context, original_mode)
        if fallback is not None:
            msg = "已回退到 Blender 原生：原点到游标（先将游标吸附到所选）"
            if event.ctrl and not event.alt:
                msg += "；Ctrl 仅旋转在回退路径下无法完全等效"
            self.report({"INFO"}, msg)
        return fallback if fallback is not None else {"CANCELLED"}


class M8_OT_MP7OriginToCursorSmart(bpy.types.Operator):
    bl_idname = "m8.mp7_origin_to_cursor_smart"
    bl_label = "到游标"
    bl_description = "设置原点到 3D 游标。Alt:仅位置；Ctrl:仅旋转。失败时回退为 Blender 的“原点到游标”"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        if event.ctrl and event.alt:
            self.report({"WARNING"}, "Ctrl 与 Alt 同时按下无法解析")
            return {"CANCELLED"}
        result = None
        if hasattr(bpy.ops, "m8") and hasattr(bpy.ops.m8, "origin_to_cursor"):
            result = _call_op_or_none(bpy.ops.m8.origin_to_cursor, "INVOKE_DEFAULT")
        if result is not None and not _is_cancelled(result):
            return result

        original_mode = context.mode
        only_location = bool(event.alt) and not bool(event.ctrl)
        only_rotation = bool(event.ctrl) and not bool(event.alt)

        if original_mode == "EDIT_MESH":
            objects = _editmode_objects(context)
            if objects:
                ok = _editmode_origin_set_from_matrix(
                    context,
                    objects,
                    context.scene.cursor.matrix.copy(),
                    only_location=only_location,
                    only_rotation=only_rotation,
                )
                if ok:
                    msg = "已回退到编辑模式原地设置：原点到游标"
                    if only_rotation:
                        msg += "；Ctrl 仅旋转已尽量等效"
                    self.report({"INFO"}, msg)
                    return {"FINISHED"}

        if original_mode == "EDIT_CURVE":
            objects = _editmode_curve_objects(context)
            if objects:
                ok = _editmode_curve_origin_set_from_matrix(
                    context,
                    objects,
                    context.scene.cursor.matrix.copy(),
                    only_location=only_location,
                    only_rotation=only_rotation,
                )
                if ok:
                    msg = "已回退到编辑模式原地设置：原点到游标"
                    if only_rotation:
                        msg += "；Ctrl 仅旋转已尽量等效"
                    self.report({"INFO"}, msg)
                    return {"FINISHED"}

        objects = list(context.selected_objects)
        active_object = context.view_layer.objects.active or (objects[0] if objects else None)
        if not active_object:
            return {"CANCELLED"}

        ensure_object_mode(context)
        fallback = call_object_op_with_selection(
            context,
            bpy.ops.object.origin_set,
            active_object=active_object,
            selected_objects=objects if objects else [active_object],
            type="ORIGIN_CURSOR",
        )
        _restore_mode(context, original_mode)
        if fallback is not None:
            msg = "已回退到 Blender 原生：原点到游标"
            if event.ctrl and not event.alt:
                msg += "；Ctrl 仅旋转在回退路径下无法完全等效"
            self.report({"INFO"}, msg)
        return fallback if fallback is not None else {"CANCELLED"}

