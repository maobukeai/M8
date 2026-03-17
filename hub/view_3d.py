from math import pi, cos, sin

import bmesh
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Color, Vector, Matrix

from ..utils import get_pref, get_pref_value

if bpy.app.background:
    SMOOTH_COLOR = None
    UNIFORM_COLOR = None
    POLYLINE_SMOOTH_COLOR = None
else:
    SMOOTH_COLOR = gpu.shader.from_builtin("SMOOTH_COLOR")
    UNIFORM_COLOR = gpu.shader.from_builtin("UNIFORM_COLOR")
    POLYLINE_SMOOTH_COLOR = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")

offset = Vector((0, 0, 0.001))




def from_bmesh_element_get_data(bm, layer, data, elements):
    """将bmesh的坐和连接顺序转换为gpu绘制的数据"""
    data["pos"] = []
    data["color"] = []
    data["indices"] = []

    for v in bm.verts:
        data["pos"].append(v.co[:])
        data["color"].append(v[layer][:])
    for element in elements:
        data["indices"].append([v.index for v in element.verts])

    bm.free()


class Shader:
    is_preprocessed_data = False

    def __init__(self, color: Color = None, line_width: float = None, vert_size: float = None,
                 alpha: float | None = None):
        self.color = get_pref_value("hub_3d_color", (0.2, 0.6, 1, 0.8)) if color is None else color
        self.line_width = get_pref_value("hub_line_width", 2) if line_width is None else line_width
        self.vert_size = get_pref_value("hub_vert_size", 6) if vert_size is None else vert_size
        self.alpha = alpha

        # 添加阶段使用bmesh来记录绘制信息
        self.vert_bm = bmesh.new()
        self.edge_bm = bmesh.new()
        self.face_bm = bmesh.new()

        self.vert_color_layer = self.vert_bm.verts.layers.color.new("color")
        self.edge_color_layer = self.edge_bm.verts.layers.color.new("color")
        self.face_color_layer = self.face_bm.verts.layers.color.new("color")

        # 需要绘制时将bmesh信息转换为gpu绘制的信息
        self.vert_data = {}
        self.edge_data = {}
        self.face_data = {}

        # 最后bind数据到shaders内绘制
        self.shaders = {}  # {"batch":shader}

    def replace_alpha(self, color, hub: "View3DHub"):
        """替换颜色的alpha
        如果颜色需要动画的话"""
        if self.alpha is not None:
            return [(*c[:3], self.alpha) for c in color]
        elif hub.is_alpha_animation:
            return [(*c[:3], hub.alpha) for c in color]
        return [c[:] for c in color]

    def ensure_lookup_table(self):
        v = self.vert_bm
        v.verts.ensure_lookup_table()
        e = self.edge_bm
        e.verts.ensure_lookup_table()
        e.edges.ensure_lookup_table()
        f = self.face_bm
        f.verts.ensure_lookup_table()
        f.edges.ensure_lookup_table()
        f.faces.ensure_lookup_table()

    def processed_faces(self):
        """将面三角化以便进行绘制"""
        bm = self.face_bm
        bmesh.ops.triangulate(bm, faces=bm.faces)

    def processed_bmesh_draw_data(self):
        vert_bm = self.vert_bm
        if len(vert_bm.verts):
            data = self.vert_data
            data["pos"] = []
            data["color"] = []
            cl = self.vert_color_layer
            for vert in vert_bm.verts:
                data["pos"].append(vert.co.copy())
                data["color"].append(vert[cl][:])
            vert_bm.free()

        edge_bm = self.edge_bm
        if len(edge_bm.edges):
            data = self.edge_data
            cl = self.edge_color_layer
            from_bmesh_element_get_data(edge_bm, cl, data, edge_bm.edges)

        face_bm = self.face_bm
        if len(face_bm.faces):
            data = self.face_data
            cl = self.face_color_layer
            from_bmesh_element_get_data(face_bm, cl, data, face_bm.faces)

    def preprocessed_data(self):
        """处理数据
        将所有添加的bmesh数据转换为gpu模块绘制的类型
        面的话需要三角化
        TODO(处理数据之后删除Bmesh,减小内存占用)
        """
        if not self.is_preprocessed_data:
            self.processed_faces()
            self.ensure_lookup_table()
            self.processed_bmesh_draw_data()
            self.is_preprocessed_data = True

    def __get_color__(self, color: Color = None):
        """如果输入为None
        取Hub3DItem的颜色
        如果Hub3dItem颜色为None
        取偏好设置颜色
        """
        if color is None:
            color = self.color

        if len(color) == 3:
            return *color, 1
        return color  # 四位颜色

    def bind_vert_shader(self, hub: "View3DHub"):
        if data := self.vert_data:
            pos = data["pos"]
            color = self.replace_alpha(data["color"], hub)

            shader = SMOOTH_COLOR
            shader.bind()
            batch = batch_for_shader(shader, "POINTS", {"pos": pos, "color": color})
            self.shaders[batch] = shader

    def bind_line_shader(self, hub: "View3DHub"):
        if data := self.edge_data:
            pos = data["pos"]
            color = self.replace_alpha(data["color"], hub)
            indices = data["indices"]

            poly_line = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
            poly_line.uniform_float("lineWidth", self.line_width)
            poly_line.uniform_float("viewportSize", gpu.state.scissor_get()[2:])
            poly_line.bind()

            batch = batch_for_shader(poly_line, "LINES", {"pos": pos, "color": color}, indices=indices)
            self.shaders[batch] = poly_line

    def bind_face_shader(self, hub: "View3DHub"):
        if data := self.face_data:
            pos = data["pos"]
            color = self.replace_alpha(data["color"], hub)
            indices = data["indices"]

            shader = SMOOTH_COLOR
            shader.bind()

            batch = batch_for_shader(shader, "TRIS", {"pos": pos, "color": color}, indices=indices)
            self.shaders[batch] = shader

    def bind(self, hub: "View3DHub"):
        """绑定着色器
        如果有alpha变化的话需要每次绘制重新bind一下
        """
        self.shaders = {}  # {"batch":shader}
        self.bind_vert_shader(hub)
        self.bind_line_shader(hub)
        self.bind_face_shader(hub)


