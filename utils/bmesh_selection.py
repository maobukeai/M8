import bmesh

def get_edge_loop(edge):
    """
    Get all edges in the loop containing the given edge.
    Returns a list of BMesh edges in order.
    """
    # Use lists to maintain order
    forward_edges = []
    backward_edges = []
    
    # Vertices to explore from
    verts = list(edge.verts)
    if len(verts) != 2:
        return [edge]
        
    v1, v2 = verts
    
    # Helper to traverse in one direction
    def traverse(start_vert, current_edge, edge_list):
        curr_v = start_vert
        curr_e = current_edge
        visited = {current_edge}
        
        while True:
            next_edge = None
            # Standard edge loop selection logic for quads
            if len(curr_v.link_edges) == 4:
                # Find the opposite edge
                connected_edges = list(curr_v.link_edges)
                current_faces = set(curr_e.link_faces)
                
                for e in connected_edges:
                    if e == curr_e:
                        continue
                    # If the edge shares no faces with the current edge, it's the opposite one
                    if not (set(e.link_faces) & current_faces):
                        next_edge = e
                        break
            
            # Check for loops and duplicates
            if (next_edge and 
                next_edge != edge and 
                next_edge not in edge_list and 
                next_edge not in forward_edges and 
                next_edge not in backward_edges and
                next_edge not in visited):
                
                edge_list.append(next_edge)
                visited.add(next_edge)
                curr_e = next_edge
                curr_v = next_edge.other_vert(curr_v)
            else:
                break

    # Traverse both directions
    traverse(v1, edge, forward_edges)
    traverse(v2, edge, backward_edges)
    
    # Combine: reverse backward path so it flows into start edge
    # backward_edges starts from edge's first vertex and goes outwards
    # forward_edges starts from edge's second vertex and goes outwards
    # So the full path is: reversed(backward) -> edge -> forward
    return list(reversed(backward_edges)) + [edge] + forward_edges

def get_edge_ring(edge):
    """
    Get all edges in the ring containing the given edge.
    Returns a list of BMesh edges in order.
    """
    forward_edges = []
    backward_edges = []
    
    faces = list(edge.link_faces)
    
    # Helper to traverse in one direction
    def traverse(start_face, current_edge, edge_list):
        curr_f = start_face
        curr_e = current_edge
        visited = {current_edge}
        
        while True:
            next_edge = None
            # Only support quads for standard ring selection
            if len(curr_f.edges) == 4:
                # Find the opposite edge in the quad
                for e in curr_f.edges:
                    if e == curr_e:
                        continue
                    # In a quad, the opposite edge shares no vertices with the current edge
                    if not (set(e.verts) & set(curr_e.verts)):
                        next_edge = e
                        break
            
            # Check if we found a valid next edge that isn't already processed
            # Also check if it's not the start edge (to prevent infinite loops in closed rings)
            if (next_edge and 
                next_edge != edge and 
                next_edge not in edge_list and 
                next_edge not in forward_edges and 
                next_edge not in backward_edges and
                next_edge not in visited):
                
                edge_list.append(next_edge)
                visited.add(next_edge)
                
                # Move to the next face across the next_edge
                next_face = None
                for f in next_edge.link_faces:
                    if f != curr_f:
                        next_face = f
                        break
                
                if next_face:
                    curr_f = next_face
                    curr_e = next_edge
                else:
                    break
            else:
                break

    # Traverse both directions if possible
    # faces[0] and faces[1] represent the two directions perpendicular to the edge
    if len(faces) >= 1:
        traverse(faces[0], edge, forward_edges)
    if len(faces) >= 2:
        traverse(faces[1], edge, backward_edges)
        
    return list(reversed(backward_edges)) + [edge] + forward_edges

def get_checker_deselect(edges, nth=2, offset=0, skip=1):
    """
    Filter a list of edges by selecting every Nth element.
    This assumes the edges are ordered.
    """
    if not edges:
        return []
    
    # Python slicing handles the basic logic: [start:stop:step]
    # offset is start
    # nth is step (kind of)
    
    # Blender's checker deselect logic:
    # nth=2, skip=1 (default): select 1, skip 1
    # nth=4, skip=1: select 1, skip 3? No.
    # Blender param is "Nth Selection": Select every Nth element? No.
    # Blender params are: "Nth Selection" (step), "Skip" (number of elements to skip?), "Offset".
    
    # Let's emulate standard "Select every Nth" behavior first as requested by "Checker Deselect"
    # Usually means: Keep 1, Skip N-1.
    # If nth=2: Keep 1, Skip 1.
    
    # For now, let's use a simple slice which corresponds to Nth=2
    # If the user wants specific pattern, we might need more complex logic.
    # Based on the cleaner.py usage: use_checker_deselect is a boolean.
    # It likely implies a standard "1 on, 1 off" pattern.
    
    return edges[offset::nth]

def sort_edge_loop(edges):
    """
    Sort a set of connected edges into an ordered list.
    NOTE: This only works for Edge Loops (sharing vertices), NOT Edge Rings.
    Deprecated for internal use, prefer get_edge_loop which returns ordered list.
    """
    if not edges:
        return []
    if isinstance(edges, list):
        return edges
        
    edges_list = list(edges)
    # Simple heuristic sort
    sorted_edges = [edges_list.pop(0)]
    
    while edges_list:
        changed = False
        last_edge = sorted_edges[-1]
        for i, e in enumerate(edges_list):
            if set(e.verts) & set(last_edge.verts):
                sorted_edges.append(edges_list.pop(i))
                changed = True
                break
        
        if not changed:
            first_edge = sorted_edges[0]
            for i, e in enumerate(edges_list):
                if set(e.verts) & set(first_edge.verts):
                    sorted_edges.insert(0, edges_list.pop(i))
                    changed = True
                    break
                    
        if not changed:
            break
            
    return sorted_edges
