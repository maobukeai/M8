import bpy


def check_operator(operator_bl_idname):
    ops_split = operator_bl_idname.split('.')
    if len(ops_split) == 2:
        prefix, suffix = ops_split
        func = getattr(getattr(bpy.ops, prefix), suffix)
        try:
            func.get_rna_type()
        except KeyError:
            return False
        return True
    return False


def check_modal_operators(bl_idname: str) -> bool:
    """检查操作符模态是否在运行"""
    for modal in bpy.context.window.modal_operators:
        if modal and modal.bl_idname == bl_idname:
            return True
    return False


def check_skin_resize_modal_operator() -> bool:
    """检查缩放是否在蒙皮缩放模态
    TRANSFORM_OT_skin_resize
    在poll中使用bmesh 会导致Ctrl A 设置蒙皮尺寸出现无法调整的问题
    使用模态来确保在模态时不显示面板
    """
    return check_modal_operators("TRANSFORM_OT_skin_resize")
