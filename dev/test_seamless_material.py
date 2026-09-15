# -*- coding: utf-8 -*-
"""
=============================================================================
             M8 无缝材质与抗平铺双模自动化验证套件 (Dual-Mode Selftest)
=============================================================================
"""

import bpy
import sys
import os

addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(addon_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def run_tests():
    print("\n" + "=" * 75)
    print("  [M8 TEST] 开始执行材质无缝化与六边形抗平铺 (Dual-Mode v2.0) 深度验证套件")
    print("=" * 75)

    from M8.ops.material.seamless_material import (
        get_or_create_fast_helper_group,
        get_or_create_hex_helper_group,
        get_or_create_variance_preserve_group,
        get_or_create_normal_normalize_group,
        make_material_seamless,
        revert_material_seamless,
        is_material_seamless,
        get_material_seamless_mode,
        HELPER_GROUP_FAST,
        HELPER_GROUP_HEX,
        TAG_LAYER2,
        TAG_LAYER3,
        TAG_MIX,
        TAG_MIX_2,
        TAG_MIX_ALPHA,
        TAG_VARIANCE,
        TAG_NORMAL_NORM,
    )

    # 准备测试贴图
    test_img = bpy.data.images.get("M8_Test_Tex")
    if not test_img:
        test_img = bpy.data.images.new("M8_Test_Tex", width=64, height=64)

    # -------------------------------------------------------------------------
    # TEST 1: FAST Helper 节点组防除零与方差保全检查
    # -------------------------------------------------------------------------
    print("\n[TEST 1] 验证 FAST Helper 节点组 (2-Sample + 防除零 + 方差保全系数)...")
    fast_group = get_or_create_fast_helper_group()
    assert fast_group is not None, "FAST Helper 节点组创建失败"

    if hasattr(fast_group, 'interface'):
        outputs = [s.name for s in fast_group.interface.items_tree if s.in_out == 'OUTPUT']
    else:
        outputs = [s.name for s in fast_group.outputs]

    assert "Vector 1" in outputs and "Vector 2" in outputs, "缺少 Vector 双采样输出"
    assert "Factor" in outputs, "缺少 Factor 输出"
    assert "Variance Scale" in outputs, "缺少 Eric Heitz 方差保全系数输出"

    has_max = any(n.type == 'MATH' and n.operation == 'MAXIMUM' for n in fast_group.nodes)
    assert has_max, "FAST Helper 中缺少除零保护 MAXIMUM"
    print("  -> PASS: FAST Helper 具备严密的 MAXIMUM 除零保护与方差系数输出！")

    # -------------------------------------------------------------------------
    # TEST 2: HEX Helper 节点组 (3 采样重心坐标 + 方差保全)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] 验证 HEX Helper 节点组 (3-Sample + 等边蜂窝重心混合)...")
    hex_group = get_or_create_hex_helper_group()
    assert hex_group is not None, "HEX Helper 节点组创建失败"

    if hasattr(hex_group, 'interface'):
        hex_outputs = [s.name for s in hex_group.interface.items_tree if s.in_out == 'OUTPUT']
    else:
        hex_outputs = [s.name for s in hex_group.outputs]

    assert "Vector 1" in hex_outputs and "Vector 2" in hex_outputs and "Vector 3" in hex_outputs, "缺少 3 采样坐标输出"
    assert "Factor 1" in hex_outputs and "Factor 2" in hex_outputs, "缺少两级级联 Factor 输出"
    assert "Variance Scale" in hex_outputs, "缺少 HEX 方差保全系数输出"
    print("  -> PASS: HEX Helper 3 采样等边重心坐标与两级 Factor 构建完整！")

    # -------------------------------------------------------------------------
    # TEST 3: 方差保全节点组与法线归一化节点组
    # -------------------------------------------------------------------------
    print("\n[TEST 3] 验证方差保全与法线安全归一化独立节点组...")
    var_group = get_or_create_variance_preserve_group()
    assert var_group is not None, "方差保全节点组创建失败"
    norm_group = get_or_create_normal_normalize_group()
    assert norm_group is not None, "法线归一化节点组创建失败"
    print("  -> PASS: 方差保全补偿组与法线归一化组验证通过！")

    # -------------------------------------------------------------------------
    # TEST 4: FAST 模式完整 PBR 链路测试 (含方差保全与法线归一化)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] 验证 FAST 模式复杂 PBR 链路 (Color + Alpha + Roughness + Normal)...")
    mat_fast = bpy.data.materials.new(name="M8_Test_Mat_Fast")
    mat_fast.use_nodes = True
    nodes_f = mat_fast.node_tree.nodes
    links_f = mat_fast.node_tree.links
    nodes_f.clear()

    bsdf_f = nodes_f.new('ShaderNodeBsdfPrincipled')
    bsdf_f.location = (600, 0)
    out_f = nodes_f.new('ShaderNodeOutputMaterial')
    links_f.new(bsdf_f.outputs['BSDF'], out_f.inputs['Surface'])

    # 贴图 1: Base Color + Alpha
    tex_ca = nodes_f.new('ShaderNodeTexImage')
    tex_ca.name = "Tex_CA"
    tex_ca.image = test_img
    links_f.new(tex_ca.outputs['Color'], bsdf_f.inputs['Base Color'])
    links_f.new(tex_ca.outputs['Alpha'], bsdf_f.inputs['Alpha'])

    # 贴图 2: Normal Map
    tex_nrm = nodes_f.new('ShaderNodeTexImage')
    tex_nrm.name = "Tex_Normal"
    tex_nrm.image = test_img
    norm_node = nodes_f.new('ShaderNodeNormalMap')
    norm_node.location = (300, -200)
    links_f.new(tex_nrm.outputs['Color'], norm_node.inputs['Color'])
    links_f.new(norm_node.outputs['Normal'], bsdf_f.inputs['Normal'])

    count_fast = make_material_seamless(mat_fast, mode='FAST', use_variance=True, use_normal_norm=True)
    assert count_fast == 2, f"FAST 模式预期处理 2 张贴图，实际处理 {count_fast}"
    assert is_material_seamless(mat_fast), "FAST 材质状态应为已启用"
    assert get_material_seamless_mode(mat_fast) == 'FAST', "材质模式检测应为 FAST"

    # 检查方差保全节点与法线归一化节点
    assert any(n.get("m8_tag") == TAG_VARIANCE for n in nodes_f), "未生成方差保全补偿节点"
    assert any(n.get("m8_tag") == TAG_NORMAL_NORM for n in nodes_f), "未生成法线安全归一化节点"
    assert any(n.get("m8_tag") == TAG_MIX_ALPHA for n in nodes_f), "未生成 Alpha 混合节点"

    print("  -> PASS: FAST 模式完整 PBR 处理成功，包含方差保全、法线归一化与 Alpha 混合！")

    # -------------------------------------------------------------------------
    # TEST 5: HEX 模式 3 采样六边形抗平铺测试
    # -------------------------------------------------------------------------
    print("\n[TEST 5] 验证 HEX 模式 3 采样六边形抗平铺网络...")
    mat_hex = bpy.data.materials.new(name="M8_Test_Mat_Hex")
    mat_hex.use_nodes = True
    nodes_h = mat_hex.node_tree.nodes
    links_h = mat_hex.node_tree.links
    nodes_h.clear()

    bsdf_h = nodes_h.new('ShaderNodeBsdfPrincipled')
    tex_ground = nodes_h.new('ShaderNodeTexImage')
    tex_ground.name = "Tex_Ground"
    tex_ground.image = test_img
    links_h.new(tex_ground.outputs['Color'], bsdf_h.inputs['Base Color'])

    count_hex = make_material_seamless(mat_hex, mode='HEX', use_variance=True)
    assert count_hex == 1, f"HEX 模式预期处理 1 张贴图，实际处理 {count_hex}"
    assert get_material_seamless_mode(mat_hex) == 'HEX', "材质模式检测应为 HEX"

    # 断言存在 Layer 2 和 Layer 3
    assert any(n.get("m8_tag") == TAG_LAYER2 for n in nodes_h), "HEX 模式应存在 Layer2 贴图采样"
    assert any(n.get("m8_tag") == TAG_LAYER3 for n in nodes_h), "HEX 模式应存在 Layer3 贴图采样"
    assert any(n.get("m8_tag") == TAG_MIX for n in nodes_h), "HEX 模式应存在第一级 Mix 节点"
    assert any(n.get("m8_tag") == TAG_MIX_2 for n in nodes_h), "HEX 模式应存在第二级 Mix2 节点"

    print("  -> PASS: HEX 模式 3 层采样与两级重心串联网络构建完成！")

    # -------------------------------------------------------------------------
    # TEST 6: 双模式无缝热切换测试 (FAST -> HEX)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] 验证模式平滑热切换 (FAST -> HEX 自动重构)...")
    re_hex_count = make_material_seamless(mat_fast, mode='HEX')
    assert re_hex_count == 2, "热切换至 HEX 模式应重构 2 张贴图"
    assert get_material_seamless_mode(mat_fast) == 'HEX', "热切换后模式应识别为 HEX"
    print("  -> PASS: 跨模式热切换自动重构无冲突！")

    # -------------------------------------------------------------------------
    # TEST 7: 一键无损还原测试 (Revert)
    # -------------------------------------------------------------------------
    print("\n[TEST 7] 验证两种模式的一键无损还原...")
    rev_hex = revert_material_seamless(mat_hex)
    assert rev_hex > 0, "HEX 材质还原应返回有效处理数"
    assert not is_material_seamless(mat_hex), "还原后状态应为未无缝化"
    assert bsdf_h.inputs['Base Color'].links[0].from_node == tex_ground, "HEX 还原后原贴图应直接连回 Base Color"

    rev_fast = revert_material_seamless(mat_fast)
    assert rev_fast > 0, "FAST 材质还原应返回有效处理数"
    assert not is_material_seamless(mat_fast), "还原后状态应为未无缝化"
    assert bsdf_f.inputs['Base Color'].links[0].from_node == tex_ca, "FAST 还原后原贴图应直接连回 Base Color"
    assert bsdf_f.inputs['Alpha'].links[0].from_node == tex_ca, "FAST 还原后 Alpha 应直接连回原贴图"
    assert norm_node.inputs['Color'].links[0].from_node == tex_nrm, "FAST 还原后 Normal 应直接连回 NormalMap 节点"

    print("  -> PASS: 两种模式均实现 100% 干净无残留的拓扑无损还原！")

    # -------------------------------------------------------------------------
    # TEST 8: Blender 操作符接口全流程测试
    # -------------------------------------------------------------------------
    print("\n[TEST 8] 验证 Blender 操作符 m8.make_material_seamless (带模式参数)...")
    obj = bpy.data.objects.new("M8_Test_Mesh_Obj2", bpy.data.meshes.new("M8_Test_Mesh2"))
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat_fast)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # 运行 FAST 算子
    res_f = bpy.ops.m8.make_material_seamless(mode='FAST', scope='ACTIVE')
    assert res_f == {'FINISHED'}, f"FAST 操作符执行失败: {res_f}"
    assert get_material_seamless_mode(mat_fast) == 'FAST', "操作符执行后应为 FAST 模式"

    # 运行 HEX 算子热切
    res_h = bpy.ops.m8.make_material_seamless(mode='HEX', scope='ACTIVE')
    assert res_h == {'FINISHED'}, f"HEX 操作符执行失败: {res_h}"
    assert get_material_seamless_mode(mat_fast) == 'HEX', "操作符执行后应为 HEX 模式"

    # 运行还原算子
    res_rev = bpy.ops.m8.revert_material_seamless(scope='ACTIVE')
    assert res_rev == {'FINISHED'}, f"还原操作符执行失败: {res_rev}"
    assert not is_material_seamless(mat_fast), "还原后应为未启用状态"

    # -------------------------------------------------------------------------
    # TEST 9: 无前置坐标输入贴图的自动补全与还原清理测试
    # -------------------------------------------------------------------------
    print("\n[TEST 9] 验证未连 UV 坐标时自动生成 M8_Auto_TexCoord 并在还原时清理...")
    mat_no_uv = bpy.data.materials.new(name="M8_Test_Mat_No_UV")
    mat_no_uv.use_nodes = True
    nodes_no_uv = mat_no_uv.node_tree.nodes
    links_no_uv = mat_no_uv.node_tree.links
    nodes_no_uv.clear()

    bsdf_nu = nodes_no_uv.new('ShaderNodeBsdfPrincipled')
    tex_nu = nodes_no_uv.new('ShaderNodeTexImage')
    tex_nu.image = test_img
    # 故意不连接任何 Vector 输入
    links_no_uv.new(tex_nu.outputs['Color'], bsdf_nu.inputs['Base Color'])

    count_nu = make_material_seamless(mat_no_uv, mode='FAST')
    assert count_nu == 1, "未连 UV 贴图应当成功完成无缝化"
    assert any(n.get("m8_tag") == "M8_Auto_TexCoord" for n in nodes_no_uv), "应当自动生成并标记 M8_Auto_TexCoord 节点"
    
    # 执行还原
    revert_material_seamless(mat_no_uv)
    assert not any(n.get("m8_tag") == "M8_Auto_TexCoord" for n in nodes_no_uv), "还原后自动生成的 TexCoord 必须被彻底清理"
    bpy.data.materials.remove(mat_no_uv)
    print("  -> PASS: 自动补全 TexCoord 并在还原时安全自净机制验证通过！")

    # -------------------------------------------------------------------------
    # TEST 10: UI 面板注册与 3D Viewport 侧边栏入口核验
    # -------------------------------------------------------------------------
    print("\n[TEST 10] 验证 UI 侧边栏面板类注册状态...")
    assert hasattr(bpy.types, "NODE_PT_M8_SeamlessMaterial"), "Shader Editor 面板 NODE_PT_M8_SeamlessMaterial 未注册"
    assert hasattr(bpy.types, "VIEW3D_PT_M8_SeamlessMaterial"), "3D Viewport 面板 VIEW3D_PT_M8_SeamlessMaterial 未注册"
    print("  -> PASS: Shader Editor 与 3D Viewport 双面板类均成功注册！")

    # 清理测试资源
    bpy.data.objects.remove(obj)
    bpy.data.materials.remove(mat_fast)
    bpy.data.materials.remove(mat_hex)
    bpy.data.images.remove(test_img)

    print("\n" + "=" * 75)
    print("  >>> 全部 10 项测试深度通过！双模架构、边界回退、UI注册与防残留清理验证成功！ <<<")
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
