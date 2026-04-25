import bpy
from ..ops.mesh.cleaner import M8_Clean_Props
from ..ops.custom_tools import M8_CustomTools_Props
from ..ops.file.image_save_preset import M8_ImageSavePresetProps

class M8_BakeRenamer_Props(bpy.types.PropertyGroup):
    """Encapsulated state for Baking Renaming tool"""
    language: bpy.props.EnumProperty(
        items=[('CN', '中文', ''), ('EN', 'English', '')],
        default='CN',
        description="Switch Interface Language"
    )
    selection_scope: bpy.props.EnumProperty(
        items=[('SELECTED', 'Selected', ''), ('VISIBLE', 'Visible', '')],
        default='SELECTED',
        name="Selection Scope"
    )
    match_order: bpy.props.EnumProperty(
        items=[('LOW', 'Low -> High', ''), ('HIGH', 'High -> Low', '')],
        default='LOW',
        name="Match Order"
    )
    prefix: bpy.props.StringProperty(default="Bake")
    start_index: bpy.props.IntProperty(default=1, min=1)
    auto_collection: bpy.props.BoolProperty(
        default=True,
        name="Auto Move to Collection",
        description="Automatically move objects to _Low/_High collections"
    )
    distance: bpy.props.FloatProperty(
        default=0.01, min=0.0001, precision=4, description="Tolerance distance (Fallback)"
    )

class M8_SceneState(bpy.types.PropertyGroup):
    """Encapsulated state for M8 Scene-level properties"""
    size_tool_padding: bpy.props.FloatProperty(
        name="间距",
        description="创建调节盒时的外扩间距",
        default=0.0,
        min=0.0,
        soft_max=1.0,
        unit='LENGTH'
    )
    clean: bpy.props.PointerProperty(type=M8_Clean_Props)
    custom_tools: bpy.props.PointerProperty(type=M8_CustomTools_Props)
    image_save_preset: bpy.props.PointerProperty(type=M8_ImageSavePresetProps)
    bake_renamer: bpy.props.PointerProperty(type=M8_BakeRenamer_Props)

class M8_WMState(bpy.types.PropertyGroup):
    """Encapsulated state for M8 WindowManager-level properties"""
    last_curve_handle_type: bpy.props.StringProperty(default="AUTOMATIC")
    last_curve_edit_action: bpy.props.StringProperty(default="")
    cursor_z_axis: bpy.props.FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))

class M8_ObjectState(bpy.types.PropertyGroup):
    """Encapsulated state for M8 Object-level tracking"""
    last_object_mode: bpy.props.StringProperty(default="")

def register():
    bpy.utils.register_class(M8_BakeRenamer_Props)
    bpy.utils.register_class(M8_SceneState)
    bpy.utils.register_class(M8_WMState)
    bpy.utils.register_class(M8_ObjectState)
    
    bpy.types.Scene.m8 = bpy.props.PointerProperty(type=M8_SceneState)
    bpy.types.WindowManager.m8 = bpy.props.PointerProperty(type=M8_WMState)
    bpy.types.Object.m8 = bpy.props.PointerProperty(type=M8_ObjectState)

def unregister():
    del bpy.types.Scene.m8
    del bpy.types.WindowManager.m8
    del bpy.types.Object.m8
    
    bpy.utils.unregister_class(M8_ObjectState)
    bpy.utils.unregister_class(M8_WMState)
    bpy.utils.unregister_class(M8_SceneState)
    bpy.utils.unregister_class(M8_BakeRenamer_Props)
