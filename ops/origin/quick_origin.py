import bpy
from mathutils import Vector, Matrix
from ...utils import ensure_object_mode, call_object_op_with_selection
from ...utils.i18n import _T

def _set_origin_matrix(obj, target_world_loc):
    if not obj or not obj.data:
        return False
    
    # Check if object supports data transform
    if not hasattr(obj.data, "transform"):
        return False

    mw = obj.matrix_world.copy()
    basis = mw.to_3x3()
    
    try:
        world_offset = target_world_loc - mw.translation
        local_offset = basis.inverted() @ world_offset
        
        # Move geometry in opposite direction
        obj.data.transform(Matrix.Translation(-local_offset))
        obj.data.update()
        
        # Move origin to target
        mw.translation = target_world_loc
        obj.matrix_world = mw
        return True
    except Exception:
        return False

class OBJECT_OT_QuickOrigin(bpy.types.Operator):
    bl_idname = "object.quick_origin"
    bl_label = _T("快速原点")
    bl_description = _T("快速设置选中物体的原点到边界框的关键位置")
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.EnumProperty(
        name=_T("位置"),
        items=[
            ('BOTTOM', _T("底部中心 (-Z)"), _T("原点到边界框底部中心")),
            ('TOP', _T("顶部中心 (+Z)"), _T("原点到边界框顶部中心")),
            ('CENTER', _T("几何中心"), _T("原点到边界框几何中心")),
            ('ORIGIN', _T("世界原点"), _T("原点到世界坐标 (0,0,0)")),
            ('X_MIN', _T("左侧中心 (-X)"), _T("原点到边界框 -X 面中心")),
            ('X_MAX', _T("右侧中心 (+X)"), _T("原点到边界框 +X 面中心")),
            ('Y_MIN', _T("前侧中心 (-Y)"), _T("原点到边界框 -Y 面中心")),
            ('Y_MAX', _T("后侧中心 (+Y)"), _T("原点到边界框 +Y 面中心")),
        ],
        default='BOTTOM'
    )

    @classmethod
    def poll(cls, context):
        # Support more types
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        processed = 0
        ensure_object_mode(context)
        
        for obj in context.selected_objects:
            # Check supported types
            if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
                continue
            
            # ORIGIN type doesn't need bbox
            if self.type == 'ORIGIN':
                target = Vector((0,0,0))
            else:
                if not getattr(obj, "bound_box", None):
                    continue
                bbox = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
                if not bbox:
                    continue
                    
                min_x = min(v.x for v in bbox)
                max_x = max(v.x for v in bbox)
                min_y = min(v.y for v in bbox)
                max_y = max(v.y for v in bbox)
                min_z = min(v.z for v in bbox)
                max_z = max(v.z for v in bbox)
                center = sum(bbox, Vector((0,0,0))) / 8.0
                
                if self.type == 'BOTTOM':
                    target = Vector((center.x, center.y, min_z))
                elif self.type == 'TOP':
                    target = Vector((center.x, center.y, max_z))
                elif self.type == 'CENTER':
                    target = center
                elif self.type == 'X_MIN':
                    target = Vector((min_x, center.y, center.z))
                elif self.type == 'X_MAX':
                    target = Vector((max_x, center.y, center.z))
                elif self.type == 'Y_MIN':
                    target = Vector((center.x, min_y, center.z))
                elif self.type == 'Y_MAX':
                    target = Vector((center.x, max_y, center.z))
                else:
                    target = center

            if _set_origin_matrix(obj, target):
                processed += 1

        self.report({'INFO'}, f"{_T('已设置 ')}{processed}{_T(' 个物体的原点')}")
        return {'FINISHED'}

class OBJECT_OT_OriginToActive(bpy.types.Operator):
    bl_idname = "object.origin_to_active"
    bl_label = _T("到活动")
    bl_description = _T("将选中物体原点设置到活动物体的位置")
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.EnumProperty(
        name=_T("对齐到"),
        items=[
            ('LOCATION', _T("位置"), _T("对齐到活动物体原点")),
            ('CENTER', _T("几何中心"), _T("对齐到活动物体几何中心")),
        ],
        default='LOCATION'
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT' and
                context.active_object is not None and
                context.selected_objects)

    def execute(self, context):
        active = context.active_object
        processed = 0
        ensure_object_mode(context)

        if self.type == 'CENTER' and getattr(active, "bound_box", None):
            bbox = [active.matrix_world @ Vector(v) for v in active.bound_box]
            if bbox:
                target = sum(bbox, Vector((0,0,0))) / 8.0
            else:
                target = active.matrix_world.translation.copy()
        else:
            target = active.matrix_world.translation.copy()

        for obj in context.selected_objects:
            if obj == active:
                continue
            if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'}:
                continue
                
            if _set_origin_matrix(obj, target):
                processed += 1

        self.report({'INFO'}, f"{_T('已对齐 ')}{processed}{_T(' 个物体原点到活动项')}")
        return {'FINISHED'}
