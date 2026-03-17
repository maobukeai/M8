from bpy.props import EnumProperty

from ....utils.items import AXIS_ENUM_PROPERTY, ALIGN_METHOD_PROPERTY, AXIS,ENUM_ALIGN_MODE


class OperatorProperty:
    align_mode: EnumProperty(items=ENUM_ALIGN_MODE)

    align_location_axis: EnumProperty(
        default=set(AXIS),
        **AXIS_ENUM_PROPERTY
    )
    # 每个一个轴的对齐方式
    align_x_method: EnumProperty(name="X", **ALIGN_METHOD_PROPERTY)
    align_y_method: EnumProperty(name="Y", **ALIGN_METHOD_PROPERTY)
    align_z_method: EnumProperty(name="Z", **ALIGN_METHOD_PROPERTY)
