SELECTED_ASSET = []


def sync_selected_asset(context):
    global SELECTED_ASSET
    if assets := getattr(context, "selected_assets", None):
        # if SELECTED_ASSET != assets:
        SELECTED_ASSET = assets.copy()
        # print("sync_selected_asset", len(context.selected_assets), len(SELECTED_ASSET))


def get_active_asset(context):
    """
    bpy.context.screen.areas[2].spaces[0].params.filename
    'brushes\\essentials_brushes-mesh_sculpt.blend\\Brush\\Thumb'

    """
    for area in context.screen.areas:
        if area.type == "FILE_BROWSER" and area.ui_type == "ASSETS":
            for space in area.spaces:
                if space.type == "FILE_BROWSER":
                    return space.active_asset
    return None


def get_active_material_asset(context):
    if active_asset := get_active_asset(context):
        if active_asset.id_type == "MATERIAL":
            return active_asset
    return None
