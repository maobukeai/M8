import bpy


def get_active_face_group_attr(obj: bpy.types.Object) -> "bpy.types.Attribute|None":
    """获取活动面组属性
    如果活动属性不是一个布尔面属性的话就反回None
    """
    if obj and obj.type == "MESH":
        index = obj.data.attributes.active_index
        size = len(obj.data.attributes)
        if index >= size:
            return None
        elif index < 0:
            return None
        attr = obj.data.attributes[index]
        if attr.data_type == "BOOLEAN" and attr.domain == "FACE":
            return attr
    return None
