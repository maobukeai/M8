import bpy
import os

class M8_ImageSavePresetProps(bpy.types.PropertyGroup):
    engine_type: bpy.props.EnumProperty(
        items=[
            ('GENERAL', "通用 PBR", "通用 PBR 命名规范"),
            ('UNITY', "Unity", "Unity 命名规范 (Albedo, MaskMap 等)"),
            ('UNREAL', "Unreal", "Unreal Engine 命名规范 (BaseColor, ORM 等)")
        ],
        name="目标引擎",
        default='GENERAL'
    )

class M8_OT_AppendFilenameSuffix(bpy.types.Operator):
    bl_idname = "m8.append_filename_suffix"
    bl_label = "添加后缀"
    bl_description = "在当前文件名后添加指定后缀"
    bl_options = {'REGISTER', 'UNDO'}
    
    suffix: bpy.props.StringProperty(name="后缀", default="_Normal")
    
    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'FILE_BROWSER'
        
    def execute(self, context):
        params = getattr(context.space_data, "params", None)
        if not params:
            return {'CANCELLED'}
            
        filename = params.filename
        if not filename:
            return {'CANCELLED'}
            
        # Separate extension
        name, ext = os.path.splitext(filename)
        
        # Suffix list to replace if one already exists
        known_suffixes = [
            "_BaseColor", "_Albedo", "_Diffuse", "_Color", "_BC", "_BaseMap",
            "_Normal", "_Normal_OpenGL", "_Normal_DirectX", "_N", "_Bump", "_Displacement", "_Height", "_H",
            "_Roughness", "_Glossiness", "_R",
            "_Metallic", "_Specular", "_Metalness", "_M",
            "_AO", "_AmbientOcclusion", "_Mixed_AO",
            "_Emission", "_Emissive", "_E",
            "_Opacity", "_Alpha", "_Transparency", "_Trans",
            "_Mask", "_MaskMap", "_Thickness", "_ClearCoat", "_Sheen",
            "_ORM", "_MADS",
            "_Detail", "_DetailNormal", "_DetailMask",
            "_ClearCoatRoughness", "_Anisotropy", "_SubsurfaceColor", "_WorldNormal"
        ]
        
        # Resolutions list to check/replace
        resolutions = ["_1K", "_2K", "_4K", "_8K"]
        all_suffixes = known_suffixes + resolutions
        
        # If the requested suffix is just an empty string (clear suffix)
        if not self.suffix:
            # We just need to strip all known suffixes and resolutions
            temp_name = name.lower()
            temp_real_name = name
            
            while True:
                found = False
                for ks in all_suffixes:
                    if temp_name.endswith(ks.lower()):
                        temp_name = temp_name[:-len(ks)]
                        temp_real_name = temp_real_name[:-len(ks)]
                        found = True
                        break
                if not found:
                    break
            
            new_filename = temp_real_name + ext
            params.filename = new_filename
            return {'FINISHED'}
            
        # Parse existing name to find base name, current PBR suffix, and current resolution
        temp_name = name.lower()
        temp_real_name = name
        
        current_res = ""
        current_pbr = ""
        
        while True:
            found = False
            for ks in all_suffixes:
                if temp_name.endswith(ks.lower()):
                    actual_suffix = temp_real_name[-len(ks):]
                    if ks in resolutions:
                        if not current_res:
                            current_res = actual_suffix
                    else:
                        if not current_pbr:
                            current_pbr = actual_suffix
                            
                    temp_name = temp_name[:-len(ks)]
                    temp_real_name = temp_real_name[:-len(ks)]
                    found = True
                    break
            if not found:
                break
                
        base_name = temp_real_name
        
        # Update either resolution or PBR suffix based on user input
        is_res_suffix = self.suffix in resolutions
        
        if is_res_suffix:
            current_res = self.suffix
        else:
            current_pbr = self.suffix
            
        # Reconstruct filename: BaseName + PBR Suffix + Resolution
        new_filename = base_name + current_pbr + current_res + ext
        params.filename = new_filename
        
        return {'FINISHED'}


