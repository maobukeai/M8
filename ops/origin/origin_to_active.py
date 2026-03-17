import bmesh

from .public_origin import PublicOrigin
from ...utils import get_operator_bl_idname
from ...utils.curve import check_curve_select
from ...utils.math import from_curve_get_matrix, from_edit_bone_get_matrix


class OriginToActive(PublicOrigin):
    bl_idname = get_operator_bl_idname("origin_to_active")
    bl_label = "To Active"

    @classmethod
    def poll(cls, context):
        if context.mode == "EDIT_MESH":
            # return [v for v in bm.verts if v.select]
            bm = bmesh.from_edit_mesh(context.active_object.data)
            for v in bm.verts:
                if v.select:
                    bm.free()
                    return True
        elif context.mode == "OBJECT":
            return len(context.selected_objects) > 1
        elif context.mode == "EDIT_CURVE":
            return check_curve_select(context.edit_object.data)
        return False

    @classmethod
    def to_matrix(cls, context):
        act = context.active_object
        active = act
        if act not in context.selected_objects and context.selected_objects:
            active = context.selected_objects[-1]
        if context.mode == "EDIT_MESH":
            from ...utils.bmesh import from_bmesh_active_select_get_matrix

            bm = bmesh.from_edit_mesh(context.active_object.data)
            matrix = from_bmesh_active_select_get_matrix(bm, active)
            if matrix:
                return matrix

        elif context.mode == "EDIT_ARMATURE":
            ad = act.data.edit_bones.active
            if ad:
                return from_edit_bone_get_matrix(act, ad)

        elif context.mode == "POSE":
            ad = act.data.bones.active
            if ad:
                return from_edit_bone_get_matrix(act, ad)
        elif context.mode == "EDIT_CURVE":
            edit = context.edit_object
            if edit and edit.type == "CURVE":
                return from_curve_get_matrix(edit, edit.data)

        return active.matrix_world.copy()
