from bpy.props import EnumProperty, FloatProperty, BoolProperty, StringProperty

from ....utils.items import AXIS_ENUM_PROPERTY, ALIGN_METHOD_PROPERTY, DEFAULT_XYZ_ENUM, ENUM_ALIGN_MODE


def __get_v__(self, key, default):
    key = f"{self.align_mode}_{key}"
    if key in self:
        return self[key]
    else:
        return default


def __set_v__(self, key, value):
    k = f"{self.align_mode}_{key}"
    self[k] = value


ENUM_DISTRIBUTION_SORTED_AXIS = [
    ("0", "X", "Sort distribution by X axis"),
    ("1", "Y", "Sort distribution by Y axis"),
    ("2", "Z", "Sort distribution by X axis"),
]
ENUM_GROUND_DOWN_MODE = [
    ("ALL", "All Object", ""),
    ("MINIMUM", "Lowest Object", ""),
]
ENUM_GROUND_PLANE_MODE = [
    ("GROUND", "Ground", "Align To Ground"),
    ("DESIGNATED_OBJECT", "Object", "Align to Designated Object Z"),
    ("RAY_CASTING", "Fall", "Align To Z Ray Casting Object"),
]
ENUM_DISTRIBUTION_MODE = [
    ("FIXED", "Fixed", "Fixed the nearest and farthest objects"),
    ("ADJUSTMENT", "Adjustment", "Adjust the distance between each object(Fixed active object)"),
]

VALID_OBJ_TYPE = ("FONT", "OBJECT", "META", "SURFACE",
                  "CURVES", "LATTICE", "POINTCLOUD", "GPENCIL", "ARMATURE", "MESH")


class OperatorProperty:
    align_mode: EnumProperty(items=[
        *ENUM_ALIGN_MODE,
        ("GROUND", "Ground", "Align Ground"),
        ("DISTRIBUTION", "Distribution", "Distribution Align"),
    ])

    distribution_mode: EnumProperty(
        items=ENUM_DISTRIBUTION_MODE,
        default="FIXED"
    )
    distribution_adjustment_value: FloatProperty(
        name="Distribution interval value", default=1)

    align_location: BoolProperty(
        name="Location",
        get=lambda self: __get_v__(self, "Location", default=True),
        set=lambda self, value: __set_v__(self, "Location", value))
    align_rotation: BoolProperty(
        name="Rotate",
        get=lambda self: __get_v__(self, "Rotate", default=True),
        set=lambda self, value: __set_v__(self, "Rotate", value))
    align_scale: BoolProperty(
        name="Scale",
        get=lambda self: __get_v__(self, "Scale", default=False),
        set=lambda self, value: __set_v__(self, "Scale", value))

    def __get_lx__(self):
        # 地面默认只开Z
        default = 4 if self.align_mode == "GROUND" else DEFAULT_XYZ_ENUM
        return __get_v__(self, "align_location_axis", default=default)

    align_location_axis: EnumProperty(
        # get=__get_lx__,
        # set=lambda self, value: __set_v__(self, "align_location_axis", value),
        **AXIS_ENUM_PROPERTY,
        default={"X", "Y", "Z"},
    )
    align_rotation_axis: EnumProperty(
        get=lambda self: __get_v__(self, "rotation_euler_axis", default=DEFAULT_XYZ_ENUM),
        set=lambda self, value: __set_v__(self, "rotation_euler_axis", value),
        **AXIS_ENUM_PROPERTY
    )
    align_scale_axis: EnumProperty(
        get=lambda self: __get_v__(self, "scale_axis", default=DEFAULT_XYZ_ENUM),
        set=lambda self, value: __set_v__(self, "scale_axis", value),
        **AXIS_ENUM_PROPERTY
    )

    distribution_sorted_axis: EnumProperty(
        name="Distribution sort axis",
        description="Align and sort the selected objects according"
                    " to the selection axis to obtain the correct movement "
                    "position",
        items=ENUM_DISTRIBUTION_SORTED_AXIS)

    ground_down_mode: EnumProperty(items=ENUM_GROUND_DOWN_MODE, name="Down Mode")
    ground_plane_mode: EnumProperty(items=ENUM_GROUND_PLANE_MODE, name="Ground Plane Mode")
    ground_object_name: StringProperty(
        name="To Object",
        description="Align To Ground Object")
    ground_ray_casting_rotation: BoolProperty(name="Ray Casting Rotation", default=True)

    # 每个一个轴的对齐方式
    align_x_method: EnumProperty(name="X", **ALIGN_METHOD_PROPERTY)
    align_y_method: EnumProperty(name="Y", **ALIGN_METHOD_PROPERTY)
    align_z_method: EnumProperty(name="Z", **ALIGN_METHOD_PROPERTY)
