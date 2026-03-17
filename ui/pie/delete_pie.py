import bpy

def _get_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None

def _add_delete_operator(layout, action_type):
    if action_type == 'DELETE_VERT':
        layout.operator("mesh.delete", text="顶点", icon='VERTEXSEL').type = 'VERT'
    elif action_type == 'DELETE_EDGE':
        layout.operator("mesh.delete", text="边", icon='EDGESEL').type = 'EDGE'
    elif action_type == 'DELETE_FACE':
        layout.operator("mesh.delete", text="面", icon='FACESEL').type = 'FACE'
    elif action_type == 'DISSOLVE_VERT':
        layout.operator("mesh.dissolve_verts", text="融并顶点", icon='VERTEXSEL')
    elif action_type == 'DISSOLVE_EDGE':
        layout.operator("mesh.dissolve_edges", text="融并边", icon='MOD_WIREFRAME')
    elif action_type == 'DISSOLVE_FACE':
        layout.operator("mesh.dissolve_faces", text="融并面", icon='FACESEL')
    elif action_type == 'LIMITED_DISSOLVE':
        layout.operator("mesh.dissolve_limited", text="有限融并", icon='MESH_DATA')
    elif action_type == 'EDGE_LOOP':
        layout.operator("mesh.delete_edgeloop", text="循环边", icon='MOD_EDGESPLIT')
    elif action_type == 'EDGE_COLLAPSE':
        layout.operator("mesh.edge_collapse", text="塌陷边", icon='UV_EDGESEL')
    elif action_type == 'ONLY_EDGE_FACE':
        layout.operator("mesh.delete", text="仅边和面", icon='EDGESEL').type = 'EDGE_FACE'
    elif action_type == 'ONLY_FACE':
        layout.operator("mesh.delete", text="仅面", icon='FACESEL').type = 'ONLY_FACE'
    elif action_type == 'DISSOLVE_ALL':
        col = layout.column(align=True)
        col.operator("m8.smart_dissolve", text="智能融并", icon='AUTOMERGE_ON')
        col.operator("mesh.dissolve_limited", text="有限融并", icon='MOD_DECIM')
    else:
        layout.separator()

class VIEW3D_MT_M8DeletePie(bpy.types.Menu):
    bl_label = "删除"
    bl_idname = "VIEW3D_MT_M8DeletePie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        prefs = _get_addon_prefs()
        
        if not prefs:
            _add_delete_operator(pie, "DELETE_VERT")
            _add_delete_operator(pie, "DELETE_FACE")
            _add_delete_operator(pie, "DELETE_EDGE")
            _add_delete_operator(pie, "DISSOLVE_ALL")
            _add_delete_operator(pie, "EDGE_LOOP")
            _add_delete_operator(pie, "EDGE_COLLAPSE")
            _add_delete_operator(pie, "ONLY_EDGE_FACE")
            _add_delete_operator(pie, "ONLY_FACE")
            return

        # Pie Menu Slots:
        # 1: Left, 2: Right, 3: Bottom, 4: Top
        # 5: Top-Left, 6: Top-Right, 7: Bottom-Left, 8: Bottom-Right
        
        # Note: Blender's pie menu order in code is: 
        # Left, Right, Bottom, Top, Top-Left, Top-Right, Bottom-Left, Bottom-Right
        
        _add_delete_operator(pie, prefs.delete_pie_left)
        _add_delete_operator(pie, prefs.delete_pie_right)
        _add_delete_operator(pie, prefs.delete_pie_down)
        _add_delete_operator(pie, prefs.delete_pie_up)
        _add_delete_operator(pie, prefs.delete_pie_top_left)
        _add_delete_operator(pie, prefs.delete_pie_top_right)
        _add_delete_operator(pie, prefs.delete_pie_bottom_left)
        _add_delete_operator(pie, prefs.delete_pie_bottom_right)
