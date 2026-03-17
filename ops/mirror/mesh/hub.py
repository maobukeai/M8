from bpy.app.translations import pgettext_iface
from mathutils import Vector

from ....hub import clear_hub
from ....hub import hub_text


class MeshHub:
    matrix_hub = None
    active_coord = Vector()

    def update_mesh_hub(self, context):
        area_hash = hash(context.area)

        axis = f"{'-' if self.is_negative_axis else ''}{self.axis}"

        text = f"{pgettext_iface('Axis Mode')}:{pgettext_iface(self.axis_mode.title())} {pgettext_iface('Axis')}:{axis}"
        texts = [{"text": text}]

        red = 0.8
        if self.use_modifier:
            text = f"{pgettext_iface('Use Modifier')}: {pgettext_iface('Keep modifier, Can be adjusted later')}"
            texts.insert(0, {"text": text, "color": (red, 0.1, 0.1)})
        else:
            text = pgettext_iface('Directly mirror without using a modifier')
            texts.insert(0, {"text": text})

        if self.bisect:
            texts.insert(0, {"text": pgettext_iface('Bisect'), "color": (red, 0.1, 0.1)})

        hub_text(self.bl_idname, texts, timeout=None, area_restrictions=area_hash)

    def clear_mesh_hub(self):
        clear_hub(self.bl_idname)
        clear_hub(f"{self.bl_idname}_active")
        clear_hub(f"{self.bl_idname}_preview")
