import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_line_plane
from bpy_extras import view3d_utils

from .axis import MirrorAxis
from .gizmo_info import GizmoInfo
from .header_text import HeaderText
from .lattice import MirrorLattice
from .mesh import MirrorMesh
from .armature import MirrorArmature
from .status_bar import StatusBar
from ...utils import get_operator_bl_idname, get_pref
from ...utils.items import ENUM_AXIS, AXIS


class MirrorOperatorProperty:

    def get_axis_mode(self):
        if "axis_mode" in self:
            return self["axis_mode"]

        if bpy.context.mode == "EDIT_MESH":
            return 0  # "ORIGIN"
        else:
            return 3  # "ACTIVE"

    def set_axis_mode(self, value):
        self["axis_mode"] = value

    axis_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("ORIGIN", "Origin", ""),
            ("CURSOR", "Cursor", ""),
            ("WORLD", "World", ""),
            ("ACTIVE", "Active", "",),
        ],
        get=get_axis_mode,
        set=set_axis_mode
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        items=ENUM_AXIS
    )
    is_negative_axis: bpy.props.BoolProperty(name="Reverse")
    bisect: bpy.props.BoolProperty(name="Bisect", default=True)

    # Humanized: More standard threshold (0.001) for better merging behavior
    threshold: bpy.props.FloatProperty(name="Threshold", default=0.001, min=0.0001)
    use_modifier: bpy.props.BoolProperty(name="Use modifier", default=True, options={"HIDDEN"})
    use_parent: bpy.props.BoolProperty(name="Parent", default=False)
    use_mirror_active: bpy.props.BoolProperty(name="Mirror active", default=False)

    @property
    def axis_index(self) -> int:
        return AXIS.index(self.axis)


