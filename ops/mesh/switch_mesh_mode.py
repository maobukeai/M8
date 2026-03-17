import bpy


class M8_OT_SwitchMeshMode(bpy.types.Operator):
    bl_idname = "m8.switch_mesh_mode"
    bl_label = "Switch Mesh Select Mode"
    bl_options = {"REGISTER", "UNDO"}

    select_mode: bpy.props.EnumProperty(
        items=[
            ("VERT", "VERT", ""),
            ("EDGE", "EDGE", ""),
            ("FACE", "FACE", ""),
        ],
        options={"ENUM_FLAG", "HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(obj and obj.type == "MESH")

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT", toggle=False)

        # Handle Shift-Click behavior (Extend/Toggle)
        # Check current state to decide action
        msm = context.tool_settings.mesh_select_mode
        current_modes = {
            "VERT": msm[0],
            "EDGE": msm[1],
            "FACE": msm[2],
        }
        
        target_modes = self.select_mode
        if len(target_modes) == 1:
            mode = list(target_modes)[0]
            # Standard single mode switch
            if not current_modes[mode]:
                 # If not active, activate it (exclusive if not extending)
                 # Wait, logic is complex.
                 # Let's trust blender's operator property?
                 # Blender's select_mode operator handles extend.
                 pass
                 
        # Simply pass through to blender operator but with better defaults?
        # Actually, let's implement the logic:
        # If we just call select_mode, it works.
        # But we want to support multi-mode setting if passed.
        
        # If multiple modes passed, enable all
        # If self.select_mode is a set in python, but here it's EnumProperty set?
        # EnumProperty with ENUM_FLAG returns a set of strings.
        
        modes_to_set = self.select_mode
        
        # If we want to support "Smart Toggle":
        # If Shift is held (handled by keymap calling with extend=True? No, keymap passes properties)
        # We don't have event here easily unless invoke.
        # So we assume the caller set the properties correctly.
        
        # But wait, the original code loops. This is bad for "Mix Mode".
        # We should calculate the final boolean triplet and set it once if possible?
        # bpy.ops.mesh.select_mode only accepts ONE type string.
        # To set mixed mode (e.g. Vert+Edge), we need to call it multiple times with use_extend=True.
        
        # Let's optimize:
        # 1. Clear others if not extending?
        # The original code:
        # first=True -> use_extend=False (Clears others), action=TOGGLE
        # next -> use_extend=True, action=ENABLE
        
        # This logic forces the first mode in the loop to clear others.
        # If we want to set "VERT" and "EDGE", 
        # 1. VERT (Clear others, Toggle)
        # 2. EDGE (Extend, Enable)
        
        # This seems correct for setting a specific combination.
        
        # But if we want to ADD to existing selection mode (Shift Click in UI), 
        # we need to know if we are "Adding".
        # The operator properties don't have "extend".
        
        # Let's stick to the original logic but ensure it's robust.
        # Actually, let's just use the loop as it was, it works for setting specific modes.
        # But we can add a check to avoid redundant calls.
        
        target_list = list(self.select_mode)
        if not target_list:
            return {"FINISHED"}
            
        # Priority: VERT > EDGE > FACE ? Order in set is undefined.
        # Sort them to ensure consistency?
        # ENUM_FLAG set is usually not ordered.
        priority = ["VERT", "EDGE", "FACE"]
        sorted_modes = sorted(list(self.select_mode), key=lambda x: priority.index(x) if x in priority else 99)
        
        first = True
        for mode in sorted_modes:
            bpy.ops.mesh.select_mode(
                type=mode,
                use_extend=not first, # First one clears previous if multiple? 
                                    # Wait, if I want to set VERT+EDGE, 
                                    # 1. VERT (Extend=False) -> Clears Face, sets Vert
                                    # 2. EDGE (Extend=True) -> Keeps Vert, sets Edge
                                    # Result: VERT+EDGE. Correct.
                action="ENABLE", # Always enable, don't toggle. Toggle is confusing for script usage.
                use_expand=False,
            )
            first = False

        return {"FINISHED"}
