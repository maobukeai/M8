import bmesh
import mathutils

def make_edges_equal_length(bm, selected_edges, target_length, iterations=50, keep_endpoints=False):
    if not selected_edges:
        return

    from collections import defaultdict
    vert_to_edges = defaultdict(list)
    for e in selected_edges:
        vert_to_edges[e.verts[0]].append(e)
        vert_to_edges[e.verts[1]].append(e)

    unvisited_edges = set(selected_edges)
    components = []

    while unvisited_edges:
        start_edge = next(iter(unvisited_edges))
        unvisited_edges.remove(start_edge)
        comp = [start_edge]
        queue = [start_edge]
        visited_in_comp = {start_edge}

        while queue:
            curr_e = queue.pop(0)
            for v in curr_e.verts:
                for nxt_e in vert_to_edges[v]:
                    if nxt_e in unvisited_edges and nxt_e not in visited_in_comp:
                        visited_in_comp.add(nxt_e)
                        unvisited_edges.remove(nxt_e)
                        queue.append(nxt_e)
                        comp.append(nxt_e)
        components.append(comp)

    for comp in components:
        # Case 1: Single isolated edge
        if len(comp) == 1:
            e = comp[0]
            v0, v1 = e.verts[0], e.verts[1]
            diff = v1.co - v0.co
            cur_len = diff.length
            if cur_len > 1e-7:
                mid = (v0.co + v1.co) * 0.5
                norm = diff / cur_len
                v0.co = mid - norm * (target_length * 0.5)
                v1.co = mid + norm * (target_length * 0.5)
            continue

        comp_verts = list(set(v for e in comp for v in e.verts))
        comp_degrees = {v: sum(1 for e in comp if v in e.verts) for v in comp_verts}
        is_open_chain = (max(comp_degrees.values()) == 2 and 
                         sum(1 for d in comp_degrees.values() if d == 1) == 2 and 
                         len(comp) == len(comp_verts) - 1)

        # For straight or nearly straight open chains, direct geometric subdivision gives instant perfect results
        if is_open_chain:
            start_v = next(v for v, d in comp_degrees.items() if d == 1)
            ordered_verts = [start_v]
            curr_v = start_v
            visited_e = set()
            while len(ordered_verts) < len(comp_verts):
                next_e = next(e for e in vert_to_edges[curr_v] if e in comp and e not in visited_e)
                visited_e.add(next_e)
                curr_v = next_e.verts[0] if next_e.verts[1] == curr_v else next_e.verts[1]
                ordered_verts.append(curr_v)

            # Check if straight
            v_start = ordered_verts[0].co
            v_end = ordered_verts[-1].co
            chain_vec = v_end - v_start
            is_straight = True
            if chain_vec.length > 1e-6:
                for v in ordered_verts[1:-1]:
                    proj, _ = mathutils.geometry.intersect_point_line(v.co, v_start, v_end)
                    if (v.co - proj).length > 1e-4:
                        is_straight = False
                        break
            else:
                is_straight = False

            if is_straight:
                k = len(ordered_verts) - 1
                if keep_endpoints:
                    step = chain_vec / k
                    for i in range(1, k):
                        ordered_verts[i].co = v_start + step * i
                else:
                    mid = (v_start + v_end) * 0.5
                    norm_dir = chain_vec.normalized()
                    total_len = k * target_length
                    new_start = mid - norm_dir * (total_len * 0.5)
                    step = norm_dir * target_length
                    for i in range(k + 1):
                        ordered_verts[i].co = new_start + step * i
                continue

        # General iterative relaxation (handles closed loops, curved chains, branched networks)
        # Fast position-based dynamics constraint projection
        fixed_verts = set()
        if is_open_chain and keep_endpoints:
            for v, d in comp_degrees.items():
                if d == 1:
                    fixed_verts.add(v)

        for _ in range(iterations):
            deltas = {v: mathutils.Vector((0, 0, 0)) for v in comp_verts}
            counts = {v: 0 for v in comp_verts}
            for e in comp:
                v0, v1 = e.verts[0], e.verts[1]
                diff = v1.co - v0.co
                cur_len = diff.length
                if cur_len > 1e-7:
                    err = cur_len - target_length
                    norm = diff / cur_len
                    # Move vertices along the edge to satisfy length
                    if v0 not in fixed_verts and v1 not in fixed_verts:
                        deltas[v0] += norm * (err * 0.5)
                        deltas[v1] -= norm * (err * 0.5)
                        counts[v0] += 1
                        counts[v1] += 1
                    elif v0 not in fixed_verts:
                        deltas[v0] += norm * err
                        counts[v0] += 1
                    elif v1 not in fixed_verts:
                        deltas[v1] -= norm * err
                        counts[v1] += 1

            max_delta = 0.0
            for v in comp_verts:
                if counts[v] > 0:
                    d = (deltas[v] / counts[v]) * 0.9
                    v.co += d
                    max_delta = max(max_delta, d.length)
            if max_delta < 1e-6:
                break

def test_all():
    print("Testing isolated edges...")
    bm = bmesh.new()
    v1 = bm.verts.new((0, 0, 0))
    v2 = bm.verts.new((1, 0, 0))
    v3 = bm.verts.new((0, 2, 0))
    v4 = bm.verts.new((3, 2, 0))
    e1 = bm.edges.new((v1, v2))
    e2 = bm.edges.new((v3, v4))
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    make_edges_equal_length(bm, [e1, e2], 2.0)
    print(f"e1: {e1.calc_length():.4f}, e2: {e2.calc_length():.4f}")
    assert abs(e1.calc_length() - 2.0) < 1e-4
    assert abs(e2.calc_length() - 2.0) < 1e-4

    print("Testing straight chain...")
    bm2 = bmesh.new()
    cv0 = bm2.verts.new((0, 0, 0))
    cv1 = bm2.verts.new((0.5, 0, 0))
    cv2 = bm2.verts.new((2.0, 0, 0))
    ce1 = bm2.edges.new((cv0, cv1))
    ce2 = bm2.edges.new((cv1, cv2))
    bm2.verts.ensure_lookup_table()
    bm2.edges.ensure_lookup_table()

    make_edges_equal_length(bm2, [ce1, ce2], 1.0)
    print(f"ce1: {ce1.calc_length():.4f}, ce2: {ce2.calc_length():.4f}")
    assert abs(ce1.calc_length() - 1.0) < 1e-4
    assert abs(ce2.calc_length() - 1.0) < 1e-4

    print("Testing closed loop...")
    bm3 = bmesh.new()
    lv0 = bm3.verts.new((0, 0, 0))
    lv1 = bm3.verts.new((2, 0, 0))
    lv2 = bm3.verts.new((2, 4, 0))
    lv3 = bm3.verts.new((0, 4, 0))
    le1 = bm3.edges.new((lv0, lv1))
    le2 = bm3.edges.new((lv1, lv2))
    le3 = bm3.edges.new((lv2, lv3))
    le4 = bm3.edges.new((lv3, lv0))
    bm3.verts.ensure_lookup_table()
    bm3.edges.ensure_lookup_table()

    make_edges_equal_length(bm3, [le1, le2, le3, le4], 3.0, iterations=100)
    for i, e in enumerate([le1, le2, le3, le4]):
        print(f"loop edge {i}: {e.calc_length():.4f}")
        assert abs(e.calc_length() - 3.0) < 0.05

    print("[PASS] All tests passed!")

if __name__ == "__main__":
    test_all()
