import bpy
from mathutils import Vector

def create_test_armature():
    for o in list(bpy.data.objects):
        if o.type == "ARMATURE" and o.name == "M8_Test_Arm":
            bpy.data.objects.remove(o, do_unlink=True)
    arm_data = bpy.data.armatures.new("M8_Test_ArmData")
    arm_obj = bpy.data.objects.new("M8_Test_Arm", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones.new("Bone.L")
    eb.head = Vector((0.1, 0.0, 0.0))
    eb.tail = Vector((0.3, 0.0, 0.2))
    eb2 = arm_data.edit_bones.new("Bone.R")
    eb2.head = Vector((-0.1, 0.0, 0.0))
    eb2.tail = Vector((-0.3, 0.0, 0.2))
    for b in arm_data.edit_bones:
        b.select = False
        b.select_head = False
        b.select_tail = False
    arm_data.edit_bones["Bone.L"].select = True
    arm_data.edit_bones["Bone.L"].select_head = True
    arm_data.edit_bones["Bone.L"].select_tail = True
    return arm_obj

def run():
    obj = create_test_armature()
    bpy.context.view_layer.objects.active = obj
    bpy.ops.m8.mirror('INVOKE_DEFAULT')

if __name__ == "__main__":
    run()
