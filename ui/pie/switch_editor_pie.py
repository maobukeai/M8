import bpy


EDITOR_TYPES = [
    ("VIEW_3D", "3D Viewport", "3D 视图", "VIEW3D", 1),
    ("IMAGE_EDITOR", "Image Editor", "图像编辑器", "IMAGE_DATA", 2),
    ("UV", "UV Editor", "UV 编辑器", "UV", 3),
    ("ShaderNodeTree", "Shader Editor", "着色器编辑器", "NODE_MATERIAL", 4),
    ("GeometryNodeTree", "Geometry Nodes", "几何节点", "GEOMETRY_NODES", 5),
    ("CompositorNodeTree", "Compositor", "合成器", "NODE_COMPOSITING", 6),
    ("TextureNodeTree", "Texture Nodes", "纹理节点", "TEXTURE", 7),
    ("DOPESHEET", "Dope Sheet", "动画摄影表", "ACTION", 8),
    ("TIMELINE", "Timeline", "时间线", "TIME", 9),
    ("FCURVES", "Graph Editor", "曲线编辑器", "GRAPH", 10),
    ("DRIVERS", "Drivers", "驱动器", "DRIVER", 11),
    ("NLA_EDITOR", "NLA Editor", "非线性动画", "NLA", 12),
    ("TEXT_EDITOR", "Text Editor", "文本编辑器", "TEXT", 13),
    ("CONSOLE", "Python Console", "Python 控制台", "CONSOLE", 14),
    ("INFO", "Info", "信息", "INFO", 15),
    ("OUTLINER", "Outliner", "大纲视图", "OUTLINER", 16),
    ("PROPERTIES", "Properties", "属性", "PROPERTIES", 17),
    ("FILE_BROWSER", "File Browser", "文件浏览器", "FILE_FOLDER", 18),
    ("ASSETS", "Asset Browser", "资产浏览器", "ASSET_MANAGER", 19),
    ("SPREADSHEET", "Spreadsheet", "电子表格", "SPREADSHEET", 20),
    ("PREFERENCES", "Preferences", "偏好设置", "PREFERENCES", 21),
    ("CLIP_EDITOR", "Movie Clip Editor", "影片剪辑编辑器", "TRACKER", 22),
    ("SEQUENCE_EDITOR", "Video Sequencer", "视频序列编辑器", "SEQUENCE", 23),
    ("RENDER", "Render", "渲染", "RENDER_STILL", 24),
    ("NONE", "None", "无", "X", 0),
]


def _get_addon_prefs():
    root_pkg = (__package__ or "").split(".")[0]
    addon = bpy.context.preferences.addons.get(root_pkg) if bpy.context and bpy.context.preferences else None
    return addon.preferences if addon else None


def _editor_type_items(self, context):
    return [(val, name_en, "", icon, order) for val, name_en, _name_zh, icon, order in EDITOR_TYPES]


def _get_editor_meta(value, lang):
    for val, name_en, name_zh, icon, _ in EDITOR_TYPES:
        if val == value:
            return (name_en if lang == "EN" else name_zh, icon)
    return (value, "NONE")


def _apply_editor_target(area, target):
    if target in {"ShaderNodeTree", "GeometryNodeTree", "CompositorNodeTree", "TextureNodeTree"}:
        area.type = "NODE_EDITOR"
        area.ui_type = target
        return
    if target in {"IMAGE_EDITOR", "UV"}:
        area.type = "IMAGE_EDITOR"
        area.ui_type = target
        return
    if target in {"DOPESHEET", "TIMELINE", "FCURVES", "DRIVERS", "NLA_EDITOR"}:
        area.type = "DOPESHEET_EDITOR"
        area.ui_type = target
        return
    if target in {"FILE_BROWSER", "ASSETS"}:
        area.type = "FILE_BROWSER"
        area.ui_type = target
        return
    area.type = target


class M8_OT_SwitchEditorArea(bpy.types.Operator):
    bl_idname = "m8.switch_editor_area"
    bl_label = "Switch Editor Area"
    bl_options = {"INTERNAL"}

    target: bpy.props.EnumProperty(items=_editor_type_items)

    def execute(self, context):
        area = context.area
        if not area:
            return {"CANCELLED"}

        target = self.target
        if target == "NONE":
            return {"FINISHED"}
        if target == "RENDER":
            scene = context.scene
            if not scene or not scene.camera:
                self.report({"WARNING"}, "当前场景没有摄像机，无法渲染")
                return {"CANCELLED"}
            try:
                bpy.ops.render.render("INVOKE_DEFAULT")
                return {"FINISHED"}
            except RuntimeError:
                self.report({"WARNING"}, "渲染执行失败")
                return {"CANCELLED"}

        window_ptr = context.window.as_pointer() if context.window else 0
        screen_ptr = context.screen.as_pointer() if context.screen else 0
        area_ptr = area.as_pointer()

        def _deferred_switch():
            wm = bpy.context.window_manager
            if not wm:
                return None
            for win in wm.windows:
                if window_ptr and win.as_pointer() != window_ptr:
                    continue
                scr = win.screen
                if not scr:
                    continue
                if screen_ptr and scr.as_pointer() != screen_ptr:
                    continue
                for ar in scr.areas:
                    if ar.as_pointer() == area_ptr:
                        try:
                            _apply_editor_target(ar, target)
                        except Exception:
                            pass
                        return None
            return None

        bpy.app.timers.register(_deferred_switch, first_interval=0.01)
        return {"FINISHED"}


class VIEW3D_MT_M8SwitchEditorPie(bpy.types.Menu):
    bl_label = "切换窗口"
    bl_idname = "M8_MT_switch_editor_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        prefs = _get_addon_prefs()
        lang = getattr(prefs, "addon_language", "ZH") if prefs else "ZH"
        default_map = {
            "left": "ShaderNodeTree",
            "right": "RENDER",
            "bottom": "UV",
            "top": "VIEW_3D",
            "top_left": "UV",
            "top_right": "TextureNodeTree",
            "bottom_left": "CompositorNodeTree",
            "bottom_right": "TEXT_EDITOR",
        }

        for slot in ("left", "right", "bottom", "top", "top_left", "top_right", "bottom_left", "bottom_right"):
            value = getattr(prefs, f"switch_editor_pie_{slot}", default_map[slot]) if prefs else default_map[slot]
            text, icon = _get_editor_meta(value, lang)
            op = pie.operator(M8_OT_SwitchEditorArea.bl_idname, text=text, icon=icon)
            op.target = value