def from_element_new_vertex(
        bm: bmesh.types.BMesh,
        verts: "[bmesh.types.BMVert,]",
        matrix: Matrix,
        layer,
        color
):
    """通过输入元素来创建一个顶点"""
    tow_vert = list()
    for vert in verts:
        # offset = offset
        if isinstance(vert, bmesh.types.BMVert):
            co = vert.co.copy()
            co += vert.normal * 0.001
        elif isinstance(vert, Vector):
            co = vert
        else:
            if len(vert) == 3:
                co = Vector(vert)
            else:
                Exception(f"from_element_new_vertex 未知数据 {vert}")
        if matrix is not None:
            co = matrix @ co
        nv = bm.verts.new(co)
        nv.index = len(bm.verts) - 1
        if layer:
            nv[layer] = color

        tow_vert.append(nv)

    bm.verts.ensure_lookup_table()
    return tow_vert


class Hub3DItem(Shader):
    depth_test = "ALWAYS"
    blend = "ALPHA"
    # NONE, ALPHA, ALPHA_PREMULT, ADDITIVE, ADDITIVE_PREMULT, MULTIPLY, SUBTRACT, INVERT,
    # NONE, ALWAYS, LESS, LESS_EQUAL, EQUAL, GREATER and GREATER_EQUAL
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"{self.__class__.__name__}(" \
               f"f:{len(self.face_bm.faces)}," \
               f"e:{len(self.edge_bm.edges)}," \
               f" v:{len(self.vert_bm.verts)})"

    def face(self, face: bmesh.types.BMFace, matrix: Matrix = None, color: Color = None):
        color = self.__get_color__(color)

        bm = self.face_bm
        vert = from_element_new_vertex(bm, face.verts, matrix, self.face_color_layer, color)
        bm.faces.new(vert)

    def face_from_verts(self, verts, matrix: Matrix = None, color: Color = None):
        color = self.__get_color__(color)

        bm = self.face_bm
        edge_vert = from_element_new_vertex(bm, verts, matrix, self.face_color_layer, color)
        bm.faces.new(edge_vert)
        return edge_vert

    def edge(self, edge: bmesh.types.BMEdge, matrix: Matrix = None, color: Color = None):
        color = self.__get_color__(color)

        bm = self.edge_bm
        tow_vert = from_element_new_vertex(bm, edge.verts, matrix, self.edge_color_layer, color)
        bm.edges.new(tow_vert)

    def edge_from_vert(self,
                       a: bmesh.types.BMVert | Vector | list,
                       b: bmesh.types.BMVert | Vector | list,
                       matrix: Matrix = None, color: Color = None):
        color = self.__get_color__(color)

        bm = self.edge_bm
        tow_vert = from_element_new_vertex(bm, [a, b], matrix, self.edge_color_layer, color)
        bm.edges.new(tow_vert)

    def vert(self, vert: [bmesh.types.BMVert | Vector | list], matrix: Matrix = None, color: Color | list = None):
        if isinstance(vert, bmesh.types.BMVert):
            co = vert.co.copy()
            co += vert.normal * 0.01
        elif isinstance(vert, Vector):
            co = vert
        elif isinstance(vert, list):
            vl = len(vert)
            if vl == 3:
                co = Vector(vl)
            else:
                return Exception(f"顶点长度应为 3 输入为{vl}")
        else:
            return Exception("请输入顶点坐标 bmesh.types.BMVert | Vector | list")

        if matrix:
            co = matrix @ co
        color = self.__get_color__(color)
        nv = self.vert_bm.verts.new(co)
        nv[self.vert_color_layer] = color

    def circle(self, matrix, radius=100, segments=36, color=None, thickness=1):
        # TODO: Implement thickness support for circle drawing
        start_v = None
        last_v = None
        for nv in self.get_circle_verts(radius, segments):
            if start_v is None:
                start_v = nv
            if last_v is not None:
                self.edge_from_vert(nv, last_v, matrix, color)
            last_v = nv
        self.edge_from_vert(start_v, last_v, matrix, color)
        
    def text(self, matrix: Matrix | Vector, text: str, color: Color = None, size: int = 20):
        """
        添加3D空间中的文字绘制请求
        注意：Hub3DItem 主要处理几何体绘制，文字绘制需要通过 TextHub 或者在 draw 方法中特殊处理
        目前架构中 TextHub 是 2D 的，View3DHub 是 3D 的。
        为了在 View3DHub 中支持文字，我们需要一个机制。
        
        或者，我们可以利用 blf 在 draw 回调中绘制。
        这里我们先将文字信息存储起来，然后在 bind/draw 时处理。
        """
        if not hasattr(self, "text_data"):
            self.text_data = []
            
        pos = matrix.to_translation() if isinstance(matrix, Matrix) else matrix
        self.text_data.append({
            "pos": pos,
            "text": text,
            "color": color,
            "size": size
        })

    def point_circle(self, matrix, radius=10, segments=36, color=None):
        verts = self.get_circle_verts(radius, segments)
        self.face_from_verts(verts, matrix, color)
        self.circle(matrix, radius, segments, color)

    def conical(self, matrix, radius=10, height=10, segments=36, color=None):
        """圆锥"""
        circle_verts = self.get_circle_verts(radius, segments)
        verts = self.face_from_verts(circle_verts, matrix, color)

        color = self.__get_color__(color)
        bm = self.face_bm
        top_v = bm.verts.new(matrix @ Vector((0, 0, height)))

        start_v = None
        last_v = None
        for v in verts:
            if start_v is None:
                start_v = v
                last_v = v
            else:
                self.face_from_verts((last_v, v, top_v), Matrix(), color)
                last_v = v
        self.face_from_verts((start_v, last_v, top_v), Matrix(), color)

    @classmethod
    def get_circle_verts(cls, radius=100, segments=36):
        segments = max(segments, 6)
        verts = []
        for i in range(segments):
            theta = 2 * pi * i / segments

            x = radius * cos(theta)
            y = radius * sin(theta)
            nv = Vector((x, y, 0))
            verts.append(nv)
        return verts

    def draw(self):
        if self.shaders:
            gpu.state.blend_set(self.blend)
            gpu.state.depth_mask_set(True)
            gpu.state.depth_test_set(
                self.depth_test)  # NONE, ALWAYS, LESS, LESS_EQUAL, EQUAL, GREATER and GREATER_EQUAL
            gpu.state.line_width_set(self.line_width)
            gpu.state.point_size_set(self.vert_size)
            for batch, shader in self.shaders.items():
                batch.draw(shader)
                
        # 绘制文字
        if hasattr(self, "text_data") and self.text_data:
            import blf
            from bpy_extras.view3d_utils import location_3d_to_region_2d
            
            context = bpy.context
            region = context.region
            region_3d = context.space_data.region_3d
            
            for item in self.text_data:
                pos_3d = item["pos"]
                pos_2d = location_3d_to_region_2d(region, region_3d, pos_3d)
                
                if pos_2d:
                    font_id = 0
                    text = item["text"]
                    color = item["color"]
                    size = item["size"]
                    
                    if color is None:
                        color = (1, 1, 1, 1)
                    elif len(color) == 3:
                        color = (*color, 1)
                        
                    blf.position(font_id, pos_2d.x + 15, pos_2d.y - 5, 0)
                    blf.size(font_id, size)
                    blf.color(font_id, *color)
                    blf.draw(font_id, text)
