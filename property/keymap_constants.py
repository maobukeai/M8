import bpy

PIE_MENU_ID = "VIEW3D_MT_size_tool_transform_pie"
SWITCH_MODE_PIE_ID = "VIEW3D_MT_m8_switch_mode_pie"
EDGE_PROPERTY_PIE_ID = "VIEW3D_MT_m8_edge_property_pie"
SWITCH_EDITOR_PIE_ID = "M8_MT_switch_editor_pie"
MIRROR_OP_ID = "m8.mirror"

TRANSFORM_PIE_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
    ("3D View Generic", "EMPTY"),
)
SWITCH_MODE_KEYMAP_BINDINGS = (
    ("Object Non-modal", "EMPTY"),
    ("Image", "IMAGE_EDITOR"),
    ("Node Editor", "NODE_EDITOR"),
    # Grease Pencil
    ("Grease Pencil", "EMPTY"),
    ("Grease Pencil (Legacy)", "EMPTY"),  # 旧版蜡笔 keymap 可能带后缀
    ("Grease Pencil Stroke Edit Mode", "EMPTY"),
    ("Grease Pencil Paint Mode", "EMPTY"),
    ("Grease Pencil Sculpt Mode", "EMPTY"),
    ("Grease Pencil Weight Paint Mode", "EMPTY"),
    ("Grease Pencil Vertex Paint Mode", "EMPTY"),
    # Grease Pencil 3.0 (Blender 4.3+)
    ("Grease Pencil Edit Mode", "EMPTY"),
    ("Grease Pencil Draw Mode", "EMPTY"),
    ("Grease Pencil Sculpt Mode", "EMPTY"), # 新版可能复用名称，但也可能不同
)
QUICK_DELETE_KEYMAP_BINDINGS = (
    ("Object Mode", "EMPTY"),
    ("Object Non-modal", "EMPTY"),
    ("Node Editor", "NODE_EDITOR"),
    ("Node Generic", "NODE_EDITOR"),
)
DELETE_PIE_KEYMAP_BINDINGS = (
    ("Mesh", "EMPTY"),
)
DELETE_PIE_ID = "VIEW3D_MT_M8DeletePie"
EDGE_PROPERTY_PIE_KEYMAP_BINDINGS = (
    ("Mesh", "EMPTY"),
)
ALIGN_OBJECT_PIE_ID = "M8_MT_ALIGN_OBJECT"
ALIGN_MESH_PIE_ID = "M8_MT_ALIGN_MESH"
ALIGN_UV_PIE_ID = "M8_MT_ALIGN_UV"
ALIGN_GENERIC_OP_ID = "m8.align_pie_context_call"

SHADING_PIE_ID = "VIEW3D_MT_m8_shading_pie"
SHADING_PIE_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
)

SAVE_PIE_ID = "VIEW3D_MT_m8_save_pie"
SAVE_PIE_KEYMAP_BINDINGS = (
    ("Window", "EMPTY"),
)
SWITCH_EDITOR_PIE_KEYMAP_BINDINGS = (
    ("Window", "EMPTY"),
)

RENAME_KEYMAP_BINDINGS = (
    ("Window", "EMPTY"),
)

MIRROR_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
    ("3D View Generic", "EMPTY"),
)

GROUP_TOOL_KEYMAP_BINDINGS = (
    ("Object Mode", "EMPTY"),
)

DOUBLE_CLICK_GROUP_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
)

ALIGN_PIE_KEYMAP_BINDINGS = (
    ("Object Mode", "VIEW_3D"),
    ("Mesh", "VIEW_3D"),
    ("UV Editor", "EMPTY"),
    ("3D View Generic", "VIEW_3D"),
)

SMART_PIE_ID = "VIEW3D_MT_M8SmartPie"
SMART_PIE_KEYMAP_BINDINGS = (
    ("Mesh", "EMPTY"),
)

TOGGLE_AREA_OP_ID = "m8.toggle_area"
TOGGLE_AREA_KEYMAP_BINDINGS = (
    ("3D View", "VIEW_3D"),
    ("Node Editor", "NODE_EDITOR"),
    ("Image", "IMAGE_EDITOR"),
)

SUBDIVISION_KEYMAP_BINDINGS = (
    ("Object Mode", "EMPTY"),
    ("Object Non-modal", "EMPTY"),
)
