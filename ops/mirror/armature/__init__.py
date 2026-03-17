import bpy
from mathutils import Vector, Matrix

from ....hub import Hub3DItem, hub_3d, clear_hub
from ....utils.items import AXIS


class MirrorArmature:
    cache_armature_hub = {}

    @classmethod
    def armature_poll(cls, context):
        return context.mode == "EDIT_ARMATURE"

    @property
    def axis_index(self) -> int:
        return AXIS.index(self.axis)

    def _plane_world(self, context):
        axis_index = self.axis_index
        plane_co = self.origin_matrix.to_translation()
        axis_vec = Vector((0.0, 0.0, 0.0))
        axis_vec[axis_index] = 1.0
        plane_no = (self.origin_matrix.to_3x3() @ axis_vec).normalized()
        return plane_co, plane_no

    def _reflect_point(self, p: Vector, plane_co: Vector, plane_no: Vector) -> Vector:
        v = p - plane_co
        d = v.dot(plane_no)
        return p - 2.0 * d * plane_no

    def _pair_name(self, name: str) -> str | None:
        suffix_map = {
            ".L": ".R",
            ".R": ".L",
            ".l": ".r",
            ".r": ".l",
            "_L": "_R",
            "_R": "_L",
            "_l": "_r",
            "_r": "_l",
            "-L": "-R",
            "-R": "-L",
            "-l": "-r",
            "-r": "-l",
        }
        for src, dst in suffix_map.items():
            if name.endswith(src):
                return name[: -len(src)] + dst
        return None

    def load_armature_preview(self, context):
        self.cache_armature_hub = {}

    def update_armature_preview(self, context, is_preview=True):
        obj = context.object
        key = (obj.name, self.axis_mode, self.is_negative_axis, self.axis)
        if key in self.cache_armature_hub:
            hub = self.cache_armature_hub[key]
        else:
            hub = Hub3DItem()
            plane_co, plane_no = self._plane_world(context)
            om = obj.matrix_world
            for eb in obj.data.edit_bones:
                if not eb.select and not eb.select_head and not eb.select_tail:
                    continue
                center = (om @ eb.head + om @ eb.tail) * 0.5
                s = (center - plane_co).dot(plane_no)
                cond = s > 1e-8 if self.is_negative_axis else s < -1e-8
                if not cond:
                    continue
                h = self._reflect_point(om @ eb.head, plane_co, plane_no)
                t = self._reflect_point(om @ eb.tail, plane_co, plane_no)
                hub.edge_from_vert(h, t)
            hub.depth_test = "LESS_EQUAL"
            self.cache_armature_hub[key] = hub
        area_hash = hash(context.area)
        timeout = None if is_preview else 1.0
        hub_3d(f"{self.bl_idname}_preview", hub, timeout=timeout, area_restrictions=area_hash)

    def draw_armature(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        col = layout.column(align=True)

        axes = col.box()
        axes_col = axes.column(align=True)
        axes_col.row(align=True).prop(self, "axis_mode", expand=True)
        axes_col.row(align=True).prop(self, "axis", expand=True)

        opt = col.box()
        opt.use_property_split = False
        opt.prop(self, "is_negative_axis", text="反向")

    def update_armature_hub(self, context):
        ...

    def clear_armature_hub(self):
        clear_hub(self.bl_idname)
        clear_hub(f"{self.bl_idname}_preview")

    def execute_armature(self, context):
        obj = context.object
        can_use_symmetrize = (self.axis == "X" and self.axis_mode in {"ORIGIN", "ACTIVE"})

        if can_use_symmetrize:
            sel_state = {eb.name: (eb.select, eb.select_head, eb.select_tail) for eb in obj.data.edit_bones}
            plane_co, plane_no = self._plane_world(context)
            om = obj.matrix_world

            has_selection = False
            for eb in obj.data.edit_bones:
                is_selected = sel_state[eb.name][0] or sel_state[eb.name][1] or sel_state[eb.name][2]
                if not is_selected:
                    eb.select = False
                    eb.select_head = False
                    eb.select_tail = False
                    continue

                center = (om @ eb.head + om @ eb.tail) * 0.5
                s = (center - plane_co).dot(plane_no)
                cond = s > 1e-8 if self.is_negative_axis else s < -1e-8

                if cond:
                    eb.select = True
                    eb.select_head = True
                    eb.select_tail = True
                    has_selection = True
                else:
                    eb.select = False
                    eb.select_head = False
                    eb.select_tail = False

            if has_selection:
                direction = "NEGATIVE_X" if self.is_negative_axis else "POSITIVE_X"
                try:
                    bpy.ops.armature.symmetrize(direction=direction)
                except Exception as e:
                    self.report({"WARNING"}, str(e))
            else:
                self.report({"INFO"}, "未找到可镜像的骨骼")

            return {"FINISHED"}

        def _ensure_target_name(src_name: str) -> str:
            pn = self._pair_name(src_name)
            if pn:
                return pn
            base = f"{src_name}_Mirror"
            if len(base) > 58:
                base = base[:58]
            candidate = base
            if obj.data.edit_bones.get(candidate) is None:
                return candidate
            i = 1
            while True:
                suffix = f"_{i}"
                cand_base = base
                if len(cand_base) + len(suffix) > 63:
                    cand_base = cand_base[: 63 - len(suffix)]
                candidate = cand_base + suffix
                if obj.data.edit_bones.get(candidate) is None:
                    return candidate
                i += 1

        plane_co, plane_no = self._plane_world(context)
        om = obj.matrix_world
        omi = om.inverted()

        pairs = []
        name_map = {}

        for eb in list(obj.data.edit_bones):
            if not eb.select and not eb.select_head and not eb.select_tail:
                continue

            center = (om @ eb.head + om @ eb.tail) * 0.5
            s = (center - plane_co).dot(plane_no)
            cond = s > 1e-8 if self.is_negative_axis else s < -1e-8
            if not cond:
                continue

            target_name = _ensure_target_name(eb.name)
            tb = obj.data.edit_bones.get(target_name)
            is_new = False
            if tb is None:
                try:
                    tb = obj.data.edit_bones.new(target_name)
                    is_new = True
                except Exception as e:
                    self.report({"WARNING"}, str(e))
                    continue

            h = self._reflect_point(om @ eb.head, plane_co, plane_no)
            t = self._reflect_point(om @ eb.tail, plane_co, plane_no)
            pairs.append((tb, omi @ h, omi @ t, eb, is_new))
            name_map[eb.name] = tb.name

        if not pairs:
            self.report({"INFO"}, "未找到可镜像的骨骼")
            return {"FINISHED"}

        for tb, h, t, src, is_new in pairs:
            tb.head = h
            tb.tail = t
            if is_new:
                tb.roll = src.roll
                tb.envelope = src.envelope

        for tb, h, t, src, is_new in pairs:
            if not src.parent:
                continue
            pp_name = self._pair_name(src.parent.name)
            parent = obj.data.edit_bones.get(pp_name) if pp_name else None
            if parent is None and src.parent.name in name_map:
                parent = obj.data.edit_bones.get(name_map[src.parent.name])
            if parent is None:
                parent = src.parent
            tb.parent = parent
            tb.use_connect = src.use_connect

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}
