import bpy
from bpy.props import EnumProperty

from ...utils import get_operator_bl_idname
from ...utils.translate import translate_lines_text
from ...utils.view import screen_relevant_direction_3d_axis

DEBUG_ALIGN = False


class AlignObjectByView(bpy.types.Operator):
    bl_idname = get_operator_bl_idname("object_align_by_view")
    bl_label = "Object Align by View"
    bl_options = {"REGISTER", "UNDO"}

    align_mode: EnumProperty(
        name="Align Mode",
        items=[
            ("Align_Left_Up", "Left Up", ""),
            ("Align_Up", "Up", ""),
            ("Align_Right_Up", "Right Up", ""),
            ("Align_Left", "Left", ""),
            ("Align_Center", "Center", ""),
            ("Align_Right", "Right", ""),
            ("Align_Left_Down", "Left Down", ""),
            ("Align_Down", "Down", ""),
            ("Align_Right_Down", "Right Down", ""),
        ]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matrix_dict = None

    @classmethod
    def description(cls, context, properties):
        for i in properties.bl_rna.properties['align_mode'].enum_items:
            if i.identifier == properties.align_mode:
                return translate_lines_text(i.name)
        return "None"

    @classmethod
    def poll(cls, context):
        return context.selected_objects.__len__()

    def draw(self, context):
        column = self.layout.column(align=True)
        column.prop(self, "align_mode", expand=True)

    @staticmethod
    def draw_nine_square_box(layout: bpy.types.UILayout, icon_only=True):
        """绘制对齐九宫格"""
        col = layout.column(align=True)

        row = col.row(align=True)
        AlignObjectByView._item_(row, "Align_Left_Up", icon_only)
        AlignObjectByView._item_(row, "Align_Up", icon_only)
        AlignObjectByView._item_(row, "Align_Right_Up", icon_only)

        row = col.row(align=True)
        AlignObjectByView._item_(row, "Align_Left", icon_only)
        AlignObjectByView._item_(row, "Align_Center", icon_only)
        AlignObjectByView._item_(row, "Align_Right", icon_only)

        row = col.row(align=True)
        AlignObjectByView._item_(row, "Align_Left_Down", icon_only)
        AlignObjectByView._item_(row, "Align_Down", icon_only)
        AlignObjectByView._item_(row, "Align_Right_Down", icon_only)

    @staticmethod
    def _item_(layout: bpy.types.UILayout, identifier, icon_only=True):
        from ...utils.icon import get_custom_icon
        layout.operator(
            AlignObjectByView.bl_idname,
            icon_value=get_custom_icon(identifier),
            text="" if icon_only else identifier.replace("ALign_", "").replace("_", "")
        ).align_mode = identifier

    def invoke(self, context, event):
        bpy.ops.ed.undo_push(message="Push Undo")
        self.matrix_dict = {obj.name: obj.matrix_world.copy() for obj in context.selected_objects}
        return self.execute(context)

    def execute(self, context):
        context.view_layer.update()
        for obj in context.selected_objects:
            obj.matrix_world = self.matrix_dict[obj.name]
            context.view_layer.update()
        context.view_layer.update()
        bpy.ops.m8.align_object("INVOKE_DEFAULT", **self.get_ops_args(context))
        context.view_layer.update()
        return {"FINISHED"}

    def get_ops_args(self, context):
        (x, x_), (y, y_) = screen_relevant_direction_3d_axis(context)
        axis_items = {
            "Align_Left_Up": {x_, y},
            "Align_Up": {y},
            "Align_Right_Up": {x, y},
            "Align_Left": {x_},
            "Align_Right": {x},
            "Align_Left_Down": {x_, y_},
            "Align_Down": {y_},
            "Align_Right_Down": {x, y_},

            "Align_Center": {"X", "Y", "Z"}
        }
        axis = axis_items[self.align_mode]
        args = dict(align_mode="ALIGN")

        for i in axis:
            value = "MIN" if len(i) >= 2 else "MAX"
            if self.align_mode == "Align_Center":
                value = "CENTER"
            args[f"align_{i[-1].lower()}_method"] = value
        args["align_location_axis"] = {i[-1] for i in axis}
        args["align_location"] = True
        if DEBUG_ALIGN:
            print(self.bl_idname, args)
        return args
