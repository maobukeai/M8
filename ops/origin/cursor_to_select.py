import bmesh
from mathutils import Matrix, Vector

from .public_origin import PublicOrigin
from ...hub import hub_matrix
from ...utils import get_operator_bl_idname
from ...utils.math import from_edit_bone_get_matrix, from_curve_get_matrix, from_pose_bone_get_matrix


class CursorToSelect(PublicOrigin):
    bl_idname = get_operator_bl_idname("cursor_to_select")
    bl_label = "To Select"
    bl_options = {"REGISTER", "UNDO"}
    is_remember_matrix = False

    def execute(self, context):
        tm = self.synthetics_matrix(context.scene.cursor.matrix, self.to_matrix(context))  # 最终变换的
        hub_matrix("CURSOR_TO_SELECT", [tm, ])
        context.scene.cursor.matrix = tm
        return {"FINISHED"}

    @classmethod
    def to_matrix(cls, context) -> Matrix:
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
                return from_pose_bone_get_matrix(act, ad)
        elif context.mode == "EDIT_CURVE":
            edit = context.edit_object
            if edit and edit.type == "CURVE":
                return from_curve_get_matrix(edit, edit.data)
            

        from ...utils.math import location_to_matrix
        loc = Vector()
        for obj in context.selected_objects:
            loc += obj.matrix_world.translation
        loc /= len(context.selected_objects)
        lm = location_to_matrix(loc)
        if act in context.selected_objects:
            return lm @ act.matrix_world.to_euler().to_matrix().to_4x4()
        else:
            cm = context.scene.cursor.matrix.copy()
            cl = location_to_matrix(cm.translation)
            return cm @ cl.inverted() @ lm
