"""
M8 N-Panel Manager: Runtime State & Zero-Pollution Snapshot Engine
记录面板的原始 bl_category 和 bl_parent_id，确保一键无痕瞬时还原，不污染 Blender 原生环境。
"""
import bpy
import traceback
from typing import Dict, List, Optional, Type


class PanelSnapshot:
    """单个面板被接管前的原始状态快照"""
    def __init__(self, original_category: str, original_parent_id: Optional[str], original_order: int):
        self.original_category: str = original_category
        self.original_parent_id: Optional[str] = original_parent_id
        self.original_order: int = original_order


class PanelStateManager:
    """全局面板状态快照与生命周期管理器"""
    _snapshots: Dict[Type[bpy.types.Panel], PanelSnapshot] = {}
    _title_panels: List[Type[bpy.types.Panel]] = []
    _hidden_panel_classes: Dict[str, Type[bpy.types.Panel]] = {}
    is_active: bool = False
    is_restoring: bool = False
    is_updating: bool = False

    @classmethod
    def record(cls, panel: Type[bpy.types.Panel]) -> PanelSnapshot:
        """记录面板的原始状态（如果未记录过）"""
        if panel not in cls._snapshots:
            orig_cat = getattr(panel, "bl_category", "Misc")
            orig_parent = getattr(panel, "bl_parent_id", None)
            orig_order = getattr(panel, "bl_order", 0)
            cls._snapshots[panel] = PanelSnapshot(orig_cat, orig_parent, orig_order)
        return cls._snapshots[panel]

    @classmethod
    def has_snapshot(cls, panel: Type[bpy.types.Panel]) -> bool:
        return panel in cls._snapshots

    @classmethod
    def get_original_category(cls, panel: Type[bpy.types.Panel]) -> str:
        if panel in cls._snapshots:
            return cls._snapshots[panel].original_category
        return getattr(panel, "bl_category", "Misc")

    @classmethod
    def get_original_parent_id(cls, panel: Type[bpy.types.Panel]) -> Optional[str]:
        if panel in cls._snapshots:
            return cls._snapshots[panel].original_parent_id
        return getattr(panel, "bl_parent_id", None)

    @classmethod
    def register_title_panel(cls, title_panel: Type[bpy.types.Panel]):
        """记录动态生成的置顶子标签面板"""
        cls._title_panels.append(title_panel)

    @classmethod
    def clear_title_panels(cls):
        """清理所有动态生成的置顶子标签面板"""
        for tp in cls._title_panels:
            try:
                idname = getattr(tp, "bl_idname", None) or getattr(tp, "__name__", "")
                if getattr(tp, "is_registered", False) or hasattr(bpy.types, idname) or hasattr(bpy.types, getattr(tp, "__name__", "")):
                    bpy.utils.unregister_class(tp)
            except Exception:
                pass
        cls._title_panels.clear()

        # 深度防漏：扫描并安全注销所有遗留的 M8 动态置顶标题面板，彻底杜绝重载残留与重叠多排
        for name in list(dir(bpy.types)):
            if name.startswith("M8_PT_SubTabs_"):
                cls_obj = getattr(bpy.types, name, None)
                if cls_obj:
                    try:
                        bpy.utils.unregister_class(cls_obj)
                    except Exception:
                        pass

    @classmethod
    def restore_all(cls):
        """
        核心安全机制：一键无痕瞬时还原所有被劫持的面板
        恢复原始 bl_category 与 bl_parent_id，并重新注册，彻底消除脏状态。
        """
        if cls.is_restoring:
            return
        cls.is_restoring = True
        try:
            # 1. 销毁所有置顶子标签面板
            cls.clear_title_panels()

            # 2. 还原所有面板属性（分代排序）
            panels_to_restore = []
            for panel, snapshot in list(cls._snapshots.items()):
                if not hasattr(panel, "__name__"):
                    continue
                curr_cat = getattr(panel, "bl_category", "")
                curr_parent = getattr(panel, "bl_parent_id", None)
                if curr_cat != snapshot.original_category or curr_parent != snapshot.original_parent_id:
                    panels_to_restore.append(panel)

            if panels_to_restore:
                # 简单分代：先子面板后父面板注销，先父面板后子面板注册
                all_names = {getattr(p, "bl_idname", None) or p.__name__ for p in panels_to_restore}
                roots = [p for p in panels_to_restore if not getattr(p, "bl_parent_id", None) or getattr(p, "bl_parent_id", None) not in all_names]
                children = [p for p in panels_to_restore if p not in roots]
                ordered_forward = roots + children

                # 逆序注销
                for panel in reversed(ordered_forward):
                    idname = getattr(panel, "bl_idname", None) or getattr(panel, "__name__", "")
                    if getattr(panel, "is_registered", False) or hasattr(bpy.types, idname) or hasattr(bpy.types, getattr(panel, "__name__", "")):
                        try:
                            bpy.utils.unregister_class(panel)
                        except Exception:
                            pass

                # 恢复属性并顺序注册
                restored_count = 0
                for panel in ordered_forward:
                    snapshot = cls._snapshots[panel]
                    if snapshot.original_category:
                        panel.bl_category = snapshot.original_category
                    elif hasattr(panel, "bl_category"):
                        try:
                            delattr(panel, "bl_category")
                        except Exception:
                            pass

                    if snapshot.original_parent_id:
                        panel.bl_parent_id = snapshot.original_parent_id
                    elif hasattr(panel, "bl_parent_id"):
                        try:
                            delattr(panel, "bl_parent_id")
                        except Exception:
                            pass

                    panel.bl_order = snapshot.original_order

                    try:
                        bpy.utils.register_class(panel)
                        restored_count += 1
                    except Exception as e:
                        print(f"[M8 NPanel] Warning registering restored panel {panel.__name__}: {e}")

            cls._snapshots.clear()
            cls.is_active = False
            print(f"[M8 NPanel] Successfully restored {restored_count if panels_to_restore else 0} panels to default state.")
        finally:
            cls.is_restoring = False
