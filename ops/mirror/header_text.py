from bpy.app.translations import pgettext_iface


class HeaderText:
    @property
    def negative_axis(self):
        a = "-" if self.is_negative_axis else ""
        return f"{a}{self.axis}"

    def update_header_text(self, context):
        if context.area:
            mod_status = "ON" if self.use_modifier else "OFF"
            
            context.area.header_text_set(
                f"{pgettext_iface('Axis Mode')}: {pgettext_iface(self.axis_mode.title())} | "
                f"{pgettext_iface('Axis')}: {self.negative_axis} | "
                f"{pgettext_iface('Bisect')}: {'ON' if self.bisect else 'OFF'} | "
                f"Mod: {mod_status} | "
                f"[M]odifier [S]bisect [C]ursor [O]rigin [A]ctive"
            )

    @staticmethod
    def clear_header_text(context):
        if context.area:
            context.area.header_text_set(None)
