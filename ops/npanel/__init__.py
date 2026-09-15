"""
M8 N-Panel Sub-Tabs & Category Organizer Package
"""
import bpy
from . import props
from . import core
from . import operators
from . import ui
from . import events
from . import backup
from . import header_menu
from . import pie
from .state import PanelStateManager

MODULE_CLASSES = (
    *core.CORE_PANEL_CLASSES,
    *operators.OPERATOR_CLASSES,
    *ui.UI_CLASSES,
    *backup.BACKUP_CLASSES,
)


def check_standalone_subtabs_conflict():
    """核心防冲突：检测并自动禁用独立原版 n_panel_sub_tabs 插件，杜绝双重注入与顶栏/面板重复"""
    try:
        conflicting_addons = [
            "bl_ext.user_default.n_panel_sub_tabs",
            "n_panel_sub_tabs",
        ]
        pref_addons = getattr(getattr(bpy.context, "preferences", None), "addons", None)
        if pref_addons:
            for addon_id in conflicting_addons:
                if addon_id in pref_addons:
                    try:
                        bpy.ops.preferences.addon_disable(module=addon_id)
                        print(f"[M8 NPanel] 已自动关闭冲突的原版独立插件 '{addon_id}'（M8 已原生内置此功能）")
                    except Exception as e:
                        print(f"[M8 NPanel] 尝试关闭冲突插件 '{addon_id}' 失败: {e}")
    except Exception:
        pass


def register():
    # 0. 自动排除冲突的原版独立插件
    check_standalone_subtabs_conflict()

    # 1. 注册数据结构
    props.register()

    # 2. 注册操作符与面板
    for cls in MODULE_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"[M8 NPanel] Failed to register class {cls}: {e}")

    # 3. 挂载编辑器顶栏菜单入口 [ 🏁 ˅ ] (VIEW3D, IMAGE_EDITOR, NODE_EDITOR 等)
    header_menu.register()

    # 4. 注册生命周期与工作区事件
    events.register()

    # 5. 注册子标签按钮右键上下文菜单钩子
    pie.register()


def unregister():
    # 0. 注销子标签按钮右键上下文菜单钩子
    pie.unregister()

    # 1. 核心安全铁律：注销时 0 延迟无痕瞬时还原所有被接管的第三方侧边栏面板！
    try:
        PanelStateManager.restore_all()
    except Exception as e:
        print(f"[M8 NPanel] Error restoring panels during unregister: {e}")

    # 2. 移除顶栏菜单入口
    header_menu.unregister()

    # 3. 注销事件与定时器
    events.unregister()

    # 4. 注销操作符与面板
    for cls in reversed(MODULE_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    # 5. 注销数据结构
    props.unregister()
