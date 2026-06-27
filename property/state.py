import bpy
from ..ops.mesh.cleaner import M8_Clean_Props
from ..ops.misc.custom_tools import M8_CustomTools_Props
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
    selection_snapshot_names: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    selection_snapshot_active: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    selection_snapshot_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    health_status: bpy.props.EnumProperty(
        name="M8 Health Status",
        items=[
            ("UNKNOWN", "Unknown", ""),
            ("OK", "OK", ""),
            ("WARNING", "Warning", ""),
            ("ERROR", "Error", ""),
        ],
        default="UNKNOWN",
        options={"SKIP_SAVE"},
    )
    health_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    health_checked_at: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    health_details: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    full_check_status: bpy.props.EnumProperty(
        name="M8 Full Check Status",
        items=[
            ("UNKNOWN", "Unknown", ""),
            ("OK", "OK", ""),
            ("WARNING", "Warning", ""),
            ("ERROR", "Error", ""),
        ],
        default="UNKNOWN",
        options={"SKIP_SAVE"},
    )
    full_check_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    full_check_checked_at: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    full_check_details: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_status: bpy.props.EnumProperty(
        name="M8 Scene Audit Status",
        items=[
            ("UNKNOWN", "Unknown", ""),
            ("OK", "OK", ""),
            ("WARNING", "Warning", ""),
            ("ERROR", "Error", ""),
        ],
        default="UNKNOWN",
        options={"SKIP_SAVE"},
    )
    scene_audit_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_checked_at: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_details: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_problem_objects: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_last_scope: bpy.props.EnumProperty(
        name="Last Audit Scope",
        items=[
            ("SELECTED", "Selected", ""),
            ("VISIBLE", "Visible", ""),
            ("ALL", "Scene", ""),
        ],
        default="SELECTED",
        options={"SKIP_SAVE"},
    )
    scene_audit_last_fix_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_last_restore_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_last_backup_manage_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_fix_history: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_make_backup: bpy.props.BoolProperty(
        name="Backup Before Fix",
        default=True,
        options={"SKIP_SAVE"},
    )
    scene_audit_backup_collection_name: bpy.props.StringProperty(
        name="Backup Collection",
        default="M8_Audit_Backups",
        options={"SKIP_SAVE"},
    )
    scene_audit_high_poly_threshold: bpy.props.IntProperty(
        name="High Poly Threshold",
        default=100000,
        min=100,
        soft_max=1000000,
        options={"SKIP_SAVE"},
    )
    scene_audit_backup_status: bpy.props.EnumProperty(
        name="M8 Scene Audit Backup Status",
        items=[
            ("UNKNOWN", "Unknown", ""),
            ("OK", "OK", ""),
            ("WARNING", "Warning", ""),
            ("ERROR", "Error", ""),
        ],
        default="UNKNOWN",
        options={"SKIP_SAVE"},
    )
    scene_audit_backup_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_backup_checked_at: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_backup_details: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    scene_audit_backup_count: bpy.props.IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    scene_audit_backup_source_count: bpy.props.IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    scene_audit_backup_missing_source_count: bpy.props.IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    scene_audit_backup_keep_per_source: bpy.props.IntProperty(
        name="Keep Per Source",
        default=2,
        min=1,
        soft_max=10,
        options={"SKIP_SAVE"},
    )

class M8_ObjectState(bpy.types.PropertyGroup):
    """Encapsulated state for M8 Object-level tracking"""
    last_object_mode: bpy.props.StringProperty(default="")

def _register_class(cls):
    try:
        bpy.utils.register_class(cls)
    except ValueError:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def _unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass


def register():
    _register_class(M8_BakeRenamer_Props)
    _register_class(M8_SceneState)
    _register_class(M8_WMState)
    _register_class(M8_ObjectState)
    
    bpy.types.Scene.m8 = bpy.props.PointerProperty(type=M8_SceneState)
    bpy.types.WindowManager.m8 = bpy.props.PointerProperty(type=M8_WMState)
    bpy.types.Object.m8 = bpy.props.PointerProperty(type=M8_ObjectState)

def unregister():
    if hasattr(bpy.types.Scene, "m8"):
        del bpy.types.Scene.m8
    if hasattr(bpy.types.WindowManager, "m8"):
        del bpy.types.WindowManager.m8
    if hasattr(bpy.types.Object, "m8"):
        del bpy.types.Object.m8
    
    _unregister_class(M8_ObjectState)
    _unregister_class(M8_WMState)
    _unregister_class(M8_SceneState)
    _unregister_class(M8_BakeRenamer_Props)