class M8_OT_SetFilenamePrefix(bpy.types.Operator):
    bl_idname = "m8.set_filename_prefix"
    bl_label = "设置前缀"
    bl_description = "使用当前活动对象或材质的名称作为文件名前缀"
    bl_options = {'REGISTER', 'UNDO'}
    
    source: bpy.props.EnumProperty(
        items=[
            ('OBJECT', "活动对象", "使用当前活动对象的名称"),
            ('MATERIAL', "活动材质", "使用当前活动材质的名称")
        ],
        name="来源",
        default='OBJECT'
    )
    
    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'FILE_BROWSER'
        
    def execute(self, context):
        params = getattr(context.space_data, "params", None)
        if not params:
            return {'CANCELLED'}
            
        filename = params.filename
        name, ext = os.path.splitext(filename) if filename else ("", ".png")
        
        prefix = ""
        if self.source == 'OBJECT':
            obj = context.active_object
            if obj:
                prefix = obj.name
        elif self.source == 'MATERIAL':
            obj = context.active_object
            if obj and obj.active_material:
                prefix = obj.active_material.name
                
        if not prefix:
            self.report({'WARNING'}, f"未找到对应的{self.source}名称")
            return {'CANCELLED'}
            
        # Check if we already have a known suffix, keep it
        known_suffixes = [
            "_BaseColor", "_Albedo", "_Diffuse", "_Color", "_BC", "_BaseMap",
            "_Normal", "_Normal_OpenGL", "_Normal_DirectX", "_N", "_Bump", "_Displacement", "_Height", "_H",
            "_Roughness", "_Glossiness", "_R",
            "_Metallic", "_Specular", "_Metalness", "_M",
            "_AO", "_AmbientOcclusion", "_Mixed_AO",
            "_Emission", "_Emissive", "_E",
            "_Opacity", "_Alpha", "_Transparency", "_Trans",
            "_Mask", "_MaskMap", "_Thickness", "_ClearCoat", "_Sheen",
            "_ORM", "_MADS",
            "_Detail", "_DetailNormal", "_DetailMask",
            "_ClearCoatRoughness", "_Anisotropy", "_SubsurfaceColor", "_WorldNormal"
        ]
        
        resolutions = ["_1K", "_2K", "_4K", "_8K"]
        all_suffixes = known_suffixes + resolutions
        
        temp_name = name.lower()
        temp_real_name = name
        
        current_res = ""
        current_pbr = ""
        
        while True:
            found = False
            for ks in all_suffixes:
                if temp_name.endswith(ks.lower()):
                    actual_suffix = temp_real_name[-len(ks):]
                    # We want to reconstruct it so that resolution is always at the end
                    if ks in resolutions:
                        current_res = actual_suffix
                    else:
                        current_pbr = actual_suffix + current_pbr # prepend since we are parsing from end to start
                        
                    temp_name = temp_name[:-len(ks)]
                    temp_real_name = temp_real_name[:-len(ks)]
                    found = True
                    break
            if not found:
                break
                
        current_suffix = current_pbr + current_res
                
        new_filename = prefix + current_suffix + ext
        params.filename = new_filename
        
        return {'FINISHED'}


class FILEBROWSER_PT_m8_image_save_presets(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "M8 贴图命名预设"

    @classmethod
    def poll(cls, context):
        if not context.space_data or context.space_data.type != 'FILE_BROWSER':
            return False
        op = context.space_data.active_operator
        if op:
            op_name = op.bl_idname.lower()
            if "save" in op_name or "export" in op_name or "bake" in op_name:
                return True
            return False
        return True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.m8.image_save_preset
        
        # 引擎切换
        row = layout.row()
        row.prop(props, "engine_type", expand=True)
        
        layout.separator(factor=0.5)
        
        # 智能命名前缀
        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text="提取前缀:")
        row.operator("m8.set_filename_prefix", text="对象", icon='OBJECT_DATA').source = 'OBJECT'
        row.operator("m8.set_filename_prefix", text="材质", icon='MATERIAL').source = 'MATERIAL'
        
        col.separator(factor=0.5)
        
        # 分辨率后缀
        row = col.row(align=True)
        row.label(text="分辨率:")
        row.operator("m8.append_filename_suffix", text="1K").suffix = "_1K"
        row.operator("m8.append_filename_suffix", text="2K").suffix = "_2K"
        row.operator("m8.append_filename_suffix", text="4K").suffix = "_4K"
        row.operator("m8.append_filename_suffix", text="8K").suffix = "_8K"
        
        layout.separator()
        
        # 核心贴图区域 (根据引擎动态变化)
        box = layout.box()
        col = box.column(align=True)
        
        if props.engine_type == 'GENERAL':
            col.label(text="PBR 核心", icon='SHADING_RENDERED')
            grid = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
            grid.operator("m8.append_filename_suffix", text="底色").suffix = "_BaseColor"
            grid.operator("m8.append_filename_suffix", text="法线").suffix = "_Normal"
            grid.operator("m8.append_filename_suffix", text="粗糙度").suffix = "_Roughness"
            grid.operator("m8.append_filename_suffix", text="金属度").suffix = "_Metallic"
            grid.operator("m8.append_filename_suffix", text="AO").suffix = "_AO"
            grid.operator("m8.append_filename_suffix", text="高度").suffix = "_Height"
            
        elif props.engine_type == 'UNITY':
            col.label(text="Unity 核心", icon='SHADING_RENDERED')
            grid = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
            grid.operator("m8.append_filename_suffix", text="反射率").suffix = "_Albedo"
            grid.operator("m8.append_filename_suffix", text="法线").suffix = "_Normal"
            grid.operator("m8.append_filename_suffix", text="遮罩图").suffix = "_MaskMap"
            grid.operator("m8.append_filename_suffix", text="金属度").suffix = "_Metallic"
            grid.operator("m8.append_filename_suffix", text="平滑度").suffix = "_Smoothness"
            grid.operator("m8.append_filename_suffix", text="AO").suffix = "_AO"
            
        elif props.engine_type == 'UNREAL':
            col.label(text="Unreal 核心", icon='SHADING_RENDERED')
            grid = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
            grid.operator("m8.append_filename_suffix", text="底色").suffix = "_BaseColor"
            grid.operator("m8.append_filename_suffix", text="法线").suffix = "_Normal"
            grid.operator("m8.append_filename_suffix", text="ORM").suffix = "_ORM"
            grid.operator("m8.append_filename_suffix", text="粗糙度").suffix = "_Roughness"
            grid.operator("m8.append_filename_suffix", text="金属度").suffix = "_Metallic"
            grid.operator("m8.append_filename_suffix", text="AO").suffix = "_AO"
        
        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.operator("m8.append_filename_suffix", text="清除后缀", icon='TRASH').suffix = ""

