from bl_ui.space_statusbar import STATUSBAR_HT_header



def draw_status_bar(self, context):
    row = self.layout.row(align=True)

    ro = row.row(align=True)
    ro.label(icon="MOUSE_LMB")
    ro.label(text="Confirm")
    row.separator(factor=2)

    ro = row.row(align=True)
    ro.label(icon="MOUSE_MMB")
    ro.label(text="Move View")
    row.separator(factor=2)

    ro = row.row(align=True)
    ro.label(icon="MOUSE_RMB")
    ro.label(icon="EVENT_ESC")
    ro.label(text="  ")
    ro.label(text="Cancel")
    row.separator(factor=2)

    ro = row.row(align=True)
    ro.label(icon="EVENT_S")
    ro.label(text="Bisect")
    row.separator(factor=2)

    ro = row.row(align=True)
    ro.label(icon="EVENT_M")
    ro.label(text="Use Modifier")
    row.separator(factor=10)

    row.label(text="Axis:")

    ro = row.row(align=True)
    ro.label(icon="EVENT_C")
    ro.label(text="Cursor")
    row.separator(factor=2)

    ro = row.row(align=True)
    ro.label(icon="EVENT_W")
    ro.label(text="World")
    row.separator(factor=2)

    ro = row.row(align=True)
    ro.label(icon="EVENT_A")
    ro.label(text="Active")
    row.separator(factor=3)

    ro = row.row(align=True)
    ro.label(icon="EVENT_O")
    ro.label(text="or")
    ro.label(icon="EVENT_Z")
    ro.label(text="Origin")
    row.separator(factor=2)


class StatusBar:
    origin_draw_func = None
    operator_runtime = None

    def replace_status_bar(self, context):
        """将状态栏替换"""
        if StatusBar.origin_draw_func is None:
            StatusBar.origin_draw_func = STATUSBAR_HT_header.draw
            StatusBar.operator_runtime = self
        STATUSBAR_HT_header.draw = draw_status_bar

    @staticmethod
    def restore_status_bar():
        """恢复状态栏"""
        if StatusBar.origin_draw_func is not None:
            STATUSBAR_HT_header.draw = StatusBar.origin_draw_func
            StatusBar.origin_draw_func = None
            StatusBar.operator_runtime = None
