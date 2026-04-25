import bpy
from .ops.mesh.random_islands import MESH_OT_SelectRandomIslands
from .ops.mesh.leaves_to_planes import MESH_OT_LeavesToPlanes
from .ops.mesh.scale_from_bottom_uv import MESH_OT_ScaleFromBottomUV
from .ops.mesh.extend_leaf_tip import MESH_OT_ExtendLeafTip
from .ops.origin.quick_origin import OBJECT_OT_QuickOrigin, OBJECT_OT_OriginToActive
from .ops.origin.mp7_origin_wrappers import (
    M8_OT_MP7CursorToSelectSmart,
    M8_OT_MP7OriginToActiveSmart,
    M8_OT_MP7OriginToCursorSmart,
)
from .ops.origin.auto_origin import register as register_auto_origin, unregister as unregister_auto_origin
from .ops.mesh.switch_mesh_mode import M8_OT_SwitchMeshMode
from .ops.mesh.switch_uv_mode import M8_OT_SwitchUVMode
from .ops.mesh.surface_sliding import M8_OT_SurfaceSliding
from .ops.mesh.optimization import (
    VIEW3D_MT_M8MeshOptimizationPie,
    M8_OT_MeshOptimizationMenu,
    M8_OT_MeshMergeByDistance,
    M8_OT_MeshDeleteLoose,
    M8_OT_MeshRecalcNormals,
    M8_OT_MeshLimitedDissolve,
    M8_OT_SmartDissolve,
)
from .ops.mesh.draw_texture import M8_OT_DrawSelected, M8_OT_CancelDrawSelected
from .ops.mesh.edge_property import (
    M8_OT_VertCrease,
    M8_OT_VertBevelWeight,
    M8_OT_EdgeCrease,
    M8_OT_EdgeBevelWeight,
    M8_OT_ClearAllEdgeProperty,
)
from .ops.object.transform import OBJECT_OT_SnapToFloor, OBJECT_OT_FreezeTransformsMaya
from .ops.object.auto_smooth import M8_OT_AutoSmooth
from .ops.object.light_quick_settings import M8_OT_LightQuickSettings
from .ops.object.camera_quick_settings import M8_OT_CameraQuickSettings
from .ops.object.select_scene_camera import M8_OT_SelectSceneCamera
from .ops.object.camera_focus_selected import M8_OT_CameraFocusSelected
from .ops.object.light_track_to_selected import M8_OT_LightTrackToSelected, M8_OT_LightClearTrackTo
from .ops.object.text_tools import M8_OT_TextQuickSettings
from .ops.object.curve_tools import M8_OT_CurveQuickSettings, M8_OT_CurveCyclicToggle, M8_OT_ObjectConvertToMesh
from .ops.object.curve_param_popup import M8_OT_CurveParamPopup
from .ops.object.mode_set_remember import M8_OT_ModeSetRemember
from .ops.object.curve_edit_tools import (
    M8_OT_CurveHandleTypeRemember,
    M8_OT_CurveSwitchDirectionRemember,
    M8_OT_CurveSubdivideRemember,
    M8_OT_CurveSmoothRemember,
)
from .ops.object.lattice_tools import M8_OT_LatticeMakeRegular
from .ops.object.quick_delete import M8_OT_QuickDelete
from .ops.object.rename import M8_OT_AdvancedRename
from .ops.object.baking_renaming import classes as baking_renaming_classes, register as register_baking_renaming, unregister as unregister_baking_renaming
from .ops.object.switch_mode import OBJECT_OT_SwitchMode, M8_OT_SwitchBoneMode
from .ops.object.double_click_edit_switch import M8_OT_DoubleClickEditSwitch
from .ops.object.group_tool import (
    M8_OT_GroupObjects,
    M8_OT_SelectGroup,
    M8_OT_DissolveGroup,
    M8_OT_AddToGroup,
    M8_OT_RemoveFromGroup,
    M8_OT_RecalculateGroupCenter,
    M8_OT_SetGroupOrigin,
    M8_OT_SelectGroupParent,
    M8_OT_LockGroup,
    M8_OT_UnlockGroup,
    M8_OT_DuplicateGroup,
    M8_OT_HideGroup,
    M8_OT_IsolateGroup,
    M8_OT_ToggleGroupEmptyVisibility,
    M8_OT_ShowAllGroups,
    M8_MT_GroupContextSubMenu,
    draw_group_context_menu,
)
from .ops.object.switch_image_mode import OBJECT_OT_SwitchImageMode
from .src import icons as mp7_icons
from .src import translate as mp7_translate
from .ops.object.cage_tool import (
    OBJECT_OT_CreateCage,
    OBJECT_OT_UpdateSnapshot,
    OBJECT_OT_FinishDetach,
    OBJECT_OT_FinishArchiveCage,
    OBJECT_OT_ActivateBackupCage,
    OBJECT_OT_ToggleBackupVisibility,
    OBJECT_OT_SelectSnapshotGroup,
    OBJECT_OT_DeleteBackupCages,
    OBJECT_OT_FinishAndClean,
    OBJECT_OT_RestoreFromSnapshot,
    OBJECT_OT_AutoAdjustZ,
    OBJECT_OT_ClearSnapshot
)
from .ops.scene.utils import OBJECT_OT_SwitchUnit, SCENE_OT_ResetSizeToolPadding
from .ui.panel.main import VIEW3D_PT_SizeAdjustPanel, VIEW3D_PT_SizeToolToolboxPanel
from .ui.pie.transform import VIEW3D_MT_SizeToolTransformPie, VIEW3D_MT_SizeToolObjectOrigin
from .ui.pie.switch_mode import (
    VIEW3D_MT_M8SwitchModePie,
    VIEW3D_MT_M8CurveConvertPie,
    VIEW3D_MT_M8CurveEditPie,
    VIEW3D_MT_M8TextEditPie,
)
from .ui.pie.shading import VIEW3D_MT_M8ShadingPie
from .ui.pie.delete_pie import VIEW3D_MT_M8DeletePie
from .ui.pie.save import VIEW3D_MT_M8SavePie
from .ui.pie.edge_property_pie import VIEW3D_MT_M8EdgePropertyPie
from .ui.pie.switch_editor_pie import VIEW3D_MT_M8SwitchEditorPie, M8_OT_SwitchEditorArea
from .ui.pie.align_generic import M8_OT_AlignPieContextCall
from .ops.smart_tools import (
    M8_OT_SmartVert,
    M8_OT_SmartEdge,
    M8_OT_SmartFace,
    M8_OT_CleanUp,
    M8_OT_SmartMergeCenter,
    M8_OT_SmartPathsMerge,
    M8_OT_SmartPathsConnect,
    M8_OT_SmartToggleSharp,
    M8_OT_SmartOffsetEdges,
    M8_OT_SmartSlideExtend,
    M8_OT_SmartEdgeToggleMode,
)
from .ops.toggle_area import M8_OT_ToggleArea
from .ui.pie.smart_pie import VIEW3D_MT_M8SmartPie
from .ops.mesh.cleaner import (
    M8_Clean_Props,
    MESH_OT_smart_edge_loop_cleaner,
    MESH_OT_simple_edge_loop_cleaner,
    MESH_OT_auto_unsubdivide,
    MESH_OT_decimate_selected,
    MESH_OT_dissolve_edges,
    MESH_OT_mark_sharp,
    MESH_OT_checker_deselect,
    MESH_OT_auto_unbevel_similar,
    MESH_OT_select_short_edges,
    MESH_OT_unbevel_selected,
    MESH_OT_flat_loop_cleaner,
    MESH_OT_select_similar_loops,
    MESH_OT_flatten_loops,
)
from .ops.custom_tools import (
    M8_OT_SortMaterials,
    M8_OT_MergeNearbyObjects,
    M8_OT_BatchCopyAlign,
    M8_OT_AlignOriginToNormal,
    VIEW3D_PT_M8_CustomTools,
    M8_CustomTools_Props,
    M8_MP7_MockDrawProperty,
    SIZE_TOOL_Preferences,
    SIZE_TOOL_OT_ResetTransformPieKeymap,
    SIZE_TOOL_OT_ForceTransformPiePriority,
    SIZE_TOOL_OT_ForceSwitchModePriority,
    SIZE_TOOL_OT_ForceAlignPiePriority,
    SIZE_TOOL_OT_ForceSavePiePriority,
    SIZE_TOOL_OT_ForceEdgePropertyPiePriority,
    SIZE_TOOL_OT_ForceMirrorPriority,
    SIZE_TOOL_OT_ForceGroupToolPriority,
    SIZE_TOOL_OT_ExclusiveTransformPieHotkey,
    SIZE_TOOL_OT_RestoreShiftSConflicts,
    SIZE_TOOL_OT_ExclusiveAlignPieHotkey,
    SIZE_TOOL_OT_RestoreAltAConflicts,
    SIZE_TOOL_OT_ExclusiveSavePieHotkey,
    SIZE_TOOL_OT_RestoreCtrlSConflicts,
    SIZE_TOOL_OT_ExclusiveEdgePropertyPieHotkey,
    SIZE_TOOL_OT_RestoreShiftEConflicts,
    SIZE_TOOL_OT_ExclusiveMirrorHotkey,
    SIZE_TOOL_OT_RestoreShiftAltXConflicts,
    SIZE_TOOL_OT_ExclusiveGroupToolHotkey,
    SIZE_TOOL_OT_RestoreCtrlGConflicts,
    SIZE_TOOL_OT_ForceDeletePiePriority,
    SIZE_TOOL_OT_ForceRenamePriority,
    SIZE_TOOL_OT_ForceShadingPiePriority,
    SIZE_TOOL_OT_ForceSmartPiePriority,
    SIZE_TOOL_OT_ForceSwitchEditorPriority,
    SIZE_TOOL_OT_ForceToggleAreaPriority,
    SIZE_TOOL_OT_ExclusiveAllHotkeys,
    SIZE_TOOL_OT_RestoreAllConflicts,
    M8_OT_ResetSwitchModePrefs,
    M8_OT_ResetPrefsUI,
    register_keymaps,
    unregister_keymaps,
    update_keymaps
)

