from .public_origin import PublicOrigin
from ...utils import get_operator_bl_idname


class OriginToCursor(PublicOrigin):
    bl_idname = get_operator_bl_idname("origin_to_cursor")
    bl_label = "To Cursor"

    @classmethod
    def poll(cls, context):
        return super().poll(context)

    @classmethod
    def to_matrix(cls, context):
        return context.scene.cursor.matrix.copy()
