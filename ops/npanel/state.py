"""
M8 N-Panel Manager: Runtime State & Zero-Pollution Snapshot Engine
记录面板的原始 bl_category 和 bl_parent_id，确保一键无痕瞬时还原，不污染 Blender 原生环境。
"""
import bpy
import traceback
from typing import Dict, List, Optional, Type


import inspect
import re


import ast
import textwrap


def _extract_from_ast_class(class_node):
    cat = None
    parent = None

    def _extract_str(val_node):
        if isinstance(val_node, ast.Constant) and isinstance(val_node.value, str):
            return val_node.value
        elif isinstance(val_node, ast.Call) and val_node.args:
            first_arg = val_node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                return first_arg.value
        return None

    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    if target.id == "bl_category" and not cat:
                        cat = _extract_str(stmt.value)
                    elif target.id == "bl_parent_id" and not parent:
                        parent = _extract_str(stmt.value)
                elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(stmt.value, (ast.Tuple, ast.List)):
                    if len(target.elts) == len(stmt.value.elts):
                        for t_elt, v_elt in zip(target.elts, stmt.value.elts):
                            if isinstance(t_elt, ast.Name):
                                if t_elt.id == "bl_category" and not cat:
                                    cat = _extract_str(v_elt)
                                elif t_elt.id == "bl_parent_id" and not parent:
                                    parent = _extract_str(v_elt)
    return cat, parent