CLASSES = [
    M8_OT_SortMaterials,
    M8_OT_MergeNearbyObjects,
    M8_OT_BatchCopyAlign,
    M8_OT_AlignOriginToNormal,
    VIEW3D_PT_M8_CustomTools,
    M8_CustomTools_Props,
    M8_MP7_MockDrawProperty,
    SIZE_TOOL_Preferences,
    SIZE_TOOL_OT_ResetTransformPieKeymap,
    SIZE_TOOL_OT_ForceTransformPiePriority,
    SIZE_TOOL_OT_ForceSwitchModePriority,
    SIZE_TOOL_OT_ExclusiveTransformPieHotkey,
    SIZE_TOOL_OT_RestoreShiftSConflicts,
    SIZE_TOOL_OT_ForceAlignPiePriority,
    SIZE_TOOL_OT_ExclusiveAlignPieHotkey,
    SIZE_TOOL_OT_RestoreAltAConflicts,
    SIZE_TOOL_OT_ForceSavePiePriority,
    SIZE_TOOL_OT_ExclusiveSavePieHotkey,
    SIZE_TOOL_OT_RestoreCtrlSConflicts,
    SIZE_TOOL_OT_ForceEdgePropertyPiePriority,
    SIZE_TOOL_OT_ExclusiveEdgePropertyPieHotkey,
    SIZE_TOOL_OT_RestoreShiftEConflicts,
    SIZE_TOOL_OT_ForceMirrorPriority,
    SIZE_TOOL_OT_ExclusiveMirrorHotkey,
    SIZE_TOOL_OT_RestoreShiftAltXConflicts,
    SIZE_TOOL_OT_ForceGroupToolPriority,
    SIZE_TOOL_OT_ExclusiveGroupToolHotkey,
    SIZE_TOOL_OT_RestoreCtrlGConflicts,
    SIZE_TOOL_OT_ExclusiveAllHotkeys,
    SIZE_TOOL_OT_RestoreAllConflicts,
    M8_OT_ResetSwitchModePrefs,
    M8_OT_ResetPrefsUI,
    MESH_OT_SelectRandomIslands,
    MESH_OT_LeavesToPlanes,
    MESH_OT_ScaleFromBottomUV,
    MESH_OT_ExtendLeafTip,
    OBJECT_OT_QuickOrigin,
    OBJECT_OT_OriginToActive,
    M8_OT_MP7CursorToSelectSmart,
    M8_OT_MP7OriginToActiveSmart,
    M8_OT_MP7OriginToCursorSmart,
    M8_OT_SwitchMeshMode,
    M8_OT_SwitchUVMode,
    M8_OT_SurfaceSliding,
    VIEW3D_MT_M8MeshOptimizationPie,
    M8_OT_MeshOptimizationMenu,
    M8_OT_MeshMergeByDistance,
    M8_OT_MeshDeleteLoose,
    M8_OT_MeshRecalcNormals,
    M8_OT_MeshLimitedDissolve,
    M8_OT_SmartDissolve,
    M8_OT_DrawSelected,
    M8_OT_CancelDrawSelected,
    M8_OT_VertCrease,
    M8_OT_VertBevelWeight,
    M8_OT_EdgeCrease,
    M8_OT_EdgeBevelWeight,
    M8_OT_ClearAllEdgeProperty,
    OBJECT_OT_SwitchMode,
    M8_OT_SwitchBoneMode,
    M8_OT_DoubleClickEditSwitch,
    M8_OT_GroupObjects,
    M8_OT_SelectGroup,
    M8_OT_DissolveGroup,
    M8_OT_AddToGroup,
    M8_OT_RemoveFromGroup,
    M8_OT_RecalculateGroupCenter,
    M8_OT_SetGroupOrigin,
    M8_OT_SelectGroupParent,
    M8_OT_LockGroup,
    M8_OT_UnlockGroup,
    M8_OT_DuplicateGroup,
    M8_OT_HideGroup,
    M8_OT_IsolateGroup,
    M8_OT_ToggleGroupEmptyVisibility,
    M8_OT_ShowAllGroups,
    M8_MT_GroupContextSubMenu,
    OBJECT_OT_SwitchImageMode,
    OBJECT_OT_SnapToFloor,
    OBJECT_OT_FreezeTransformsMaya,
    M8_OT_AutoSmooth,
    M8_OT_LightQuickSettings,
    M8_OT_CameraQuickSettings,
    M8_OT_SelectSceneCamera,
    M8_OT_CameraFocusSelected,
    M8_OT_LightTrackToSelected,
    M8_OT_LightClearTrackTo,
    M8_OT_TextQuickSettings,
    M8_OT_CurveQuickSettings,
    M8_OT_CurveCyclicToggle,
    M8_OT_ObjectConvertToMesh,
    M8_OT_CurveParamPopup,
    M8_OT_ModeSetRemember,
    M8_OT_CurveHandleTypeRemember,
    M8_OT_CurveSwitchDirectionRemember,
    M8_OT_CurveSubdivideRemember,
    M8_OT_CurveSmoothRemember,
    M8_OT_LatticeMakeRegular,
    M8_OT_QuickDelete,
    M8_OT_AdvancedRename,
    OBJECT_OT_CreateCage,
    OBJECT_OT_UpdateSnapshot,
    OBJECT_OT_FinishDetach,
    OBJECT_OT_FinishArchiveCage,
    OBJECT_OT_ActivateBackupCage,
    OBJECT_OT_ToggleBackupVisibility,
    OBJECT_OT_SelectSnapshotGroup,
    OBJECT_OT_DeleteBackupCages,
    OBJECT_OT_FinishAndClean,
    OBJECT_OT_RestoreFromSnapshot,
    OBJECT_OT_AutoAdjustZ,
    OBJECT_OT_ClearSnapshot,
    OBJECT_OT_SwitchUnit,
    SCENE_OT_ResetSizeToolPadding,
    VIEW3D_PT_SizeAdjustPanel,
    VIEW3D_PT_SizeToolToolboxPanel,
    VIEW3D_MT_SizeToolTransformPie,
    VIEW3D_MT_SizeToolObjectOrigin,
    VIEW3D_MT_M8SwitchModePie,
    VIEW3D_MT_M8CurveConvertPie,
    VIEW3D_MT_M8CurveEditPie,
    VIEW3D_MT_M8TextEditPie,
    VIEW3D_MT_M8ShadingPie,
    VIEW3D_MT_M8DeletePie,
    VIEW3D_MT_M8SavePie,
    VIEW3D_MT_M8EdgePropertyPie,
    VIEW3D_MT_M8SwitchEditorPie,
    M8_OT_SwitchEditorArea,
    M8_OT_AlignPieContextCall,
    M8_OT_OpenCurrentFolder,
    M8_OT_OpenTempDir,
    M8_OT_OpenAutoSave,
    M8_OT_SwitchFile,
    M8_OT_IncrementalSave,
    M8_OT_ExportFBX,
    M8_OT_ToggleUnityFBXPreset,
    M8_OT_ResetUnityFBXPreset,
    M8_OT_PackResources,
    M8_OT_PurgeUnusedMaterials,
    M8_OT_ShowSaveReport,
    M8_OT_PlaceholderOp,
    M8_OT_OpenPreferences,
    M8_OT_ToggleScreencastKeys,
    M8_OT_CreateAssetGroup,
    M8_OT_OrphansPurgeKeepAssets,
    M8_OT_CallOperatorWithAddon,
    M8_ImageSavePresetProps,
    M8_OT_AppendFilenameSuffix,
    M8_OT_SetFilenamePrefix,
    FILEBROWSER_PT_m8_image_save_presets,
    FILEBROWSER_PT_m8_image_save_presets_extra,
    M8_OT_InternalScreencast,
    RestartBlender,
    M8_OT_SmartPassThroughWrapper,
    Mirror,
    AlignObject,
    AlignObjectByView,
    AlignMesh,
    AlignUV,
    Relax,
    Straighten,
    OriginToBottom,
    OriginToCursor,
    OriginToActive,
    CursorToSelect,
    AlignMeshPie,
    AlignObjectPie,
    AlignUVPie,
    M8_OT_SmartVert,
    M8_OT_SmartEdge,
    M8_OT_SmartFace,
    M8_OT_CleanUp,
    M8_OT_SmartMergeCenter,
    M8_OT_SmartPathsMerge,
    M8_OT_SmartPathsConnect,
    M8_OT_SmartToggleSharp,
    M8_OT_SmartOffsetEdges,
    M8_OT_SmartSlideExtend,
    M8_OT_SmartEdgeToggleMode,
    M8_OT_ToggleArea,
    VIEW3D_MT_M8SmartPie,
    M8_Clean_Props,
    MESH_OT_smart_edge_loop_cleaner,
    MESH_OT_simple_edge_loop_cleaner,
    MESH_OT_auto_unsubdivide,
    MESH_OT_decimate_selected,
    MESH_OT_dissolve_edges,
    MESH_OT_mark_sharp,
    MESH_OT_checker_deselect,
    MESH_OT_auto_unbevel_similar,
    MESH_OT_select_short_edges,
    MESH_OT_unbevel_selected,
    MESH_OT_flat_loop_cleaner,
    MESH_OT_select_similar_loops,
    MESH_OT_flatten_loops,
    VIEW3D_PT_M8_CleanUp,
    VIEW3D_PT_M8_MeshCleaner,
]

