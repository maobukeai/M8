import platform

import bpy

from ..utils import get_operator_bl_idname, get_pref


def get_event_key(event: bpy.types.Event):
    alt = event.alt
    shift = event.shift
    ctrl = event.ctrl

    not_key = ((not ctrl) and (not alt) and (not shift))

    only_ctrl = (ctrl and (not alt) and (not shift))
    only_alt = ((not ctrl) and alt and (not shift))
    only_shift = ((not ctrl) and (not alt) and shift)

    shift_alt = ((not ctrl) and alt and shift)
    ctrl_alt = (ctrl and alt and (not shift))

    ctrl_shift = (ctrl and (not alt) and shift)
    ctrl_shift_alt = (ctrl and alt and shift)
    return not_key, only_ctrl, only_alt, only_shift, shift_alt, ctrl_alt, ctrl_shift, ctrl_shift_alt


class PublicEvent:
    not_key: bool
    only_ctrl: bool
    only_alt: bool
    only_shift: bool
    shift_alt: bool
    ctrl_alt: bool
    ctrl_shift: bool
    ctrl_shift_alt: bool

    def set_event_key(self, event):
        self.not_key, self.only_ctrl, self.only_alt, self.only_shift, self.shift_alt, self.ctrl_alt, self.ctrl_shift, self.ctrl_shift_alt = \
            get_event_key(event)


def start_blender(step=1, open_recent=False, factory_startup=False, recover_auto_save=False):
    """Create a new Blender thread through subprocess
    
    open_recent:
        Open the most recently used file
        
    factory_startup:
        Open with factory settings (--factory-startup)
        
    recover_auto_save:
        Open the last auto-save file (quit.blend)

    offset
    
    -p, --window-geometry <sx> <sy> <w> <h>
        Open with lower left corner at <sx>, <sy> and width and height as <w>, <h>.
    https://docs.blender.org/manual/en/4.3/advanced/command_line/arguments.html#window-options
    """
    import subprocess
    import os
    
    if not factory_startup:
        try:
            bpy.ops.wm.save_userpref()
        except Exception:
            import traceback
            traceback.print_exc()

    args = [bpy.app.binary_path, ]
    
    if factory_startup:
        args.append("--factory-startup")

    if open_recent:
        # 获取最近打开的文件列表
        recent_files_path = os.path.join(bpy.utils.user_resource('CONFIG'), 'recent-files.txt')
        if os.path.exists(recent_files_path):
            try:
                with open(recent_files_path, 'r', encoding='utf-8') as f:
                    # 读取第一行非空路径
                    for line in f:
                        recent_file = line.strip()
                        if recent_file and os.path.exists(recent_file):
                            args.append(recent_file)
                            break
            except Exception:
                pass
                
    if recover_auto_save:
        # 尝试加载 quit.blend (自动保存)
        # 通常位于临时目录或 CONFIG/../autosave/
        # Blender 默认退出时会保存 quit.blend 到临时目录
        import tempfile
        temp_dir = tempfile.gettempdir()
        quit_blend = os.path.join(temp_dir, "quit.blend")
        
        # 也可以尝试找 autosave 目录下的最新文件
        # 这里优先使用 quit.blend，因为它是最近一次退出的状态
        if os.path.exists(quit_blend):
            args.append(quit_blend)
        else:
            pass

    window = bpy.context.window
    offset = step * 20

    args.append("-p")
    args.extend((
        str(window.x + offset),
        str(window.y - offset),
        str(window.width),
        str(window.height),
    ))

    try:
        subprocess.Popen(args)
    except Exception:
        import traceback
        traceback.print_exc()


def reload_addon(root_module: str):
    import sys
    import importlib
    
    root = sys.modules.get(root_module)
    if root and hasattr(root, "unregister"):
        try:
            root.unregister()
        except Exception:
            import traceback
            traceback.print_exc()

    module_names = [n for n in sys.modules.keys() if n == root_module or n.startswith(root_module + ".")]
    for name in sorted(module_names, key=len, reverse=True):
        mod = sys.modules.get(name)
        if not mod:
            continue
        try:
            importlib.reload(mod)
        except Exception:
            import traceback
            traceback.print_exc()

    root = sys.modules.get(root_module)
    if root and hasattr(root, "register"):
        try:
            root.register()
        except Exception:
            import traceback
            traceback.print_exc()


class RestartBlender(
    bpy.types.Operator,
    PublicEvent,
):
    bl_idname = get_operator_bl_idname("restart_blender")
    bl_label = "Restart Blender"
    bl_options = {"REGISTER"}

    @classmethod
    def description(cls, context, properties):
        from ..utils.translate import translate_lines_text
        return translate_lines_text(
            "",
            "Click           Open a New Blender",
            "Alt         Reload M8 Addon",
            "Ctrl         Start and Recover Auto Save",
            "Shift       Open Recent File",
            "",
            "Ctrl+Alt+Shift Open Blender with Factory Settings",
        )

    def run_cmd(self, event: bpy.types.Event):
        self.set_event_key(event)
        
        if self.not_key:
            try:
                start_blender()
            except Exception as e:
                self.report({"ERROR"}, str(e))
        elif self.only_alt:
            root_module = (__package__ or "").split(".")[0]
            if root_module:
                def _do_reload():
                    reload_addon(root_module)
                    return None
                bpy.app.timers.register(_do_reload, first_interval=0.01)
        elif self.only_ctrl:
            # Ctrl: 恢复自动保存 (quit.blend)
            try:
                start_blender(recover_auto_save=True)
                bpy.ops.wm.quit_blender()
            except Exception as e:
                self.report({"ERROR"}, str(e))
        elif self.only_shift:
            # Shift: 打开最近的文件
            try:
                start_blender(open_recent=True)
            except Exception as e:
                self.report({"ERROR"}, str(e))
        elif self.ctrl_shift_alt:
            # Ctrl+Alt+Shift: 工厂模式启动
            try:
                start_blender(factory_startup=True)
            except Exception as e:
                self.report({"ERROR"}, str(e))
        else:
            try:
                start_blender()
                self.report({"INFO"}, self.bl_description)
            except Exception as e:
                self.report({"ERROR"}, str(e))

    def invoke(self, context, event):
        if platform.system() == "Windows":
            self.run_cmd(event)
        elif platform.system() == "Linux":
            self.report({"INFO"}, "This feature currently does not support Linux systems")
        else:
            self.report({"INFO"}, "This feature currently does not support this system")
        return {"FINISHED"}


def draw_restart_blender_top_bar(self, context):
    pref = get_pref()
    is_draw = True

    try:
        func = getattr(getattr(bpy.ops, "wm"), "restart_blender")
        func.get_rna_type()
        is_draw = False
    except KeyError:
        ...
    
    if getattr(pref, "activate_restart_blender", True) and is_draw:
        row = self.layout.row(align=True)
        row.alert = True
        row.operator(
            operator=RestartBlender.bl_idname,
            text="",
            emboss=False,
            icon="QUIT"
        )


def register():
    bpy.utils.register_class(RestartBlender)
    if hasattr(bpy.types, "TOPBAR_MT_editor_menus"):
        bpy.types.TOPBAR_MT_editor_menus.append(draw_restart_blender_top_bar)


def unregister():
    if getattr(RestartBlender, "is_registered", False):
        bpy.utils.unregister_class(RestartBlender)
    if hasattr(bpy.types, "TOPBAR_MT_editor_menus"):
        bpy.types.TOPBAR_MT_editor_menus.remove(draw_restart_blender_top_bar)
