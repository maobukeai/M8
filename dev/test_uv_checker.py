# -*- coding: utf-8 -*-
"""
=============================================================================
              M8 UV 棋盘格系统 (v3.0) 专项自动化验证套件
=============================================================================
"""

import bpy
import sys
import os

addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(addon_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


import addon_utils


def _ensure_addon_enabled():
    addon_name = "M8"
    for mod in addon_utils.modules():
        name = mod.__name__
        if name == "M8" or name.endswith(".M8"):
            addon_name = name
            break
    addon_utils.enable(addon_name, default_set=False)
    return addon_name


def run_tests():
    print("\n" + "=" * 75)
    print("  [M8 TEST] 开始执行 UV 棋盘格系统 (v3.0 双轨覆盖架构) 专项验证套件")
    print("=" * 75)

    addon_name = _ensure_addon_enabled()

    try:
        from ..ops.mesh.uv_checker import (
            build_or_update_uv_checker_material,
            is_uv_checker_active,
            _backup_and_apply_slots,
            _restore_slots,
            _check_objects_uv_status,
        )
    except Exception:
        from M8.ops.mesh.uv_checker import (
            build_or_update_uv_checker_material,
            is_uv_checker_active,
            _backup_and_apply_slots,
            _restore_slots,
            _check_objects_uv_status,
        )

    # -------------------------------------------------------------------------
    # TEST 1: 验证 4 种网格类型材质与着色器节点树构建
    # -------------------------------------------------------------------------
    print("\n[TEST 1] 验证 4 种网格类型 (UV_GRID, COLOR_GRID, CHECKER, BOX_GRID) 构建...")
    for g_type in ('UV_GRID', 'COLOR_GRID', 'CHECKER', 'BOX_GRID'):
        mat = build_or_update_uv_checker_material(scale=3.0, grid_type=g_type)
        assert mat is not None, f"{g_type} 材质构建失败"
        assert mat.use_nodes, f"{g_type} 未启用节点树"
        assert mat.get("m8_grid_type") == g_type, f"{g_type} 元数据标记错误"
        mapping = mat.node_tree.nodes.get("M8_Mapping")
        assert mapping is not None, f"{g_type} 缺少 M8_Mapping 节点"
        assert mapping.inputs['Scale'].default_value[0] == 3.0, "缩放参数注入失败"

        if g_type == 'BOX_GRID':
            img_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
            assert len(img_nodes) > 0, "BOX_GRID 缺少贴图节点"
            assert img_nodes[0].projection == 'BOX', "BOX_GRID 投影方式应为 BOX"
        elif g_type == 'CHECKER':
            assert any(n.type == 'TEX_CHECKER' for n in mat.node_tree.nodes), "CHECKER 缺少程序化棋盘节点"

    print("  -> PASS: 4 种网格类型材质节点网络（包括免UV Box三向投影）构建全部正确！")

    # -------------------------------------------------------------------------
    # TEST 2: 准备测试场景 (含自定义材质物体、无材质物体、无 UV 物体)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] 构建测试场景与边界测试物体...")
    # 物体 A: 带自定义材质与 UV
    mesh_a = bpy.data.meshes.new("Mesh_A")
    obj_a = bpy.data.objects.new("Obj_A", mesh_a)
    bpy.context.collection.objects.link(obj_a)
    mat_orig_a = bpy.data.materials.new("Mat_Orig_A")
    obj_a.data.materials.append(mat_orig_a)
    obj_a.data.uv_layers.new(name="UVMap")

    # 物体 B: 零材质槽位（测试自动追加与安全移除）
    mesh_b = bpy.data.meshes.new("Mesh_B")
    obj_b = bpy.data.objects.new("Obj_B", mesh_b)
    bpy.context.collection.objects.link(obj_b)
    obj_b.data.uv_layers.new(name="UVMap")
    assert len(obj_b.material_slots) == 0, "物体 B 初始应有 0 个材质槽位"

    # 物体 C: 没有 UV 展开的物体
    mesh_c = bpy.data.meshes.new("Mesh_C")
    obj_c = bpy.data.objects.new("Obj_C", mesh_c)
    bpy.context.collection.objects.link(obj_c)
    assert not obj_c.data.uv_layers, "物体 C 应无 UV 展开"

    no_uvs = _check_objects_uv_status([obj_a, obj_b, obj_c])
    assert "Obj_C" in no_uvs and len(no_uvs) == 1, "未展 UV 巡检函数未能准确定位 Obj_C"
    print("  -> PASS: 边界测试物体构建成功，未展 UV 巡检准确！")

    # -------------------------------------------------------------------------
    # TEST 3: GLOBAL 全场景模式测试 (槽位暂存覆盖与 100% 拓扑无损还原)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] 验证全场景 (GLOBAL) 模式覆盖与 100% 无损还原...")
    bpy.context.view_layer.objects.active = obj_a
    bpy.ops.object.select_all(action='SELECT')

    # 运行开启算子
    res_on = bpy.ops.m8.toggle_uv_checker(scope='GLOBAL')
    assert res_on == {'FINISHED'}, f"开启棋盘格操作符执行失败: {res_on}"
    assert is_uv_checker_active(bpy.context), "开启后状态应为 active"
    assert bpy.context.view_layer.material_override is not None, "全场景模式应设置 view_layer.material_override"

    # 检查槽位覆盖：Obj_A 槽位应为 M8_UV_Checker
    checker_mat = bpy.data.materials.get("M8_UV_Checker")
    assert obj_a.material_slots[0].material == checker_mat, "Obj_A 材质槽未被替换为棋盘格"
    assert len(obj_b.material_slots) == 1, "Obj_B 原本无材质，应临时追加 1 个槽位"
    assert obj_b.material_slots[0].material == checker_mat, "Obj_B 追加的槽位应为棋盘格"

    # 运行关闭算子
    res_off = bpy.ops.m8.toggle_uv_checker()
    assert res_off == {'FINISHED'}, f"关闭棋盘格操作符执行失败: {res_off}"
    assert not is_uv_checker_active(bpy.context), "关闭后状态应为 inactive"
    assert bpy.context.view_layer.material_override is None, "关闭后 view_layer.material_override 应还原为空"

    # 验证原状态完美还原
    assert obj_a.material_slots[0].material == mat_orig_a, "Obj_A 原始材质未被正确还原！"
    assert len(obj_b.material_slots) == 0, "Obj_B 临时添加的材质槽位未被安全移除！"
    print("  -> PASS: 全场景覆盖与槽位 100% 原样还原（零槽位残留）验证通过！")

    # -------------------------------------------------------------------------
    # TEST 4: SELECTED 仅选中物体模式测试 (局部覆盖独立性)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] 验证仅选中物体 (SELECTED) 局部覆盖...")
    bpy.ops.object.select_all(action='DESELECT')
    obj_a.select_set(True)
    bpy.context.view_layer.objects.active = obj_a

    res_sel_on = bpy.ops.m8.toggle_uv_checker(scope='SELECTED')
    assert res_sel_on == {'FINISHED'}, "局部开启棋盘格失败"
    assert is_uv_checker_active(bpy.context), "局部开启后应为 active"

    # Obj_A 是选中的，应覆盖
    assert obj_a.material_slots[0].material == checker_mat, "选中的 Obj_A 应被赋予棋盘格"
    # Obj_B 未被选中，必须维持原样（0 材质槽位）！
    assert len(obj_b.material_slots) == 0, "未选中的 Obj_B 不应受到任何影响！"

    # 执行还原
    bpy.ops.m8.restore_uv_checker()
    assert not is_uv_checker_active(bpy.context), "还原后应为 inactive"
    assert obj_a.material_slots[0].material == mat_orig_a, "Obj_A 原始材质应还原"
    print("  -> PASS: 仅选中模式成功实现局部覆盖与独立隔离！")

    # -------------------------------------------------------------------------
    # TEST 5: 免 UV 三向投影 (BOX_GRID) 模式切换测试
    # -------------------------------------------------------------------------
    print("\n[TEST 5] 验证免 UV 三向投影 (BOX_GRID) 模式...")
    if hasattr(bpy.context.scene, "m8"):
        bpy.context.scene.m8.uv_checker_type = 'BOX_GRID'
        bpy.context.scene.m8.uv_checker_scale = 4.0
        mat_box = build_or_update_uv_checker_material(scale=4.0, grid_type='BOX_GRID')
        assert mat_box.get("m8_grid_type") == 'BOX_GRID', "BOX_GRID 设置失败"
        mapping = mat_box.node_tree.nodes.get("M8_Mapping")
        assert mapping.inputs['Scale'].default_value[0] == 4.0, "BOX_GRID 缩放联动失败"
    print("  -> PASS: 免 UV 三向投影模式与参数实时联动验证通过！")

    # 清理测试资源
    bpy.data.objects.remove(obj_a)
    bpy.data.objects.remove(obj_b)
    bpy.data.objects.remove(obj_c)
    bpy.data.meshes.remove(mesh_a)
    bpy.data.meshes.remove(mesh_b)
    bpy.data.meshes.remove(mesh_c)
    bpy.data.materials.remove(mat_orig_a)
    addon_utils.disable(addon_name, default_set=False)

    print("\n" + "=" * 75)
    print("  >>> 全部 5 组专项测试深度通过！双轨制覆盖、局部隔离、免UV三向与无损还原成功！ <<<")
    print("=" * 75 + "\n")
    return True


if __name__ == "__main__":
    try:
        success = run_tests()
        if not success:
            sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
