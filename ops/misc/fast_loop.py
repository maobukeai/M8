import bpy
import bmesh
import gpu
import blf
import mathutils
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d, location_3d_to_region_2d
from mathutils.bvhtree import BVHTree

# Helper to translate text using M8 i18n
from ...utils.i18n import _T

def get_prefs():
    try:
        root_pkg = ".".join(__package__.split(".")[:3]) if __package__ and __package__.startswith("bl_ext") else (__package__.split(".")[0] if __package__ else "M8")
        return bpy.context.preferences.addons[root_pkg].preferences
    except Exception:
        return None

def format_length(context, value):
    unit_settings = context.scene.unit_settings
    system = unit_settings.system
    
    if system == 'NONE':
        return f"{value:.3f}"
        
    elif system == 'METRIC':
        scale = unit_settings.scale_length
        val_scaled = value * scale
        
        if val_scaled < 0.001:
            return f"{val_scaled * 1000.0:.2f}mm"
        elif val_scaled < 1.0:
            return f"{val_scaled * 100.0:.1f}cm"
        else:
            return f"{val_scaled:.3f}m"
            
    elif system == 'IMPERIAL':
        inches = value / 0.0254
        if inches < 12.0:
            return f"{inches:.2f}\""
        else:
            feet = inches / 12.0
            return f"{feet:.2f}'"
            
    return f"{value:.3f}"

