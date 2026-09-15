"""
M8 N-Panel Manager: Lifecycle & Workspace Event Handlers
包含：启动延迟初始化定时器（确保第三方插件全部加载后再重组）、工作区自适应切换监听 (msgbus)
"""
import bpy
from bpy.app.handlers import persistent
import fnmatch
from . import core

_msgbus_owner = object()


def startup_delayed_timer():
    """启动延迟定时器：在 Blender 启动 1.5 秒后自动应用，避免与其它第三方插件启动顺序竞态"""
    try:
        context = bpy.context
        if not context or not hasattr(context, "scene"):
            return None
        settings = getattr(context.scene, "m8_npanel", None)
        if settings:
            from . import backup
            # 若当前场景无分类，尝试从磁盘加载全局预设
            backup.load_presets_from_disk(context, force=False)
            if settings.enabled:
                core.apply_organization(context)
    except Exception as e:
        print(f"[M8 NPanel] Startup timer error: {e}")
    return None  # 仅执行一次


@persistent
def on_load_post(dummy):
    """工程文件加载后自动加载预设并重新挂载定时器与工作区监听"""
    try:
        context = bpy.context
        if context and hasattr(context, "scene"):
            from . import backup
            backup.load_presets_from_disk(context, force=False)
    except Exception:
        pass

    if not bpy.app.timers.is_registered(startup_delayed_timer):
        bpy.app.timers.register(startup_delayed_timer, first_interval=1.5)
    setup_workspace_listener()


def on_workspace_changed(*args):
    """工作区切换回调：智能激活与工作区相符的分类"""
    try:
        context = bpy.context
        if not context or not hasattr(context, "workspace"):
            return
        settings = getattr(context.scene, "m8_npanel", None)
        if not settings or not settings.enabled or not settings.workspace_auto_switch:
            return

        ws_name = context.workspace.name.lower()

        # 智能匹配规则
        mapping = [
            ("*model*", "建模"),
            ("*sculpt*", "建模"),
            ("*shad*", "材质"),
            ("*uv*", "材质"),
            ("*textur*", "材质"),
            ("*render*", "渲染"),
            ("*light*", "渲染"),
            ("*anim*", "动画"),
            ("*rig*", "装配"),
            ("*compos*", "合成"),
        ]

        target_cat = None
        for pattern, cat_sub in mapping:
            if fnmatch.fnmatch(ws_name, pattern):
                for c in settings.categories:
                    if cat_sub in c.name:
                        target_cat = c
                        break
            if target_cat:
                break

        if target_cat:
            # 激活对应分类并刷新
            for i, c in enumerate(settings.categories):
                if c.name == target_cat.name:
                    settings.category_index = i
                    break
            core.apply_organization(context)
            if getattr(context, "area", None):
                context.area.tag_redraw()

    except Exception:
        pass


def setup_workspace_listener():
    """注册 Blender msgbus 工作区变更监听"""
    try:
        bpy.msgbus.clear_by_owner(_msgbus_owner)
        bpy.msgbus.subscribe_rna(
            key=(bpy.types.Window, "workspace"),
            owner=_msgbus_owner,
            args=(),
            notify=on_workspace_changed,
        )
    except Exception as e:
        print(f"[M8 NPanel] Failed to subscribe workspace msgbus: {e}")


def register():
    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)
    setup_workspace_listener()
    if not bpy.app.timers.is_registered(startup_delayed_timer):
        bpy.app.timers.register(startup_delayed_timer, first_interval=1.5)


def unregister():
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    if bpy.app.timers.is_registered(startup_delayed_timer):
        bpy.app.timers.unregister(startup_delayed_timer)
