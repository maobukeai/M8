import bpy
import bmesh
from bpy_extras import view3d_utils
from mathutils import Vector

def get_region_rv3d(context):
    region = getattr(context, "region", None)
    rv3d = getattr(context, "region_data", None)
    if region and rv3d and getattr(region, "type", "") == "WINDOW":
        return region, rv3d
    wm = getattr(context, "window_manager", None)
    if not wm:
        return None, None
    for win in wm.windows:
        screen = getattr(win, "screen", None)
        if not screen:
            continue
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for r in area.regions:
                if r.type == "WINDOW":
                    return r, area.spaces.active.region_3d
    return None, None

def closest_vert_2d(obj, region, rv3d, mouse_xy, verts):
    if not region or not rv3d or not mouse_xy:
        return None
    mx, my = mouse_xy
    best = None
    best_d2 = None
    mat = obj.matrix_world
    for v in verts:
        co2d = view3d_utils.location_3d_to_region_2d(region, rv3d, mat @ v.co)
        if co2d is None:
            continue
        dx = co2d.x - mx
        dy = co2d.y - my
        d2 = dx * dx + dy * dy
        if best_d2 is None or d2 < best_d2:
            best = v
            best_d2 = d2
    return best

def weld_to_target(bm, verts, target):
    if not target or not verts:
        return False
    targetmap = {}
    for v in verts:
        if v is target:
            continue
        targetmap[v] = target
    if not targetmap:
        return False
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    return True

def pointmerge_to_co(bm, verts, co):
    if not verts:
        return False
    bmesh.ops.pointmerge(bm, verts=verts, merge_co=co)
    return True

def last_selected_vert(bm, selected_set):
    try:
        for elem in reversed(list(bm.select_history)):
            if isinstance(elem, bmesh.types.BMVert) and elem in selected_set and elem.select:
                return elem
    except Exception:
        pass
    return None

def avg_co(verts):
    if not verts:
        return None
    co = verts[0].co.copy()
    for v in verts[1:]:
        co += v.co
    co *= 1.0 / float(len(verts))
    return co

def edge_components(edges):
    comps = []
    remaining = set(edges)
    while remaining:
        e0 = next(iter(remaining))
        stack = [e0]
        remaining.remove(e0)
        comp = {e0}
        comp_verts = {e0.verts[0], e0.verts[1]}
        while stack:
            e = stack.pop()
            for v in e.verts:
                for e2 in v.link_edges:
                    if e2 in remaining:
                        remaining.remove(e2)
                        stack.append(e2)
                        comp.add(e2)
                        comp_verts.add(e2.verts[0])
                        comp_verts.add(e2.verts[1])
        comps.append((list(comp), list(comp_verts)))
    return comps

def face_islands(selected_faces):
    comps = []
    remaining = set(selected_faces)
    while remaining:
        f0 = next(iter(remaining))
        stack = [f0]
        remaining.remove(f0)
        comp = {f0}
        comp_verts = set(f0.verts)
        while stack:
            f = stack.pop()
            for e in f.edges:
                for f2 in e.link_faces:
                    if f2 in remaining and f2.select:
                        remaining.remove(f2)
                        stack.append(f2)
                        comp.add(f2)
                        comp_verts.update(f2.verts)
        comps.append((list(comp), list(comp_verts)))
    return comps

def ordered_path_from_edges(edges):
    adj = {}
    for e in edges:
        v1, v2 = e.verts
        adj.setdefault(v1, []).append(v2)
        adj.setdefault(v2, []).append(v1)
    endpoints = [v for v, ns in adj.items() if len(ns) == 1]
    if len(endpoints) != 2:
        return None
    for v, ns in adj.items():
        if len(ns) > 2:
            return None
    start = endpoints[0]
    path = [start]
    prev = None
    cur = start
    while True:
        ns = adj.get(cur, [])
        nxt = None
        for n in ns:
            if n is prev:
                continue
            nxt = n
            break
        if nxt is None:
            break
        path.append(nxt)
        prev, cur = cur, nxt
        if cur is endpoints[1]:
            break
    if path[-1] is not endpoints[1]:
        return None
    return path

def selected_edges_from_vertex_selection(bm):
    edges = []
    for e in bm.edges:
        if e.verts[0].select and e.verts[1].select:
            edges.append(e)
    return edges

def selected_edges_any(bm):
    edges = [e for e in bm.edges if e.select]
    if edges:
        return edges
    return selected_edges_from_vertex_selection(bm)

def set_edge_bevel_weight(bm, edges, weight):
    try:
        layer = bm.edges.layers.bevel_weight.verify()
        for e in edges:
            e[layer] = float(weight)
        return True
    except AttributeError:
        return False

def ensure_bevel_modifier(obj, name):
    mod = None
    created = False
    try:
        mod = obj.modifiers.get(name)
    except Exception:
        mod = None
    if mod and getattr(mod, "type", "") != "BEVEL":
        mod = None
    if not mod:
        mod = obj.modifiers.new(name=name, type="BEVEL")
        created = True
    return mod, created

def get_addon_prefs(package_name):
    try:
        root_pkg = (package_name or "").split(".")[0]
        addon = bpy.context.preferences.addons.get(root_pkg) if bpy.context and bpy.context.preferences else None
        return addon.preferences if addon else None
    except Exception:
        return None
