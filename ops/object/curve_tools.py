import bpy


class M8_OT_CurveQuickSettings(bpy.types.Operator):
    bl_idname = "m8.curve_quick_settings"
    bl_label = "曲线快速设置"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type in {"CURVE", "FONT", "SURFACE"} and obj.data)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        data = obj.data

        layout.use_property_split = True
        layout.use_property_decorate = False

        if hasattr(data, "dimensions"):
            layout.prop(data, "dimensions")
        if hasattr(data, "resolution_u"):
            layout.prop(data, "resolution_u")
        if hasattr(data, "render_resolution_u"):
            layout.prop(data, "render_resolution_u")

        if hasattr(data, "fill_mode"):
            layout.prop(data, "fill_mode")
        if hasattr(data, "use_fill_caps"):
            layout.prop(data, "use_fill_caps")

        box = layout.box()
        box.label(text="挤出/倒角", icon="MOD_SOLIDIFY")
        box.use_property_split = True
        box.use_property_decorate = False
        if hasattr(data, "extrude"):
            box.prop(data, "extrude")
        if hasattr(data, "bevel_depth"):
            box.prop(data, "bevel_depth")
        if hasattr(data, "bevel_resolution"):
            box.prop(data, "bevel_resolution")
        if hasattr(data, "offset"):
            box.prop(data, "offset")

    def execute(self, context):
        return {"FINISHED"}


class M8_OT_CurveCyclicToggle(bpy.types.Operator):
    bl_idname = "m8.curve_cyclic_toggle"
    bl_label = "切换闭合"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Allow checking if any selected object is valid
        return context.selected_objects

    def execute(self, context):
        processed = 0
        changed = False
        
        # 确保我们在对象模式，或者至少可以访问数据
        # 如果在编辑模式，最好先切换出来，修改后再切回去，或者使用 bmesh/editmode 方式
        # 但这里是修改 spline 属性，直接修改 data 属性通常可行，但 update 可能会报错
        
        for obj in context.selected_objects:
            if obj.type not in {"CURVE", "SURFACE"}:
                continue
            
            if not obj.data:
                continue

            # Toggle based on the first spline of each object or consistent toggle?
            # Let's toggle each spline individually or sync them?
            # Standard behavior: toggle state.
            
            if hasattr(obj.data, "splines"):
                for spline in obj.data.splines:
                    # 对于 NURBS 曲线，属性可能是 use_cyclic_u / use_cyclic_v
                    # 对于 BEZIER / POLY 曲线，属性是 use_cyclic_u
                    
                    # 简单的逻辑：取反
                    if hasattr(spline, "use_cyclic_u"):
                        spline.use_cyclic_u = not spline.use_cyclic_u
                        changed = True
                        
                    if hasattr(spline, "use_cyclic_v"):
                         spline.use_cyclic_v = not spline.use_cyclic_v
                         changed = True
            
            if changed:
                processed += 1
                
        if processed > 0:
            # Force update dependency graph
            # Curve 数据块没有 update() 方法，使用 update_tag() 标记更新
            for obj in context.selected_objects:
                if obj.type in {"CURVE", "SURFACE"} and obj.data:
                    obj.data.update_tag()
            
            context.view_layer.update()
            self.report({'INFO'}, f"已切换 {processed} 个曲线的闭合状态")
            return {"FINISHED"}
            
        return {"CANCELLED"}


class M8_OT_ObjectConvertToMesh(bpy.types.Operator):
    bl_idname = "m8.convert_to_mesh"
    bl_label = "转换为网格"
    bl_options = {"REGISTER", "UNDO"}

    keep_original: bpy.props.BoolProperty(name="保留原物体", default=True)

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        ensure_object_mode = False
        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
                ensure_object_mode = True
            except Exception:
                pass

        selected_objects = [o for o in context.selected_objects if o.type in {"CURVE", "FONT", "SURFACE", "META"}]
        
        if not selected_objects:
            self.report({'WARNING'}, "未选中可转换的物体")
            return {"CANCELLED"}

        processed = 0
        
        # Deselect all first to manage selection manually
        bpy.ops.object.select_all(action='DESELECT')
        
        for obj in selected_objects:
            try:
                # Set active
                context.view_layer.objects.active = obj
                
                target_obj = obj
                if self.keep_original:
                    # Duplicate
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    bpy.ops.object.duplicate()
                    target_obj = context.active_object
                
                # Convert
                # Ensure only target is selected for conversion
                bpy.ops.object.select_all(action='DESELECT')
                target_obj.select_set(True)
                context.view_layer.objects.active = target_obj
                
                bpy.ops.object.convert(target="MESH")
                processed += 1
                
            except Exception as e:
                print(f"Error converting {obj.name}: {e}")
                continue

        # Restore selection: select all converted meshes
        # If keep_original was True, we probably want to select the new meshes
        # If False, the original objects are converted (and are now meshes), so select them.
        
        # Actually, let's just restore user expectation: select result objects.
        # Since we processed them, they are currently selected one by one.
        # We should collect them? 
        # Easier: Just finish. The last one is selected.
        # Let's try to select all processed ones.
        
        # But references might be lost after convert? 
        # object.convert keeps the object reference valid (it changes type).
        
        self.report({'INFO'}, f"已转换 {processed} 个物体为网格")
        return {"FINISHED"}
