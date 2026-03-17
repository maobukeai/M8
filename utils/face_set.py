import bpy

"""
雕刻面集
"""

SCULPT_FACE_SET_NAME = ".sculpt_face_set"

FACE_SET_COLOR_NAME = "Face Set Color"


def create_face_set_color_attribute(obj: bpy.types.Object) -> bpy.types.FloatColorAttribute:
    """创建面集颜色属性
    如果属性不对就删掉新创建一个反回
    """
    attributes = obj.data.attributes

    face_set_color = None
    if FACE_SET_COLOR_NAME in attributes:
        attr = attributes[FACE_SET_COLOR_NAME]
        # if attr.data_type == "FLOAT_COLOR" and attr.domain == "CORNER":
        #     face_set_color = attr
        # else:
        #     名称是对的但是属性的类型不对,直接删掉重新创建一个
        attributes.remove(attr)

    if face_set_color is None:
        face_set_color = attributes.new(FACE_SET_COLOR_NAME, "FLOAT_COLOR", "CORNER")
    return face_set_color


def update_face_set_color(obj: bpy.types.Object) -> "{int:int}":
    from .face_set_overlay_color import bke_paint_face_set_overlay_color_get
    data = {}

    if obj.type != "MESH":
        print(f"{obj.name} 不是一个网格物体")
        return data

    if obj.mode == "EDIT":  # 编辑模式,使用bmesh
        create_face_set_color_attribute(obj)

        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)

        if SCULPT_FACE_SET_NAME in bm.faces.layers.int:
            face_set_layer = bm.faces.layers.int[SCULPT_FACE_SET_NAME]
            if FACE_SET_COLOR_NAME in bm.loops.layers.float_color:
                color_layer = bm.loops.layers.float_color[FACE_SET_COLOR_NAME]
            else:
                print("未找到面拐颜色属性")
                color_layer = bm.loops.layers.float_color.new(FACE_SET_COLOR_NAME)

            for face in bm.faces:
                face_set = face[face_set_layer]  # 面集索引
                color = bke_paint_face_set_overlay_color_get(0, face_set)

                for loop in face.loops:
                    loop[color_layer] = color

                if face_set not in data:
                    data[face_set] = 0
                data[face_set] = data[face_set] + 1

        else:
            print(f"在编辑模式Bmesh内未找到面集属性 {SCULPT_FACE_SET_NAME}")

    else:  # 物体模式,使用颜色属性
        attributes = obj.data.attributes
        if SCULPT_FACE_SET_NAME in attributes:
            attr = attributes[SCULPT_FACE_SET_NAME]
            color_attribute = create_face_set_color_attribute(obj)

            color_index = 0
            for face_index, face in enumerate(obj.data.polygons):
                face_set_index = attr.data[face_index].value  # 面集索引
                color = bke_paint_face_set_overlay_color_get(0, face_set_index)
                for v in face.vertices:
                    color_attribute.data[color_index].color = color
                    color_index += 1

                # 添加面集索引数量
                if face_set_index not in data:
                    data[face_set_index] = 0
                data[face_set_index] = data[face_set_index] + 1

            attributes.active_color = color_attribute
        else:
            print(f"在网格属性中未找到面集属性 {SCULPT_FACE_SET_NAME}")
    return data
