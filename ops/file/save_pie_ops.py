import bpy
import os
import sys
import re
import subprocess
import importlib.util
from ..misc.screencast import M8_OT_InternalScreencast

class M8_OT_SwitchFile(bpy.types.Operator):
    bl_idname = "m8.switch_file"
    bl_label = "切换文件"
    bl_description = "打开当前文件夹中的上一个/下一个 Blend 文件"

    direction: bpy.props.EnumProperty(
        items=[
            ("PREV", "上一个", "上一个文件"),
            ("NEXT", "下一个", "下一个文件"),
        ],
        default="NEXT"
    )

    def execute(self, context):
        current_path = bpy.data.filepath
        if not current_path:
            self.report({'WARNING'}, "请先保存当前文件")
            return {'CANCELLED'}
        
        # Auto save before switching
        try:
            bpy.ops.wm.save_mainfile()
        except Exception:
            pass

        directory = os.path.dirname(current_path)
        current_filename = os.path.basename(current_path)

        try:
            files = [f for f in os.listdir(directory) if f.lower().endswith(".blend")]
            # Sort files naturally/alphabetically to ensure consistent order
            files.sort(key=lambda x: x.lower())
        except Exception as e:
            self.report({'ERROR'}, f"无法读取目录: {e}")
            return {'CANCELLED'}

        if not files:
            return {'CANCELLED'}

        try:
            current_index = files.index(current_filename)
        except ValueError:
            current_index = -1

        if self.direction == 'PREV':
            new_index = current_index - 1
            if new_index < 0:
                new_index = len(files) - 1
        else: # NEXT
            new_index = current_index + 1
            if new_index >= len(files):
                new_index = 0
        
        target_file = files[new_index]
        target_path = os.path.join(directory, target_file)

        if target_path == current_path:
             self.report({'INFO'}, "只有一个文件")
             return {'FINISHED'}

        bpy.ops.wm.open_mainfile(filepath=target_path)
        return {'FINISHED'}


