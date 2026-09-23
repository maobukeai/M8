"""Armature Mirror headless test suite for M8 Blender add-on.

Run from Blender, for example:
    blender --background --factory-startup --python dev/selftest_armature_mirror.py

Instantiates a Python test class that derives the MirrorArmature mixin directly,
rather than calling bpy.ops.m8.mirror in EXEC_DEFAULT mode (which skips invoke and
leaves mirror_mode=None / origin_matrix unset, causing None.lower() errors).
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from mathutils import Matrix, Vector

import bpy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import addon_utils


def _ensure_addon_enabled():
    addon_name = "M8"
    for mod in addon_utils.modules():
        name = mod.__name__
        if name == "M8" or name.endswith(".M8"):
            addon_name = name
            break
    addon_utils.enable(addon_name, default_set=True)
    return addon_name


class _ArmatureTestOp:
    """
    Minimal Python operator substitute that combines MirrorArmature with the
    required attributes that the real Mirror operator sets in invoke().

    We do NOT call bpy.ops.m8.mirror in EXEC_DEFAULT mode because that skips
    invoke(), leaving mirror_mode=None and causing 'None.lower()' AttributeError.
    Instead we bind the mixin methods directly and supply all required state.
    """

    # --- Required MirrorArmature / MirrorOperatorProperty fields ---
    axis: str = "X"
    axis_mode: str = "ORIGIN"
    is_negative_axis: bool = False
    origin_matrix: Matrix = Matrix()   # set per-test below

    # Minimal stubs for MirrorArmature methods that touch hub/GPU (no-op headless)
    def load_armature_preview(self, context):
        pass

    def update_armature_preview(self, context, is_preview=True):
        pass

    def clear_armature_hub(self):
        pass

    def update_armature_hub(self, context):
        pass

    def report(self, level, msg):
        print(f"  [report {level}] {msg}")

    @property
    def axis_index(self) -> int:
        from M8.utils.items import AXIS
        return AXIS.index(self.axis)


# Bind all MirrorArmature methods onto our test class
def _bind_armature_mixin(cls):
    from M8.ops.mirror.armature import MirrorArmature
    for attr_name in dir(MirrorArmature):
        if attr_name.startswith("__"):
            continue
        val = getattr(MirrorArmature, attr_name)
        if callable(val) and not hasattr(cls, attr_name):
            setattr(cls, attr_name, val)
    # Explicitly copy the key methods we need
    for name in ("_plane_world", "_reflect_point", "_pair_name",
                 "execute_armature", "armature_poll",
                 "load_armature_preview", "update_armature_preview",
                 "clear_armature_hub", "update_armature_hub",
                 "draw_armature"):
        try:
            setattr(cls, name, getattr(MirrorArmature, name))
        except AttributeError:
            pass


_bind_armature_mixin(_ArmatureTestOp)


def run():
    report = {
        "test": "armature_mirror",
        "registered": False,
        "symmetrize_x_result": None,
        "mirror_y_result": None,
        "bones_after_x": [],
        "bones_after_y": [],
        "ok": False,
        "unregistered": False,
    }

    addon_name = _ensure_addon_enabled()
    report["registered"] = True

    try:
        # Clean previous test objects
        for o in list(bpy.data.objects):
            if o.name.startswith("M8_Test_Arm"):
                bpy.data.objects.remove(o, do_unlink=True)
        for a in list(bpy.data.armatures):
            if a.name.startswith("M8_Test_Arm"):
                bpy.data.armatures.remove(a)

        # -----------------------------------------------------------------
        # TEST 1: Symmetrize along X axis via execute_armature
        # -----------------------------------------------------------------
        arm_data = bpy.data.armatures.new("M8_Test_ArmData_X")
        arm_obj = bpy.data.objects.new("M8_Test_Arm_X", arm_data)
        bpy.context.collection.objects.link(arm_obj)
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='EDIT')

        eb = arm_data.edit_bones.new("Bone.L")
        eb.head = Vector((0.1, 0.0, 0.0))
        eb.tail = Vector((0.3, 0.0, 0.2))

        for b in arm_data.edit_bones:
            b.select = False
            b.select_head = False
            b.select_tail = False
        arm_data.edit_bones["Bone.L"].select = True
        arm_data.edit_bones["Bone.L"].select_head = True
        arm_data.edit_bones["Bone.L"].select_tail = True

        # Build test operator instance for X-axis symmetrize
        # Production condition: cond = s > 1e-8 if is_negative_axis else s < -1e-8
        # Bone.L has head.x=0.1, tail.x=0.3 → center.x ≈ 0.2 (positive side).
        # To select it, we need is_negative_axis=False and cond = center.x < -1e-8 → FAILS.
        # With is_negative_axis=True, cond = center.x > 1e-8 → True (positive side selected).
        op_x = _ArmatureTestOp()
        op_x.axis = "X"
        op_x.axis_mode = "ORIGIN"
        op_x.is_negative_axis = True      # positive-side source requires is_negative_axis=True
        op_x.origin_matrix = arm_obj.matrix_world.copy()

        res_x = op_x.execute_armature(bpy.context)
        report["symmetrize_x_result"] = list(res_x) if isinstance(res_x, (set, list)) else str(res_x)

        bpy.ops.object.mode_set(mode='EDIT')
        bone_names_x = [b.name for b in arm_data.edit_bones]
        report["bones_after_x"] = bone_names_x
        print(f"  Bones after X symmetrize: {bone_names_x}")

        assert "Bone.R" in bone_names_x or any("Mirror" in n for n in bone_names_x), (
            f"Expected mirrored bone (Bone.R or Bone.L_Mirror), found: {bone_names_x}"
        )
        mirrored_bone = (arm_data.edit_bones.get("Bone.R")
                         or arm_data.edit_bones.get("Bone.L_Mirror"))
        assert mirrored_bone is not None, f"Could not find mirrored bone. Bones: {bone_names_x}"
        assert mirrored_bone.head.x < 0, \
            f"Mirrored bone head X should be negative, got {mirrored_bone.head.x}"

        # -----------------------------------------------------------------
        # TEST 2: Custom reflection along Y axis
        # -----------------------------------------------------------------
        eb_y = arm_data.edit_bones.new("Arm_Y_Bone")
        eb_y.head = Vector((0.0, 0.5, 0.1))
        eb_y.tail = Vector((0.0, 1.0, 0.2))

        for b in arm_data.edit_bones:
            b.select = False
            b.select_head = False
            b.select_tail = False
        eb_y.select = True
        eb_y.select_head = True
        eb_y.select_tail = True

        # Y-axis reflection: bone is at y=0.5..1.0 (positive side)
        # With is_negative_axis=True, cond = center.y > 1e-8 → True (positive side selected)
        op_y = _ArmatureTestOp()
        op_y.axis = "Y"
        op_y.axis_mode = "ORIGIN"
        op_y.is_negative_axis = True
        op_y.origin_matrix = arm_obj.matrix_world.copy()

        res_y = op_y.execute_armature(bpy.context)
        report["mirror_y_result"] = list(res_y) if isinstance(res_y, (set, list)) else str(res_y)

        bpy.ops.object.mode_set(mode='EDIT')
        bone_names_y = [b.name for b in arm_data.edit_bones]
        report["bones_after_y"] = bone_names_y
        print(f"  Bones after Y reflection: {bone_names_y}")

        mirrored_y = [n for n in bone_names_y if "Mirror" in n or
                      (n.endswith(".R") and "Arm_Y" in n) or
                      (n.startswith("Arm_Y") and n != "Arm_Y_Bone")]
        assert any("Arm_Y_Bone" in n for n in bone_names_y if n != "Arm_Y_Bone") or mirrored_y, (
            f"Expected mirrored Y bone, found: {bone_names_y}"
        )

        # Verify reflected bone is on the negative Y side with strict tolerance
        eb_y = arm_data.edit_bones.get("Arm_Y_Bone")
        assert eb_y is not None, "Source bone 'Arm_Y_Bone' should exist in edit_bones"
        for n in bone_names_y:
            if n != "Arm_Y_Bone" and "Arm_Y" in n:
                rb = arm_data.edit_bones.get(n)
                if rb:
                    # Strict reflection: head.y == -source.head.y within tolerance
                    assert abs(rb.head.y - (-eb_y.head.y)) < 1e-4, (
                        f"Reflected Y bone '{n}' head.y={rb.head.y:.6f} should equal "
                        f"-source.head.y={-eb_y.head.y:.6f}"
                    )
                    assert abs(rb.tail.y - (-eb_y.tail.y)) < 1e-4, (
                        f"Reflected Y bone '{n}' tail.y={rb.tail.y:.6f} should equal "
                        f"-source.tail.y={-eb_y.tail.y:.6f}"
                    )
                    # Verify envelope properties are copied correctly
                    assert abs(rb.envelope_distance - eb_y.envelope_distance) < 1e-6, (
                        f"envelope_distance mismatch: {rb.envelope_distance} vs {eb_y.envelope_distance}"
                    )
                    assert abs(rb.envelope_weight - eb_y.envelope_weight) < 1e-6, (
                        f"envelope_weight mismatch: {rb.envelope_weight} vs {eb_y.envelope_weight}"
                    )
                    assert abs(rb.head_radius - eb_y.head_radius) < 1e-6, (
                        f"head_radius mismatch: {rb.head_radius} vs {eb_y.head_radius}"
                    )
                    assert abs(rb.tail_radius - eb_y.tail_radius) < 1e-6, (
                        f"tail_radius mismatch: {rb.tail_radius} vs {eb_y.tail_radius}"
                    )
                    assert rb.use_envelope_multiply == eb_y.use_envelope_multiply, (
                        f"use_envelope_multiply mismatch: {rb.use_envelope_multiply} vs {eb_y.use_envelope_multiply}"
                    )
                    print(f"  Reflected bone '{n}': head={tuple(rb.head)}, tail={tuple(rb.tail)}")

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(arm_obj, do_unlink=True)
        bpy.data.armatures.remove(arm_data)

        report["ok"] = True

    finally:
        addon_utils.disable(addon_name, default_set=True)
        report["unregistered"] = True

    return report


if __name__ == "__main__":
    try:
        result = run()
        print("M8_ARMATURE_MIRROR_RESULT " + json.dumps(result, ensure_ascii=False, sort_keys=True))
        if not result.get("ok"):
            sys.exit(1)
    except Exception as exc:
        traceback.print_exc()
        sys.exit(1)