def get_source_attributes(panel: Type[bpy.types.Panel]):
    """从 Python 源码 AST/代码行中提取面板类及其基类定义时的真实原始 bl_category 与 bl_parent_id"""
    orig_cat = None
    orig_parent = None
    try:
        for cls in getattr(panel, "__mro__", [panel]):
            if cls in (bpy.types.Panel, bpy.types.UIList, object):
                break
            try:
                src = textwrap.dedent(inspect.getsource(cls))
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        a_cat, a_parent = _extract_from_ast_class(node)
                        if not orig_cat and a_cat:
                            orig_cat = a_cat
                        if not orig_parent and a_parent is not None:
                            orig_parent = a_parent
                        break
            except Exception:
                try:
                    lines, _ = inspect.getsourcelines(cls)
                    for line in lines:
                        line_str = line.strip()
                        if line_str.startswith("#"):
                            continue
                        if not orig_cat:
                            m = re.search(r'\bbl_category\s*=\s*(?:[a-zA-Z0-9_.]+\s*\(\s*)?[\'\"]([^\'\"]+)[\'\"]', line_str)
                            if m:
                                orig_cat = m.group(1)
                        if not orig_parent:
                            m = re.search(r'\bbl_parent_id\s*=\s*(?:[a-zA-Z0-9_.]+\s*\(\s*)?[\'\"]([^\'\"]+)[\'\"]', line_str)
                            if m:
                                orig_parent = m.group(1)
                except Exception:
                    continue
            if orig_cat and orig_parent:
                break
    except Exception:
        pass
    return orig_cat, orig_parent


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
        """记录面板的原始状态（基于源码类定义提取真实值，彻底免疫内存脏状态污染）"""
        from . import classifier

        # 0. 优先尝试从类对象自身固化的永久不可逆属性中读取
        pinned_cat = getattr(panel, "_m8_original_category", None)
        pinned_parent = getattr(panel, "_m8_original_parent_id", None)

        if panel in cls._snapshots:
            snap = cls._snapshots[panel]
            # 深度自愈：若发现快照已被脏值或大分类名称污染，立即通过源码自愈修复
            is_dirty = (
                snap.original_category in ("M8_HIDDEN", "NSUBHIDE") or
                classifier.is_category_tab_name(snap.original_category) or
                (snap.original_parent_id and snap.original_parent_id.startswith("M8_PT_HiddenPanel"))
            )
            if is_dirty:
                src_cat, src_parent = get_source_attributes(panel)
                if src_cat and not classifier.is_category_tab_name(src_cat):
                    snap.original_category = src_cat
                elif pinned_cat and not classifier.is_category_tab_name(pinned_cat):
                    snap.original_category = pinned_cat
                if src_parent is not None:
                    snap.original_parent_id = src_parent
                elif pinned_parent is not None:
                    snap.original_parent_id = pinned_parent
                elif snap.original_parent_id and snap.original_parent_id.startswith("M8_PT_HiddenPanel"):
                    snap.original_parent_id = None
            return snap

        src_cat, src_parent = get_source_attributes(panel)
        curr_cat = getattr(panel, "bl_category", "Misc")
        curr_parent = getattr(panel, "bl_parent_id", None)
        orig_order = getattr(panel, "bl_order", 0)

        # 优先顺序: 源码提取 > 类对象固化记忆 > 当前内存属性 (严禁大分类/隐藏标志渗透)
        if src_cat and not classifier.is_category_tab_name(src_cat):
            orig_cat = src_cat
        elif pinned_cat and not classifier.is_category_tab_name(pinned_cat):
            orig_cat = pinned_cat
        else:
            orig_cat = curr_cat

        if orig_cat in ("M8_HIDDEN", "NSUBHIDE") or classifier.is_category_tab_name(orig_cat):
            orig_cat = "Misc"

        if src_parent is not None:
            orig_parent = src_parent
        elif pinned_parent is not None:
            orig_parent = pinned_parent
        else:
            orig_parent = curr_parent
            if orig_parent and orig_parent.startswith("M8_PT_HiddenPanel"):
                orig_parent = None

        # 将真实原始属性不可逆地固化到类对象上，抵御一切快照清除与重载攻击
        if orig_cat not in ("M8_HIDDEN", "NSUBHIDE", "Misc") and not classifier.is_category_tab_name(orig_cat):
            try:
                setattr(panel, "_m8_original_category", orig_cat)
            except Exception:
                pass
        if orig_parent is None or not orig_parent.startswith("M8_PT_HiddenPanel"):
            try:
                setattr(panel, "_m8_original_parent_id", orig_parent)
            except Exception:
                pass

        snap = PanelSnapshot(orig_cat, orig_parent, orig_order)
        cls._snapshots[panel] = snap
        return snap

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
    def get_original_order(cls, panel: Type[bpy.types.Panel]) -> int:
        if panel in cls._snapshots:
            return cls._snapshots[panel].original_order
        return getattr(panel, "bl_order", 0)

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
    def _topological_sort(cls, panels: List[Type[bpy.types.Panel]], parent_map: Dict[Type[bpy.types.Panel], Optional[str]]) -> List[Type[bpy.types.Panel]]:
        """根据 parent_map 对面板进行严格的拓扑分代排序：父级必定先于子级"""
        unique_panels = list(dict.fromkeys(panels))
        # 兼容 bl_idname 与类名双重索引
        all_names = {getattr(p, "bl_idname", None) for p in unique_panels if getattr(p, "bl_idname", None)} | {getattr(p, "__name__", "") for p in unique_panels if getattr(p, "__name__", "")}

        sorted_result: List[Type[bpy.types.Panel]] = []
        current_gen = []
        for p in unique_panels:
            pid = parent_map.get(p)
            if not pid or pid not in all_names or pid.startswith("M8_PT_HiddenPanel"):
                current_gen.append(p)
        sorted_result.extend(current_gen)

        all_sorted_names = {getattr(p, "bl_idname", None) for p in current_gen if getattr(p, "bl_idname", None)} | {getattr(p, "__name__", "") for p in current_gen if getattr(p, "__name__", "")}
        while len(sorted_result) < len(unique_panels):
            next_gen = [
                p for p in unique_panels
                if p not in sorted_result and parent_map.get(p) in all_sorted_names
            ]
            if not next_gen:
                remaining = [p for p in unique_panels if p not in sorted_result]
                sorted_result.extend(remaining)
                break
            sorted_result.extend(next_gen)
            all_sorted_names |= {getattr(p, "bl_idname", None) for p in next_gen if getattr(p, "bl_idname", None)} | {getattr(p, "__name__", "") for p in next_gen if getattr(p, "__name__", "")}

        return sorted_result

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
                # 级联扩散：若父级需要还原，其所有子孙面板必须联动重新注册，确保父级重构后重新挂载子面板
                restore_set = set(panels_to_restore)
                queue = list(panels_to_restore)
                all_by_id = {getattr(p, "bl_idname", None): p for p in cls._snapshots if getattr(p, "bl_idname", None)}
                all_by_name = {getattr(p, "__name__", ""): p for p in cls._snapshots if getattr(p, "__name__", "")}

                child_map = {}
                for p, snap in cls._snapshots.items():
                    orig_p = snap.original_parent_id
                    if orig_p and not orig_p.startswith("M8_PT_HiddenPanel"):
                        parent_obj = all_by_id.get(orig_p) or all_by_name.get(orig_p)
                        if parent_obj:
                            child_map.setdefault(parent_obj, []).append(p)

                while queue:
                    curr = queue.pop(0)
                    for child in child_map.get(curr, []):
                        if child not in restore_set:
                            restore_set.add(child)
                            queue.append(child)
                            panels_to_restore.append(child)

                # 拓扑分代排序：注销基于当前 bl_parent_id 逆序，注册基于目标 original_parent_id 正序（父先子后）
                current_parents = {p: getattr(p, "bl_parent_id", None) for p in panels_to_restore}
                target_parents = {p: cls._snapshots[p].original_parent_id for p in panels_to_restore}

                ordered_unregister = cls._topological_sort(panels_to_restore, current_parents)
                ordered_register = cls._topological_sort(panels_to_restore, target_parents)

                # 逆序注销（子面板先注销，父面板后注销）
                for panel in reversed(ordered_unregister):
                    idname = getattr(panel, "bl_idname", None) or getattr(panel, "__name__", "")
                    if getattr(panel, "is_registered", False) or hasattr(bpy.types, idname) or hasattr(bpy.types, getattr(panel, "__name__", "")):
                        try:
                            bpy.utils.unregister_class(panel)
                        except Exception:
                            pass

                # 恢复属性并顺序注册（父面板先注册，子面板后注册）
                restored_count = 0
                failed_panels = []
                for panel in ordered_register:
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
                        failed_panels.append(panel)

                # 多轮拓扑补救重试机制：持续重试直至全部成功或收敛
                while failed_panels:
                    remaining_failed = []
                    registered_any = False
                    for panel in failed_panels:
                        try:
                            bpy.utils.register_class(panel)
                            restored_count += 1
                            registered_any = True
                        except Exception:
                            remaining_failed.append(panel)
                    if not registered_any or len(remaining_failed) == len(failed_panels):
                        for panel in remaining_failed:
                            print(f"[M8 NPanel] Warning registering restored panel {panel.__name__}")
                        break
                    failed_panels = remaining_failed

            cls._snapshots.clear()
            cls.is_active = False

            # 同步恢复 HardOps 与 BoxCutter 原始首选项
            try:
                from .core import sync_special_addon_preferences
                sync_special_addon_preferences("HardOps", "HardOps")
                sync_special_addon_preferences("BoxCutter", "BoxCutter")
            except Exception:
                pass

            # 安全兜底：清理所有可能残留挂载在隐藏面板上的孤儿面板
            for sub in bpy.types.Panel.__subclasses__():
                pid = getattr(sub, "bl_parent_id", None)
                if pid and str(pid).startswith("M8_PT_HiddenPanel"):
                    try:
                        delattr(sub, "bl_parent_id")
                        bpy.utils.unregister_class(sub)
                        bpy.utils.register_class(sub)
                    except Exception:
                        pass

            print(f"[M8 NPanel] Successfully restored {restored_count if panels_to_restore else 0} panels to default state.")
        finally:
            cls.is_restoring = False
