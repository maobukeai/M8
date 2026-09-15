# M8 Material Operations
from .material_ops import (
    M8_OT_MaterialNew,
    M8_OT_MaterialMakeSingleUser,
    M8_OT_MaterialLinkToSelected,
    M8_OT_SelectSameMaterial,
    M8_OT_MaterialCleanSlots,
)
from .seamless_material import (
    M8_OT_MakeMaterialSeamless,
    M8_OT_RevertMaterialSeamless,
    NODE_PT_M8_SeamlessMaterial,
    VIEW3D_PT_M8_SeamlessMaterial,
    SEAMLESS_CLASSES,
)