CLASSES.extend(baking_renaming_classes)

_startup_timer_registered = False
_startup_apply_runs = 0
_startup_done = False          # True after the first successful full init
_registration_errors = []

def _get_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

def _startup_apply():
    global _startup_apply_runs, _startup_done
    prefs = _get_addon_prefs()
    wm = bpy.context.window_manager if bpy.context else None
    if not prefs or not wm or not getattr(wm, "keyconfigs", None):
        # Blender not ready yet, keep waiting (counts towards the 10-run limit)
        _startup_apply_runs += 1
        if _startup_apply_runs < 10:
            return 0.5
        return None

    # Force register keymaps after startup to ensure they stick.
    # Sometimes addon prefs are not fully ready when _startup_apply first runs.
    keymap_ok = False
    try:
        register_keymaps()
        if prefs:
            update_keymaps(prefs, bpy.context)
        keymap_ok = True
    except Exception:
        pass

    if not _startup_done:
        # --- First successful run: perform one-time init ---
        exclusive_ok = True
        if getattr(prefs, "auto_exclusive_shift_s_on_startup", False):
            try:
                bpy.ops.size_tool.exclusive_transform_pie_hotkey()
                bpy.ops.size_tool.exclusive_align_pie_hotkey()
                bpy.ops.size_tool.exclusive_edge_property_pie_hotkey()
                bpy.ops.size_tool.exclusive_save_pie_hotkey()
            except Exception:
                exclusive_ok = False  # ops not ready, must retry

        if getattr(prefs, "auto_new_object_origin_bottom", True):
            register_auto_origin()
        else:
            unregister_auto_origin()

        try:
            enabled = bool(getattr(prefs, "auto_pack_resources_on_save", False)) or bool(getattr(prefs, "auto_purge_unused_materials_on_save", False))
            if enabled:
                register_auto_pack()
            else:
                unregister_auto_pack()
        except Exception:
            pass

        if keymap_ok and exclusive_ok:
            _startup_done = True  # all good, no need for further full inits

    _startup_apply_runs += 1

    # Early exit: once init succeeded, keep at most 2 extra safety passes then stop.
    if _startup_done and _startup_apply_runs >= 2:
        return None

    # Fallback: give up after 10 attempts regardless
    if _startup_apply_runs < 10:
        return 0.5
    return None