class FILEBROWSER_PT_m8_image_save_presets_extra(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_parent_id = "FILEBROWSER_PT_m8_image_save_presets"
    bl_label = "更多后缀"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.m8.image_save_preset
        
        col = layout.column(align=True)
        grid = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        
        if props.engine_type == 'GENERAL':
            grid.operator("m8.append_filename_suffix", text="发光").suffix = "_Emission"
            grid.operator("m8.append_filename_suffix", text="不透明度").suffix = "_Opacity"
            grid.operator("m8.append_filename_suffix", text="漫反射").suffix = "_Diffuse"
            
            grid.operator("m8.append_filename_suffix", text="高光").suffix = "_Specular"
            grid.operator("m8.append_filename_suffix", text="光泽度").suffix = "_Glossiness"
            grid.operator("m8.append_filename_suffix", text="凹凸").suffix = "_Bump"
            
            grid.operator("m8.append_filename_suffix", text="Alpha").suffix = "_Alpha"
            grid.operator("m8.append_filename_suffix", text="遮罩").suffix = "_Mask"
            grid.operator("m8.append_filename_suffix", text="清漆").suffix = "_ClearCoat"
            
        elif props.engine_type == 'UNITY':
            # Unity 特有或常用的附加贴图
            grid.operator("m8.append_filename_suffix", text="发光").suffix = "_Emission"
            grid.operator("m8.append_filename_suffix", text="透明度").suffix = "_Transparency"
            grid.operator("m8.append_filename_suffix", text="细节图").suffix = "_Detail"
            
            grid.operator("m8.append_filename_suffix", text="细节法线").suffix = "_DetailNormal"
            grid.operator("m8.append_filename_suffix", text="细节遮罩").suffix = "_DetailMask"
            grid.operator("m8.append_filename_suffix", text="厚度").suffix = "_Thickness"
            
            grid.operator("m8.append_filename_suffix", text="基础图").suffix = "_BaseMap"
            grid.operator("m8.append_filename_suffix", text="高光").suffix = "_Specular"
            grid.operator("m8.append_filename_suffix", text="光泽度").suffix = "_Glossiness"
            
        elif props.engine_type == 'UNREAL':
            # Unreal 特有或常用的附加贴图
            grid.operator("m8.append_filename_suffix", text="发光").suffix = "_Emissive"
            grid.operator("m8.append_filename_suffix", text="不透明度").suffix = "_Opacity"
            grid.operator("m8.append_filename_suffix", text="MADS").suffix = "_MADS"
            
            grid.operator("m8.append_filename_suffix", text="高光").suffix = "_Specular"
            grid.operator("m8.append_filename_suffix", text="清漆").suffix = "_ClearCoat"
            grid.operator("m8.append_filename_suffix", text="清漆粗糙").suffix = "_ClearCoatRoughness"
            
            grid.operator("m8.append_filename_suffix", text="各向异性").suffix = "_Anisotropy"
            grid.operator("m8.append_filename_suffix", text="次表面").suffix = "_SubsurfaceColor"
            grid.operator("m8.append_filename_suffix", text="世界法线").suffix = "_WorldNormal"

classes = [
    M8_ImageSavePresetProps,
    M8_OT_AppendFilenameSuffix,
    M8_OT_SetFilenamePrefix,
    FILEBROWSER_PT_m8_image_save_presets,
    FILEBROWSER_PT_m8_image_save_presets_extra,
]
