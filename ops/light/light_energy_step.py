import bpy

from ...utils.i18n import _T


class M8_OT_LightEnergyStep(bpy.types.Operator):
    bl_idname = "m8.light_energy_step"
    bl_label = _T("灯光能量步进")
    bl_options = {"REGISTER", "UNDO"}

    delta: bpy.props.FloatProperty(name="Delta", default=10.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == "LIGHT" and obj.data and hasattr(obj.data, "energy"))

    def execute(self, context):
        obj = context.active_object
        light = obj.data
        try:
            light.energy = max(0.0, float(light.energy) + float(self.delta))
        except Exception:
            self.report({"WARNING"}, _T("调整灯光能量失败"))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{_T('灯光能量：')}{light.energy:.1f}")
        return {"FINISHED"}