def _set_windows_console_utf8():
    import platform

    if platform.system() != "Windows":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

def register():
    global _startup_timer_registered
    global _startup_apply_runs
    global _startup_done
    global _registration_errors
    from .utils.logger import get_logger
    logger = get_logger()
    
    _registration_errors = []
    _set_windows_console_utf8()
    try:
        m8_icons.register()
    except Exception as e:
        logger.error(f"Failed to register m8_icons: {e}", exc_info=True)

    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            try:
                bpy.utils.unregister_class(cls)
                bpy.utils.register_class(cls)
            except Exception as e:
                _registration_errors.append(cls)
                logger.error(f"Failed to re-register class {cls.__name__}: {e}", exc_info=True)
        except Exception as e:
            _registration_errors.append(cls)
            logger.error(f"Failed to register class {cls.__name__}: {e}", exc_info=True)
    
    prefs = _get_addon_prefs()
    if not prefs or getattr(prefs, "auto_new_object_origin_bottom", True):
        register_auto_origin()
    try:
        mp7_icons.register()
    except Exception as e:
        logger.error(f"Failed to register mp7_icons: {e}", exc_info=True)
    try:
        mp7_translate.register()
    except Exception as e:
        logger.error(f"Failed to register mp7_translate: {e}", exc_info=True)
    register_keymaps()
    if hasattr(bpy.types, "TOPBAR_MT_editor_menus"):
        bpy.types.TOPBAR_MT_editor_menus.append(draw_restart_blender_top_bar)
    
    # Register Group Tool Context Menu
    # Prepend to make it more visible at the top
    bpy.types.VIEW3D_MT_object_context_menu.prepend(draw_group_context_menu)

    if prefs:
        try:
            enabled = bool(getattr(prefs, "auto_pack_resources_on_save", False)) or bool(getattr(prefs, "auto_purge_unused_materials_on_save", False))
            if enabled:
                register_auto_pack()
            else:
                unregister_auto_pack()

            # Ensure Unity FBX global scale default is 100.0 if somehow stuck at 1.0 (migration fix)
            if hasattr(prefs, "unity_fbx_global_scale"):
                current_val = getattr(prefs, "unity_fbx_global_scale", 1.0)
                if abs(current_val - 1.0) < 0.001:
                    prefs.unity_fbx_global_scale = 100.0
        except Exception:
            pass
            
    from .property import state
    state.register()

    if (not bpy.app.background) and (not _startup_timer_registered):
        _startup_apply_runs = 0
        _startup_done = False
        bpy.app.timers.register(_startup_apply, first_interval=0.1)
        _startup_timer_registered = True

    try:
        register_baking_renaming()
    except Exception:
        import traceback
        traceback.print_exc()