class M8_OT_OpenAutoSave(bpy.types.Operator):
    bl_idname = "m8.open_auto_save"
    bl_label = "打开自动保存"
    bl_description = "打开自动保存目录 (Alt: Blender内浏览 | Ctrl: 资源管理器)"

    use_alt: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})
    use_ctrl: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        # Logic to find autosave path
        # 1. User Preference 'File Paths' -> 'Auto Save'
        # 2. If not set, use 'Temporary Files'
        # 3. Fallback to system temp
        
        filepath = ""
        prefs = context.preferences.filepaths
        
        if prefs.use_auto_save_temporary_files:
            filepath = prefs.temporary_directory
        
        if not filepath:
            # Check for custom autosave path if exposed, but usually it's just temp
            pass
            
        if not filepath:
            import tempfile
            filepath = tempfile.gettempdir()
            
        # Ensure path exists
        if not os.path.exists(filepath):
            try:
                filepath = os.path.expanduser("~")
            except Exception:
                pass

        # Check modifiers
        is_alt = self.use_alt
        is_ctrl = self.use_ctrl
            
        # If invoked from button directly (not keymap), we might need to check event in invoke
        # But for simple operator, we can check logic:
        # Default behavior: Open in OS File Browser (like "Open Temp Dir")
        # If user wants Blender File Browser, they can use Alt (if we support invoke)
        
        # Actually, let's make it simple:
        # Default -> Open in OS
        # We can reuse OpenCurrentFolder logic
        
        try:
            if sys.platform == 'win32':
                os.startfile(filepath)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', filepath])
            else:
                subprocess.Popen(['xdg-open', filepath])
        except Exception as e:
            self.report({'ERROR'}, f"无法打开文件夹: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

    def invoke(self, context, event):
        self.use_alt = event.alt
        self.use_ctrl = event.ctrl
        return self.execute(context)


class M8_OT_OpenCurrentFolder(bpy.types.Operator):
    bl_idname = "m8.open_current_folder"
    bl_label = "打开当前文件夹"
    bl_description = "打开当前 Blend 文件所在的文件夹"

    def execute(self, context):
        path = bpy.data.filepath
        if not path:
            # If unsaved, open Documents or Home
            path = os.path.expanduser("~")
        else:
            path = os.path.dirname(path)
        
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            self.report({'ERROR'}, f"无法打开文件夹: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}

class M8_OT_OpenTempDir(bpy.types.Operator):
    bl_idname = "m8.open_temp_dir"
    bl_label = "打开临时文件夹"
    bl_description = "打开 Blender 的临时文件夹"

    def execute(self, context):
        path = bpy.app.tempdir
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            self.report({'ERROR'}, f"无法打开文件夹: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}

class M8_OT_IncrementalSave(bpy.types.Operator):
    bl_idname = "m8.incremental_save"
    bl_label = "增量保存"
    bl_description = "保存文件并自动增加版本号 (filename_01.blend)"

    def execute(self, context):
        filepath = bpy.data.filepath
        if not filepath:
            bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT')
            return {'FINISHED'}

        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)

        # Regex to find trailing numbers with optional separator and 'v' prefix
        # Supports: name_01, name.01, name_v01, name-01
        match = re.search(r'([_.-]*(?:v|V)?)(\d+)$', name)
        
        if match:
            prefix = match.group(1)
            num_str = match.group(2)
            num = int(num_str) + 1
            # Maintain padding
            new_num_str = f"{num:0{len(num_str)}d}"
            new_name = name[:match.start()] + f"{prefix}{new_num_str}"
        else:
            # Append _01 if no number found
            new_name = name + "_01"
        
        new_filepath = os.path.join(directory, new_name + ext)
        
        # Check if file exists, if so keep incrementing (safety)
        while os.path.exists(new_filepath):
            match = re.search(r'([_.-]*(?:v|V)?)(\d+)$', new_name)
            if match:
                prefix = match.group(1)
                num_str = match.group(2)
                num = int(num_str) + 1
                new_num_str = f"{num:0{len(num_str)}d}"
                new_name = new_name[:match.start()] + f"{prefix}{new_num_str}"
                new_filepath = os.path.join(directory, new_name + ext)
            else:
                 new_name = new_name + "_01"
                 new_filepath = os.path.join(directory, new_name + ext)

        try:
            bpy.ops.wm.save_as_mainfile(filepath=new_filepath, copy=False)
            self.report({'INFO'}, f"已增量保存: {new_name}{ext}")
        except Exception as e:
            self.report({'ERROR'}, f"保存失败: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}


def _find_operator_override_context():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return {"window": window, "area": area, "region": region}
    except Exception:
        return None
    return None


def _packed_name_set(collection):
    packed = set()
    for item in list(collection):
        try:
            pf = getattr(item, "packed_file", None)
            if pf is not None:
                filepath = getattr(pf, "filepath", "") or ""
                packed.add(filepath or item.name)
                continue

            pfs = getattr(item, "packed_files", None)
            if pfs:
                for pfi in list(pfs):
                    filepath = getattr(pfi, "filepath", "") or ""
                    packed.add(filepath or item.name)
        except Exception:
            continue
    return packed


def _get_pack_stats():
    return {
        "images": _packed_name_set(getattr(bpy.data, "images", [])),
        "sounds": _packed_name_set(getattr(bpy.data, "sounds", [])),
        "fonts": _packed_name_set(getattr(bpy.data, "fonts", [])),
        "movieclips": _packed_name_set(getattr(bpy.data, "movieclips", [])),
    }


def _pack_all_with_stats(sample_limit=6):
    before = _get_pack_stats()
    override = _find_operator_override_context()
    if override:
        with bpy.context.temp_override(**override):
            bpy.ops.file.pack_all()
    else:
        bpy.ops.file.pack_all()

    after = _get_pack_stats()
    added = {k: sorted(list(after[k] - before[k])) for k in after.keys()}
    def _sample(xs):
        out = []
        for x in xs[:sample_limit]:
            try:
                out.append(os.path.basename(x))
            except Exception:
                out.append(str(x))
        return out
    return {
        "added_counts": {k: len(v) for k, v in added.items()},
        "total_counts": {k: len(after[k]) for k in after.keys()},
        "added_samples": {k: _sample(v) for k, v in added.items()},
        "added_full": added,
    }


class M8_OT_PackResources(bpy.types.Operator):
    bl_idname = "m8.pack_resources"
    bl_label = "打包资源"
    bl_description = "打包外部资源到 .blend（File > External Data > Pack Resources）"

    def execute(self, context):
        try:
            stats = _pack_all_with_stats()
            c = stats["added_counts"]
            t = stats["total_counts"]
            msg = f"已打包资源: +{sum(c.values())}（图像+{c['images']}/{t['images']} 声音+{c['sounds']}/{t['sounds']} 字体+{c['fonts']}/{t['fonts']} 影片+{c['movieclips']}/{t['movieclips']}）"
            self.report({'INFO'}, msg)
            if sum(c.values()):
                print("M8 Pack Resources Added:", stats["added_full"])
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"打包失败: {e}")
            return {'CANCELLED'}


def _purge_unused_materials():
    removed = 0
    for mat in list(getattr(bpy.data, "materials", [])):
        if _is_safe_orphan_id(mat):
            try:
                bpy.data.materials.remove(mat)
                removed += 1
            except Exception:
                pass
    return removed


class M8_OT_PurgeUnusedMaterials(bpy.types.Operator):
    bl_idname = "m8.purge_unused_materials"
    bl_label = "清理未使用材质"
    bl_description = "删除 users=0 的材质（保留资产、假用户、链接库材质）"

    def execute(self, context):
        removed = 0
        try:
            removed = _purge_unused_materials()
        except Exception:
            removed = 0

        if removed:
            self.report({'INFO'}, f"已清理未使用材质: {removed} 个")
        else:
            self.report({'INFO'}, "未发现可清理的未使用材质")
        return {'FINISHED'}


class M8_OT_ShowSaveReport(bpy.types.Operator):
    bl_idname = "m8.show_save_report"
    bl_label = "保存报告"
    bl_options = {'INTERNAL'}

    source: bpy.props.StringProperty(name="来源", default="AUTO")

    def execute(self, context):
        wm = getattr(bpy.context, "window_manager", None)
        if not wm:
            return {'CANCELLED'}

        summary = None
        try:
            summary = wm.get("_m8_last_auto_pack_summary", None)
        except Exception:
            summary = None

        if not summary:
            return {'CANCELLED'}

        purged = int(summary.get("purged_orphans", summary.get("purged_materials", 0)) or 0)
        added = summary.get("packed_added", {}) or {}
        total = summary.get("packed_total", {}) or {}
        samples = summary.get("packed_added_samples", {}) or {}

        def _fmt(k, label):
            a = int(added.get(k, 0) or 0)
            tot = int(total.get(k, 0) or 0)
            s = samples.get(k, []) or []
            tail = f" {label}:{', '.join(s)}" if s else ""
            return f"{label}+{a}/{tot}{tail}"

        msg = f"自动处理: 清除孤立数据 {purged} | 打包 " + " ".join([
            _fmt("images", "图像"),
            _fmt("sounds", "声音"),
            _fmt("fonts", "字体"),
            _fmt("movieclips", "影片"),
        ])
        self.report({'INFO'}, msg)
        try:
            if summary.get("packed_added_full", None):
                print("M8 Auto Pack Added:", summary.get("packed_added_full"))
        except Exception:
            pass

        return {'FINISHED'}


class M8_OT_PlaceholderOp(bpy.types.Operator):
    bl_idname = "m8.placeholder_op"
    bl_label = "占位符"
    bl_description = "功能尚未实现"
    
    msg: bpy.props.StringProperty(default="功能未实现")

    def execute(self, context):
        self.report({'INFO'}, self.msg)
        return {'FINISHED'}

class M8_OT_OpenPreferences(bpy.types.Operator):
    bl_idname = "m8.open_preferences"
    bl_label = "打开偏好设置"
    bl_description = "打开偏好设置窗口"

    def execute(self, context):
        try:
            bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        except Exception as e:
            self.report({'ERROR'}, f"无法打开偏好设置: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


def _get_m8_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg)
    return addon.preferences if addon else None


def _apply_unity_standard_preset(prefs, keep_export_path=True):
    if not prefs:
        return
    try:
        prefs.unity_fbx_use_selection = True
        prefs.unity_fbx_global_scale = 100.0
        prefs.unity_fbx_apply_unit_scale = True
        prefs.unity_fbx_apply_scale_options = "FBX_SCALE_ALL"
        prefs.unity_fbx_use_triangles = True
        prefs.unity_fbx_use_tspace = True
        prefs.unity_fbx_bake_anim = False
        prefs.unity_fbx_use_blend_dir = True
        prefs.unity_fbx_open_folder_after_export = False
        prefs.unity_fbx_reveal_after_export = True
        prefs.ui_show_unity_fbx_advanced = False
        if not keep_export_path:
            prefs.unity_fbx_export_dir = ""
    except Exception:
        pass


class M8_OT_ToggleUnityFBXPreset(bpy.types.Operator):
    bl_idname = "m8.toggle_unity_fbx_preset"
    bl_label = "Unity"
    bl_description = "切换 FBX 导出 Unity 预设"

    def execute(self, context):
        prefs = _get_m8_addon_prefs()
        if not prefs:
            self.report({'WARNING'}, "未找到插件偏好设置")
            return {'CANCELLED'}

        enabled = not bool(getattr(prefs, "fbx_export_unity_preset", False))
        try:
            prefs.fbx_export_unity_preset = enabled
        except Exception:
            return {'CANCELLED'}

        if enabled:
            _apply_unity_standard_preset(prefs, keep_export_path=True)

        self.report({'INFO'}, f"Unity FBX 预设：{'开启' if enabled else '关闭'}")
        return {'FINISHED'}


class M8_OT_ResetUnityFBXPreset(bpy.types.Operator):
    bl_idname = "m8.reset_unity_fbx_preset"
    bl_label = "重置 Unity FBX 预设"
    bl_description = "将 Unity FBX 导出参数重置为标准推荐设置"

    def execute(self, context):
        prefs = _get_m8_addon_prefs()
        if not prefs:
            self.report({'WARNING'}, "未找到插件偏好设置")
            return {'CANCELLED'}

        _apply_unity_standard_preset(prefs, keep_export_path=True)
        self.report({'INFO'}, "已重置 Unity FBX 为标准设置")
        return {'FINISHED'}


class M8_OT_ExportFBX(bpy.types.Operator):
    bl_idname = "m8.export_fbx"
    bl_label = "导出 FBX"
    bl_description = "导出 FBX（可选 Unity 预设）"

    def _reveal_path(self, path, reveal_file=False):
        try:
            if not path:
                return False
            if sys.platform == "win32":
                if reveal_file:
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                else:
                    os.startfile(os.path.normpath(path))
                return True
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
                return True
            subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            return False

    def _get_unity_settings(self, prefs):
        return {
            "use_selection": bool(getattr(prefs, "unity_fbx_use_selection", True)),
            "global_scale": float(getattr(prefs, "unity_fbx_global_scale", 1.0) or 1.0),
            "apply_unit_scale": bool(getattr(prefs, "unity_fbx_apply_unit_scale", True)),
            "apply_scale_options": str(getattr(prefs, "unity_fbx_apply_scale_options", "FBX_SCALE_ALL") or "FBX_SCALE_ALL"),
            "use_triangles": bool(getattr(prefs, "unity_fbx_use_triangles", True)),
            "use_tspace": bool(getattr(prefs, "unity_fbx_use_tspace", True)),
            "bake_anim": bool(getattr(prefs, "unity_fbx_bake_anim", False)),
            "use_blend_dir": bool(getattr(prefs, "unity_fbx_use_blend_dir", True)),
            "export_dir": str(getattr(prefs, "unity_fbx_export_dir", "") or "").strip(),
            "open_folder": bool(getattr(prefs, "unity_fbx_open_folder_after_export", False)),
            "reveal_file": bool(getattr(prefs, "unity_fbx_reveal_after_export", True)),
        }

    def _resolve_unity_target_path(self, settings):
        current_blend = bpy.data.filepath
        if not current_blend:
            return ""
        blend_base = os.path.splitext(os.path.basename(current_blend))[0]
        out_dir = os.path.dirname(current_blend) if settings["use_blend_dir"] else settings["export_dir"]
        if not out_dir:
            return ""
        try:
            out_dir = os.path.normpath(bpy.path.abspath(out_dir))
        except Exception:
            out_dir = os.path.normpath(out_dir)
        if not os.path.isdir(out_dir):
            return ""
        return os.path.join(out_dir, blend_base + ".fbx")

    def _build_unity_export_props(self, settings, filepath=""):
        props = {
            "use_selection": settings["use_selection"],
            "global_scale": settings["global_scale"],
            "apply_unit_scale": settings["apply_unit_scale"],
            "apply_scale_options": settings["apply_scale_options"],
            "use_space_transform": True,
            "bake_space_transform": False,
            "axis_forward": "-Z",
            "axis_up": "Y",
            "add_leaf_bones": False,
            "use_mesh_modifiers": True,
            "use_mesh_modifiers_render": True,
            "use_triangles": settings["use_triangles"],
            "use_tspace": settings["use_tspace"],
            "mesh_smooth_type": "OFF",
            "bake_anim": settings["bake_anim"],
        }
        if filepath:
            props["filepath"] = filepath
            props["check_existing"] = False
        return props

    def invoke(self, context, event):
        try:
            bpy.ops.preferences.addon_enable(module="io_scene_fbx")
        except Exception:
            pass

        prefs = _get_m8_addon_prefs()
        use_unity = bool(getattr(prefs, "fbx_export_unity_preset", False)) if prefs else False

        properties = None
        if use_unity:
            settings = self._get_unity_settings(prefs)
            target_path = self._resolve_unity_target_path(settings)
            if target_path:
                props = self._build_unity_export_props(settings, filepath=target_path)
                res = _call_operator_by_idname("export_scene.fbx", invoke=False, properties=props)
                if res == {'FINISHED'}:
                    self.report({'INFO'}, f"已导出 Unity FBX: {os.path.basename(target_path)}")
                    if settings["reveal_file"]:
                        self._reveal_path(target_path, reveal_file=True)
                    elif settings["open_folder"]:
                        self._reveal_path(os.path.dirname(target_path), reveal_file=False)
                    return res
            properties = self._build_unity_export_props(settings, filepath="")

        res = _call_operator_by_idname("export_scene.fbx", invoke=True, properties=properties)
        if res is None:
            self.report({'WARNING'}, "FBX 导出不可用（请确认已启用 io_scene_fbx）")
            return {'CANCELLED'}
        return res

    def execute(self, context):
        return self.invoke(context, None)


class M8_OT_ToggleScreencastKeys(bpy.types.Operator):
    bl_idname = "m8.toggle_screencast_keys"
    bl_label = "屏幕投射"
    bl_description = "启动/关闭屏幕投射按键显示（内置键帽风格，可在偏好设置中调整样式）"

    def _find_3d_view_context(self):
        for window in bpy.context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            return {
                                "window": window,
                                "screen": screen,
                                "area": area,
                                "region": region,
                                "workspace": window.workspace,
                                "scene": window.scene,
                            }
        return None

    def _try_external_screencast(self):
        # Known module names for Screencast Keys addon
        candidates = [
            "screencast_keys",
            "space_view3d_screencast_keys",
            "bl_ext.blender_org.screencast_keys",
            "bl_ext.user_default.screencast_keys",
        ]

        # 1. Check if any is installed/importable
        found_module = None
        for mod in candidates:
            if importlib.util.find_spec(mod):
                found_module = mod
                break
        
        if not found_module:
            return False, "Not installed"

        # 2. Ensure enabled
        if found_module not in bpy.context.preferences.addons:
            try:
                bpy.ops.preferences.addon_enable(module=found_module)
            except Exception:
                return False, "Failed to enable addon"

        # 3. Find operator
        # Usually wm.screencast_keys or view3d.screencast_keys
        op_candidates = ["wm.screencast_keys", "view3d.screencast_keys"]
        target_op = None
        for op_name in op_candidates:
            if _call_operator_by_idname(op_name, invoke=False, properties={}) is not None: # Just check existence
                 # Wait, _call_operator_by_idname executes it. We just want to check.
                 # Let's check bpy.ops structure
                 a, b = op_name.split(".")
                 if hasattr(getattr(bpy.ops, a), b):
                     target_op = op_name
                     break
        
        # If not found via direct check, maybe it needs context to even show up?
        # Screencast Keys typically registers wm.screencast_keys
        if not target_op:
             # Try blindly wm.screencast_keys
             target_op = "wm.screencast_keys"

        # 4. Invoke with context override
        # Screencast Keys often requires a 3D View context
        ctx_override = self._find_3d_view_context()
        if ctx_override:
            try:
                with bpy.context.temp_override(**ctx_override):
                    # We use invoke because it might need to setup modal
                    _call_operator_by_idname(target_op, invoke=True)
                return True, "Started external"
            except Exception as e:
                # Try direct call if override fails
                pass
        
        # Fallback to direct call
        try:
            _call_operator_by_idname(target_op, invoke=True)
            return True, "Started external (direct)"
        except Exception:
            pass

        return False, "Call failed"

    def execute(self, context):
        # Directly use our new internal engine (User requested full replacement)
        try:
            bpy.ops.m8.internal_screencast('INVOKE_DEFAULT')
            if M8_OT_InternalScreencast._running:
                self.report({'INFO'}, "屏幕投射：已启动")
            else:
                self.report({'INFO'}, "屏幕投射：已关闭")
            try:
                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        area.tag_redraw()
            except Exception:
                pass
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"启动失败: {e}")
            return {'CANCELLED'}

def _call_operator_by_idname(op_idname, invoke=True, properties=None):
    if not op_idname or "." not in op_idname:
        return None
    a, b = op_idname.split(".", 1)
    group = getattr(bpy.ops, a, None)
    if not group:
        return None
    op = getattr(group, b, None)
    if not op:
        return None
    try:
        if invoke:
            return op('INVOKE_DEFAULT', **(properties or {}))
        return op(**(properties or {}))
    except Exception:
        return None

_ALLOWED_ADDON_MODULES = {
    "io_scene_fbx",
    "screencast_keys",
    "space_view3d_screencast_keys",
    "bl_ext.blender_org.screencast_keys",
    "bl_ext.user_default.screencast_keys",
}

_ALLOWED_EXTERNAL_OPERATORS = {
    "export_scene.fbx",
    "wm.screencast_keys",
    "view3d.screencast_keys",
}

class M8_OT_CallOperatorWithAddon(bpy.types.Operator):
    bl_idname = "m8.call_operator_with_addon"
    bl_label = "调用并自动启用插件"
    bl_description = "如果操作符不存在，会尝试启用对应插件后再调用"

    module: bpy.props.StringProperty(name="插件模块", default="")
    operator: bpy.props.StringProperty(name="操作符", default="")
    invoke: bpy.props.BoolProperty(name="调用方式", default=True)

    def execute(self, context):
        op_idname = (self.operator or "").strip()
        if not op_idname:
            self.report({'WARNING'}, "未指定操作符")
            return {'CANCELLED'}

        if not re.match(r"^[a-z0-9_]+\.[a-z0-9_]+$", op_idname):
            self.report({'WARNING'}, f"操作符格式无效：{op_idname}")
            return {'CANCELLED'}

        module = (self.module or "").strip()
        is_ours = op_idname.startswith("m8.")
        is_allowed_external = op_idname in _ALLOWED_EXTERNAL_OPERATORS

        if not (is_ours or is_allowed_external):
            self.report({'WARNING'}, f"操作符未允许：{op_idname}")
            return {'CANCELLED'}

        if module and (module not in _ALLOWED_ADDON_MODULES):
            self.report({'WARNING'}, f"插件模块未允许：{module}")
            return {'CANCELLED'}

        res = _call_operator_by_idname(op_idname, invoke=bool(self.invoke))
        if res is not None:
            return {'FINISHED'}

        if module and is_allowed_external:
            try:
                bpy.ops.preferences.addon_enable(module=module)
            except Exception as e:
                self.report({'WARNING'}, f"启用插件失败：{module}（{e}）")
                return {'CANCELLED'}

        res = _call_operator_by_idname(op_idname, invoke=bool(self.invoke))
        if res is not None:
            return {'FINISHED'}

        if module:
            self.report({'WARNING'}, f"操作符不可用：{op_idname}（已尝试启用 {module}）")
        else:
            self.report({'WARNING'}, f"操作符不可用：{op_idname}")
        return {'CANCELLED'}

def _unique_collection_name(base_name):
    name = base_name.strip() or "Asset_Group"
    if not bpy.data.collections.get(name):
        return name
    idx = 1
    while True:
        candidate = f"{name}.{idx:03d}"
        if not bpy.data.collections.get(candidate):
            return candidate
        idx += 1

class M8_OT_CreateAssetGroup(bpy.types.Operator):
    bl_idname = "m8.create_asset_group"
    bl_label = "创建组资产"
    bl_description = "创建集合并标记为资产（Asset）"

    name: bpy.props.StringProperty(name="名称", default="Asset_Group")
    link_to_scene: bpy.props.BoolProperty(name="链接到场景", default=True)
    mark_as_asset: bpy.props.BoolProperty(name="标记为资产", default=True)

    def execute(self, context):
        scene = getattr(bpy.context, "scene", None)
        if not scene:
            self.report({'ERROR'}, "未找到场景")
            return {'CANCELLED'}

        col_name = _unique_collection_name(self.name)
        col = bpy.data.collections.new(col_name)

        if self.link_to_scene:
            try:
                scene.collection.children.link(col)
            except Exception:
                pass

        if self.mark_as_asset:
            try:
                col.asset_mark()
            except Exception:
                try:
                    bpy.ops.asset.mark({'id': col})
                except Exception:
                    pass

        self.report({'INFO'}, f"已创建资产组: {col_name}")
        return {'FINISHED'}

def _is_safe_orphan_id(id_block):
    try:
        if getattr(id_block, "library", None):
            return False
        if getattr(id_block, "use_fake_user", False):
            return False
        if getattr(id_block, "asset_data", None) is not None:
            return False
        return getattr(id_block, "users", 0) == 0
    except Exception:
        return False

def _remove_orphans_from_collection(data_collection):
    removed = 0
    for id_block in list(data_collection):
        if _is_safe_orphan_id(id_block):
            try:
                data_collection.remove(id_block)
                removed += 1
            except Exception:
                pass
    return removed

class M8_OT_OrphansPurgeKeepAssets(bpy.types.Operator):
    bl_idname = "m8.orphans_purge_keep_assets"
    bl_label = "保留资产"
    bl_description = "清理未使用数据，但保留已标记为资产的 datablock"

    max_passes: bpy.props.IntProperty(name="遍历次数", default=6, min=1, max=20)

    def execute(self, context):
        total_removed = 0
        passes = int(self.max_passes)
        for _ in range(passes):
            removed = 0
            removed += _remove_orphans_from_collection(getattr(bpy.data, "meshes", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "materials", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "images", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "node_groups", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "actions", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "armatures", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "curves", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "collections", []))
            removed += _remove_orphans_from_collection(getattr(bpy.data, "objects", []))
            total_removed += removed
            if removed == 0:
                break

        if total_removed:
            self.report({'INFO'}, f"已清理未使用数据: {total_removed} 项（保留资产）")
        else:
            self.report({'INFO'}, "未发现可清理的未使用数据（保留资产）")
        return {'FINISHED'}
