import bpy
from ...utils.i18n import _T

class M8_OT_MaterialNew(bpy.types.Operator):
    bl_idname = "m8.material_new"
    bl_label = _T("新建材质")
    bl_description = _T("为活动物体新建标准材质；若在编辑模式且有选中面，自动指定给所选面")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, _T("请先选择一个网格物体"))
            return {'CANCELLED'}

        base_name = f"{obj.name}_Mat"
        mat = bpy.data.materials.new(name=base_name)
        mat.use_nodes = True

        if len(obj.material_slots) == 0:
            obj.data.materials.append(mat)
        else:
            if context.mode == 'EDIT_MESH':
                if obj.active_material is None:
                    obj.material_slots[obj.active_material_index].material = mat
                else:
                    obj.data.materials.append(mat)
                    obj.active_material_index = len(obj.material_slots) - 1
                try:
                    bpy.ops.object.material_slot_assign()
                except Exception:
                    pass
            else:
                if obj.active_material is None:
                    obj.material_slots[obj.active_material_index].material = mat
                else:
                    obj.data.materials.append(mat)
                    obj.active_material_index = len(obj.material_slots) - 1

        self.report({'INFO'}, _T("已新建材质: ") + mat.name)
        return {'FINISHED'}


class M8_OT_MaterialMakeSingleUser(bpy.types.Operator):
    bl_idname = "m8.material_make_single_user"
    bl_label = _T("独立材质副本")
    bl_description = _T("将当前材质从多物体共享中独立出来（变为单用户），避免修改时影响其他物体")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.active_material:
            self.report({'WARNING'}, _T("活动物体无材质"))
            return {'CANCELLED'}

        mat = obj.active_material
        if mat.users <= 1:
            self.report({'INFO'}, _T("当前材质已是独立副本"))
            return {'FINISHED'}

        old_users = mat.users
        new_mat = mat.copy()
        obj.material_slots[obj.active_material_index].material = new_mat
        self.report({'INFO'}, f"{_T('材质已独立化: ')}{new_mat.name} ({_T('原共享数: ')}{old_users})")
        return {'FINISHED'}


class M8_OT_MaterialLinkToSelected(bpy.types.Operator):
    bl_idname = "m8.material_link_to_selected"
    bl_label = _T("赋予至选中物体")
    bl_description = _T("将活动物体的材质赋予给当前选中的所有其他网格物体")
    bl_options = {'REGISTER', 'UNDO'}

    link_all_slots: bpy.props.BoolProperty(
        name=_T("同步全部材质槽"),
        description=_T("若开启则同步所有材质槽，默认仅赋予活动槽材质"),
        default=False
    )

    def execute(self, context):
        active_obj = context.active_object
        if not active_obj or not active_obj.active_material:
            self.report({'WARNING'}, _T("活动物体无可用材质"))
            return {'CANCELLED'}

        active_mat = active_obj.active_material
        targets = [o for o in context.selected_objects if o != active_obj and o.type == 'MESH']
        if not targets:
            self.report({'WARNING'}, _T("未选中其他网格物体"))
            return {'CANCELLED'}

        if self.link_all_slots:
            try:
                bpy.ops.object.make_links_data(type='MATERIAL')
                self.report({'INFO'}, _T("已将全部材质槽同步至 %d 个物体") % len(targets))
                return {'FINISHED'}
            except Exception as ex:
                self.report({'ERROR'}, f"同步失败: {ex}")
                return {'CANCELLED'}

        count = 0
        for tgt in targets:
            if len(tgt.material_slots) == 0:
                tgt.data.materials.append(active_mat)
            else:
                tgt.material_slots[tgt.active_material_index].material = active_mat
            count += 1

        self.report({'INFO'}, _T("已将材质 [%s] 赋予至 %d 个选中物体") % (active_mat.name, count))
        return {'FINISHED'}


class M8_OT_SelectSameMaterial(bpy.types.Operator):
    bl_idname = "m8.select_same_material"
    bl_label = _T("选择同材质")
    bl_description = _T("编辑模式下全选使用该材质的面；物体模式下全选使用该材质的物体")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.active_material:
            self.report({'WARNING'}, _T("活动物体无可用材质"))
            return {'CANCELLED'}

        target_mat = obj.active_material

        if context.mode == 'EDIT_MESH':
            try:
                bpy.ops.mesh.select_material()
                self.report({'INFO'}, _T("已选中该材质对应的所有面"))
            except Exception as ex:
                self.report({'WARNING'}, f"选面失败: {ex}")
            return {'FINISHED'}

        count = 0
        for o in context.view_layer.objects:
            if o.type == 'MESH' and not o.hide_viewport and o.visible_get():
                mats = [s.material for s in o.material_slots if s.material]
                if target_mat in mats:
                    o.select_set(True)
                    count += 1

        self.report({'INFO'}, _T("已选中 %d 个使用材质 [%s] 的物体") % (count, target_mat.name))
        return {'FINISHED'}


class M8_OT_MaterialCleanSlots(bpy.types.Operator):
    bl_idname = "m8.material_clean_slots"
    bl_label = _T("清理空材质槽")
    bl_description = _T("清理当前物体上未指定材质的空槽位以及多边形中未使用的冗余槽位")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}

        was_edit = (context.mode == 'EDIT_MESH')
        if was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')

        removed = 0
        # 1. 移除空槽位 (slot.material is None)
        i = len(obj.material_slots) - 1
        while i >= 0:
            if obj.material_slots[i].material is None:
                obj.active_material_index = i
                bpy.ops.object.material_slot_remove()
                removed += 1
            i -= 1

        # 2. 检查多边形中完全未引用的槽位
        if len(obj.material_slots) > 1 and hasattr(obj.data, "polygons"):
            used_indices = set(p.material_index for p in obj.data.polygons)
            i = len(obj.material_slots) - 1
            while i >= 0:
                if i not in used_indices and len(obj.material_slots) > 1:
                    obj.active_material_index = i
                    bpy.ops.object.material_slot_remove()
                    removed += 1
                i -= 1

        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')

        self.report({'INFO'}, _T("已清理 %d 个冗余/空材质槽") % removed)
        return {'FINISHED'}


classes = (
    M8_OT_MaterialNew,
    M8_OT_MaterialMakeSingleUser,
    M8_OT_MaterialLinkToSelected,
    M8_OT_SelectSameMaterial,
    M8_OT_MaterialCleanSlots,
)
