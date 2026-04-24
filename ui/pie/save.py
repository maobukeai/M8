import bpy
from ...ops.file.save_pie_ops import (
    M8_OT_OpenCurrentFolder,
    M8_OT_OpenTempDir,
    M8_OT_OpenAutoSave,
    M8_OT_SwitchFile,
    M8_OT_IncrementalSave,
    M8_OT_ExportFBX,
    M8_OT_ToggleUnityFBXPreset,
    M8_OT_PackResources,
    M8_OT_PurgeUnusedMaterials,
    M8_OT_ToggleScreencastKeys,
    M8_OT_OpenPreferences,
    M8_OT_CreateAssetGroup,
    M8_OT_OrphansPurgeKeepAssets,
    M8_OT_CallOperatorWithAddon,
)
from ...ops.misc.screencast import M8_OT_InternalScreencast
from ...utils.adapter import get_adapter_blender_icon as _ICON
from ..icons import get_icon_id

def _safe_operator(layout, idname, text="", icon='NONE', icon_value=0, emboss=True, depress=False, **props):
    """安全调用 layout.operator()。
    icon_value（自定义预览图标）和 icon（内置图标名）不能同时传，
    优先使用有效的 icon_value，否则退回内置 icon。
    """
    try:
        if icon_value:
            # 自定义图标有效，只传 icon_value
            op = layout.operator(idname, text=text, icon_value=icon_value, emboss=emboss, depress=depress)
        else:
            # 退回内置图标
            op = layout.operator(idname, text=text, icon=icon, emboss=emboss, depress=depress)
        for k, v in props.items():
            setattr(op, k, v)
        return op
    except Exception:
        row = layout.row(align=True)
        row.enabled = False
        row.label(text=text or idname, icon="ERROR")
        return None

def _safe_menu(layout, menu_id, text="", icon='NONE', icon_value=0):
    """安全调用 layout.menu()，同上只传一种图标源。"""
    try:
        if icon_value:
            layout.menu(menu_id, text=text, icon_value=icon_value)
        else:
            layout.menu(menu_id, text=text, icon=icon)
        return True
    except Exception:
        row = layout.row(align=True)
        row.enabled = False
        row.label(text=text or menu_id, icon="ERROR")
        return False

def _get_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