class Mirror(
    bpy.types.Operator,
    MirrorOperatorProperty,
    MirrorAxis,
    StatusBar,
    HeaderText,
    GizmoInfo,

    MirrorLattice,
    MirrorMesh,
    MirrorArmature,
):
    bl_idname = get_operator_bl_idname("mirror")
    bl_label = "M8_mirror"
    bl_options = {"REGISTER", "UNDO", "UNDO_GROUPED"}

    mirror_mode = None

    @classmethod
    def get_hub_scale(cls, context):
        pref = get_pref()
        if getattr(pref, "mirror_use_fixed_scale", False):
            return getattr(pref, "mirror_fixed_scale_value", 1.0)
            
        region_3d = context.space_data.region_3d
        view_distance = region_3d.view_distance
        return view_distance * 0.2 * pref.hub_scale

    @classmethod
    def poll(cls, context):
        if context.mode == "EDIT_MESH":
            return True
        elif context.mode == "EDIT_LATTICE":
            return cls.lattice_poll(context)
        elif context.mode == "EDIT_ARMATURE":
            return cls.armature_poll(context)
        return len(cls.get_selected_mesh_objects(context))

    def set_mirror_mode(self, context):
        if context.mode == "EDIT_LATTICE":
            self.mirror_mode = "LATTICE"
        elif context.mode == "EDIT_ARMATURE":
            self.mirror_mode = "ARMATURE"
        else:
            self.mirror_mode = "MESH"

    modifier_name = None

    origin_matrix = Matrix()
    active_matrix = Matrix()
    display_matrix = Matrix()
    backups_matrix = {}

    def draw(self, context):
        if not self.mirror_mode:
            self.set_mirror_mode(context)
        getattr(self, f"draw_{self.mirror_mode.lower()}")(context)

    def exit(self, context):
        getattr(self, f"clear_{self.mirror_mode.lower()}_hub")()
        self.restore_gizmo_state(context)
        self.restore_status_bar()
        self.clear_header_text(context)
        context.area.tag_redraw()

    def update_info(self, context, event):
        self.update_matrix_hub(context)
        axis_changed = self.update_axis_from_event(context, event)
        getattr(self, f"update_{self.mirror_mode.lower()}_hub")(context)

        self.update_header_text(context)
        
        # 只有当轴向改变时才更新预览，提升性能
        if axis_changed:
            getattr(self, f"update_{self.mirror_mode.lower()}_preview")(context)

    def invoke(self, context, event):
        if self.check_runtime():
            return {"CANCELLED"}

        self.set_mirror_mode(context)
        self.cache_hub = {}
        wm = context.window_manager
        wm.modal_handler_add(self)

        getattr(self, f"load_{self.mirror_mode.lower()}_preview")(context)

        self.remember_gizmo_state(context)
        self.replace_status_bar(context)

        self.init_active_matrix(context)
        self.update_matrix(context)
        
        # Initialize display matrix (mouse position logic)
        self.init_display_matrix(context, event)
        
        self.update_info(context, event)
        self.backups_matrix = {obj.name: obj.matrix_world.copy() for obj in context.scene.objects}

        bpy.ops.ed.undo_push(message="Push Undo")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """
        视角移动可以通过
        其它按键全部拦截
        ('RUNNING_MODAL', 'CANCELLED', 'FINISHED', 'PASS_THROUGH', 'INTERFACE')
        """
        # 优化流畅性：只在必要时重绘
        context.area.tag_redraw()
        
        # print(self.bl_idname, event.type, event.value)
        is_press = event.value == "PRESS"
        is_release = event.value == "RELEASE"
        
        if event.type == "LEFTMOUSE" and is_press:
            self.exit(context)
            self.execute(context)
            return {"FINISHED"}
            
        # 支持松开快捷键即确认
        # 检查偏好设置是否启用了自动确认
        if get_pref().mirror_auto_confirm:
            # 默认主键是 X
            trigger_key = 'X' # 默认
            
            # 如果是松开触发键，且当前有激活的轴向，则执行
            if event.type == trigger_key and is_release:
                self.exit(context)
                self.execute(context)
                return {"FINISHED"}

        if self.check_cancel(event):
            self.exit(context)
            return {"CANCELLED"}

        elif event.type in ("INBETWEEN_MOUSEMOVE", "MOUSEMOVE", "WHEELDOWNMOUSE", "WHEELUPMOUSE", "MIDDLEMOUSE"):
            self.update_info(context, event)
            return {"PASS_THROUGH"}

        elif event.type in ("S", "M", "C", "O", "Z", "W", "A") and is_press:
            if event.type == "C":
                self.axis_mode = "CURSOR" if self.axis_mode != "CURSOR" else "ORIGIN"
            elif event.type in ("O", "Z"):
                self.axis_mode = "ORIGIN"
            elif event.type == "W":
                self.axis_mode = "WORLD" if self.axis_mode != "WORLD" else "ORIGIN"
            elif event.type == "A":
                self.axis_mode = "ACTIVE" if self.axis_mode != "ACTIVE" else "ORIGIN"
            elif self.mirror_mode == "MESH":
                if event.type == "S":
                    self.bisect = not self.bisect
                elif event.type == "M":
                    self.use_modifier = not self.use_modifier
            
            # 按键切换后也需要更新
            self.update_matrix(context)
            # 强制更新预览
            self.update_matrix_hub(context)
            self.update_axis_from_event(context, event)
            getattr(self, f"update_{self.mirror_mode.lower()}_hub")(context)
            self.update_header_text(context)
            getattr(self, f"update_{self.mirror_mode.lower()}_preview")(context)

        # self.update_matrix(context) # 移到按键事件中，避免每一帧都更新矩阵
        # self.update_info(context, event) # 已经在 MOUSEMOVE 中处理了
        # context.area.tag_redraw() # 开头已经调用
        return {"RUNNING_MODAL"}

    @staticmethod
    def check_cancel(event):
        return event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS" or event.type == "WINDOW_DEACTIVATE"

    @property
    def edit_mesh_symmetrize_direction(self) -> str:
        n = "NEGATIVE" if self.is_negative_axis else "POSITIVE"
        return f"{n}_{self.axis.upper()}"

    def execute(self, context):
        return getattr(self, f"execute_{self.mirror_mode.lower()}")(context)

    def init_active_matrix(self, context):

        if context.mode == "EDIT_MESH":
            import bmesh
            from ...utils.bmesh import from_bmesh_active_select_get_matrix

            bm = bmesh.from_edit_mesh(context.active_object.data)

            # check select vert
            for vert in bm.verts:
                if vert.select:
                    break
            else:
                return

            active = self.get_mesh_active_object(context)
            matrix = from_bmesh_active_select_get_matrix(bm, active)
            if matrix:
                self.active_matrix = matrix
        elif context.mode == "EDIT_LATTICE":
            self.active_matrix = context.edit_object.matrix_world.copy()
        elif context.mode == "EDIT_ARMATURE":
            self.active_matrix = context.edit_object.matrix_world.copy()
        else:
            active = self.get_mesh_active_object(context)
            self.active_matrix = active.matrix_world.copy()

    def update_matrix(self, context):
        ax = self.axis_mode
        if ax == "ORIGIN":
            self.origin_matrix = context.object.matrix_world
        elif ax == "CURSOR":
            self.origin_matrix = context.scene.cursor.matrix
        elif ax == "WORLD":
            self.origin_matrix = Matrix()
        elif ax == "ACTIVE":
            self.origin_matrix = self.active_matrix
            
        # Sync rotation to display_matrix
        if hasattr(self, "display_matrix"):
            loc = self.display_matrix.to_translation()
            rot = self.origin_matrix.to_quaternion()
            scale = self.origin_matrix.to_scale()
            self.display_matrix = Matrix.LocRotScale(loc, rot, scale)

    def init_display_matrix(self, context, event):
        pref = get_pref()
        use_mouse = getattr(pref, "mirror_use_mouse_pos", True)
        
        if not use_mouse:
            self.display_matrix = self.origin_matrix.copy()
            return

        # Calculate mouse position in 3D
        region = context.region
        rv3d = context.space_data.region_3d
        coord = (event.mouse_region_x, event.mouse_region_y)
        
        loc = self.origin_matrix.to_translation()
        rot = self.origin_matrix.to_quaternion()
        scale = self.origin_matrix.to_scale()
        
        # Get view direction and origin
        view_inv = rv3d.view_matrix.inverted()
        view_loc = view_inv.translation
        view_dir = view_inv.to_3x3() @ Vector((0, 0, -1))
        
        # Ray from mouse
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        
        # Plane passing through object origin, facing camera
        # intersect_line_plane(line_a, line_b, plane_co, plane_no)
        new_loc = intersect_line_plane(ray_origin, ray_origin + ray_vector, loc, view_dir)
        
        if new_loc:
            self.display_matrix = Matrix.LocRotScale(new_loc, rot, scale)
        else:
            self.display_matrix = self.origin_matrix.copy()


class_tuples = (
    Mirror,
)

register_class, unregister_class = bpy.utils.register_classes_factory(class_tuples)


def register():
    register_class()


def unregister():
    unregister_class()
