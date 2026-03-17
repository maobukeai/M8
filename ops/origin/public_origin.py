import bmesh
import bpy
from mathutils import Matrix, Vector

from ...hub import hub_matrix
from ...utils import get_pref
from ...utils.math import scale_to_matrix, location_to_matrix, rotation_to_matrix


def remember_matrix(context):
    if context.mode == "EDIT_MESH":
        bpy.ops.object.mode_set(mode='OBJECT')
        context.scene.update_tag()
        context.view_layer.update()
        bpy.ops.ed.undo_push(message="Push Undo")
        bpy.ops.object.mode_set(mode='EDIT')


class PublicOrigin(bpy.types.Operator):
    bl_options = {"REGISTER", "UNDO"}

    only_location: bool
    only_rotation: bool
    not_calculate_rotation: bool
    use_transform_data_origin: bool

    is_remember_matrix = True

    @classmethod
    def get_ui_ops_mesh_args(cls, context) -> dict:
        from bpy.app.translations import pgettext_iface
        if context.mode == "EDIT_MESH":
            select_mode = context.scene.tool_settings.mesh_select_mode[:]
            if select_mode == (True, False, False):
                return {"text": pgettext_iface("To Vert"), "icon": "VERTEXSEL"}
            elif select_mode == (False, True, False):
                return {"text": pgettext_iface("To Edge"), "icon": "EDGESEL"}
            elif select_mode == (False, False, True):
                return {"text": pgettext_iface("To Face"), "icon": "FACESEL"}
            else:
                return {"text": pgettext_iface("To Select"), "icon": "RESTRICT_SELECT_OFF"}
        return {"text": pgettext_iface(cls.bl_label), "icon": "TRIA_RIGHT"}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects)

    @classmethod
    def description(cls, context, properties):
        from ...utils.translate import translate_lines_text
        from bpy.app.translations import pgettext
        ops = pgettext(cls.bl_label)
        return translate_lines_text(
            pgettext("Set Selected Objects' Origin %s") % ops,
            "ALT: only set Origin Location",
            "CTRL: only set Origin Rotation"
        )

    def draw_event_error(self, __):
        layout = self.layout
        layout.label(text="Do not press ctrl and alt at the same time")
        layout.label(text="If you want to set the position and rotation at the same time please do not press")

    def draw_pref_error(self, _):
        pref = get_pref()

        layout = self.layout
        layout.label(text="Please select at least one of the default operations")
        layout.prop(pref, "origin_default_operator_types")

    def invoke(self, context, event):
        """
        invoke不应被覆写
        使用execute
        """
        from bpy.app.translations import pgettext_iface
        self.only_location, self.only_rotation = event.alt, event.ctrl
        if self.only_location and self.only_rotation:
            context.window_manager.popup_menu(self.__class__.draw_event_error,
                                              title=pgettext_iface("Error"),
                                              icon="INFO")
            return {'CANCELLED'}
        if not (self.only_location or self.only_rotation):
            pref = get_pref()
            pl = len(pref.origin_default_operator_types)

            if pl == 0:
                context.window_manager.popup_menu(self.__class__.draw_event_error,
                                                  title=pgettext_iface("Pref Error"),
                                                  icon="INFO")
                return {'CANCELLED'}
            if pl == 1:
                if "ROTATE" in pref.origin_default_operator_types:
                    self.only_rotation = True
                if "LOCATION" in pref.origin_default_operator_types:
                    self.only_location = True

        bpy.ops.ed.undo_push(message="Push Undo")
        if self.is_remember_matrix:
            remember_matrix(context)
            res = self.execute(context)
            remember_matrix(context)
        else:
            res = self.execute(context)
        return res

    def execute(self, context):
        to_matrix_fun = getattr(self, "to_matrix", None)  # to_matrix(context) -> Matrix
        to_matrix = to_matrix_fun(context) if to_matrix_fun else None
        get_obj_matrix = getattr(self, "get_obj_matrix", None)  # get_obj_matrix(context,object) -> Matrix
        if not to_matrix and not get_obj_matrix:
            self.report({'ERROR'}, "No to_matrix or get_obj_matrix")
            return {'CANCELLED'}

        preview_matrices = []
        if to_matrix:
            for obj in context.selected_objects:
                preview_matrices.append(self.set_matrix(context, obj, to_matrix))
                context.view_layer.update()
        elif get_obj_matrix:
            for obj in context.selected_objects:
                matrix = get_obj_matrix(obj)
                if matrix:
                    preview_matrices.append(self.set_matrix(context, obj, matrix))
                context.view_layer.update()
        hub_matrix("SET_ORIGIN", preview_matrices)
        return {'FINISHED'}

    def set_matrix(self,
                   context: bpy.types.Context,
                   obj: bpy.types.Object,
                   to_matrix: Matrix,
                   ):
        """
        from_matrix 直接从物体取
            # from_matrix: Matrix,
        1.如果是物体直接设置矩阵,如果是网格需要再计算一次顶点的变化
        """
        DEBUG_ORIGIN = False
        om = obj.matrix_world.copy()  # 原来的
        tm = self.synthetics_matrix(om, to_matrix)  # 最终变换的
        if DEBUG_ORIGIN:
            print("set_matrix", obj.name, obj.type)
            print("om =", om.__repr__())
            print("tm = ", tm.__repr__())

        transform_matrix = tm.inverted() @ om
        if obj.type == "MESH":
            context.view_layer.update()
            bm: bmesh.types.BMesh
            if context.mode == "EDIT_MESH":
                bm = bmesh.from_edit_mesh(obj.data)
            else:
                bm = bmesh.new()
                bm.from_mesh(obj.data)

            if DEBUG_ORIGIN:
                print("transform_matrix =", transform_matrix.__repr__())
            bm.transform(transform_matrix)
            bm.normal_update()
            if context.mode == "EDIT_MESH":
                bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=False)
            else:
                bm.to_mesh(obj.data)
            context.scene.update_tag(refresh={'TIME'})
            obj.update_tag(refresh={'OBJECT', 'DATA', 'TIME'})
            context.view_layer.update()
        elif obj.type == "CURVE":
            for spline in obj.data.splines:
                for point in spline.points:
                    co = point.co.copy()
                    new_co = transform_matrix @ Vector((co.x, co.y, co.z))
                    point.co = Vector((*new_co, co.w))
                for b_point in spline.bezier_points:
                    b_point.co = transform_matrix @ b_point.co
            context.view_layer.update()
        elif obj.type == "GPENCIL":
            for layer in obj.data.layers:
                for frame in layer.frames:
                    for stroke in frame.strokes:
                        for point in stroke.points:
                            point.co = transform_matrix @ point.co
            context.view_layer.update()
        elif obj.type == "SURFACE":
            # 会出现扭曲
            # for spline in obj.data.splines:
            #     for point in spline.points:
            #         point.co = transform_matrix @ point.co
            ...
        if DEBUG_ORIGIN:
            print()
        obj.matrix_world = tm
        return tm

    def synthetics_matrix(self, a_matrix, b_matrix) -> Matrix:
        """合成矩阵"""
        a_loc = location_to_matrix(a_matrix.translation)
        a_rot = rotation_to_matrix(a_matrix.to_euler())
        a_sca = scale_to_matrix(a_matrix.to_scale())

        b_loc = location_to_matrix(b_matrix.translation)
        b_rot = rotation_to_matrix(b_matrix.to_euler())
        if self.only_location:
            return b_loc @ a_rot @ a_sca
        elif self.only_rotation:
            return a_loc @ b_rot @ a_sca
        else:
            return b_loc @ b_rot @ a_sca