def draw_top_ui(layout):
    # Main container row
    main_row = layout.row(align=True)
    
    # --- Left Column ---
    col_left = main_row.column(align=True)
    col_left.scale_x = 1.1
    
    # Box 1: Recent
    box = col_left.box()
    col = box.column(align=True)
    row = col.row(align=True)
    _safe_menu(row, "TOPBAR_MT_file_open_recent", text="(R) 最近打开文件", icon_value=get_icon_id("recent"), icon="FILE_HIDDEN")
    
    # Box 2: Open/Reload
    box = col_left.box()
    col = box.column(align=True)
    row = col.row(align=True)
    _safe_operator(row, M8_OT_OpenCurrentFolder.bl_idname, text="打开当前", icon_value=get_icon_id("open"), icon="FILE_FOLDER")
    _safe_operator(row, M8_OT_OpenTempDir.bl_idname, text="打开临时", icon_value=get_icon_id("temp"), icon="TEMP")
    
    row = col.row(align=True)
    _safe_operator(row, "wm.revert_mainfile", text="重新加载", icon="FILE_REFRESH")
    _safe_operator(row, M8_OT_OpenAutoSave.bl_idname, text="自动保存", icon_value=get_icon_id("autosave"), icon="RECOVER_LAST")
    
    # Box 3: Screencast / Keymap
    box = col_left.box()
    col = box.column(align=True)
    row = col.row(align=True)
    is_running = bool(getattr(M8_OT_InternalScreencast, "_running", False))
    _safe_operator(
        row,
        M8_OT_ToggleScreencastKeys.bl_idname,
        text="关闭屏幕投射" if is_running else "启用屏幕投射",
        icon="PAUSE" if is_running else "PLAY",
        depress=is_running,
    )
    _safe_operator(row, M8_OT_OpenPreferences.bl_idname, text="偏好设置", icon_value=get_icon_id("prefs"), icon="PREFERENCES")

    # --- Center Column (Import/Export) ---
    col_center = main_row.column(align=True)
    box = col_center.box()
    col = box.column(align=True)

    # Items
    # 1. All (Header)
    row = col.row(align=True)
    split = row.split(factor=0.25)
    
    c1 = split.column(align=True)
    c1.alignment = 'LEFT'
    c1.label(text="全部")
    
    split = split.split(factor=0.5)
    c2 = split.column(align=True)
    c2.menu("TOPBAR_MT_file_import", text="导入", icon="TRIA_DOWN")
    
    c3 = split.column(align=True)
    c3.menu("TOPBAR_MT_file_export", text="导出", icon="TRIA_DOWN")

    col.separator()

    # 2. Specific Items
    io_items = [
        ("OBJ", "io_scene_obj", "wm.obj_import", "wm.obj_export", {}, {}),
        ("glTF", "io_scene_gltf2", "import_scene.gltf", "export_scene.gltf", {}, {}),
        ("FBX", "io_scene_fbx", "import_scene.fbx", "export_scene.fbx", {}, {}),
        ("USD", "io_scene_usd", "wm.usd_import", "wm.usd_export", {}, {}),
    ]

    for label, module, imp, exp, imp_props, exp_props in io_items:
        row = col.row(align=True)
        is_fbx = (label == "FBX")
        split = row.split(factor=0.25)

        c1 = split.column(align=True)
        c1.alignment = 'LEFT'
        c1.label(text=label)

        split = split.split(factor=0.5)
        
        # Import
        c2 = split.column(align=True)
        op = c2.operator(M8_OT_CallOperatorWithAddon.bl_idname, text="导入", icon="IMPORT")
        op.module = module
        op.operator = imp
        op.invoke = True
        if imp_props:
            for k, v in imp_props.items():
                setattr(op, k, v)
        
        # Export
        c3 = split.column(align=True)
        if is_fbx:
            _safe_operator(c3, M8_OT_ExportFBX.bl_idname, text="导出", icon="EXPORT")
        else:
            op = c3.operator(M8_OT_CallOperatorWithAddon.bl_idname, text="导出", icon="EXPORT")
            op.module = module
            op.operator = exp
            op.invoke = True
            if exp_props:
                for k, v in exp_props.items():
                    setattr(op, k, v)

        if is_fbx:
            col.separator(factor=0.2)
            row_u = col.row(align=True)
            row_u.scale_y = 1.2
            
            prefs = _get_addon_prefs()
            enabled = bool(getattr(prefs, "fbx_export_unity_preset", False)) if prefs else False
            
            sub = row_u.row(align=True)
            sub.scale_x = 1.0
            if enabled:
                sub.alert = True
                
            _safe_operator(
                sub,
                M8_OT_ToggleUnityFBXPreset.bl_idname,
                text="Unity 预设已开启" if enabled else "启用 Unity 预设",
                icon_value=get_icon_id("unity"),
                icon="EXPORT",       # fallback: 有效的内置图标
                depress=enabled,
            )

    # Switch File Row (Below Import/Export)
    col.separator()
    row = col.row(align=True)
    op_prev = _safe_operator(row, M8_OT_SwitchFile.bl_idname, text="上一个文件",
                              icon_value=get_icon_id("prev"), icon="TRIA_LEFT")
    if op_prev: op_prev.direction = "PREV"
    
    op_next = _safe_operator(row, M8_OT_SwitchFile.bl_idname, text="下一个文件",
                              icon_value=get_icon_id("next"), icon="TRIA_RIGHT")
    if op_next: op_next.direction = "NEXT"

    # --- Right Column ---
    col_right = main_row.column(align=True)
    col_right.scale_x = 1.1
    box = col_right.box()
    col = box.column(align=True)
    
    row = col.row(align=True)
    _safe_operator(row, "wm.append", text="追加", icon="APPEND_BLEND")
    _safe_operator(row, "wm.link", text="关联", icon="LINK_BLEND")
    prev_ctx = row.operator_context
    row.operator_context = 'EXEC_DEFAULT'
    _safe_operator(row, "outliner.orphans_purge", text="清除", icon="BRUSH_DATA")
    row.operator_context = prev_ctx
    
    row = col.row(align=True)
    _safe_operator(row, M8_OT_PackResources.bl_idname, text="打包资源",
                   icon_value=get_icon_id("pack"), icon="PACKAGE")
    _safe_operator(row, "object.material_slot_remove_unused", text="清理材质",
                   icon_value=get_icon_id("purge"), icon="MATERIAL")

    row = col.row(align=True)
    _safe_operator(row, M8_OT_CreateAssetGroup.bl_idname, text="创建组资产", icon="ASSET_MANAGER")
    
    row = col.row(align=True)
    _safe_operator(row, "wm.read_homefile", text="清空.blend文件", icon="FILE_BLANK")
    _safe_operator(row, M8_OT_OrphansPurgeKeepAssets.bl_idname, text="保留资产", icon="LIBRARY_DATA_DIRECT")



class VIEW3D_MT_M8SavePie(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_m8_save_pie"
    bl_label = "保存, 打开, 追加"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        dirty = bool(getattr(bpy.data, "is_dirty", False))
        
        # 1. West (4): Open
        pie.operator("wm.open_mainfile", text="打开...", icon="FILE_FOLDER")
        
        # 2. East (6): Save
        pie.operator("wm.save_mainfile", text="保存*" if dirty else "保存", icon=_ICON("FILE_TICK"))
        
        # 3. South (2): Save As
        pie.operator("wm.save_as_mainfile", text="另存为*" if dirty else "另存为", icon="DUPLICATE")
        
        # 4. North (8): Top UI
        col = pie.column()
        draw_top_ui(col)
        
        # 5. NW (7): Empty
        pie.separator()
        
        # 6. NE (9): Empty
        pie.separator()
        
        # 7. SW (1): New
        pie.menu("TOPBAR_MT_file_new", text="新建", icon="FILE_NEW")
        
        # 8. SE (3): Incremental Save
        pie.operator(M8_OT_IncrementalSave.bl_idname, text="增量保存*" if dirty else "增量保存", icon="EXPORT")

