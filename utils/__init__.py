import bpy
from os.path import dirname, realpath, join, abspath
from mathutils import Matrix, Vector

CAGE_TAG_KEY = "size_tool_is_cage"
CAGE_ORIG_SIZE_KEY = "orig_size"
CAGE_BACKUP_SUFFIX = "_Backup"
SNAP_SIZE_KEY = "cage_snap_size"
SNAP_LOC_KEY = "cage_snap_loc"
SNAP_MATRIX_WORLD_KEY = "cage_snap_matrix_world"
SNAP_GROUP_KEY = "cage_snap_group"
SNAP_APPLIED_SCALE_KEY = "cage_snap_applied_scale"
BACKUP_COLLECTION_NAME = "SizeTool_Backups"

def get_addon_prefs():
    # Use the root package name to get the addon preferences
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

def get_backup_suffix():
    prefs = get_addon_prefs()
    suffix = getattr(prefs, "backup_suffix", None) if prefs else None
    return suffix if suffix else CAGE_BACKUP_SUFFIX

def get_backup_collection_name():
    prefs = get_addon_prefs()
    name = getattr(prefs, "backup_collection_name", None) if prefs else None
    return name if name else BACKUP_COLLECTION_NAME

def get_archive_default_bake():
    prefs = get_addon_prefs()
    return bool(getattr(prefs, "archive_default_bake", False)) if prefs else False

def is_size_cage(obj):
    if not obj:
        return False
    if obj.name.endswith(get_backup_suffix()):
        return False
    if obj.get(CAGE_TAG_KEY):
        return True
    return "Dimension_Control_Box" in obj.name

def ensure_object_mode(context):
    if getattr(context, "mode", "OBJECT") == "OBJECT":
        return
    active = context.view_layer.objects.active
    if not active and context.selected_objects:
        context.view_layer.objects.active = context.selected_objects[0]
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except RuntimeError:
        pass

def call_object_op_with_selection(context, op_callable, *, active_object, selected_objects, **kwargs):
    prev_selected = list(context.selected_objects)
    prev_active = context.view_layer.objects.active
    try:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_objects:
            obj.select_set(True)
        context.view_layer.objects.active = active_object

        if hasattr(context, "temp_override"):
            with context.temp_override(
                active_object=active_object,
                selected_objects=list(selected_objects),
                selected_editable_objects=list(selected_objects),
                object=active_object,
            ):
                return op_callable(**kwargs)
        return op_callable(**kwargs)
    finally:
        try:
            bpy.ops.object.select_all(action='DESELECT')
        except RuntimeError:
            pass
        for obj in prev_selected:
            try:
                obj.select_set(True)
            except ReferenceError:
                pass
        if prev_active:
            try:
                context.view_layer.objects.active = prev_active
            except ReferenceError:
                pass

def get_transparent_material():
    mat_name = "DIMENSION_UI_TRANSPARENT"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_trans = nodes.new(type='ShaderNodeBsdfTransparent')
        mat.node_tree.links.new(node_trans.outputs[0], node_output.inputs[0])
        if hasattr(mat, "blend_method"):
            mat.blend_method = 'BLEND'
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = 'NONE'
    return mat

def matrix_world_to_tuple16(matrix):
    row_major = []
    for r in matrix:
        row_major.extend((float(r[0]), float(r[1]), float(r[2]), float(r[3])))
    return tuple(row_major)

def tuple16_to_matrix_world(values):
    if not values or len(values) != 16:
        raise ValueError("Invalid matrix data")
    return Matrix((
        (values[0], values[1], values[2], values[3]),
        (values[4], values[5], values[6], values[7]),
        (values[8], values[9], values[10], values[11]),
        (values[12], values[13], values[14], values[15]),
    ))

def get_or_create_collection(name):
    coll = bpy.data.collections.get(name)
    if coll:
        return coll
    coll = bpy.data.collections.new(name=name)
    scene = bpy.context.scene or (bpy.data.scenes[0] if bpy.data.scenes else None)
    if scene:
        scene.collection.children.link(coll)
    return coll

def move_object_to_collection(obj, collection):
    if not obj or not collection:
        return
    for coll in list(obj.users_collection):
        try:
            coll.objects.unlink(obj)
        except RuntimeError:
            pass
    try:
        collection.objects.link(obj)
    except RuntimeError:
        pass

def get_operator_bl_idname(suffix: str) -> str:
    return f"m8.{suffix}"

def get_menu_bl_idname(suffix: str) -> str:
    return f"M8_MT_{suffix.upper()}"

def get_panel_bl_idname(suffix: str) -> str:
    return f"M8_PT_{suffix.upper()}"

# MP7Tools Compatibility
ADDON_FOLDER = dirname(dirname(realpath(__file__)))
BACKUPS_FOLDER = abspath(join(ADDON_FOLDER, "src", "backups"))
BACKUPS_PREFERENCES_FILE = join(BACKUPS_FOLDER, "preferences")

def get_pref():
    return get_addon_prefs()

def get_pref_value(key, default=None):
    pref = get_pref()
    if pref is None:
        return default
    try:
        return getattr(pref, key, default)
    except AttributeError:
        return default


def view_selected(context):
    mt = get_pref().moving_view_type
    if mt == "NONE":
        return
    for area in context.screen.areas:
        if area.type == "VIEW_3D" and area == context.area:
            for region in area.regions:
                if region.type == "WINDOW":
                    with context.temp_override(area=area, region=region):
                        if mt == "MAINTAINING_ZOOM":
                            view_distance = context.space_data.region_3d.view_distance
                            bpy.ops.view3d.view_selected("EXEC_DEFAULT", use_all_regions=True)
                            context.space_data.region_3d.view_distance = view_distance
                        elif mt == "ANIMATION":
                            bpy.ops.view3d.view_selected("INVOKE_DEFAULT", use_all_regions=True)

def update_view_layer_active_object_by_index(index: int, context):
    act_obj = context.scene.objects[index]
    for obj in context.view_layer.objects:
        obj.select_set(obj == act_obj)
    context.view_layer.objects.active = act_obj
    view_selected(context)

def update_view_layer_active_collection_by_index(index: int, context):
    from .collection import get_view_layout_all_layer_collection
    layer_collection_items = get_view_layout_all_layer_collection(context)
    collections_dict = {i.collection: i for i in layer_collection_items}
    collection = bpy.data.collections[index]
    layer_collection = collections_dict[collection]
    context.view_layer.active_layer_collection = layer_collection

def get_local_selected_assets(context):
    cur_lib_name = context.area.spaces.active.params.asset_library_reference
    match_obj = [asset_file.local_id for asset_file in context.selected_assets if
                 cur_lib_name in {"LOCAL", "ALL"}]
    return match_obj

def refresh_ui(context, screen=True):
    if context.screen and screen:
        context.screen.update_tag()
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    region.tag_redraw()
    if context.area:
        context.area.tag_redraw()
    if context.region:
        context.region.tag_redraw()
