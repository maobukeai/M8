import bmesh.types


def get_continuously_edges_list(bm: bmesh.types.BMesh) -> list[[bmesh.types.BMEdge]] | None:
    """获取连续的边列表
    """
    if bm.select_mode != {"EDGE"}:
        return None
    selected_edges = [e for e in bm.edges if e.select]
    link_list = []

    edges = selected_edges.copy()

    def get_edge_link(e):
        link_item = [e]
        for v in e.verts:
            for le in v.link_edges:
                if le in edges and le.select:
                    edges.pop(edges.index(le))
                    link_item.extend(get_edge_link(le))
        return link_item

    while edges:
        item = edges.pop()
        link_list.append(get_edge_link(item))
    return link_list
