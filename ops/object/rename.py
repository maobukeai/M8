import bpy
import re
import datetime
import time
import random

class M8_OT_AdvancedRename(bpy.types.Operator):
    bl_idname = "m8.advanced_rename"
    bl_label = "高级重命名"
    bl_description = "批量重命名选中物体，支持查找替换、前后缀等功能"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "new_name"

    # Operation Mode
    mode: bpy.props.EnumProperty(
        name="模式",
        items=[
            ("SET", "设置名称", "设置新的基础名称", "EDITMODE_HLT", 0),
            ("REPLACE", "查找替换", "查找并替换字符", "FIND_DATA", 1),
            ("ADD", "添加前后缀", "添加前缀或后缀", "ADD", 2),
            ("STRIP", "移除字符", "移除开头或结尾的字符", "X", 3),
            ("CASE", "大小写转换", "转换名称大小写", "SMALL_CAPS", 4),
        ],
        default="SET"
    )

    # Target
    target: bpy.props.EnumProperty(
        name="目标",
        items=[
            ("SELECTED", "选定对象", "重命名所有选中的对象"),
            ("ACTIVE", "活动对象", "仅重命名当前活动对象"),
        ],
        default="SELECTED"
    )

    rename_data: bpy.props.BoolProperty(
        name="同步重命名数据", 
        description="同时重命名物体的数据块 (Mesh, Curve 等)", 
        default=False
    )

    rename_material: bpy.props.BoolProperty(
        name="同步重命名材质", 
        description="同时重命名物体的活动材质", 
        default=False
    )
    
    # Advanced Filters
    filter_visible_only: bpy.props.BoolProperty(
        name="仅限可见对象",
        description="仅重命名当前可见的对象，忽略隐藏对象",
        default=False
    )

    # Properties for SET mode
    new_name: bpy.props.StringProperty(
        name="新名称", 
        default="", 
        description="变量: $N(编号), $O(原名), $T(类型), $Ts(简写), $C(集合), $P(父级), $M(材质), $date, $time"
    )
    use_numbering: bpy.props.BoolProperty(name="添加编号", default=True)
    use_random: bpy.props.BoolProperty(name="随机顺序", description="打乱选中物体的编号顺序", default=False)
    smart_numbering: bpy.props.BoolProperty(name="智能延续", description="自动检测场景中已存在的最大编号并延续", default=True)
    start_number: bpy.props.IntProperty(name="起始编号", default=1, min=0)
    step_number: bpy.props.IntProperty(name="步长", default=1, min=1)
    pad_digits: bpy.props.IntProperty(name="位数填充", default=3, min=1, max=10)

    # Properties for REPLACE mode
    find_str: bpy.props.StringProperty(name="查找", default="")
    replace_str: bpy.props.StringProperty(name="替换", default="")
    use_regex: bpy.props.BoolProperty(name="正则表达式", default=False)
    case_sensitive: bpy.props.BoolProperty(name="区分大小写", default=False)

    # Properties for ADD mode
    prefix: bpy.props.StringProperty(name="前缀", default="")
    suffix: bpy.props.StringProperty(name="后缀", default="")
    add_check_exists: bpy.props.BoolProperty(name="避免重复", description="如果名称中已存在该前缀/后缀，则不重复添加", default=True)

    # Properties for STRIP mode
    strip_start: bpy.props.BoolProperty(name="移除开头数字/空格", default=False)
    strip_end: bpy.props.BoolProperty(name="移除结尾数字/空格", default=False)
    strip_ext: bpy.props.BoolProperty(name="移除后缀/扩展名", description="移除最后一个点(.)或下划线(_)之后的内容", default=False)
    strip_chars: bpy.props.StringProperty(name="移除指定字符", default="")
    strip_first_n: bpy.props.IntProperty(name="移除前 N 个字符", default=0, min=0)
    strip_last_n: bpy.props.IntProperty(name="移除后 N 个字符", default=0, min=0)

    # Properties for CASE mode
    case_mode: bpy.props.EnumProperty(
        name="转换类型",
        items=[
            ("UPPER", "大写 (UPPER)", ""),
            ("LOWER", "小写 (lower)", ""),
            ("TITLE", "标题 (Title Case)", ""),
            ("CAPITAL", "首字母大写 (Capital)", ""),
            ("CAMEL", "小驼峰 (camelCase)", ""),
            ("PASCAL", "大驼峰 (PascalCase)", ""),
            ("SNAKE", "蛇形 (snake_case)", ""),
            ("KEBAB", "短横线 (kebab-case)", ""),
            ("SPACE_TO_UNDERSCORE", "空格 -> 下划线", ""),
            ("UNDERSCORE_TO_SPACE", "下划线 -> 空格", ""),
        ],
        default="LOWER"
    )

    ui_show_advanced: bpy.props.BoolProperty(name="高级选项", default=False)

    def update_preset(self, context):
        if self.preset == 'NONE': return
        
        # Apply presets
        if self.preset == 'CLEAR_SUFFIX':
            self.mode = 'STRIP'
            self.strip_ext = True
            self.strip_end = True # Also strip trailing numbers usually
        elif self.preset == 'GAME_ASSET':
            self.mode = 'SET'
            self.new_name = "$Ts_$O"
            self.use_numbering = True
        elif self.preset == 'NORMALIZE':
            self.mode = 'CASE'
            self.case_mode = 'SNAKE'
        elif self.preset == 'CLEAN_IMPORT':
            self.mode = 'STRIP'
            self.strip_ext = True
            self.strip_start = True # Remove leading import numbers
        elif self.preset == 'PREFIX_Collection':
            self.mode = 'SET'
            self.new_name = "$C_$O"
            self.use_numbering = True

        # Reset preset to NONE to allow re-selecting same one
        # self.preset = 'NONE' # Cannot do this in update func easily without recursion risk or issues
        pass

    preset: bpy.props.EnumProperty(
        name="快速预设",
        items=[
            ("NONE", "选择预设...", ""),
            ("GAME_ASSET", "游戏资产 ($Ts_$O)", "例如: SM_Cube"),
            ("PREFIX_Collection", "集合前缀 ($C_$O)", "例如: Scene_Cube"),
            ("NORMALIZE", "规范化 (snake_case)", "转为小写下划线"),
            ("CLEAR_SUFFIX", "清除后缀 (.001)", "移除扩展名和尾部数字"),
            ("CLEAN_IMPORT", "清理导入数据", "移除扩展名和头部数字"),
        ],
        default="NONE",
        update=update_preset
    )

    # Sort Options
    sort_method: bpy.props.EnumProperty(
        name="排序",
        items=[
            ("NAME", "名称 (A-Z)", ""),
            ("X", "X 轴位置", ""),
            ("Y", "Y 轴位置", ""),
            ("Z", "Z 轴位置", ""),
            ("SELECTION", "选择顺序", ""),
        ],
        default="NAME"
    )
    
    sort_reverse: bpy.props.BoolProperty(name="反向排序", default=False)

    @classmethod
    def poll(cls, context):
        return context.selected_objects or context.active_object

    def check(self, context):
        return True

    def invoke(self, context, event):
        # Always reset to SET mode and current active object name for a fresh start
        self.mode = 'SET'
        
        # Reset target logic: if multiple objects selected, default to SELECTED, else ACTIVE (or just SELECTED is fine if size=1)
        if len(context.selected_objects) > 1:
            self.target = 'SELECTED'
        else:
            self.target = 'SELECTED' # Actually selected works fine for single too

        # Always update new_name from active object
        obj = context.active_object
        if obj:
            # Smart numbering detection
            # Try to match trailing number
            match = re.search(r'[\._](\d+)$', obj.name)
            if match:
                # Found number suffix
                # We don't set start_number here anymore, we let the smart_numbering logic handle it if enabled?
                # Actually, "Smart Continue" means finding GLOBAL max number.
                # The previous logic was just "Parsing current number".
                # Let's keep parsing current number as a fallback or initial state.
                num_str = match.group(1)
                self.start_number = int(num_str)
                # Remove number from new_name default
                base_name = obj.name[:match.start()]
                self.new_name = base_name
            else:
                self.new_name = obj.name
                self.start_number = 1
        else:
            self.new_name = ""
            self.start_number = 1

        # Default numbering off if only 1 object
        if len(context.selected_objects) <= 1:
            self.use_numbering = False
        else:
            self.use_numbering = True
            
            # Auto-padding based on count
            count = len(context.selected_objects)
            if count >= 1000:
                self.pad_digits = 4
            elif count >= 10000:
                self.pad_digits = 5
            # Default is 3, which is fine for < 1000

        # Smart Numbering: Check scene for max number if we have a base name
        if self.use_numbering and self.smart_numbering and self.new_name:
            self._update_smart_start_number(context)

        return context.window_manager.invoke_props_dialog(self, width=450)

    def _update_smart_start_number(self, context):
        # Scan scene for objects starting with new_name
        # Assume separator is _ or .
        # Pattern: ^{new_name}[_.](\d+)$
        # We need to escape new_name for regex
        if not self.new_name: return
        
        try:
            pattern = re.compile(r'^' + re.escape(self.new_name) + r'[_\.](\d+)$')
            max_num = 0
            found = False
            
            # Optimization: Only check if necessary? No, we need to scan to find max.
            # Scanning all objects might be slow in huge scenes.
            # But usually it's fast enough.
            for o in context.scene.objects:
                m = pattern.match(o.name)
                if m:
                    found = True
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
            
            if found:
                self.start_number = max_num + 1
        except Exception:
            pass

    def _truncate_middle(self, text, max_len=45):
        if len(text) <= max_len:
            return text
        # Keep start and end
        keep = (max_len - 3) // 2
        return f"{text[:keep]}...{text[-keep:]}"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        # Presets at the very top
        row = layout.row()
        row.prop(self, "preset", text="")
        layout.separator()

        # To ensure focus is on the most important field, draw it first if possible,
        # or at least at the top.
        
        # For SET mode, new_name is crucial.
        if self.mode == 'SET':
            col = layout.column(align=True)
            col.prop(self, "new_name")
            
            # Check for invalid characters in filename
            invalid_chars = r'[\\/:*?"<>|]'
            if re.search(invalid_chars, self.new_name):
                col.label(text="名称包含非法字符: \\ / : * ? \" < > |", icon="ERROR")
            
            layout.separator()

        layout.prop(self, "mode", text="操作")

        # Main Settings Box
        box = layout.box()
        
        # Unified Target Selection at the top of the box
        # But we need to check if target is relevant for all modes? Yes.
        # Smart Target UI: Hide if only 1 object selected (Target is irrelevant then)
        if len(context.selected_objects) > 1:
            row = box.row()
            row.prop(self, "target", expand=True)
        
        # Advanced Options (Collapsible)
        box.prop(self, "ui_show_advanced", icon="TRIA_DOWN" if self.ui_show_advanced else "TRIA_RIGHT")
        if self.ui_show_advanced:
            col = box.column(align=True)
            col.prop(self, "rename_data")
            col.prop(self, "rename_material")
            col.prop(self, "filter_visible_only")
        
        box.separator()

        if self.mode == 'SET':
            # Sort Options (Only relevant for multi-selection)
            if self.target == 'SELECTED':
                row = box.row()
                row.prop(self, "sort_method")
                row.prop(self, "sort_reverse", text="", icon="SORT_ASC")
            
            if self.target == 'SELECTED':
                row = box.row(align=True)
                row.prop(self, "use_numbering")
                if self.use_numbering:
                    row.prop(self, "use_random", text="", icon="RANDOM_TERM")
                    row.prop(self, "smart_numbering", text="", icon="AUTO")
                    row.prop(self, "start_number")
                    row.prop(self, "step_number")
                    row.prop(self, "pad_digits")
        
        elif self.mode == 'REPLACE':
            col = box.column(align=True)
            col.prop(self, "find_str", icon="VIEWZOOM")
            col.prop(self, "replace_str", icon="FILE_REFRESH")
            
            row = box.row(align=True)
            row.prop(self, "case_sensitive")
            row.prop(self, "use_regex")
            
            # Regex validation check
            if self.use_regex and self.find_str:
                try:
                    re.compile(self.find_str)
                except re.error as e:
                    box.label(text=f"Regex 错误: {e}", icon="ERROR")
            
            # Regex Cheat Sheet Hint
            if self.use_regex:
                box.label(text="常用: \\d+ (数字), ^ (开头), $ (结尾), . (任意)", icon="INFO")

        elif self.mode == 'ADD':
            col = box.column(align=True)
            col.prop(self, "prefix")
            col.prop(self, "suffix")
            col.prop(self, "add_check_exists")

        elif self.mode == 'STRIP':
            col = box.column(align=True)
            col.prop(self, "strip_start")
            col.prop(self, "strip_end")
            col.prop(self, "strip_ext")
            col.prop(self, "strip_chars")
            
            row = col.row(align=True)
            row.prop(self, "strip_first_n")
            row.prop(self, "strip_last_n")

        elif self.mode == 'CASE':
            box.prop(self, "case_mode", expand=True)

        # Draw Preview at the bottom
        if context.selected_objects or context.active_object:
            try:
                # Find first object that would actually change
                objects = self._get_sorted_objects(context, for_preview=True)
                
                preview_obj = None
                preview_name = ""
                display_name = ""
                last_obj = None
                last_name = ""
                
                # Check up to 20 objects to find one that changes
                check_objects = objects[:20] if len(objects) > 20 else objects
                total_count = len(objects)

                for i, obj in enumerate(check_objects):
                    name = self._calculate_new_name(obj, i, total_count)
                    if name != obj.name:
                        if not preview_obj:
                            preview_obj = obj
                            preview_name = name
                        # Keep updating last found change
                        last_obj = obj
                        last_name = name
                
                # If we have a huge list, also calculate the VERY LAST object to show range
                if total_count > 1 and not last_obj:
                     # No changes found in first 20, maybe none at all?
                     pass
                elif total_count > 1:
                     # Calculate explicitly for the last object in the full list
                     last_idx = total_count - 1
                     real_last_obj = objects[last_idx]
                     last_name = self._calculate_new_name(real_last_obj, last_idx, total_count)

                # If no change found, just show the first one
                if not preview_obj and objects:
                    preview_obj = objects[0]
                    preview_name = self._calculate_new_name(preview_obj, 0, total_count)

                if preview_obj:
                    display_name = self._truncate_middle(preview_name, max_len=30) # Shorter to fit range
                    
                    # Separate preview box
                    pbox = layout.box()
                    row = pbox.row()
                    row.alignment = 'LEFT'
                    # Show which object is being previewed if it's not the active one?
                    # Maybe just show "Result" is enough.
                    count_text = f" (共 {total_count} 个对象)" if total_count > 1 else ""
                    
                    # Check if name is actually different
                    is_changed = (preview_obj.name != preview_name)
                    
                    # Collision check...
                    collision = False
                    if is_changed and preview_name in bpy.data.objects:
                        if bpy.data.objects.get(preview_name) != preview_obj:
                            collision = True

                    if collision:
                        row.alert = True
                        row.label(text=f"冲突: {display_name} (自动后缀)", icon="ERROR")
                    elif not is_changed:
                        row.alert = True # Or use WARNING icon
                        row.label(text=f"无变化{count_text}", icon="INFO")
                    else:
                        # Show Range if multiple objects
                        if total_count > 1 and last_name and last_name != preview_name:
                             last_display = self._truncate_middle(last_name, max_len=30)
                             row.label(text=f"结果: {display_name} ... {last_display}{count_text}", icon="CHECKMARK")
                        else:
                             row.label(text=f"结果: {display_name}{count_text}", icon="CHECKMARK")
            except Exception:
                pass

    def _to_snake_case(self, text):
        # Convert camel/Pascal to snake_case first
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower().replace('-', '_').replace(' ', '_')

    def _to_camel_case(self, text, pascal=False):
        # First ensure snake case to handle spaces/hyphens/mixed properly
        snake = self._to_snake_case(text)
        components = snake.split('_')
        # Filter empty components
        components = [c for c in components if c]
        if not components:
            return text
            
        if pascal:
            return "".join(x.title() for x in components)
        else:
            return components[0].lower() + "".join(x.title() for x in components[1:])

    def _get_sorted_objects(self, context, for_preview=False):
        if self.target == 'ACTIVE':
            if context.active_object:
                return [context.active_object]
            return []
            
        # Get selected objects
        objects = list(context.selected_objects)
        if not objects and context.active_object:
            objects = [context.active_object]
            
        if self.use_random and self.target == 'SELECTED' and self.mode == 'SET':
            # Stable shuffle for preview to avoid flickering
            if for_preview:
                random.Random(42).shuffle(objects)
            else:
                # Real shuffle for execution
                random.shuffle(objects)
            return objects

        if self.sort_method == 'NAME':
            objects.sort(key=lambda x: x.name)
        elif self.sort_method == 'X':
            objects.sort(key=lambda x: x.location.x)
        elif self.sort_method == 'Y':
            objects.sort(key=lambda x: x.location.y)
        elif self.sort_method == 'Z':
            objects.sort(key=lambda x: x.location.z)
        # SELECTION relies on context.selected_objects order which is usually selection order (last selected is last?)
        # Actually context.selected_objects order is not guaranteed to be selection order in all Blender versions,
        # but often it is stable. 'selected_objects' is not ordered by selection time.
        # However, we can't easily get selection history for all objects without iterating efficiently.
        # For now, let's assume 'SELECTION' just means "don't sort" (use internal list order).
        # Improvement: Try to use context.view_layer.objects.active as last, but for full order we need more.
        # Actually, for most users "Selection Order" just means "Don't sort alphabetically".
        # If we really want selection history, we might need to look at state, but API doesn't expose history list easily.
        # Let's keep it as is (no sort), but add a note if needed. 
        # Actually, let's just leave it unsorted as "Default/Selection".
        
        if self.sort_reverse:
            objects.reverse()
            
        return objects

    def _get_short_type(self, obj):
        type_map = {
            'MESH': 'SM',
            'CURVE': 'CV',
            'SURFACE': 'SF',
            'META': 'MB',
            'FONT': 'TX',
            'ARMATURE': 'SK',
            'LATTICE': 'LT',
            'EMPTY': 'MT',
            'CAMERA': 'Cam',
            'LIGHT': 'Lgt',
            'LIGHT_PROBE': 'Prb',
            'SPEAKER': 'Spk',
        }
        return type_map.get(obj.type, 'Obj')

    def _calculate_new_name(self, obj, index, total_count):
        old_name = obj.name
        new_name = old_name

        if self.mode == 'SET':
            new_name = self.new_name
            
            # Replace basic variables
            if "$O" in new_name:
                new_name = new_name.replace("$O", old_name)
            if "$T" in new_name:
                # Type name (e.g. 'MESH' -> 'Mesh')
                t_name = obj.type.title().replace("_", " ") if obj.type else "Object"
                new_name = new_name.replace("$T", t_name)
            if "$Ts" in new_name:
                new_name = new_name.replace("$Ts", self._get_short_type(obj))
            if "$C" in new_name:
                # First collection name
                c_name = obj.users_collection[0].name if obj.users_collection else "Scene"
                new_name = new_name.replace("$C", c_name)
            if "$P" in new_name:
                p_name = obj.parent.name if obj.parent else ""
                new_name = new_name.replace("$P", p_name)
            if "$M" in new_name:
                # Active material name
                m_name = obj.active_material.name if obj.active_material else ""
                new_name = new_name.replace("$M", m_name)
            if "$date" in new_name:
                new_name = new_name.replace("$date", datetime.datetime.now().strftime("%Y%m%d"))
            if "$time" in new_name:
                new_name = new_name.replace("$time", datetime.datetime.now().strftime("%H%M%S"))
            
            if self.target == 'SELECTED' and self.use_numbering:
                num = self.start_number + (index * self.step_number)
                fmt = f"{{:0{self.pad_digits}d}}"
                suffix = fmt.format(num)
                
                # Check for $N placeholder
                if "$N" in new_name:
                    new_name = new_name.replace("$N", suffix)
                else:
                    if not new_name.endswith("_"):
                         new_name += "_"
                    new_name += suffix
            else:
                # If numbering disabled but $N exists, replace with empty
                if "$N" in new_name:
                    new_name = new_name.replace("$N", "")

        elif self.mode == 'REPLACE':
            if self.find_str:
                flags = 0 if self.case_sensitive else re.IGNORECASE
                if self.use_regex:
                    try:
                        new_name = re.sub(self.find_str, self.replace_str, old_name, flags=flags)
                    except Exception:
                        pass # Regex error, ignore
                else:
                    if not self.case_sensitive:
                        pattern = re.compile(re.escape(self.find_str), re.IGNORECASE)
                        new_name = pattern.sub(self.replace_str, old_name)
                    else:
                        new_name = old_name.replace(self.find_str, self.replace_str)

        elif self.mode == 'ADD':
            if self.add_check_exists:
                if self.prefix and not new_name.startswith(self.prefix):
                    new_name = f"{self.prefix}{new_name}"
                elif not self.add_check_exists: # Logic error in previous step, fixed here
                     pass # Handled below
                
                if self.suffix and not new_name.endswith(self.suffix):
                    new_name = f"{new_name}{self.suffix}"
            else:
                new_name = f"{self.prefix}{new_name}{self.suffix}"

        elif self.mode == 'STRIP':
            if self.strip_chars:
                new_name = new_name.strip(self.strip_chars)
            if self.strip_start:
                new_name = re.sub(r"^[\d\s._-]+", "", new_name)
            if self.strip_end:
                new_name = re.sub(r"[\d\s._-]+$", "", new_name)
            if self.strip_ext:
                # Remove extension (everything after last dot) or suffix after last underscore
                # Usually extension is last dot. Let's try to be smart.
                # If there is a dot, remove from dot. If no dot, check for underscore.
                if "." in new_name:
                    new_name = new_name.rsplit(".", 1)[0]
                elif "_" in new_name:
                    new_name = new_name.rsplit("_", 1)[0]
            
            if self.strip_first_n > 0:
                new_name = new_name[self.strip_first_n:]
            if self.strip_last_n > 0 and len(new_name) > self.strip_last_n:
                new_name = new_name[:-self.strip_last_n]

        elif self.mode == 'CASE':
            if self.case_mode == 'UPPER':
                new_name = new_name.upper()
            elif self.case_mode == 'LOWER':
                new_name = new_name.lower()
            elif self.case_mode == 'TITLE':
                new_name = new_name.title()
            elif self.case_mode == 'CAPITAL':
                new_name = new_name.capitalize()
            elif self.case_mode == 'CAMEL':
                new_name = self._to_camel_case(new_name, pascal=False)
            elif self.case_mode == 'PASCAL':
                new_name = self._to_camel_case(new_name, pascal=True)
            elif self.case_mode == 'SNAKE':
                new_name = self._to_snake_case(new_name)
            elif self.case_mode == 'KEBAB':
                new_name = self._to_snake_case(new_name).replace('_', '-')
            elif self.case_mode == 'SPACE_TO_UNDERSCORE':
                new_name = new_name.replace(' ', '_')
            elif self.case_mode == 'UNDERSCORE_TO_SPACE':
                new_name = new_name.replace('_', ' ')

        return new_name

    def execute(self, context):
        start_time = time.time()
        # Pass for_preview=False to get the actual shuffled list if random is ON
        objects = self._get_sorted_objects(context, for_preview=False)
        
        # Filter visible only if requested
        if self.filter_visible_only:
            objects = [o for o in objects if o.visible_get()]

        if not objects:
            self.report({'WARNING'}, "没有选中的对象 (或全部被过滤)")
            return {'CANCELLED'}

        count = 0
        total = len(objects)
        for i, obj in enumerate(objects):
            new_name = self._calculate_new_name(obj, i, total)
            
            # Empty name protection
            if not new_name.strip():
                # Fallback to original name or default
                # Just skip renaming? or warn?
                # Let's skip and report warning?
                # Or use "Object"
                continue

            if new_name != obj.name:
                obj.name = new_name
                count += 1
            
            # Handle Data renaming
            if self.rename_data and obj.data:
                obj.data.name = new_name
            
            # Handle Material renaming (active material only)
            if self.rename_material and obj.active_material:
                obj.active_material.name = new_name

        elapsed = time.time() - start_time
        time_msg = f" ({elapsed:.2f}s)" if elapsed > 0.1 else ""
        self.report({'INFO'}, f"已重命名 {count} 个对象{time_msg} (按 Ctrl+Z 撤销)")
        return {'FINISHED'}
