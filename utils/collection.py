import bpy


def get_view_layout_all_layer_collection(context) -> list[bpy.types.LayerCollection]:
    """获取所有视图层的视图层集合"""

    def get_items(item) -> list[bpy.types.LayerCollection]:
        items = [item, ]
        for i in item.children:
            items.extend(get_items(i))
        return items

    return get_items(context.view_layer.layer_collection)