class M8_OT_FastLoop(bpy.types.Operator):
    bl_idname = "m8.fast_loop"
    bl_label = _T("快速循环切刀 (Fast Loop)")
    bl_description = _T("在视图中悬停并交互式快速添加循环边或顶点")
    bl_options = {'REGISTER', 'UNDO'}

    # Add settings as properties for user preferences or keymap tweaking
    segments: bpy.props.IntProperty(name="Segments", default=1, min=1, max=100)
    vertex_mode: bpy.props.BoolProperty(name="Vertex Mode", default=False)
    guide_mode: bpy.props.BoolProperty(name="Guide Mode", default=False)
    snap_divisions: bpy.props.IntProperty(name="Snap Divisions", default=4, min=1, max=100)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def get_oriented_edge_ring(self, bm, start_edge):
        """Trace a quad edge-ring with topology-derived, stable orientation.

        The previous implementation chose each opposite edge direction by comparing
        world-space distances.  That is ambiguous on folded, curved, or compact
        topology and can make the slide direction flip between adjacent faces.
        Face-loop winding provides the exact correspondence between the two
        opposite edges of a quad, independently of the mesh shape.
        """
        ring_map = {start_edge.index: False}
        visited = {start_edge}

        def opposite_edge(face, edge, reversed_direction):
            """Return the opposite quad edge and its matching start direction."""
            if len(face.verts) != 4:
                return None, False

            for loop in face.loops:
                if loop.edge != edge:
                    continue

                opposite_loop = loop.link_loop_next.link_loop_next
                opposite = opposite_loop.edge
                edge_start = edge.verts[1] if reversed_direction else edge.verts[0]

                # In a quad A-B-C-D, a cut from A on AB connects to D on
                # CD; a cut from B connects to C.  Use loop winding rather
                # than coordinate distance to preserve this correspondence.
                if edge_start == loop.vert:
                    opposite_start = opposite_loop.link_loop_next.vert
                elif edge_start == loop.link_loop_next.vert:
                    opposite_start = opposite_loop.vert
                else:
                    return None, False

                return opposite, opposite.verts[1] == opposite_start

            return None, False

        def walk(start_face):
            curr_face = start_face
            curr_edge = start_edge
            curr_rev = False

            while curr_face:
                opp_edge, opp_rev = opposite_edge(curr_face, curr_edge, curr_rev)
                if opp_edge is None or opp_edge in visited:
                    break

                ring_map[opp_edge.index] = opp_rev
                visited.add(opp_edge)

                # A ring cannot pass unambiguously through non-manifold or
                # branching topology.  Stop there, matching Loop Cut's safe
                # behaviour instead of selecting an arbitrary adjacent face.
                next_faces = [
                    face for face in opp_edge.link_faces
                    if face != curr_face and len(face.verts) == 4
                ]
                if len(next_faces) != 1:
                    break

                curr_face = next_faces[0]
                curr_edge = opp_edge
                curr_rev = opp_rev

        # Each linked quad face is one direction of the ring.  Walking both
        # also handles boundary loops while the shared visited set closes rings.
        for face in start_edge.link_faces:
            walk(face)

        return ring_map

    def update_ring_and_preview(self, context, edge_idx, hit_loc):
        """Update the edge ring and calculated preview geometry positions."""
        self.hovered_edge_idx = edge_idx
        self.dimension_draws = []
        if edge_idx < 0 or not self.bm:
            self.edge_ring_edges = []
            self.edge_ring_edge_indices = []
            self.edge_ring_orientations = {}
            self.preview_points = []
            self.preview_lines = []
            return

        self.bm.edges.ensure_lookup_table()
        try:
            start_edge = self.bm.edges[edge_idx]
        except IndexError:
            return

        # 1. Determine Edge Ring & Orientations
        if self.guide_mode:
            # Guide mode: use all selected edges
            selected_edges = [e for e in self.bm.edges if e.select]
            if start_edge not in selected_edges:
                selected_edges.append(start_edge)
            self.edge_ring_orientations = {start_edge.index: False}
            for e in selected_edges:
                if e != start_edge:
                    d0 = (start_edge.verts[0].co - e.verts[0].co).length
                    d1 = (start_edge.verts[0].co - e.verts[1].co).length
                    self.edge_ring_orientations[e.index] = d0 > d1
        else:
            # Auto mode: traverse ring and orient
            self.edge_ring_orientations = self.get_oriented_edge_ring(self.bm, start_edge)

        self.edge_ring_edges = [self.bm.edges[idx] for idx in self.edge_ring_orientations.keys() if idx < len(self.bm.edges)]
        self.edge_ring_edge_indices = [edge.index for edge in self.edge_ring_edges]

        # 2. Compute Slide Factor on Hovered Edge
        is_start_rev = self.edge_ring_orientations[start_edge.index]
        v1 = start_edge.verts[1] if is_start_rev else start_edge.verts[0]
        v2 = start_edge.verts[0] if is_start_rev else start_edge.verts[1]
        p1, p2 = v1.co, v2.co
        L_active = (p2 - p1).length

        _, factor = mathutils.geometry.intersect_point_line(hit_loc, p1, p2)
        factor = max(0.0, min(1.0, factor))

        # Handle Snapping
        if self.snap_enabled and self.snap_divisions > 0:
            snapped = round(factor * self.snap_divisions) / self.snap_divisions
            factor = max(0.0, min(1.0, snapped))

        # Convert factor to slide offset [-1.0, 1.0]
        self.slide_offset = 2.0 * factor - 1.0

        # 3. Calculate Preview Points
        self.preview_points = []
        edge_to_points = {} # edge index -> list of preview points in world space

        obj = context.active_object
        mw = obj.matrix_world

        for edge in self.edge_ring_edges:
            is_rev = self.edge_ring_orientations[edge.index]
            ev1 = edge.verts[1] if is_rev else edge.verts[0]
            ev2 = edge.verts[0] if is_rev else edge.verts[1]
            ep1, ep2 = ev1.co, ev2.co
            L_edge = (ep2 - ep1).length
            
            # Apply Even spacing adjustment
            slide_factor = factor
            if self.use_even and L_edge > 0.0001:
                if not self.flipped:
                    slide_factor = factor * (L_active / L_edge)
                else:
                    slide_factor = 1.0 - (1.0 - factor) * (L_active / L_edge)
                slide_factor = max(0.0, min(1.0, slide_factor))

            # Apply Perpendicular plane adjustment
            if self.perpendicular:
                plane_origin = p1.lerp(p2, slide_factor)
                plane_normal = (p2 - p1).normalized()
                isect_point = mathutils.geometry.intersect_line_plane(ep1, ep2, plane_origin, plane_normal)
                if isect_point is not None:
                    _, slide_factor = mathutils.geometry.intersect_point_line(isect_point, ep1, ep2)
                    slide_factor = max(0.0, min(1.0, slide_factor))

            # Compute slide offset for this edge
            edge_offset = 2.0 * slide_factor - 1.0

            # Calculate points along edge
            points_on_edge = []
            factors_to_calculate = []
            
            # Basic multi-loop segment factors
            for i in range(self.segments):
                t_0 = (i + 1) / (self.segments + 1)
                
                # Apply Spacing scale factor (collapsing/expanding spacing around 0.5 midpoint)
                if self.segments > 1:
                    d_0 = t_0 - 0.5
                    t_0 = 0.5 + d_0 * self.scale_factor

                if edge_offset >= 0:
                    t_final = t_0 + edge_offset * (1.0 - t_0)
                else:
                    t_final = t_0 + edge_offset * t_0
                factors_to_calculate.append(t_final)

            # Apply Symmetrical Mirroring
            if self.mirrored:
                mirrored_factors = []
                for t in factors_to_calculate:
                    mirrored_factors.append(t)
                    mirrored_factors.append(1.0 - t)
                # Remove duplicates and sort
                factors_to_calculate = sorted(list(set(mirrored_factors)))

            if self.use_curvature:
                self.bm.normal_update()
            for t_final in factors_to_calculate:
                local_pt = ep1 * (1.0 - t_final) + ep2 * t_final
                if self.use_curvature:
                    n1 = ev1.normal
                    n2 = ev2.normal
                    d = ep2 - ep1
                    h1 = d.dot(n1)
                    h2 = -d.dot(n2)
                    n_avg = (n1 * (1.0 - t_final) + n2 * t_final).normalized()
                    offset_mag = t_final * (1.0 - t_final) * (h1 * (1.0 - t_final) + h2 * t_final) * 0.5
                    local_pt = local_pt + offset_mag * n_avg
                world_pt = mw @ local_pt
                points_on_edge.append(world_pt)
                self.preview_points.append(world_pt)
            edge_to_points[edge.index] = points_on_edge

            # Calculate 3D dimensions for the hovered edge if segments == 1
            if edge.index == start_edge.index and self.segments == 1 and len(factors_to_calculate) == 1:
                t_final = factors_to_calculate[0]
                
                # First midpoint (0 to t_final)
                t1 = t_final * 0.5
                local_pt1 = ep1 * (1.0 - t1) + ep2 * t1
                if self.use_curvature:
                    n1 = ev1.normal
                    n2 = ev2.normal
                    d = ep2 - ep1
                    h1 = d.dot(n1)
                    h2 = -d.dot(n2)
                    n_avg1 = (n1 * (1.0 - t1) + n2 * t1).normalized()
                    offset1 = t1 * (1.0 - t1) * (h1 * (1.0 - t1) + h2 * t1) * 0.5
                    local_pt1 = local_pt1 + offset1 * n_avg1
                mid1_w = mw @ local_pt1
                
                # Second midpoint (t_final to 1.0)
                t2 = t_final + (1.0 - t_final) * 0.5
                local_pt2 = ep1 * (1.0 - t2) + ep2 * t2
                if self.use_curvature:
                    n1 = ev1.normal
                    n2 = ev2.normal
                    d = ep2 - ep1
                    h1 = d.dot(n1)
                    h2 = -d.dot(n2)
                    n_avg2 = (n1 * (1.0 - t2) + n2 * t2).normalized()
                    offset2 = t2 * (1.0 - t2) * (h1 * (1.0 - t2) + h2 * t2) * 0.5
                    local_pt2 = local_pt2 + offset2 * n_avg2
                mid2_w = mw @ local_pt2
                
                len1 = L_edge * t_final
                len2 = L_edge * (1.0 - t_final)
                
                self.dimension_draws = [
                    (mid1_w, format_length(context, len1)),
                    (mid2_w, format_length(context, len2))
                ]

        # 4. Calculate Preview Lines for Loop Cut Mode
        self.preview_lines = []
        if not self.vertex_mode:
            ring_edge_indices = {e.index for e in self.edge_ring_edges}
            self.bm.faces.ensure_lookup_table()
            # Draw connecting lines inside faces that contain exactly two edges of the ring
            for face in self.bm.faces:
                face_ring_edges = [e for e in face.edges if e.index in ring_edge_indices]
                if len(face_ring_edges) == 2:
                    e1_idx = face_ring_edges[0].index
                    e2_idx = face_ring_edges[1].index
                    if e1_idx in edge_to_points and e2_idx in edge_to_points:
                        pts1 = edge_to_points[e1_idx]
                        pts2 = edge_to_points[e2_idx]
                        for idx in range(min(len(pts1), len(pts2))):
                            self.preview_lines.append(pts1[idx])
                            self.preview_lines.append(pts2[idx])
    def get_edge_loop(self, context, start_edge):
        if not start_edge or not start_edge.is_valid:
            return []
        
        loop_edges = [start_edge]
        visited = {start_edge}
        
        # Traverse in both directions along the edge loop
        for start_vert in start_edge.verts:
            curr_edge = start_edge
            curr_vert = start_vert
            
            while True:
                next_edge = None
                linked_edges = [e for e in curr_vert.link_edges if not e.hide]
                
                if len(linked_edges) == 4:
                    # Standard grid vertex (valence 4): find the opposite edge
                    # The opposite edge shares no faces with the current edge
                    curr_faces = set(curr_edge.link_faces)
                    for e in linked_edges:
                        if e != curr_edge:
                            if not set(e.link_faces).intersection(curr_faces):
                                next_edge = e
                                break
                elif len(linked_edges) == 2:
                    # Boundary or simple valence-2 vertex: choose the other edge
                    for e in linked_edges:
                        if e != curr_edge:
                            next_edge = e
                            break
                            
                if next_edge and next_edge not in visited:
                    visited.add(next_edge)
                    loop_edges.append(next_edge)
                    curr_vert = next_edge.other_vert(curr_vert)
                    curr_edge = next_edge
                else:
                    break
                    
        return loop_edges

    def perform_remove_loop(self, context):
        if self.hovered_edge_idx < 0:
            return
        start_edge = self.bm.edges[self.hovered_edge_idx]
        loop_edges = self.get_edge_loop(context, start_edge)
        if not loop_edges:
            return
            
        bmesh.ops.dissolve_edges(self.bm, edges=loop_edges, use_verts=True)
        bmesh.update_edit_mesh(self.target_object.data)
        bpy.ops.ed.undo_push(message="Remove Edge Loop")
        
        # Refresh BMesh and BVHTree
        self.bm = bmesh.from_edit_mesh(self.target_object.data)
        self.bvh = BVHTree.FromBMesh(self.bm)
        self.bms[self.target_object.name] = self.bm
        self.bvhs[self.target_object.name] = self.bvh
        self.bm.edges.ensure_lookup_table()
        self.bm.verts.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()
        
        # Reset hovered state
        self.hovered_edge_idx = -1
        self.edge_ring_edge_indices = []
        self.last_hit_loc = None
        self.preview_points = []
        self.preview_lines = []
        self.freeze_edge = False

    def perform_cut(self, context, shift=False):
        """Apply subdivision and UV correction onto the edit bmesh."""
        if not self.bm or not getattr(self, "edge_ring_edge_indices", None):
            return

        # An edit-mesh update invalidates every cached BMEdge wrapper.  Resolve
        # fresh edges from the last preview's indices before cutting again.
        self.bm = bmesh.from_edit_mesh(self.target_object.data)
        self.bms[self.target_object.name] = self.bm
        self.bm.edges.ensure_lookup_table()

        # Creating/removing a BMesh custom-data layer can invalidate BMEdge
        # wrappers.  Set up every temporary edge layer before resolving any
        # edges that will be kept across this method.
        selected_edge_layer_name = "m8_fast_loop_was_selected"
        new_loop_edge_layer_name = "m8_fast_loop_new_loop"
        for layer_name in (selected_edge_layer_name, new_loop_edge_layer_name):
            old_layer = self.bm.edges.layers.int.get(layer_name)
            if old_layer:
                self.bm.edges.layers.int.remove(old_layer)
        selected_edge_layer = self.bm.edges.layers.int.new(selected_edge_layer_name)
        new_loop_edge_layer = self.bm.edges.layers.int.new(new_loop_edge_layer_name)

        ring_edges = [
            self.bm.edges[index]
            for index in self.edge_ring_edge_indices
            if 0 <= index < len(self.bm.edges)
        ]
        if (
            not ring_edges
            or self.hovered_edge_idx not in self.edge_ring_orientations
            or not 0 <= self.hovered_edge_idx < len(self.bm.edges)
        ):
            return

        start_edge = self.bm.edges[self.hovered_edge_idx]
        is_start_rev = self.edge_ring_orientations[self.hovered_edge_idx]
        v1_ref = (start_edge.verts[1] if is_start_rev else start_edge.verts[0]).co.copy()
        v2_ref = (start_edge.verts[0] if is_start_rev else start_edge.verts[1]).co.copy()
        L_active = (v2_ref - v1_ref).length

        # Preserve the user's selected edges in custom data rather than by
        # BMesh index.  Subdivide replaces edges and may reassign indices.
        for edge in self.bm.edges:
            edge[selected_edge_layer] = int(edge.select)

        uv_layer = self.bm.loops.layers.uv.active

        # Store original vertices/segments info consistently using our edge orientations
        orig_segments = []
        for e in ring_edges:
            is_rev = self.edge_ring_orientations[e.index]
            v1 = e.verts[1] if is_rev else e.verts[0]
            v2 = e.verts[0] if is_rev else e.verts[1]
            orig_segments.append((
                v1.index,
                v2.index,
                v1.co.copy(),
                v2.co.copy(),
                e.index
            ))

        # Collect original loop UVs
        orig_uvs = {}
        if uv_layer:
            for f in self.bm.faces:
                for l in f.loops:
                    orig_uvs[(f.index, l.vert.index)] = l[uv_layer].uv.copy()

        # Temporary layers preserve the per-face UV seam source through the
        # subdivision and the external EdgeFlow operator.
        orig_face_layer_name = "m8_fast_loop_orig_face"
        source_edge_layer_name = "m8_fast_loop_source_edge"
        old_face_layer = self.bm.faces.layers.int.get(orig_face_layer_name)
        if old_face_layer:
            self.bm.faces.layers.int.remove(old_face_layer)
        old_source_layer = self.bm.verts.layers.int.get(source_edge_layer_name)
        if old_source_layer:
            self.bm.verts.layers.int.remove(old_source_layer)

        orig_face_idx_layer = self.bm.faces.layers.int.new(orig_face_layer_name)
        source_edge_layer = self.bm.verts.layers.int.new(source_edge_layer_name)
        for f in self.bm.faces:
            f[orig_face_idx_layer] = f.index

        edge_sources = {
            edge_index: (v1_index, v2_index, p1.copy(), p2.copy())
            for v1_index, v2_index, p1, p2, edge_index in orig_segments
        }

        old_vert_indices = {v.index for v in self.bm.verts}
        old_edges = set(self.bm.edges)

        # Calculate segments count after factoring in mirroring
        cuts_count = self.segments
        if self.mirrored:
            # Symmetrical cuts double the count (unless overlapping at 0.5, but BMesh handles duplicates)
            cuts_count = self.segments * 2

        # Perform native BMesh subdivision
        if self.vertex_mode:
            bmesh.ops.subdivide_edges(self.bm, edges=ring_edges, cuts=cuts_count)
        else:
            bmesh.ops.subdivide_edgering(self.bm, edges=ring_edges, cuts=cuts_count, interp_mode='LINEAR')

        self.bm.verts.ensure_lookup_table()
        self.bm.edges.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()

        all_new_edges = [e for e in self.bm.edges if e not in old_edges]

        self.bm.verts.ensure_lookup_table()
        self.bm.edges.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()

        new_verts = [v for v in self.bm.verts if v.index not in old_vert_indices]
        new_vert_set = set(new_verts)

        # Loop edges = new edges whose BOTH endpoints are brand-new vertices
        # (these are the cross-cut edges forming the new loop, not the edge halves)
        new_loop_edges = [e for e in all_new_edges if e.verts[0] in new_vert_set and e.verts[1] in new_vert_set]
        # Fallback: if the heuristic returned nothing (rare mesh topologies), use all new edges
        if not new_loop_edges:
            new_loop_edges = all_new_edges

        # Mark the actual cut loop.  The temporary layer was created before
        # resolving BMesh edges, so assigning it cannot invalidate this list.
        for edge in new_loop_edges:
            edge[new_loop_edge_layer] = 1

        def restore_kept_selection(bm):
            """Restore pre-cut selection and select the new loop for S mode."""
            selected_layer = bm.edges.layers.int.get(selected_edge_layer_name)
            loop_layer = bm.edges.layers.int.get(new_loop_edge_layer_name)
            if not self.keep_selection or not selected_layer or not loop_layer:
                return
            for edge in bm.edges:
                if edge[selected_layer] or edge[loop_layer]:
                    # select_set propagates to vertices; assigning edge.select
                    # alone fails to display the result in vertex selection mode.
                    edge.select_set(True)

        # Group new vertices by original edge segment
        from collections import defaultdict
        edge_to_new_verts = defaultdict(list)

        for v in new_verts:
            for v1_idx, v2_idx, p1_co, p2_co, e_idx in orig_segments:
                proj_co, factor = mathutils.geometry.intersect_point_line(v.co, p1_co, p2_co)
                dist = (v.co - proj_co).length
                if dist < 0.0001:
                    edge_to_new_verts[e_idx].append((v, factor, v1_idx, v2_idx, p1_co, p2_co))
                    # +1 distinguishes an untagged original vertex from edge 0.
                    v[source_edge_layer] = e_idx + 1
                    break

        # Position and correct UVs
        if self.use_curvature:
            self.bm.normal_update()
        for e_idx, n_verts in edge_to_new_verts.items():
            # Subdivision may reassign the original edge index.  The cached
            # endpoints are stable and contain the exact pre-cut length.
            _, _, edge_p1, edge_p2 = edge_sources[e_idx]
            L_edge = (edge_p2 - edge_p1).length

            # Sort new verts by factor (from start to end)
            n_verts.sort(key=lambda x: x[1])
            num_cuts = len(n_verts)
            
            # Since subdivide_edgering creates cuts_count vertices, we calculate their targets:
            # We map their indices to the custom factor targets
            for i, (v, _, v1_idx, v2_idx, p1_co, p2_co) in enumerate(n_verts):
                # Target factor calculation
                t_0 = (i + 1) / (num_cuts + 1)
                
                # If mirrored, num_cuts contains both sides. We sort them, so the spacing matches.
                # If not mirrored, we can apply the normal spacing scaling:
                if not self.mirrored and self.segments > 1:
                    d_0 = t_0 - 0.5
                    t_0 = 0.5 + d_0 * self.scale_factor

                # Convert general slide offset to this edge's factor
                # Start edge factor:
                start_factor = (self.slide_offset + 1.0) / 2.0
                
                # Apply Even spacing adjustment
                slide_factor = start_factor
                if self.use_even and L_edge > 0.0001:
                    if not self.flipped:
                        slide_factor = start_factor * (L_active / L_edge)
                    else:
                        slide_factor = 1.0 - (1.0 - start_factor) * (L_active / L_edge)
                    slide_factor = max(0.0, min(1.0, slide_factor))

                # Apply Perpendicular plane adjustment
                if self.perpendicular:
                    plane_origin = v1_ref.lerp(v2_ref, slide_factor)
                    plane_normal = (v2_ref - v1_ref).normalized()
                    isect_point = mathutils.geometry.intersect_line_plane(p1_co, p2_co, plane_origin, plane_normal)
                    if isect_point is not None:
                        _, slide_factor = mathutils.geometry.intersect_point_line(isect_point, p1_co, p2_co)
                        slide_factor = max(0.0, min(1.0, slide_factor))

                # Edge specific offset
                edge_offset = 2.0 * slide_factor - 1.0

                if edge_offset >= 0:
                    t_final = t_0 + edge_offset * (1.0 - t_0)
                else:
                    t_final = t_0 + edge_offset * t_0

                # Set new position
                v.co = p1_co * (1.0 - t_final) + p2_co * t_final
                
                # Apply Curvature Flow offset if enabled
                if self.use_curvature:
                    vert1 = self.bm.verts[v1_idx]
                    vert2 = self.bm.verts[v2_idx]
                    n1 = vert1.normal
                    n2 = vert2.normal
                    d = p2_co - p1_co
                    h1 = d.dot(n1)
                    h2 = -d.dot(n2)
                    n_avg = (n1 * (1.0 - t_final) + n2 * t_final).normalized()
                    offset_mag = t_final * (1.0 - t_final) * (h1 * (1.0 - t_final) + h2 * t_final) * 0.5
                    v.co += offset_mag * n_avg

                # Apply UV interpolation
                if uv_layer:
                    for l in v.link_loops:
                        orig_face_idx = l.face[orig_face_idx_layer]
                        key1 = (orig_face_idx, v1_idx)
                        key2 = (orig_face_idx, v2_idx)
                        if key1 in orig_uvs and key2 in orig_uvs:
                            uv1 = orig_uvs[key1]
                            uv2 = orig_uvs[key2]
                            l[uv_layer].uv = uv1 * (1.0 - t_final) + uv2 * t_final

        # Automerge support
        if context.scene.tool_settings.use_mesh_automerge:
            threshold = context.scene.tool_settings.double_threshold
            bmesh.ops.remove_doubles(self.bm, verts=new_verts, dist=threshold)

        # Get EdgeFlow params from M8 prefs (same defaults as original Fast-Loop: tension=180, iter=1, min_angle=0)
        prefs = get_prefs()
        ef_tension = getattr(prefs, 'fast_loop_tension', 180) if prefs else 180
        ef_iterations = getattr(prefs, 'fast_loop_iterations', 1) if prefs else 1
        ef_min_angle = getattr(prefs, 'fast_loop_min_angle', 0) if prefs else 0
        reproject_uv_after_flow = getattr(prefs, 'fast_loop_reproject_uv_after_edge_flow', True) if prefs else True

        def reproject_flow_uvs():
            """Reparameterize only newly cut vertices after EdgeFlow.

            Each loop corner keeps its original face ID, so UV seams remain
            independent.  The new interpolation factor is based on the final
            vertex position relative to the two original cut-edge endpoints.
            """
            if not reproject_uv_after_flow:
                return

            active_uv_layer = self.bm.loops.layers.uv.active
            face_layer = self.bm.faces.layers.int.get(orig_face_layer_name)
            source_layer = self.bm.verts.layers.int.get(source_edge_layer_name)
            if not active_uv_layer or not face_layer or not source_layer:
                return

            for vert in self.bm.verts:
                source_edge_index = vert[source_layer] - 1
                source = edge_sources.get(source_edge_index)
                if source is None:
                    continue

                v1_index, v2_index, p1_co, p2_co = source
                distance_1 = (vert.co - p1_co).length
                distance_2 = (vert.co - p2_co).length
                total_distance = distance_1 + distance_2
                if total_distance <= 1e-8:
                    continue
                factor = max(0.0, min(1.0, distance_1 / total_distance))

                for loop in vert.link_loops:
                    original_face_index = loop.face[face_layer]
                    uv1 = orig_uvs.get((original_face_index, v1_index))
                    uv2 = orig_uvs.get((original_face_index, v2_index))
                    if uv1 is not None and uv2 is not None:
                        loop[active_uv_layer].uv = uv1.lerp(uv2, factor)

        # Determine if we should run EdgeFlow:
        # shift XOR enable_edge_flow == True means "run edge flow"
        run_edge_flow = shift ^ self.enable_edge_flow

        if run_edge_flow:
            if hasattr(bpy.ops.mesh, "set_edge_flow"):
                # EdgeFlow operates on every selected edge.  S explicitly opts
                # into including the user's pre-selected edges alongside the
                # newly-created loop in the Set Flow calculation.
                loop_layer = self.bm.edges.layers.int.get(new_loop_edge_layer_name)
                selected_layer = self.bm.edges.layers.int.get(selected_edge_layer_name)
                for e in self.bm.edges:
                    e.select = bool(
                        (loop_layer and e[loop_layer])
                        or (self.keep_selection and selected_layer and e[selected_layer])
                    )
                # Do not flush here.  In vertex/face selection modes a flush can
                # clear these edge flags, leaving EdgeFlow with an empty input.
                bmesh.update_edit_mesh(self.target_object.data)
                try:
                    result = bpy.ops.mesh.set_edge_flow(
                        # EdgeFlow initializes its runtime state in invoke().
                        # EXEC_DEFAULT skips that step and raises on current
                        # Blender/EdgeFlow versions.
                        'INVOKE_DEFAULT',
                        tension=ef_tension,
                        iterations=ef_iterations,
                        min_angle=ef_min_angle
                    )
                    if 'FINISHED' not in result:
                        self.report({'WARNING'}, "Edge Flow cancelled; the new loop was kept without smoothing")
                except Exception as ex:
                    self.report({'ERROR'}, f"Edge Flow failed: {str(ex)}")

                # Restore the selection that existed before the cut.  Keep the
                # newly created loop only when the persistent-selection option is
                # explicitly enabled.
                self.bm = bmesh.from_edit_mesh(self.target_object.data)
                self.bms[self.target_object.name] = self.bm
                reproject_flow_uvs()

                restore_kept_selection(self.bm)
                self.bm.select_flush_mode()
                bmesh.update_edit_mesh(self.target_object.data)
            else:
                self.report({'WARNING'}, "未找到 Edge Flow 插件，请先安装并启用它。")
                # Fallback: same as no-EdgeFlow path
                for e in all_new_edges:
                    if e.is_valid:
                        e.select = False
                restore_kept_selection(self.bm)
                self.bm.select_flush_mode()
                bmesh.update_edit_mesh(self.target_object.data)
                self.bms[self.target_object.name] = self.bm
        else:
            # No EdgeFlow path
            # S OFF → deselect all new edges cleanly
            # S ON  → new loop edges stay selected + pre-existing user selection restored
            for e in all_new_edges:
                if e.is_valid:
                    e.select = False
            restore_kept_selection(self.bm)
            self.bm.select_flush_mode()
            bmesh.update_edit_mesh(self.target_object.data)
            self.bms[self.target_object.name] = self.bm

        # These layers are only needed while the cut is being processed.  Their
        # removal prevents temporary data from accumulating in edit meshes.
        face_layer = self.bm.faces.layers.int.get(orig_face_layer_name)
        if face_layer:
            self.bm.faces.layers.int.remove(face_layer)
        source_layer = self.bm.verts.layers.int.get(source_edge_layer_name)
        if source_layer:
            self.bm.verts.layers.int.remove(source_layer)
        selected_edge_layer = self.bm.edges.layers.int.get(selected_edge_layer_name)
        if selected_edge_layer:
            self.bm.edges.layers.int.remove(selected_edge_layer)
        new_loop_edge_layer = self.bm.edges.layers.int.get(new_loop_edge_layer_name)
        if new_loop_edge_layer:
            self.bm.edges.layers.int.remove(new_loop_edge_layer)
        bmesh.update_edit_mesh(self.target_object.data)


    def invoke(self, context, event):
        if context.space_data.type != 'VIEW_3D':
            self.report({'WARNING'}, _T("此工具必须在3D视图中运行"))
            return {'CANCELLED'}

        # Initialize BMesh and BVHTrees for all selected edit meshes
        self.edit_objects = [o for o in context.selected_objects if o.type == 'MESH' and o.mode == 'EDIT']
        if not self.edit_objects:
            if context.active_object and context.active_object.type == 'MESH':
                self.edit_objects = [context.active_object]
                
        if not self.edit_objects:
            self.report({'WARNING'}, _T("未选择任何编辑模式下的网格"))
            return {'CANCELLED'}

        self.bms = {}
        self.bvhs = {}
        for o in self.edit_objects:
            bm = bmesh.from_edit_mesh(o.data)
            self.bms[o.name] = bm
            self.bvhs[o.name] = BVHTree.FromBMesh(bm)
            
        # Default active target object
        self.target_object = context.active_object if context.active_object in self.edit_objects else self.edit_objects[0]
        self.bm = self.bms[self.target_object.name]
        self.bvh = self.bvhs[self.target_object.name]

        # Initialize state variables
        self._draw_handler_2d = None
        self._draw_handler_3d = None
        
        self.hovered_edge_idx = -1
        self.last_hit_loc = None
        self.slide_offset = 0.0
        self.snap_enabled = False
        self.last_ctrl = False
        self.last_shift = False
        self.edge_ring_edges = []
        self.edge_ring_edge_indices = []
        self.edge_ring_orientations = {}
        self.preview_points = []
        self.preview_lines = []
        self.input_mode = 'SEGMENTS'
        self.numeric_str = ""
        self.dimension_draws = []

        # Advanced options
        self.use_even = False
        self.flipped = False
        self.mirrored = False
        self.perpendicular = False
        self.freeze_edge = False
        self.is_scaling = False
        self.scale_factor = 1.0
        self.is_remove_mode = False
        self.use_curvature = False
        self.enable_edge_flow = False
        self.keep_selection = False

        prefs = get_prefs()
        if prefs:
            self.segments = prefs.fast_loop_segments
            self.vertex_mode = prefs.fast_loop_vertex_mode
            self.guide_mode = prefs.fast_loop_guide_mode
            self.snap_divisions = prefs.fast_loop_snap_divisions
            self.use_even = prefs.fast_loop_use_even
            self.flipped = prefs.fast_loop_flipped
            self.mirrored = prefs.fast_loop_mirrored
            self.perpendicular = prefs.fast_loop_perpendicular
            self.use_curvature = getattr(prefs, "fast_loop_use_curvature", False)
            self.enable_edge_flow = getattr(prefs, "fast_loop_enable_edge_flow", False)
            self.keep_selection = getattr(prefs, "fast_loop_keep_selection", False)

        # Saved states for scaling cancel
        self.prev_scale_factor = 1.0

        # Register draw handlers
        self._draw_handler_2d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_2d, (context,), 'WINDOW', 'POST_PIXEL'
        )
        self._draw_handler_3d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback_3d, (context,), 'WINDOW', 'POST_VIEW'
        )

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def end_modal(self, context):
        if self._draw_handler_2d:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler_2d, 'WINDOW')
            self._draw_handler_2d = None
        if self._draw_handler_3d:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler_3d, 'WINDOW')
            self._draw_handler_3d = None
        context.area.tag_redraw()

    def get_valid_bm_and_bvh(self, obj):
        """Ensure both BMesh and BVHTree are valid and in sync for the object."""
        bm_updated = False
        try:
            bm = self.bms.get(obj.name)
            if not bm or not bm.is_valid:
                bm_updated = True
        except (ReferenceError, AttributeError):
            bm_updated = True
            
        if bm_updated:
            try:
                bm = bmesh.from_edit_mesh(obj.data)
                self.bms[obj.name] = bm
                self.bvhs[obj.name] = BVHTree.FromBMesh(bm)
                if obj == self.target_object:
                    self.bm = bm
                    self.bvh = self.bvhs[obj.name]
            except Exception as e:
                print(f"Failed to rebuild BMesh/BVH for {obj.name}: {e}")
                
        return self.bms.get(obj.name), self.bvhs.get(obj.name)

    def cancel(self, context):
        self.end_modal(context)

    def trigger_update(self, context, event):
        """Perform hover raycasting using the cached BVHTrees and update preview."""
        if not self.bvhs:
            return

        # If scaling is active, we bypass new raycast and use frozen edge & coordinates
        if self.is_scaling:
            if self.hovered_edge_idx >= 0 and self.last_hit_loc is not None:
                self.update_ring_and_preview(context, self.hovered_edge_idx, self.last_hit_loc)
            return

        mouse_coords = (event.mouse_region_x, event.mouse_region_y)
        region = context.region
        rv3d = context.region_data
        if not rv3d:
            return

        ray_origin = region_2d_to_origin_3d(region, rv3d, mouse_coords)
        ray_vector = region_2d_to_vector_3d(region, rv3d, mouse_coords)

        # 1. If freeze edge is active, we project mouse ray onto the locked edge of self.target_object
        if self.freeze_edge and self.hovered_edge_idx >= 0:
            mw = self.target_object.matrix_world
            mw_inv = mw.inverted()
            self.bm.edges.ensure_lookup_table()
            edge = self.bm.edges[self.hovered_edge_idx]
            v1_world = mw @ edge.verts[0].co
            v2_world = mw @ edge.verts[1].co
            isect = mathutils.geometry.intersect_line_line(ray_origin, ray_origin + ray_vector, v1_world, v2_world)
            if isect:
                self.last_hit_loc = mw_inv @ isect[1]
                self.update_ring_and_preview(context, self.hovered_edge_idx, self.last_hit_loc)
            return

        # 2. Otherwise, find which edit mesh object is closest to the mouse ray
        best_obj = None
        best_hit = None
        best_dist = float('inf')
        
        for o in self.edit_objects:
            mw = o.matrix_world
            mw_inv = mw.inverted()
            local_origin = mw_inv @ ray_origin
            local_vector = (mw_inv.to_3x3() @ ray_vector).normalized()
            
            loc, norm, face_idx, dist = self.bvhs[o.name].ray_cast(local_origin, local_vector)
            if face_idx is not None and face_idx >= 0:
                world_hit = mw @ loc
                d = (ray_origin - world_hit).length
                if d < best_dist:
                    best_dist = d
                    best_obj = o
                    best_hit = (loc, norm, face_idx, dist)

        # 3. Switch active target mesh if hovered object changed
        if best_obj:
            self.target_object = best_obj
            self.bm = self.bms[best_obj.name]
            self.bvh = self.bvhs[best_obj.name]
            
            mw = best_obj.matrix_world
            mw_inv = mw.inverted()
            loc, norm, face_idx, dist = best_hit
        else:
            mw = self.target_object.matrix_world
            mw_inv = mw.inverted()
            face_idx = None

        # 4. Check for remove loop mode (Ctrl + Shift)
        if event.ctrl and event.shift:
            self.is_remove_mode = True
            
            closest_edge = None
            if face_idx is not None and face_idx >= 0:
                self.bm.faces.ensure_lookup_table()
                face = self.bm.faces[face_idx]
                min_dist = float('inf')
                for edge in face.edges:
                    p1, p2 = edge.verts[0].co, edge.verts[1].co
                    projected_co, factor = mathutils.geometry.intersect_point_line(loc, p1, p2)
                    factor = max(0.0, min(1.0, factor))
                    closest_segment_co = p1 * (1.0 - factor) + p2 * factor
                    dist = (loc - closest_segment_co).length
                    if dist < min_dist:
                        min_dist = dist
                        closest_edge = edge
                        
            if closest_edge:
                self.hovered_edge_idx = closest_edge.index
                self.last_hit_loc = loc
                
                # Get the entire edge loop of the hovered edge
                loop_edges = self.get_edge_loop(context, closest_edge)
                
                # Generate preview lines
                self.preview_points = []
                self.preview_lines = []
                for e in loop_edges:
                    self.preview_lines.append(mw @ e.verts[0].co)
                    self.preview_lines.append(mw @ e.verts[1].co)
            else:
                self.hovered_edge_idx = -1
                self.last_hit_loc = None
                self.preview_points = []
                self.preview_lines = []
            return
        else:
            self.is_remove_mode = False

        # 5. Normal loop cut mode raycasting and preview generation
        if face_idx is not None and face_idx >= 0:
            self.bm.faces.ensure_lookup_table()
            face = self.bm.faces[face_idx]
            closest_edge = None
            min_dist = float('inf')
            for edge in face.edges:
                p1, p2 = edge.verts[0].co, edge.verts[1].co
                projected_co, factor = mathutils.geometry.intersect_point_line(loc, p1, p2)
                factor = max(0.0, min(1.0, factor))
                closest_segment_co = p1 * (1.0 - factor) + p2 * factor
                dist = (loc - closest_segment_co).length
                if dist < min_dist:
                    min_dist = dist
                    closest_edge = edge
            
            if closest_edge:
                self.last_hit_loc = loc
                self.update_ring_and_preview(context, closest_edge.index, loc)
        else:
            self.update_ring_and_preview(context, -1, None)

    def modal(self, context, event):
        # Ensure all BMeshes and BVHTrees are valid at the start of modal tick
        valid_edit_objects = []
        for o in self.edit_objects:
            try:
                if o and o.name in bpy.data.objects:
                    self.get_valid_bm_and_bvh(o)
                    valid_edit_objects.append(o)
            except ReferenceError:
                pass
        self.edit_objects = valid_edit_objects

        # Check target_object validity
        try:
            target_valid = self.target_object and self.target_object.name in bpy.data.objects
        except ReferenceError:
            target_valid = False
            
        if not target_valid and self.edit_objects:
            self.target_object = self.edit_objects[0]
            try:
                self.bm = self.bms.get(self.target_object.name)
                self.bvh = self.bvhs.get(self.target_object.name)
            except Exception:
                pass

        # Allow view navigation to pass through
        if event.type in {'MIDDLEMOUSE', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        # Plain scroll → viewport zoom (pass through); Ctrl/Shift+scroll → adjust segment count
        if event.type == 'WHEELUPMOUSE':
            if event.ctrl or event.shift:
                self.segments += 1
                self.trigger_update(context, event)
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}
        if event.type == 'WHEELDOWNMOUSE':
            if event.ctrl or event.shift:
                self.segments = max(1, self.segments - 1)
                self.trigger_update(context, event)
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        context.area.tag_redraw()

        modifiers_changed = (self.last_ctrl != event.ctrl) or (self.last_shift != event.shift)
        self.last_ctrl = event.ctrl
        self.last_shift = event.shift

        self.snap_enabled = event.ctrl

        # 1. Spacing Scaling Mode Key Intercepts
        if self.is_scaling:
            if event.type == 'MOUSEMOVE':
                delta_x = event.mouse_x - event.mouse_prev_x
                mult = 0.001 if event.shift else 0.005
                self.scale_factor = max(0.01, min(2.0, self.scale_factor + delta_x * mult))
                self.trigger_update(context, event)
                return {'RUNNING_MODAL'}
            elif event.type in {'LEFTMOUSE', 'RET', 'W'} and event.value == 'PRESS':
                # Confirm spacing scale
                self.is_scaling = False
                self.trigger_update(context, event)
                return {'RUNNING_MODAL'}
            elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
                # Revert spacing scale
                self.scale_factor = self.prev_scale_factor
                self.is_scaling = False
                self.trigger_update(context, event)
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        # Toggle Numeric Offset mode with TAB key
        if event.type == 'TAB' and event.value == 'PRESS':
            if self.input_mode == 'SEGMENTS':
                self.input_mode = 'NUMERIC'
                self.numeric_str = ""
            else:
                self.input_mode = 'SEGMENTS'
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}

        # Handle keyboard direct value entry if in NUMERIC input mode
        if self.input_mode == 'NUMERIC' and event.type != 'LEFTMOUSE':
            if event.value == 'PRESS':
                # Map keys
                char_map = {
                    'ZERO': '0', 'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4',
                    'FIVE': '5', 'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9',
                    'NUMPAD_0': '0', 'NUMPAD_1': '1', 'NUMPAD_2': '2', 'NUMPAD_3': '3', 'NUMPAD_4': '4',
                    'NUMPAD_5': '5', 'NUMPAD_6': '6', 'NUMPAD_7': '7', 'NUMPAD_8': '8', 'NUMPAD_9': '9',
                    'PERIOD': '.', 'NUMPAD_PERIOD': '.',
                    'MINUS': '-', 'NUMPAD_MINUS': '-'
                }
                if event.type == 'BACKSPACE':
                    self.numeric_str = self.numeric_str[:-1]
                    if self.numeric_str and self.numeric_str not in {"-", "."}:
                        try:
                            val = float(self.numeric_str)
                            if abs(val) > 1.0:
                                val /= 100.0
                            self.slide_offset = max(-1.0, min(1.0, val))
                        except ValueError:
                            pass
                    else:
                        self.slide_offset = 0.0
                    self.trigger_update(context, event)
                elif event.type in {'RET', 'NUMPAD_ENTER'}:
                    # Confirm input, switch back to normal mode
                    self.input_mode = 'SEGMENTS'
                    self.trigger_update(context, event)
                elif event.type in {'ESC', 'RIGHTMOUSE'}:
                    # Cancel input, revert to 0.0 offset
                    self.input_mode = 'SEGMENTS'
                    self.slide_offset = 0.0
                    self.numeric_str = ""
                    self.trigger_update(context, event)
                elif event.type in char_map:
                    # Don't add multiple decimal points
                    if char_map[event.type] == '.' and '.' in self.numeric_str:
                        return {'RUNNING_MODAL'}
                    # Don't add multiple minus signs
                    if char_map[event.type] == '-' and len(self.numeric_str) > 0:
                        return {'RUNNING_MODAL'}
                    
                    self.numeric_str += char_map[event.type]
                    try:
                        val = float(self.numeric_str)
                        if abs(val) > 1.0:
                            val /= 100.0
                        self.slide_offset = max(-1.0, min(1.0, val))
                    except ValueError:
                        pass
                    self.trigger_update(context, event)
            return {'RUNNING_MODAL'}

        # 2. Regular Hotkeys and Event processing
        if event.type == 'UP_ARROW' and event.value == 'PRESS':
            self.segments += 1
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'DOWN_ARROW' and event.value == 'PRESS':
            self.segments = max(1, self.segments - 1)
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}

        # Instant segment count number keys
        num_keys = {
            'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5, 'SIX': 6, 'SEVEN': 7, 'EIGHT': 8, 'NINE': 9,
            'NUMPAD_1': 1, 'NUMPAD_2': 2, 'NUMPAD_3': 3, 'NUMPAD_4': 4, 'NUMPAD_5': 5, 'NUMPAD_6': 6, 'NUMPAD_7': 7, 'NUMPAD_8': 8, 'NUMPAD_9': 9
        }
        if event.type in num_keys and event.value == 'PRESS':
            self.segments = num_keys[event.type]
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}

        # Toggles — temporary per-session, except S which persists via prefs
        elif event.type == 'C' and event.value == 'PRESS':
            self.use_curvature = not self.use_curvature
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'V' and event.value == 'PRESS':
            self.vertex_mode = not self.vertex_mode
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'A' and event.value == 'PRESS':
            self.guide_mode = not self.guide_mode
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'E' and event.value == 'PRESS':
            self.use_even = not self.use_even
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'F' and event.value == 'PRESS':
            self.flipped = not self.flipped
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'M' and event.value == 'PRESS':
            self.mirrored = not self.mirrored
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'SLASH' and event.value == 'PRESS':
            self.perpendicular = not self.perpendicular
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'COMMA' and event.value == 'PRESS':
            self.freeze_edge = not self.freeze_edge
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'S' and event.value == 'PRESS':
            self.keep_selection = not self.keep_selection
            prefs = get_prefs()
            if prefs:
                prefs.fast_loop_keep_selection = self.keep_selection
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'W' and event.value == 'PRESS':
            if self.segments > 1:
                self.is_scaling = True
                self.prev_scale_factor = self.scale_factor
            return {'RUNNING_MODAL'}

        # Shift + Right Click to center
        elif event.type == 'RIGHTMOUSE' and event.shift and event.value == 'PRESS':
            self.trigger_update(context, event) # ensure updated coords
            self.slide_offset = 0.0
            self.perform_cut(context)
            bpy.ops.ed.undo_push(message="Fast Loop Cut")
            # Refresh BMesh and BVHTree
            self.bm = bmesh.from_edit_mesh(self.target_object.data)
            self.bvh = BVHTree.FromBMesh(self.bm)
            self.bms[self.target_object.name] = self.bm
            self.bvhs[self.target_object.name] = self.bvh
            self.bm.edges.ensure_lookup_table()
            self.bm.verts.ensure_lookup_table()
            self.bm.faces.ensure_lookup_table()
            # Reset hovered state
            self.hovered_edge_idx = -1
            self.edge_ring_edge_indices = []
            self.last_hit_loc = None
            self.preview_points = []
            self.preview_lines = []
            self.freeze_edge = False
            # Recalculate hover immediately
            self.trigger_update(context, event)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Confirm cut
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.trigger_update(context, event) # ensure updated coords
            if self.hovered_edge_idx >= 0:
                if self.is_remove_mode:
                    self.perform_remove_loop(context)
                    self.trigger_update(context, event)
                else:
                    self.perform_cut(context, shift=event.shift)
                    bpy.ops.ed.undo_push(message="Fast Loop Cut")
                    # Refresh BMesh and BVHTree
                    self.bm = bmesh.from_edit_mesh(self.target_object.data)
                    self.bvh = BVHTree.FromBMesh(self.bm)
                    self.bms[self.target_object.name] = self.bm
                    self.bvhs[self.target_object.name] = self.bvh
                    self.bm.edges.ensure_lookup_table()
                    self.bm.verts.ensure_lookup_table()
                    self.bm.faces.ensure_lookup_table()
                    # Reset hovered state
                    self.hovered_edge_idx = -1
                    self.edge_ring_edge_indices = []
                    self.last_hit_loc = None
                    self.preview_points = []
                    self.preview_lines = []
                    self.freeze_edge = False
                    # Recalculate hover immediately
                    self.trigger_update(context, event)
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            else:
                # Clicked on empty space (no edge ring detected)
                return {'RUNNING_MODAL'}

        # Confirm and Exit
        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            self.end_modal(context)
            return {'FINISHED'}

        # Cancel / Exit operator
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self.end_modal(context)
            return {'FINISHED'}

        # Trigger update on mouse movements or modifier state changes (Ctrl / Shift)
        if event.type == 'MOUSEMOVE' or modifiers_changed:
            self.trigger_update(context, event)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def draw_callback_3d(self, context):
        """Draw viewport preview geometry."""
        try:
            if not self.is_remove_mode and not self.edge_ring_edges:
                return

            gpu.state.blend_set('ALPHA')
            
            # 1. Draw points
            if not self.is_remove_mode and self.preview_points:
                gpu.state.point_size_set(6.0)
                shader = gpu.shader.from_builtin('UNIFORM_COLOR')
                shader.bind()
                shader.uniform_float("color", (0.0, 0.8, 1.0, 1.0) if self.vertex_mode else (1.0, 0.8, 0.0, 1.0))
                batch = batch_for_shader(shader, 'POINTS', {"pos": self.preview_points})
                batch.draw(shader)

            # 2. Draw lines
            if self.preview_lines:
                shader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')
                shader.bind()
                shader.uniform_float("lineWidth", 2.0)
                shader.uniform_float("viewportSize", (context.area.width, context.area.height))
                
                color = (1.0, 0.2, 0.2, 1.0) if self.is_remove_mode else (0.0, 0.8, 1.0, 1.0)
                colors = [color] * len(self.preview_lines)
                batch = batch_for_shader(shader, 'LINES', {"pos": self.preview_lines, "color": colors})
                batch.draw(shader)

            gpu.state.blend_set('NONE')
        except ReferenceError:
            pass

    def draw_callback_2d(self, context):
        """Draw viewport text HUD with a beautiful background card."""
        try:
            x = 90
            w = 260
            h = 230
            y = context.area.height - h - 80

            # Use UNIFORM_COLOR for the semi-transparent black background box
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            shader.bind()
            shader.uniform_float("color", (0.08, 0.08, 0.08, 0.75))
            gpu.state.blend_set('ALPHA')
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": pts})
            batch.draw(shader)

            # Draw border stroke
            shader.uniform_float("color", (0.2, 0.2, 0.2, 0.9))
            batch_border = batch_for_shader(shader, 'LINE_LOOP', {"pos": pts})
            batch_border.draw(shader)
            gpu.state.blend_set('NONE')

            # Draw text overlay
            font_id = 0
            blf.size(font_id, 11)
            line_height = 16
            text_x = x + 10
            text_y = y + 10

            # Title
            blf.color(font_id, 0.0, 0.8, 1.0, 1.0)
            blf.position(font_id, text_x, text_y + line_height * 12 - 5, 0)
            blf.draw(font_id, f"M8 Fast Loop")

            # Instruction details
            blf.color(font_id, 1.0, 1.0, 1.0, 0.85)
            
            # Mode / Direct Numeric Input
            if self.input_mode == 'NUMERIC':
                blf.color(font_id, 0.0, 0.8, 1.0, 1.0)
                blf.position(font_id, text_x, text_y + line_height * 11 - 5, 0)
                blf.draw(font_id, f"键入定位 (百分比/绝对值): {self.numeric_str}_")
                blf.color(font_id, 1.0, 1.0, 1.0, 0.85)
            else:
                mode_str = _T("顶点模式") if self.vertex_mode else _T("切刀模式")
                blf.position(font_id, text_x, text_y + line_height * 11 - 5, 0)
                blf.draw(font_id, f"[V] {_T('当前模式')}: {mode_str} | [Tab] {_T('数值定位')}")

            # Segments
            blf.position(font_id, text_x, text_y + line_height * 10 - 5, 0)
            blf.draw(font_id, f"[Shift+滚轮/1-9/↑↓] {_T('段数 (Cuts)')}: {self.segments}")

            # Snap
            snap_str = _T("开启") if self.snap_enabled else _T("关闭")
            blf.position(font_id, text_x, text_y + line_height * 9 - 5, 0)
            blf.draw(font_id, f"[Ctrl] {_T('吸附状态')}: {snap_str} ({self.snap_divisions} {_T('等分')})")

            # Even & Flip
            even_str = _T("等距") if self.use_even else _T("等比")
            flip_str = "A" if not self.flipped else "B"
            blf.position(font_id, text_x, text_y + line_height * 8 - 5, 0)
            blf.draw(font_id, f"[E/F] {_T('等距类型')}: {even_str} | {_T('对齐边界')}: {flip_str}")

            # Mirror
            mirror_str = _T("对称") if self.mirrored else _T("非对称")
            blf.position(font_id, text_x, text_y + line_height * 7 - 5, 0)
            blf.draw(font_id, f"[M] {_T('对称镜像')}: {mirror_str}")

            # Perpendicular
            perp_str = _T("开启") if self.perpendicular else _T("关闭")
            blf.position(font_id, text_x, text_y + line_height * 6 - 5, 0)
            blf.draw(font_id, f"[/] {_T('法向投影')}: {perp_str}")

            # Lock/Freeze edge
            lock_str = _T("锁定") if self.freeze_edge else _T("解锁")
            blf.position(font_id, text_x, text_y + line_height * 5 - 5, 0)
            blf.draw(font_id, f"[,] {_T('锁定滑动边')}: {lock_str}")

            # Guide mode
            guide_str = _T("开启") if self.guide_mode else _T("关闭")
            blf.position(font_id, text_x, text_y + line_height * 4 - 5, 0)
            blf.draw(font_id, f"[A] {_T('引导模式')}: {guide_str}")

            # Curvature flow
            curve_str = _T("开启") if self.use_curvature else _T("关闭")
            blf.position(font_id, text_x, text_y + line_height * 3 - 5, 0)
            blf.draw(font_id, f"[C] {_T('曲率平滑')}: {curve_str}")

            # Spacing
            if self.segments > 1:
                blf.position(font_id, text_x, text_y + line_height * 2 - 5, 0)
                blf.draw(font_id, f"[W] {_T('线圈间距')}: {self.scale_factor * 100:.1f}%")
            else:
                blf.position(font_id, text_x, text_y + line_height * 2 - 5, 0)
                blf.color(font_id, 1.0, 1.0, 1.0, 0.4)
                blf.draw(font_id, f"[W] {_T('线圈间距')} ({_T('仅多段可用')})")

            # Include the current selection when calculating Set Flow.
            keep_sel_str = _T("开启") if self.keep_selection else _T("关闭")
            blf.color(font_id, 1.0, 1.0, 1.0, 0.85)
            blf.position(font_id, text_x, text_y + line_height * 1 - 5, 0)
            blf.draw(font_id, f"[S] {_T('选中边参与 Set Flow')}: {keep_sel_str}")

            # Confirm / Cancel Info
            if self.is_remove_mode:
                blf.color(font_id, 1.0, 0.2, 0.2, 0.95)
                blf.position(font_id, text_x, text_y - 5, 0)
                blf.draw(font_id, f"[L-Click] {_T('删除选中环线')} | [Esc] {_T('取消')}")
            elif self.is_scaling:
                blf.color(font_id, 1.0, 0.4, 0.0, 0.95)
                blf.position(font_id, text_x, text_y - 5, 0)
                blf.draw(font_id, f"[W / Enter / L-Click] {_T('确认间距')} | [Esc] {_T('取消')}")
            else:
                blf.color(font_id, 1.0, 0.8, 0.0, 0.95)
                blf.position(font_id, text_x, text_y - 5, 0)
                blf.draw(font_id, f"[L-Click] {_T('添加/重复加线')} | [Shift+L-Click] Set Flow | [Shift+R-Click] {_T('居中切')} | [Esc] {_T('确认退出')}")

            # 3. Draw 3D dimensions near hovered edge sub-segments
            if not self.is_remove_mode and self.dimension_draws:
                region = context.region
                rv3d = context.region_data
                if region and rv3d:
                    blf.size(font_id, 12)
                    for mid_w, text_str in self.dimension_draws:
                        co2d = location_3d_to_region_2d(region, rv3d, mid_w)
                        if co2d:
                            # Draw shadow
                            blf.color(font_id, 0.0, 0.0, 0.0, 0.75)
                            blf.position(font_id, co2d.x + 1, co2d.y - 1, 0)
                            blf.draw(font_id, text_str)
                            
                            # Draw front text
                            blf.color(font_id, 1.0, 0.8, 0.0, 0.95)
                            blf.position(font_id, co2d.x, co2d.y, 0)
                            blf.draw(font_id, text_str)
        except ReferenceError:
            pass
