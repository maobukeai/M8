class GizmoInfo:
    show_gizmo = None

    @staticmethod
    def remember_gizmo_state(context):
        GizmoInfo.show_gizmo = context.space_data.show_gizmo
        context.space_data.show_gizmo = not context.space_data.show_gizmo
        context.space_data.show_gizmo = False

    @staticmethod
    def restore_gizmo_state(context):
        if context.space_data:
            context.space_data.show_gizmo = GizmoInfo.show_gizmo
        GizmoInfo.show_gizmo = None

    @staticmethod
    def check_runtime():
        """检查是否已经在运行时了,避免出现运行多个操作符模态"""
        return GizmoInfo.show_gizmo is not None