def unregister():
    global _startup_timer_registered
    from .utils.logger import get_logger
    logger = get_logger()

    unregister_keymaps()
    try:
        mp7_translate.unregister()
    except Exception as e:
        logger.error(f"Failed to unregister mp7_translate: {e}", exc_info=True)
    try:
        mp7_icons.unregister()
    except Exception as e:
        logger.error(f"Failed to unregister mp7_icons: {e}", exc_info=True)
    if hasattr(bpy.types, "TOPBAR_MT_editor_menus"):
        bpy.types.TOPBAR_MT_editor_menus.remove(draw_restart_blender_top_bar)
    
    # Unregister Group Tool Context Menu
    try:
        bpy.types.VIEW3D_MT_object_context_menu.remove(draw_group_context_menu)
    except Exception as e:
        logger.error(f"Failed to unregister group context menu: {e}", exc_info=True)

    try:
        unregister_auto_origin()
    except Exception as e:
        logger.warning(f"Failed to unregister auto origin: {e}")
    try:
        unregister_baking_renaming()
    except Exception as e:
        logger.warning(f"Failed to unregister baking renaming: {e}")
    try:
        unregister_auto_pack()
    except Exception as e:
        logger.warning(f"Failed to unregister auto pack: {e}")
    _startup_timer_registered = False

    from .property import state
    try:
        state.unregister()
    except Exception as e:
        logger.debug(f"Failed to unregister state properties: {e}")

    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            logger.debug(f"Class {cls.__name__} was not unregistered properly: {e}")
    
    try:
        m8_icons.unregister()
    except Exception as e:
        logger.warning(f"Failed to unregister m8_icons: {e}")
