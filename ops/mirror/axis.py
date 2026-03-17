from math import pi

from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Matrix, Euler, Vector

from ...hub import Hub3DItem, hub_3d
from ...hub.draw import MatrixHub
from ...utils import get_pref, get_pref_value
from ...utils.items import AXIS
from ...utils.math import location_to_matrix, rotation_to_matrix


class MirrorAxis:

    def get_coord_matrix(self, active_coord, context) -> Matrix:
        """活动矩阵点的坐标"""
        region_3d = context.space_data.region_3d
        view_matrix = region_3d.view_matrix
        loc = location_to_matrix(active_coord)
        rot = rotation_to_matrix(view_matrix.to_euler()).inverted()
        return loc @ rot

    @property
    def conical_rotation_matrix(self) -> Matrix:
        """圆锥旋转矩阵
        用来控制方向"""
        key = (self.axis, self.is_negative_axis)
        if res := {
            ("Z", True): Euler((pi, 0, 0), "XYZ"),

            ("X", True): Euler((0, -pi / 2, 0), "XYZ"),
            ("X", False): Euler((0, pi / 2, 0), "XYZ"),

            ("Y", True): Euler((pi / 2, 0, 0), "XYZ"),
            ("Y", False): Euler((-pi / 2, 0, 0), "XYZ"),
        }.get(key):
            return rotation_to_matrix(res)
        return Matrix()

    def update_axis_from_event(self, context, event):
        """Mirror用来判断是否在轴上时使用
        更新最近的轴点位置
        """
        region = context.region
        if not context.space_data:
            return
        region_3d = context.space_data.region_3d

        matrix_hub = self.matrix_hub
        coords, _ = matrix_hub.get_coords_colors_old()

        mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        sensitivity = float(get_pref_value("mirror_sensitivity", 2.0))
        if sensitivity < 0.5:
            sensitivity = 0.5
        if sensitivity > 4.0:
            sensitivity = 4.0
        distance = 250.0 * sensitivity
        if distance < 160.0:
            distance = 160.0
        if distance > 700.0:
            distance = 700.0
        
        hub_3d_item = Hub3DItem(vert_size=3)

        hub = Hub3DItem(vert_size=max(6.0, min(get_pref_value("mirror_preview_vert_size", 6) * 1.5, 18.0)))
        
        # 缓存当前 active_coord 以检测变化
        current_active_coord = getattr(self, "active_coord", None)
        has_changed = False

        best_coord = None
        best_axis = None
        best_is_negative = None
        best_dist = distance

        for index, coord in enumerate(coords):
            co = location_3d_to_region_2d(region, region_3d, coord)

            axis = AXIS[index // 2]
            is_negative = (index % 2) == 0
            if mouse and co:
                mouse_distance = (mouse - co).length
                if mouse_distance < best_dist:
                    if self.bisect or self.mirror_mode in {"LATTICE", "ARMATURE"}:
                        best_dist = mouse_distance
                        best_axis = axis
                        best_is_negative = is_negative
                        best_coord = coord
                    else:
                        if not is_negative:
                            best_dist = mouse_distance
                            best_axis = axis
                            best_is_negative = is_negative
                            best_coord = coord

        if best_coord is not None:
            self.axis = best_axis
            self.is_negative_axis = best_is_negative
            self.active_coord = best_coord
        else:
            self.active_coord = None
                            
        # 只有当激活的轴点发生变化时才返回 True，用于后续判断是否更新预览
        if current_active_coord != getattr(self, "active_coord", None):
            has_changed = True
            
        area_hash = hash(context.area)

        self.update_hub_circle(context, event, coords, hub)

        hub_3d(self.bl_idname, hub_3d_item, timeout=None, area_restrictions=area_hash)

        hub.blend = "ALPHA"
        hub.depth_test = "NONE"
        hub_3d(f"{self.bl_idname}_active", hub, timeout=None, area_restrictions=area_hash)
        
        return has_changed

    def draw_mirror_plane(self, context, hub):
        """绘制表示镜像平面的矩形"""
        if not self.axis:
            return

        base_scale = self.get_hub_scale(context)
        plane_size = max(0.12, min(base_scale * 1.35, 1.2))
        
        if getattr(self, "mirror_mode", None) == "ARMATURE":
            matrix = self.origin_matrix.copy()
        else:
            matrix = getattr(self, "display_matrix", self.origin_matrix).copy()
        matrix = Matrix.LocRotScale(matrix.to_translation(), matrix.to_quaternion(), Vector((1, 1, 1)))
        
        # 根据当前轴向计算平面的旋转
        rot_mat = Matrix()
        if self.axis == 'X':
            rot_mat = Euler((0, pi/2, 0), 'XYZ').to_matrix().to_4x4()
        elif self.axis == 'Y':
            rot_mat = Euler((pi/2, 0, 0), 'XYZ').to_matrix().to_4x4()
        
        # 应用旋转
        matrix = matrix @ rot_mat
        
        # 定义平面的四个顶点 (XY平面)
        verts = [
            Vector((-plane_size, -plane_size, 0)),
            Vector((plane_size, -plane_size, 0)),
            Vector((plane_size, plane_size, 0)),
            Vector((-plane_size, plane_size, 0))
        ]
        
        # 中心点偏移，用于绘制十字线
        mid_top = Vector((0, plane_size, 0))
        mid_bottom = Vector((0, -plane_size, 0))
        mid_left = Vector((-plane_size, 0, 0))
        mid_right = Vector((plane_size, 0, 0))
        
        # 转换到世界坐标
        world_verts = [matrix @ v for v in verts]
        world_mid_top = matrix @ mid_top
        world_mid_bottom = matrix @ mid_bottom
        world_mid_left = matrix @ mid_left
        world_mid_right = matrix @ mid_right
        
        axis_index = AXIS.index(self.axis)
        axis_rgb = MatrixHub.get_color(axis_index)
        color = (*axis_rgb, 0.85)
        
        face_color = (color[0], color[1], color[2], 0.06)
        hub.face_from_verts(world_verts, color=face_color)

        for i in range(4):
            hub.edge_from_vert(world_verts[i], world_verts[(i+1)%4], color=color)
            hub.edge_from_vert(world_verts[i], world_verts[(i+1)%4], color=(1, 1, 1, 0.16))
            
        inner_color = (color[0], color[1], color[2], 0.28)
        
        if self.bisect:
             inner_color = (color[0], color[1], color[2], 0.92)
             hub.edge_from_vert(world_mid_top, world_mid_bottom, color=inner_color)
             hub.edge_from_vert(world_mid_left, world_mid_right, color=inner_color)
        else:
             inner_color = (color[0], color[1], color[2], 0.22)
             hub.edge_from_vert(world_mid_top, world_mid_bottom, color=inner_color)
             hub.edge_from_vert(world_mid_left, world_mid_right, color=inner_color)

    def get_object_mirror_state(self, context):
        """获取当前活动物体的镜像轴开启状态"""
        # 返回结构: {index: is_on} (index 0-5对应 X+, X-, Y+, Y-, Z+, Z-)
        state = {}
        obj = context.object
        if not obj: return state
        
        # 查找修改器
        new_mod_name = "M8_mirror"
        old_mod_name = "MP7 Mirror"
        target_mod_name = getattr(self, "modifier_name", None) or new_mod_name
        mod_index = obj.modifiers.find(target_mod_name)
        if mod_index == -1 and target_mod_name == new_mod_name:
            mod_index = obj.modifiers.find(old_mod_name)
            if mod_index != -1:
                try:
                    obj.modifiers[mod_index].name = new_mod_name
                except Exception:
                    pass
                mod_index = obj.modifiers.find(new_mod_name)
        
        if mod_index != -1:
            mod = obj.modifiers[mod_index]
            if mod.type == 'MIRROR':
                # AXIS = ['X', 'Y', 'Z']
                for i, axis_name in enumerate(AXIS):
                    if mod.use_axis[i]:
                        # 检查翻转方向
                        is_negative = not mod.use_bisect_flip_axis[i]
                        # 索引规则：X+(0), X-(1), Y+(2), Y-(3), Z+(4), Z-(5)
                        # 这里 is_negative 决定了是 + 还是 -
                        # 注意：原始逻辑中 index // 2 是轴向，index % 2 != 1 是负轴
                        # 但我们的 Gizmo 排列可能是 X+, X-, Y+, Y-, ...
                        # 让我们看看 get_coords_colors_old 的顺序
                        # MatrixHub 中通常是 X, -X, Y, -Y, Z, -Z
                        
                        # 无论正负，如果 use_axis[i] 为 True，说明该轴向已开启
                        # 如果启用了 Bisect，那么需要区分正负
                        # 如果没启用 Bisect，通常是对称的，两边都算开启？
                        # 这里为了简单，如果开启了轴向，我们就把对应的正负两个点都标记为“已开启”
                        # 或者根据 flip 状态标记其中一个？
                        
                        # 如果 Bisect 开启，则只标记 flip 指向的那一边？
                        if mod.use_bisect_axis[i]:
                             # is_negative True -> Flip Axis False -> 保留正轴，切掉负轴？
                             # Blender Mirror Bisect: Flip 意味着翻转保留方向
                             # 默认 Flip False: 保留 Negative，切掉 Positive (也就是 Negative 侧可见)
                             # Flip True: 保留 Positive，切掉 Negative
                             
                             # 我们的 Gizmo 点代表“往这边镜像”
                             # 如果点在 X+，意味着我们想把 X- 的东西镜像到 X+ ?
                             # 或者意味着我们想保留 X+ ?
                             
                             # 让我们简化：如果轴开启了，就把对应的两个点都高亮，
                             # 除非能明确区分方向。
                             state[i*2] = True # Positive
                             state[i*2+1] = True # Negative
                        else:
                             # 非 Bisect 模式，完全镜像，两边都亮
                             state[i*2] = True
                             state[i*2+1] = True
        return state

    def update_hub_circle(self, context, event, coords, hub):
        region = context.region
        region_3d = context.space_data.region_3d
        
        # 获取当前已开启的轴状态
        mirror_state = self.get_object_mirror_state(context)
        
        # 绘制镜像平面
        if self.active_coord:
             self.draw_mirror_plane(context, hub)

        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        
        # 用于记录是否绘制了文字，确保每帧只绘制一次
        has_drawn_text = False

        base_scale = self.get_hub_scale(context)
        
        def draw_dot(matrix, radius, fill_color, outline_color, segments):
            verts = hub.get_circle_verts(radius, segments)
            hub.face_from_verts(verts, matrix, color=fill_color)
            hub.circle(matrix, radius=radius, color=outline_color, segments=segments)
        
        for index, coord in enumerate(coords):
            co = location_3d_to_region_2d(region, region_3d, coord)

            is_negative = (index % 2) == 0
            if mouse and co:
                axis_index = index // 2

                is_active = self.active_coord == coord
                is_enabled = mirror_state.get(index, False) # 检查该点对应的轴是否已开启

                axis_color = MatrixHub.get_color(axis_index)
                color = [i * .7 for i in axis_color] if is_negative else axis_color

                base_radius = .07 if is_active else .045
                circle_size = max(0.01, min(base_scale * base_radius, 0.09))
                
                if event.type != "MIDDLEMOUSE" and event.value != "PRESS":
                    # circle 在中键移动视图时不显示

                    matrix = self.get_coord_matrix(coord, context)
                    segments = 24
                    
                    # 如果该轴已开启，绘制实心点，或者加一个外圈指示
                    if is_enabled:
                         draw_dot(matrix, circle_size * 1.25, (*color[:3], 0.16), (*color[:3], 0.95), segments)
                         draw_dot(matrix, circle_size * 0.62, (1, 1, 1, 0.55), (1, 1, 1, 0.9), 18)
                    else:
                         # 未开启，绘制普通点
                         draw_dot(matrix, circle_size, (*color[:3], 0.10), (*color[:3], 0.75), segments)
                    
                    # 激活状态下增加额外的高亮圈
                    if is_active:
                         hub.circle(matrix, radius=circle_size * 1.75, color=(1, 1, 1, 0.28), segments=32)
                         hub.circle(matrix, radius=circle_size * 2.05, color=(1, 1, 1, 0.12), segments=32)
                         
                         # 在激活点旁边绘制文字 (HUD)
                         if not has_drawn_text:
                             # 计算文字位置：在点的一侧
                             # 这里需要将 3D 点转换为 2D 偏移吗？
                             # Hub3DItem.text 需要的是 3D 坐标
                             
                             # 构建显示的文本
                             axis_name = AXIS[axis_index]
                             if is_negative: axis_name = "-" + axis_name
                             
                             text_content = f"{axis_name}"
                             if self.bisect:
                                 text_content += " (Bisect)"
                             
                             # 文字颜色
                             text_color = (*color[:3], 1.0)
                             
                             # 添加文字到 Hub
                             # 位置偏移一点，避免遮挡点
                             hub.text(matrix, text_content, color=text_color, size=20)
                             has_drawn_text = True

                    # if is_active:
                    #     loc = location_to_matrix(self.active_coord)
                    #     rot = rotation_to_matrix(self.origin_matrix.to_euler()) @ self.conical_rotation_matrix
                    #     hub.conical(loc @ rot, radius=circle_size * 1.1, color=color, segments=6,
                    #                 height=circle_size * 6)

    def update_matrix_hub(self, context):
        """更新矩阵轴的大小视图缩放时同步缩放"""
        area_hash = hash(context.area)
        
        if getattr(self, "mirror_mode", None) == "ARMATURE":
            matrix = self.origin_matrix
        else:
            matrix = getattr(self, "display_matrix", self.origin_matrix)
        
        matrix = Matrix.LocRotScale(matrix.to_translation(), matrix.to_quaternion(), Vector((1, 1, 1)))
        
        scale_value = self.get_hub_scale(context)
        self.matrix_hub = MatrixHub(
            self.bl_idname,
            matrix,
            scale=scale_value,
            timeout=None,
            is_six_axis=self.bisect or self.mirror_mode in {"LATTICE", "ARMATURE"},
            area_restrictions=area_hash)
