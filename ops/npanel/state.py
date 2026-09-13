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
                if hasattr(bpy.types, tp.__name__):
                    bpy.utils.unregister_class(tp)
            except Exception:
                pass
        cls._title_panels.clear()

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

            # 2. 还原所有面板属性
            restored_count = 0
            for panel, snapshot in list(cls._snapshots.items()):
                try:
                    if not hasattr(panel, "__name__"):
                        continue

                    need_update = False
                    curr_cat = getattr(panel, "bl_category", None)
                    curr_parent = getattr(panel, "bl_parent_id", None)

                    if curr_cat != snapshot.original_category:
                        need_update = True
                    if curr_parent != snapshot.original_parent_id:
                        need_update = True

                    if need_update:
                        is_reg = hasattr(bpy.types, panel.__name__)
                        if is_reg:
                            bpy.utils.unregister_class(panel)

                        # 恢复属性
                        panel.bl_category = snapshot.original_category
                        if snapshot.original_parent_id:
                            panel.bl_parent_id = snapshot.original_parent_id
                        elif hasattr(panel, "bl_parent_id"):
                            try:
                                delattr(panel, "bl_parent_id")
                            except Exception:
                                pass

                        panel.bl_order = snapshot.original_order

                        if is_reg:
                            bpy.utils.register_class(panel)
                        restored_count += 1
                except Exception as e:
                    print(f"[M8 NPanel] Warning restoring panel {panel}: {e}")

            cls._snapshots.clear()
            cls.is_active = False
            print(f"[M8 NPanel] Successfully restored {restored_count} panels to default state.")
        finally:
            cls.is_restoring = False
