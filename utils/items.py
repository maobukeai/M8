AXIS = ("X", "Y", "Z")
DEFAULT_XYZ_ENUM = 263

ENUM_AXIS = [
    ("X", "X", "X Axis"),
    ("Y", "Y", "Y Axis"),
    ("Z", "Z", "Z Axis"),
]

ENUM_ALIGN_MODE = [
    ("ORIGINAL", "World",
     "Aligning to the world origin is the same as resetting"),
    ("ACTIVE", "Active", "Align to Active Vector"),
    ("CURSOR", "Cursor", "Align to Cursor(Scale reset 1)"),
    ("ALIGN",
     "Align",
     "General alignment, you can set the alignment of each axis"
     "(maximum, center, minimum)"),
]

AXIS_ENUM_PROPERTY = dict(
    name="Axis to be aligned",
    description="Select the axis to be aligned, multiple choices are allowed",
    items=ENUM_AXIS,
    options={"ENUM_FLAG", "SKIP_SAVE"})

ALIGN_METHOD_PROPERTY = dict(
    items=[
        ("MIN", "Min", "Align to Min Point"),
        ("CENTER", "Center", "Center Align"),
        ("MAX", "Max", "Align to Max Point"),
    ],
    default="CENTER",
)
