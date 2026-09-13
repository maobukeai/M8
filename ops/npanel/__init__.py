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
from .state import PanelStateManager

MODULE_CLASSES = (
    *core.CORE_PANEL_CLASSES,
    *operators.OPERATOR_CLASSES,
    *ui.UI_CLASSES,
    *backup.BACKUP_CLASSES,
)


def register():
    # 1. 注册数据结构
    props.register()

    # 2. 注册操作符与面板
    for cls in MODULE_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"[M8 NPanel] Failed to register class {cls}: {e}")

    # 3. 挂载 3D 视图顶栏快速入口
    if hasattr(bpy.types, "VIEW3D_HT_header"):
        try:
            bpy.types.VIEW3D_HT_header.append(ui.draw_view3d_header)
        except Exception:
            pass

    # 4. 注册生命周期与工作区事件
    events.register()


def unregister():
    # 1. 核心安全铁律：注销时 0 延迟无痕瞬时还原所有被接管的第三方侧边栏面板！
    try:
        PanelStateManager.restore_all()
    except Exception as e:
        print(f"[M8 NPanel] Error restoring panels during unregister: {e}")

    # 2. 移除顶栏入口
    if hasattr(bpy.types, "VIEW3D_HT_header"):
        try:
            bpy.types.VIEW3D_HT_header.remove(ui.draw_view3d_header)
        except Exception:
            pass

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
