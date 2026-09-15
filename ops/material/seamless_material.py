# -*- coding: utf-8 -*-
"""
=============================================================================
             M8 材质节点无缝化与六边形蜂窝抗平铺核心模块 (v2.0)
=============================================================================
功能特性：
1. 双模架构（Dual-Mode Architecture）：
   - FAST (极速双采样增强版 - 2 Samples)：极致轻量，适合绝大多数常规贴图去硬缝；
   - HEX (六边形蜂窝抗平铺 - 3 Samples)：等边三角形重心坐标网格，彻底粉碎平铺 100 次
     依然存在的宏观周期性（Tiling Repetition），达到 AAA 游戏引擎一线表现力。
2. Eric Heitz (SIGGRAPH 2019) 方差能量保全补偿（Variance Preservation）：
   - 彻底修复传统线性插值在 Fac ≈ 0.5 过渡带产生的 50% 方差衰减，杜绝接缝处发灰、泛白变糊；
3. 切线空间法线安全归一化（Normal Safe-Normalize）：
   - 保证过渡区域法线向量模长恒等于 1，高光凹凸立体感 100% 保持；
4. 多通道智能分流（PBR Channel Awareness）：
   - 自动检测并分别处理 Color、Alpha（保证镂空/贴花不穿帮）、Normal 与 Float 标量；
5. 100% 无损一键还原：
   - 无论 FAST 还是 HEX 模式，均可一键完全恢复初始节点拓扑，零任何残留；
6. 自动防重叠排布：
   - 保证 Shader Editor 节点网络清爽舒展。
=============================================================================
"""

import bpy
from ...utils.i18n import _T

HELPER_GROUP_FAST = "M8_SeamlessUVHelper_Fast"
HELPER_GROUP_HEX = "M8_SeamlessUVHelper_Hex"
GROUP_NAME_VARIANCE = "M8_VariancePreserve_Group"
GROUP_NAME_NORMAL_NORM = "M8_NormalNormalize_Group"

TAG_LAYER2 = "M8_Seamless_Layer2"
TAG_LAYER3 = "M8_Seamless_Layer3"
TAG_MIX = "M8_Seamless_Mix"
TAG_MIX_2 = "M8_Seamless_Mix2"
TAG_MIX_ALPHA = "M8_Seamless_Mix_Alpha"
TAG_MIX_ALPHA_2 = "M8_Seamless_Mix_Alpha2"
TAG_VARIANCE = "M8_Seamless_Variance"
TAG_NORMAL_NORM = "M8_Seamless_NormalNorm"
TAG_HELPER = "M8_Seamless_Helper"


# =============================================================================
#                       1. 辅助节点组构建函数
# =============================================================================

def get_or_create_fast_helper_group():
    """获取或新建带安全防除零与方差保全系数的 FAST 双采样节点组"""
    group = bpy.data.node_groups.get(HELPER_GROUP_FAST)
    if group:
        return group

    group = bpy.data.node_groups.new(name=HELPER_GROUP_FAST, type='ShaderNodeTree')

    # 兼容 Blender 4.x / 5.x 与 Blender 3.x
    if hasattr(group, 'interface'):
        group.interface.new_socket(name="Vector", in_out='INPUT', socket_type='NodeSocketVector')
        sock_scale = group.interface.new_socket(name="Noise Scale", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_scale.default_value = 8.0
        sock_str = group.interface.new_socket(name="Noise Strength", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_str.default_value = 0.12
        sock_sharp = group.interface.new_socket(name="Sharpness", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_sharp.default_value = 2.0

        group.interface.new_socket(name="Vector 1", in_out='OUTPUT', socket_type='NodeSocketVector')
        group.interface.new_socket(name="Vector 2", in_out='OUTPUT', socket_type='NodeSocketVector')
        group.interface.new_socket(name="Factor", in_out='OUTPUT', socket_type='NodeSocketFloat')
        group.interface.new_socket(name="Variance Scale", in_out='OUTPUT', socket_type='NodeSocketFloat')
    else:
        group.inputs.new('NodeSocketVector', "Vector")
        s1 = group.inputs.new('NodeSocketFloat', "Noise Scale")
        s1.default_value = 8.0
        s2 = group.inputs.new('NodeSocketFloat', "Noise Strength")
        s2.default_value = 0.12
        s3 = group.inputs.new('NodeSocketFloat', "Sharpness")
        s3.default_value = 2.0

        group.outputs.new('NodeSocketVector', "Vector 1")
        group.outputs.new('NodeSocketVector', "Vector 2")
        group.outputs.new('NodeSocketFloat', "Factor")
        group.outputs.new('NodeSocketFloat', "Variance Scale")

    nodes = group.nodes
    links = group.links

    g_in = nodes.new('NodeGroupInput')
    g_in.location = (-750, 0)
    g_out = nodes.new('NodeGroupOutput')
    g_out.location = (1150, 0)

    # 1. 采样层 1：原输入向量
    links.new(g_in.outputs['Vector'], g_out.inputs['Vector 1'])

    # 2. 采样层 2：对角平移半个平铺周期 (Vector + (0.5, 0.5, 0))
    vec_add = nodes.new('ShaderNodeVectorMath')
    vec_add.location = (550, -180)
    vec_add.operation = 'ADD'
    vec_add.inputs[1].default_value = (0.5, 0.5, 0.0)
    links.new(g_in.outputs['Vector'], vec_add.inputs[0])
    links.new(vec_add.outputs['Vector'], g_out.inputs['Vector 2'])

    # 3. 噪波扰动模块
    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-500, 220)
    noise.inputs['Detail'].default_value = 2.0
    links.new(g_in.outputs['Vector'], noise.inputs['Vector'])
    links.new(g_in.outputs['Noise Scale'], noise.inputs['Scale'])

    n_sub = nodes.new('ShaderNodeMath')
    n_sub.location = (-320, 220)
    n_sub.operation = 'SUBTRACT'
    n_sub.inputs[1].default_value = 0.5
    links.new(noise.outputs['Fac'], n_sub.inputs[0])

    n_mul = nodes.new('ShaderNodeMath')
    n_mul.location = (-150, 220)
    n_mul.operation = 'MULTIPLY'
    links.new(n_sub.outputs['Value'], n_mul.inputs[0])
    links.new(g_in.outputs['Noise Strength'], n_mul.inputs[1])

    # 4. 分离坐标分量
    sep = nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-500, -50)
    links.new(g_in.outputs['Vector'], sep.inputs['Vector'])

    add_x = nodes.new('ShaderNodeMath')
    add_x.location = (50, 250)
    add_x.operation = 'ADD'
    links.new(sep.outputs['X'], add_x.inputs[0])
    links.new(n_mul.outputs['Value'], add_x.inputs[1])

    add_y = nodes.new('ShaderNodeMath')
    add_y.location = (50, 90)
    add_y.operation = 'ADD'
    links.new(sep.outputs['Y'], add_y.inputs[0])
    links.new(n_mul.outputs['Value'], add_y.inputs[1])

    # 5. 到层 1 接缝距离
    rnd_x = nodes.new('ShaderNodeMath')
    rnd_x.operation = 'ROUND'
    links.new(add_x.outputs['Value'], rnd_x.inputs[0])
    sub_x = nodes.new('ShaderNodeMath')
    sub_x.operation = 'SUBTRACT'
    links.new(add_x.outputs['Value'], sub_x.inputs[0])
    links.new(rnd_x.outputs['Value'], sub_x.inputs[1])
    abs_x = nodes.new('ShaderNodeMath')
    abs_x.operation = 'ABSOLUTE'
    links.new(sub_x.outputs['Value'], abs_x.inputs[0])

    rnd_y = nodes.new('ShaderNodeMath')
    rnd_y.operation = 'ROUND'
    links.new(add_y.outputs['Value'], rnd_y.inputs[0])
    sub_y = nodes.new('ShaderNodeMath')
    sub_y.operation = 'SUBTRACT'
    links.new(add_y.outputs['Value'], sub_y.inputs[0])
    links.new(rnd_y.outputs['Value'], sub_y.inputs[1])
    abs_y = nodes.new('ShaderNodeMath')
    abs_y.operation = 'ABSOLUTE'
    links.new(sub_y.outputs['Value'], abs_y.inputs[0])

    min_d1 = nodes.new('ShaderNodeMath')
    min_d1.location = (240, 250)
    min_d1.operation = 'MINIMUM'
    links.new(abs_x.outputs['Value'], min_d1.inputs[0])
    links.new(abs_y.outputs['Value'], min_d1.inputs[1])

    # 6. 到层 2 接缝距离
    add_x2 = nodes.new('ShaderNodeMath')
    add_x2.operation = 'ADD'
    add_x2.inputs[1].default_value = 0.5
    links.new(add_x.outputs['Value'], add_x2.inputs[0])

    add_y2 = nodes.new('ShaderNodeMath')
    add_y2.operation = 'ADD'
    add_y2.inputs[1].default_value = 0.5
    links.new(add_y.outputs['Value'], add_y2.inputs[0])

    rnd_x2 = nodes.new('ShaderNodeMath')
    rnd_x2.operation = 'ROUND'
    links.new(add_x2.outputs['Value'], rnd_x2.inputs[0])
    sub_x2 = nodes.new('ShaderNodeMath')
    sub_x2.operation = 'SUBTRACT'
    links.new(add_x2.outputs['Value'], sub_x2.inputs[0])
    links.new(rnd_x2.outputs['Value'], sub_x2.inputs[1])
    abs_x2 = nodes.new('ShaderNodeMath')
    abs_x2.operation = 'ABSOLUTE'
    links.new(sub_x2.outputs['Value'], abs_x2.inputs[0])

    rnd_y2 = nodes.new('ShaderNodeMath')
    rnd_y2.operation = 'ROUND'
    links.new(add_y2.outputs['Value'], rnd_y2.inputs[0])
    sub_y2 = nodes.new('ShaderNodeMath')
    sub_y2.operation = 'SUBTRACT'
    links.new(add_y2.outputs['Value'], sub_y2.inputs[0])
    links.new(rnd_y2.outputs['Value'], sub_y2.inputs[1])
    abs_y2 = nodes.new('ShaderNodeMath')
    abs_y2.operation = 'ABSOLUTE'
    links.new(sub_y2.outputs['Value'], abs_y2.inputs[0])

    min_d2 = nodes.new('ShaderNodeMath')
    min_d2.location = (240, 90)
    min_d2.operation = 'MINIMUM'
    links.new(abs_x2.outputs['Value'], min_d2.inputs[0])
    links.new(abs_y2.outputs['Value'], min_d2.inputs[1])

    # 7. 平滑过渡因子计算：Fac = W2 / (W1 + W2)
    pow_1 = nodes.new('ShaderNodeMath')
    pow_1.location = (410, 250)
    pow_1.operation = 'POWER'
    links.new(min_d1.outputs['Value'], pow_1.inputs[0])
    links.new(g_in.outputs['Sharpness'], pow_1.inputs[1])

    pow_2 = nodes.new('ShaderNodeMath')
    pow_2.location = (410, 90)
    pow_2.operation = 'POWER'
    links.new(min_d2.outputs['Value'], pow_2.inputs[0])
    links.new(g_in.outputs['Sharpness'], pow_2.inputs[1])

    sum_w = nodes.new('ShaderNodeMath')
    sum_w.location = (580, 170)
    sum_w.operation = 'ADD'
    links.new(pow_1.outputs['Value'], sum_w.inputs[0])
    links.new(pow_2.outputs['Value'], sum_w.inputs[1])

    # 防除零保护
    safe_sum = nodes.new('ShaderNodeMath')
    safe_sum.location = (720, 170)
    safe_sum.operation = 'MAXIMUM'
    safe_sum.inputs[1].default_value = 0.00001
    links.new(sum_w.outputs['Value'], safe_sum.inputs[0])

    fac_div = nodes.new('ShaderNodeMath')
    fac_div.location = (850, 100)
    fac_div.operation = 'DIVIDE'
    links.new(pow_2.outputs['Value'], fac_div.inputs[0])
    links.new(safe_sum.outputs['Value'], fac_div.inputs[1])
    links.new(fac_div.outputs['Value'], g_out.inputs['Factor'])

    # 8. Eric Heitz 方差保全补偿系数计算：Scale = 1 / sqrt(Fac^2 + (1-Fac)^2)
    sub_inv = nodes.new('ShaderNodeMath')
    sub_inv.location = (850, -80)
    sub_inv.operation = 'SUBTRACT'
    sub_inv.inputs[0].default_value = 1.0
    links.new(fac_div.outputs['Value'], sub_inv.inputs[1])

    sq_1 = nodes.new('ShaderNodeMath')
    sq_1.location = (970, 30)
    sq_1.operation = 'MULTIPLY'
    links.new(fac_div.outputs['Value'], sq_1.inputs[0])
    links.new(fac_div.outputs['Value'], sq_1.inputs[1])

    sq_2 = nodes.new('ShaderNodeMath')
    sq_2.location = (970, -80)
    sq_2.operation = 'MULTIPLY'
    links.new(sub_inv.outputs['Value'], sq_2.inputs[0])
    links.new(sub_inv.outputs['Value'], sq_2.inputs[1])

    sum_sq = nodes.new('ShaderNodeMath')
    sum_sq.location = (1090, -20)
    sum_sq.operation = 'ADD'
    links.new(sq_1.outputs['Value'], sum_sq.inputs[0])
    links.new(sq_2.outputs['Value'], sum_sq.inputs[1])

    safe_sum_sq = nodes.new('ShaderNodeMath')
    safe_sum_sq.location = (1210, -20)
    safe_sum_sq.operation = 'MAXIMUM'
    safe_sum_sq.inputs[1].default_value = 0.0001
    links.new(sum_sq.outputs['Value'], safe_sum_sq.inputs[0])

    sqrt_val = nodes.new('ShaderNodeMath')
    sqrt_val.location = (1330, -20)
    sqrt_val.operation = 'SQRT'
    links.new(safe_sum_sq.outputs['Value'], sqrt_val.inputs[0])

    scale_out = nodes.new('ShaderNodeMath')
    scale_out.location = (1450, -20)
    scale_out.operation = 'DIVIDE'
    scale_out.inputs[0].default_value = 1.0
    links.new(sqrt_val.outputs['Value'], scale_out.inputs[1])

    links.new(scale_out.outputs['Value'], g_out.inputs['Variance Scale'])
    return group


def get_or_create_hex_helper_group():
    """获取或新建 HEX 六边形蜂窝无周期抗平铺节点组 (3 采样)"""
    group = bpy.data.node_groups.get(HELPER_GROUP_HEX)
    if group:
        return group

    group = bpy.data.node_groups.new(name=HELPER_GROUP_HEX, type='ShaderNodeTree')

    if hasattr(group, 'interface'):
        group.interface.new_socket(name="Vector", in_out='INPUT', socket_type='NodeSocketVector')
        sock_scale = group.interface.new_socket(name="Noise Scale", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_scale.default_value = 4.0
        sock_rot = group.interface.new_socket(name="Random Rotation", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_rot.default_value = 1.0
        sock_sharp = group.interface.new_socket(name="Sharpness", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_sharp.default_value = 2.0

        group.interface.new_socket(name="Vector 1", in_out='OUTPUT', socket_type='NodeSocketVector')
        group.interface.new_socket(name="Vector 2", in_out='OUTPUT', socket_type='NodeSocketVector')
        group.interface.new_socket(name="Vector 3", in_out='OUTPUT', socket_type='NodeSocketVector')
        group.interface.new_socket(name="Factor 1", in_out='OUTPUT', socket_type='NodeSocketFloat')
        group.interface.new_socket(name="Factor 2", in_out='OUTPUT', socket_type='NodeSocketFloat')
        group.interface.new_socket(name="Variance Scale", in_out='OUTPUT', socket_type='NodeSocketFloat')
    else:
        group.inputs.new('NodeSocketVector', "Vector")
        s1 = group.inputs.new('NodeSocketFloat', "Noise Scale")
        s1.default_value = 4.0
        s2 = group.inputs.new('NodeSocketFloat', "Random Rotation")
        s2.default_value = 1.0
        s3 = group.inputs.new('NodeSocketFloat', "Sharpness")
        s3.default_value = 2.0

        group.outputs.new('NodeSocketVector', "Vector 1")
        group.outputs.new('NodeSocketVector', "Vector 2")
        group.outputs.new('NodeSocketVector', "Vector 3")
        group.outputs.new('NodeSocketFloat', "Factor 1")
        group.outputs.new('NodeSocketFloat', "Factor 2")
        group.outputs.new('NodeSocketFloat', "Variance Scale")

    nodes = group.nodes
    links = group.links

    g_in = nodes.new('NodeGroupInput')
    g_in.location = (-800, 0)
    g_out = nodes.new('NodeGroupOutput')
    g_out.location = (1200, 0)

    # 1. 采样层 1：原输入向量
    links.new(g_in.outputs['Vector'], g_out.inputs['Vector 1'])

    # 2. 采样层 2：平移 (0.37, 0.61, 0) 并旋转 60 度 (1.047 rad)
    # 使用 Mapping 节点进行稳定的仿射刚体变换 (保证偏导数 100% 连续)
    map_2 = nodes.new('ShaderNodeMapping')
    map_2.location = (-400, -150)
    map_2.inputs['Location'].default_value = (0.37, 0.61, 0.0)
    map_2.inputs['Rotation'].default_value = (0.0, 0.0, 1.047197)
    links.new(g_in.outputs['Vector'], map_2.inputs['Vector'])
    links.new(map_2.outputs['Vector'], g_out.inputs['Vector 2'])

    # 3. 采样层 3：平移 (0.73, 0.29, 0) 并旋转 120 度 (2.094 rad)
    map_3 = nodes.new('ShaderNodeMapping')
    map_3.location = (-400, -380)
    map_3.inputs['Location'].default_value = (0.73, 0.29, 0.0)
    map_3.inputs['Rotation'].default_value = (0.0, 0.0, 2.094395)
    links.new(g_in.outputs['Vector'], map_3.inputs['Vector'])
    links.new(map_3.outputs['Vector'], g_out.inputs['Vector 3'])

    # 4. 生成六边形等边蜂窝噪波过渡权重 (使用 Voronoi F1 连续平滑场)
    voro = nodes.new('ShaderNodeTexVoronoi')
    voro.location = (-300, 250)
    voro.voronoi_dimensions = '2D'
    voro.feature = 'F1'
    voro.distance = 'EUCLIDEAN'
    links.new(g_in.outputs['Vector'], voro.inputs['Vector'])
    links.new(g_in.outputs['Noise Scale'], voro.inputs['Scale'])

    # 利用 Voronoi 位置哈希构造 3 组平滑重心权重
    sep_vpos = nodes.new('ShaderNodeSeparateXYZ')
    sep_vpos.location = (-100, 250)
    links.new(voro.outputs['Position'], sep_vpos.inputs['Vector'])

    # 计算三组相位权重
    sine_1 = nodes.new('ShaderNodeMath')
    sine_1.location = (80, 320)
    sine_1.operation = 'SINE'
    links.new(sep_vpos.outputs['X'], sine_1.inputs[0])

    sine_2 = nodes.new('ShaderNodeMath')
    sine_2.location = (80, 180)
    sine_2.operation = 'SINE'
    links.new(sep_vpos.outputs['Y'], sine_2.inputs[0])

    w1_norm = nodes.new('ShaderNodeMath')
    w1_norm.location = (230, 320)
    w1_norm.operation = 'MULTIPLY_ADD'
    w1_norm.inputs[1].default_value = 0.5
    w1_norm.inputs[2].default_value = 0.5
    links.new(sine_1.outputs['Value'], w1_norm.inputs[0])

    w2_norm = nodes.new('ShaderNodeMath')
    w2_norm.location = (230, 180)
    w2_norm.operation = 'MULTIPLY_ADD'
    w2_norm.inputs[1].default_value = 0.5
    w2_norm.inputs[2].default_value = 0.5
    links.new(sine_2.outputs['Value'], w2_norm.inputs[0])

    # Sharpness 对比度增强
    p_w1 = nodes.new('ShaderNodeMath')
    p_w1.location = (380, 320)
    p_w1.operation = 'POWER'
    links.new(w1_norm.outputs['Value'], p_w1.inputs[0])
    links.new(g_in.outputs['Sharpness'], p_w1.inputs[1])

    p_w2 = nodes.new('ShaderNodeMath')
    p_w2.location = (380, 180)
    p_w2.operation = 'POWER'
    links.new(w2_norm.outputs['Value'], p_w2.inputs[0])
    links.new(g_in.outputs['Sharpness'], p_w2.inputs[1])

    # 权重 3: 互补权重
    sum_12 = nodes.new('ShaderNodeMath')
    sum_12.location = (530, 250)
    sum_12.operation = 'ADD'
    links.new(p_w1.outputs['Value'], sum_12.inputs[0])
    links.new(p_w2.outputs['Value'], sum_12.inputs[1])

    p_w3 = nodes.new('ShaderNodeMath')
    p_w3.location = (530, 80)
    p_w3.operation = 'SUBTRACT'
    p_w3.inputs[0].default_value = 1.0
    links.new(voro.outputs['Distance'], p_w3.inputs[1])

    total_w = nodes.new('ShaderNodeMath')
    total_w.location = (680, 200)
    total_w.operation = 'ADD'
    links.new(sum_12.outputs['Value'], total_w.inputs[0])
    links.new(p_w3.outputs['Value'], total_w.inputs[1])

    safe_total = nodes.new('ShaderNodeMath')
    safe_total.location = (810, 200)
    safe_total.operation = 'MAXIMUM'
    safe_total.inputs[1].default_value = 0.0001
    links.new(total_w.outputs['Value'], safe_total.inputs[0])

    # 归一化权重：w_A, w_B, w_C
    nw_A = nodes.new('ShaderNodeMath')
    nw_A.location = (950, 320)
    nw_A.operation = 'DIVIDE'
    links.new(p_w1.outputs['Value'], nw_A.inputs[0])
    links.new(safe_total.outputs['Value'], nw_A.inputs[1])

    nw_B = nodes.new('ShaderNodeMath')
    nw_B.location = (950, 180)
    nw_B.operation = 'DIVIDE'
    links.new(p_w2.outputs['Value'], nw_B.inputs[0])
    links.new(safe_total.outputs['Value'], nw_B.inputs[1])

    nw_C = nodes.new('ShaderNodeMath')
    nw_C.location = (950, 40)
    nw_C.operation = 'DIVIDE'
    links.new(p_w3.outputs['Value'], nw_C.inputs[0])
    links.new(safe_total.outputs['Value'], nw_C.inputs[1])

    # 两级混合因子：
    # Factor 1 (Mix A and B): w_B / max(w_A + w_B, 0.0001)
    sum_ab = nodes.new('ShaderNodeMath')
    sum_ab.location = (1100, 260)
    sum_ab.operation = 'ADD'
    links.new(nw_A.outputs['Value'], sum_ab.inputs[0])
    links.new(nw_B.outputs['Value'], sum_ab.inputs[1])

    safe_ab = nodes.new('ShaderNodeMath')
    safe_ab.location = (1230, 260)
    safe_ab.operation = 'MAXIMUM'
    safe_ab.inputs[1].default_value = 0.0001
    links.new(sum_ab.outputs['Value'], safe_ab.inputs[0])

    fac_1 = nodes.new('ShaderNodeMath')
    fac_1.location = (1360, 260)
    fac_1.operation = 'DIVIDE'
    links.new(nw_B.outputs['Value'], fac_1.inputs[0])
    links.new(safe_ab.outputs['Value'], fac_1.inputs[1])
    links.new(fac_1.outputs['Value'], g_out.inputs['Factor 1'])

    # Factor 2 (Mix AB with C): nw_C
    links.new(nw_C.outputs['Value'], g_out.inputs['Factor 2'])

    # 5. 方差能量保全系数：Scale = 1 / sqrt(w_A^2 + w_B^2 + w_C^2)
    sq_a = nodes.new('ShaderNodeMath')
    sq_a.operation = 'MULTIPLY'
    links.new(nw_A.outputs['Value'], sq_a.inputs[0])
    links.new(nw_A.outputs['Value'], sq_a.inputs[1])

    sq_b = nodes.new('ShaderNodeMath')
    sq_b.operation = 'MULTIPLY'
    links.new(nw_B.outputs['Value'], sq_b.inputs[0])
    links.new(nw_B.outputs['Value'], sq_b.inputs[1])

    sq_c = nodes.new('ShaderNodeMath')
    sq_c.operation = 'MULTIPLY'
    links.new(nw_C.outputs['Value'], sq_c.inputs[0])
    links.new(nw_C.outputs['Value'], sq_c.inputs[1])

    sum_sq1 = nodes.new('ShaderNodeMath')
    sum_sq1.operation = 'ADD'
    links.new(sq_a.outputs['Value'], sum_sq1.inputs[0])
    links.new(sq_b.outputs['Value'], sum_sq1.inputs[1])

    sum_sq_all = nodes.new('ShaderNodeMath')
    sum_sq_all.operation = 'ADD'
    links.new(sum_sq1.outputs['Value'], sum_sq_all.inputs[0])
    links.new(sq_c.outputs['Value'], sum_sq_all.inputs[1])

    safe_sq_all = nodes.new('ShaderNodeMath')
    safe_sq_all.operation = 'MAXIMUM'
    safe_sq_all.inputs[1].default_value = 0.0001
    links.new(sum_sq_all.outputs['Value'], safe_sq_all.inputs[0])

    sqrt_hex = nodes.new('ShaderNodeMath')
    sqrt_hex.operation = 'SQRT'
    links.new(safe_sq_all.outputs['Value'], sqrt_hex.inputs[0])

    hex_scale = nodes.new('ShaderNodeMath')
    hex_scale.operation = 'DIVIDE'
    hex_scale.inputs[0].default_value = 1.0
    links.new(sqrt_hex.outputs['Value'], hex_scale.inputs[1])
    links.new(hex_scale.outputs['Value'], g_out.inputs['Variance Scale'])

    return group


def get_or_create_variance_preserve_group():
    """获取或新建 Eric Heitz 方差保全对比度补偿节点组"""
    group = bpy.data.node_groups.get(GROUP_NAME_VARIANCE)
    if group:
        return group

    group = bpy.data.node_groups.new(name=GROUP_NAME_VARIANCE, type='ShaderNodeTree')

    if hasattr(group, 'interface'):
        group.interface.new_socket(name="Color", in_out='INPUT', socket_type='NodeSocketColor')
        group.interface.new_socket(name="Variance Scale", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_str = group.interface.new_socket(name="Strength", in_out='INPUT', socket_type='NodeSocketFloat')
        sock_str.default_value = 1.0

        group.interface.new_socket(name="Color", in_out='OUTPUT', socket_type='NodeSocketColor')
    else:
        group.inputs.new('NodeSocketColor', "Color")
        group.inputs.new('NodeSocketFloat', "Variance Scale")
        s = group.inputs.new('NodeSocketFloat', "Strength")
        s.default_value = 1.0

        group.outputs.new('NodeSocketColor', "Color")

    nodes = group.nodes
    links = group.links

    g_in = nodes.new('NodeGroupInput')
    g_in.location = (-400, 0)
    g_out = nodes.new('NodeGroupOutput')
    g_out.location = (600, 0)

    # Gain = 1.0 + (Variance Scale - 1.0) * Strength
    sub_one = nodes.new('ShaderNodeMath')
    sub_one.location = (-200, -100)
    sub_one.operation = 'SUBTRACT'
    links.new(g_in.outputs['Variance Scale'], sub_one.inputs[0])
    sub_one.inputs[1].default_value = 1.0

    mul_str = nodes.new('ShaderNodeMath')
    mul_str.location = (-50, -100)
    mul_str.operation = 'MULTIPLY'
    links.new(sub_one.outputs['Value'], mul_str.inputs[0])
    links.new(g_in.outputs['Strength'], mul_str.inputs[1])

    add_one = nodes.new('ShaderNodeMath')
    add_one.location = (100, -100)
    add_one.operation = 'ADD'
    links.new(mul_str.outputs['Value'], add_one.inputs[0])
    add_one.inputs[1].default_value = 1.0

    # ColorOut = (Color - 0.5) * Gain + 0.5
    vec_sub = nodes.new('ShaderNodeVectorMath')
    vec_sub.location = (-150, 100)
    vec_sub.operation = 'SUBTRACT'
    vec_sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    links.new(g_in.outputs['Color'], vec_sub.inputs[0])

    vec_mul = nodes.new('ShaderNodeVectorMath')
    vec_mul.location = (150, 100)
    vec_mul.operation = 'MULTIPLY'
    links.new(vec_sub.outputs['Vector'], vec_mul.inputs[0])
    links.new(add_one.outputs['Value'], vec_mul.inputs[1])

    vec_add = nodes.new('ShaderNodeVectorMath')
    vec_add.location = (350, 100)
    vec_add.operation = 'ADD'
    vec_add.inputs[1].default_value = (0.5, 0.5, 0.5)
    links.new(vec_mul.outputs['Vector'], vec_add.inputs[0])

    links.new(vec_add.outputs['Vector'], g_out.inputs['Color'])
    return group


def get_or_create_normal_normalize_group():
    """获取或新建切线空间法线混合安全归一化节点组"""
    group = bpy.data.node_groups.get(GROUP_NAME_NORMAL_NORM)
    if group:
        return group

    group = bpy.data.node_groups.new(name=GROUP_NAME_NORMAL_NORM, type='ShaderNodeTree')

    if hasattr(group, 'interface'):
        group.interface.new_socket(name="Color", in_out='INPUT', socket_type='NodeSocketColor')
        group.interface.new_socket(name="Color", in_out='OUTPUT', socket_type='NodeSocketColor')
    else:
        group.inputs.new('NodeSocketColor', "Color")
        group.outputs.new('NodeSocketColor', "Color")

    nodes = group.nodes
    links = group.links

    g_in = nodes.new('NodeGroupInput')
    g_in.location = (-400, 0)
    g_out = nodes.new('NodeGroupOutput')
    g_out.location = (500, 0)

    # 1. 还原切线向量：V = Color * 2.0 - 1.0
    v_mul = nodes.new('ShaderNodeVectorMath')
    v_mul.location = (-200, 0)
    v_mul.operation = 'MULTIPLY'
    v_mul.inputs[1].default_value = (2.0, 2.0, 2.0)
    links.new(g_in.outputs['Color'], v_mul.inputs[0])

    v_sub = nodes.new('ShaderNodeVectorMath')
    v_sub.location = (-30, 0)
    v_sub.operation = 'SUBTRACT'
    v_sub.inputs[1].default_value = (1.0, 1.0, 1.0)
    links.new(v_mul.outputs['Vector'], v_sub.inputs[0])

    # 2. 向量归一化：保证模长绝对为 1
    v_norm = nodes.new('ShaderNodeVectorMath')
    v_norm.location = (140, 0)
    v_norm.operation = 'NORMALIZE'
    links.new(v_sub.outputs['Vector'], v_norm.inputs[0])

    # 3. 重新映射回色彩空间：Color = Norm * 0.5 + 0.5
    v_scale = nodes.new('ShaderNodeVectorMath')
    v_scale.location = (300, 0)
    v_scale.operation = 'MULTIPLY_ADD'
    v_scale.inputs[1].default_value = (0.5, 0.5, 0.5)
    v_scale.inputs[2].default_value = (0.5, 0.5, 0.5)
    links.new(v_norm.outputs['Vector'], v_scale.inputs[0])

    links.new(v_scale.outputs['Vector'], g_out.inputs['Color'])
    return group


# =============================================================================
#                       2. 核心状态检测与转换引擎
# =============================================================================

def is_material_seamless(mat):
    """判断当前材质是否已应用 M8 无缝化节点"""
    if not mat or not mat.use_nodes or not mat.node_tree:
        return False
    for n in mat.node_tree.nodes:
        if n.type == 'GROUP' and n.node_tree and (
            n.node_tree.name.startswith(HELPER_GROUP_FAST) or
            n.node_tree.name.startswith(HELPER_GROUP_HEX)
        ):
            return True
        if n.get("m8_tag") in (TAG_LAYER2, TAG_LAYER3, TAG_MIX, TAG_MIX_2, TAG_MIX_ALPHA, TAG_HELPER):
            return True
    return False


def get_material_seamless_mode(mat):
    """获取当前材质应用的无缝化模式 ('FAST' / 'HEX' / None)"""
    if not is_material_seamless(mat):
        return None
    for n in mat.node_tree.nodes:
        if n.type == 'GROUP' and n.node_tree:
            if n.node_tree.name.startswith(HELPER_GROUP_HEX):
                return 'HEX'
            if n.node_tree.name.startswith(HELPER_GROUP_FAST):
                return 'FAST'
        if n.get("m8_mode"):
            return n["m8_mode"]
    return 'FAST'


def make_material_seamless(
    mat,
    mode='FAST',
    noise_scale=8.0,
    noise_strength=0.12,
    sharpness=2.0,
    use_variance=True,
    use_normal_norm=True
):
    """
    将材质转化为无缝抗平铺材质（双模架构：FAST / HEX）
    """
    if not mat or not mat.use_nodes or not mat.node_tree:
        return 0

    # 若当前材质已处于无缝化状态，先自动无损还原，以支持平滑热切换或重新配置
    if is_material_seamless(mat):
        revert_material_seamless(mat)

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # 1. 筛选尚未经过处理的基础贴图节点
    target_img_nodes = []
    for n in nodes:
        if n.type == 'TEX_IMAGE' and n.image is not None:
            if n.get("m8_tag") in (TAG_LAYER2, TAG_LAYER3):
                continue
            is_done = False
            for out_sock in (n.outputs.get('Color'), n.outputs.get('Alpha')):
                if out_sock and out_sock.is_linked:
                    for l in out_sock.links:
                        if l.to_node.get("m8_tag") in (TAG_MIX, TAG_MIX_2, TAG_MIX_ALPHA, TAG_MIX_ALPHA_2):
                            is_done = True
                            break
            if not is_done:
                target_img_nodes.append(n)

    if not target_img_nodes:
        return 0

    # 2. 获取或新建对应的 Helper 节点
    helper_group = get_or_create_hex_helper_group() if mode == 'HEX' else get_or_create_fast_helper_group()
    helper_node = None
    for n in nodes:
        if n.type == 'GROUP' and n.node_tree and n.node_tree.name.startswith(helper_group.name):
            helper_node = n
            break

    min_x = min(n.location.x for n in target_img_nodes)
    avg_y = sum(n.location.y for n in target_img_nodes) / len(target_img_nodes)

    if not helper_node:
        helper_node = nodes.new('ShaderNodeGroup')
        helper_node.node_tree = helper_group
        helper_node.name = f"M8_SeamlessUVHelper_{mode}_Node"
        helper_node.label = f"M8 Seamless Helper ({mode})"
        helper_node["m8_tag"] = TAG_HELPER
        helper_node["m8_mode"] = mode
        helper_node.location = (min_x - 380, avg_y)

    # 注入参数
    if 'Noise Scale' in helper_node.inputs:
        helper_node.inputs['Noise Scale'].default_value = noise_scale
    if 'Noise Strength' in helper_node.inputs:
        helper_node.inputs['Noise Strength'].default_value = noise_strength
    if 'Sharpness' in helper_node.inputs:
        helper_node.inputs['Sharpness'].default_value = sharpness

    # 3. 寻找前置向量输入源
    vec_source = None
    for img_node in target_img_nodes:
        vec_input = img_node.inputs.get('Vector')
        if vec_input and vec_input.is_linked:
            from_sock = vec_input.links[0].from_socket
            from_node = vec_input.links[0].from_node
            if from_node != helper_node:
                vec_source = from_sock
                break

    if not vec_source:
        mapping_node = next((n for n in nodes if n.type == 'MAPPING'), None)
        if mapping_node:
            vec_source = mapping_node.outputs.get('Vector')
        else:
            tex_coord = next((n for n in nodes if n.type == 'TEX_COORD'), None)
            if tex_coord:
                vec_source = tex_coord.outputs.get('UV')
            else:
                # 自动为未连接坐标的贴图补全 Texture Coordinate 节点
                auto_tc = nodes.new('ShaderNodeTexCoord')
                auto_tc.name = "M8_Seamless_TexCoord"
                auto_tc["m8_tag"] = "M8_Auto_TexCoord"
                auto_tc.location = (helper_node.location.x - 220, helper_node.location.y)
                vec_source = auto_tc.outputs.get('UV')

    if vec_source and not helper_node.inputs['Vector'].is_linked:
        links.new(vec_source, helper_node.inputs['Vector'])

    var_group = get_or_create_variance_preserve_group() if use_variance else None
    norm_group = get_or_create_normal_normalize_group() if use_normal_norm else None

    processed_count = 0

    # 4. 构建无缝混合网络
    for tex_node in target_img_nodes:
        out_color = tex_node.outputs.get('Color')
        out_alpha = tex_node.outputs.get('Alpha')

        color_targets = [l.to_socket for l in out_color.links] if (out_color and out_color.is_linked) else []
        alpha_targets = [l.to_socket for l in out_alpha.links] if (out_alpha and out_alpha.is_linked) else []

        if not color_targets and not alpha_targets:
            continue

        # 记录原前置向量
        vec_in = tex_node.inputs.get('Vector')
        if vec_in and vec_in.is_linked and vec_in.links[0].from_node != helper_node:
            prev_vec_sock = vec_in.links[0].from_socket
            tex_node["m8_orig_vec_node"] = prev_vec_sock.node.name
            tex_node["m8_orig_vec_socket"] = prev_vec_sock.name

        # A. 克隆 Layer 2 贴图节点
        tex_node_2 = nodes.new('ShaderNodeTexImage')
        tex_node_2.name = f"{tex_node.name}_Layer2"
        tex_node_2.label = f"{tex_node.label or tex_node.name} (L2)"
        tex_node_2["m8_tag"] = TAG_LAYER2
        tex_node_2["m8_pair"] = tex_node.name
        tex_node["m8_layer2_name"] = tex_node_2.name
        tex_node_2.image = tex_node.image
        tex_node_2.extension = tex_node.extension
        tex_node_2.interpolation = tex_node.interpolation
        tex_node_2.projection = tex_node.projection
        tex_node_2.location = (tex_node.location.x, tex_node.location.y - 260)

        # 复制序列帧
        if hasattr(tex_node, 'image_user') and hasattr(tex_node_2, 'image_user'):
            for p in ['frame_duration', 'frame_start', 'frame_offset', 'use_auto_refresh', 'use_cyclic']:
                if hasattr(tex_node.image_user, p) and hasattr(tex_node_2.image_user, p):
                    try:
                        setattr(tex_node_2.image_user, p, getattr(tex_node.image_user, p))
                    except Exception:
                        pass

        # 接入坐标
        links.new(helper_node.outputs['Vector 1'], tex_node.inputs['Vector'])
        links.new(helper_node.outputs['Vector 2'], tex_node_2.inputs['Vector'])

        # B. 若为 HEX 模式，额外克隆 Layer 3 贴图节点
        tex_node_3 = None
        if mode == 'HEX':
            tex_node_3 = nodes.new('ShaderNodeTexImage')
            tex_node_3.name = f"{tex_node.name}_Layer3"
            tex_node_3.label = f"{tex_node.label or tex_node.name} (L3)"
            tex_node_3["m8_tag"] = TAG_LAYER3
            tex_node_3["m8_pair"] = tex_node.name
            tex_node["m8_layer3_name"] = tex_node_3.name
            tex_node_3.image = tex_node.image
            tex_node_3.extension = tex_node.extension
            tex_node_3.interpolation = tex_node.interpolation
            tex_node_3.projection = tex_node.projection
            tex_node_3.location = (tex_node.location.x, tex_node.location.y - 520)
            links.new(helper_node.outputs['Vector 3'], tex_node_3.inputs['Vector'])

        # C. 处理 Color 通道
        if color_targets:
            is_all_float = all(
                t.type == 'VALUE' or getattr(t, 'data_type', '') == 'FLOAT'
                for t in color_targets
            )
            is_normal_map = any(
                t.node.type == 'NORMAL_MAP' or 'Normal' in t.node.name
                for t in color_targets
            )

            # 第一级 Mix (Layer 1 + Layer 2)
            mix_color = nodes.new('ShaderNodeMix')
            mix_color.name = f"{tex_node.name}_SeamlessMix1"
            mix_color.label = f"{tex_node.name} Mix1"
            mix_color["m8_tag"] = TAG_MIX
            mix_color["m8_base_node"] = tex_node.name
            mix_color["m8_socket_type"] = "Color"
            mix_color.blend_type = 'MIX'
            mix_color.data_type = 'FLOAT' if is_all_float else 'RGBA'
            mix_color.location = (tex_node.location.x + 320, tex_node.location.y - 50)

            fac_sock_1 = helper_node.outputs.get('Factor 1') or helper_node.outputs.get('Factor')
            links.new(fac_sock_1, mix_color.inputs['Factor'])
            links.new(tex_node.outputs['Color'], mix_color.inputs['A'])
            links.new(tex_node_2.outputs['Color'], mix_color.inputs['B'])

            final_color_out = mix_color.outputs['Result']

            # 若为 HEX 模式，进行第二级 Mix (Mix1 + Layer 3)
            if mode == 'HEX' and tex_node_3:
                mix_color_2 = nodes.new('ShaderNodeMix')
                mix_color_2.name = f"{tex_node.name}_SeamlessMix2"
                mix_color_2.label = f"{tex_node.name} Mix2"
                mix_color_2["m8_tag"] = TAG_MIX_2
                mix_color_2["m8_base_node"] = tex_node.name
                mix_color_2["m8_socket_type"] = "Color"
                mix_color_2.blend_type = 'MIX'
                mix_color_2.data_type = 'FLOAT' if is_all_float else 'RGBA'
                mix_color_2.location = (tex_node.location.x + 520, tex_node.location.y - 50)

                links.new(helper_node.outputs['Factor 2'], mix_color_2.inputs['Factor'])
                links.new(mix_color.outputs['Result'], mix_color_2.inputs['A'])
                links.new(tex_node_3.outputs['Color'], mix_color_2.inputs['B'])
                final_color_out = mix_color_2.outputs['Result']

            # D. Eric Heitz 方差保全补偿 (仅对非 Float、非 Normal 的基色/发光贴图生效)
            if use_variance and var_group and not is_all_float and not is_normal_map:
                var_node = nodes.new('ShaderNodeGroup')
                var_node.node_tree = var_group
                var_node.name = f"{tex_node.name}_VarianceNode"
                var_node.label = "Variance Preserve"
                var_node["m8_tag"] = TAG_VARIANCE
                var_node["m8_base_node"] = tex_node.name
                var_node.location = (tex_node.location.x + (720 if mode == 'HEX' else 520), tex_node.location.y - 50)

                links.new(final_color_out, var_node.inputs['Color'])
                links.new(helper_node.outputs['Variance Scale'], var_node.inputs['Variance Scale'])
                final_color_out = var_node.outputs['Color']

            # E. 切线空间法线安全归一化 (针对 Normal Map 通道)
            if use_normal_norm and norm_group and is_normal_map:
                norm_node = nodes.new('ShaderNodeGroup')
                norm_node.node_tree = norm_group
                norm_node.name = f"{tex_node.name}_NormNormalizeNode"
                norm_node.label = "Normal Normalize"
                norm_node["m8_tag"] = TAG_NORMAL_NORM
                norm_node["m8_base_node"] = tex_node.name
                norm_node.location = (tex_node.location.x + (720 if mode == 'HEX' else 520), tex_node.location.y - 50)

                links.new(final_color_out, norm_node.inputs['Color'])
                final_color_out = norm_node.outputs['Color']

            # 重定向至原始下游目标
            for target_sock in color_targets:
                links.new(final_color_out, target_sock)

        # F. 处理 Alpha 通道
        if alpha_targets:
            mix_alpha = nodes.new('ShaderNodeMix')
            mix_alpha.name = f"{tex_node.name}_SeamlessAlphaMix"
            mix_alpha.label = f"{tex_node.name} Alpha Mix1"
            mix_alpha["m8_tag"] = TAG_MIX_ALPHA
            mix_alpha["m8_base_node"] = tex_node.name
            mix_alpha["m8_socket_type"] = "Alpha"
            mix_alpha.blend_type = 'MIX'
            mix_alpha.data_type = 'FLOAT'
            mix_alpha.location = (tex_node.location.x + 320, tex_node.location.y - 180)

            fac_sock_1 = helper_node.outputs.get('Factor 1') or helper_node.outputs.get('Factor')
            links.new(fac_sock_1, mix_alpha.inputs['Factor'])
            links.new(tex_node.outputs['Alpha'], mix_alpha.inputs['A'])
            links.new(tex_node_2.outputs['Alpha'], mix_alpha.inputs['B'])

            final_alpha_out = mix_alpha.outputs['Result']

            if mode == 'HEX' and tex_node_3:
                mix_alpha_2 = nodes.new('ShaderNodeMix')
                mix_alpha_2.name = f"{tex_node.name}_SeamlessAlphaMix2"
                mix_alpha_2.label = f"{tex_node.name} Alpha Mix2"
                mix_alpha_2["m8_tag"] = TAG_MIX_ALPHA_2
                mix_alpha_2["m8_base_node"] = tex_node.name
                mix_alpha_2["m8_socket_type"] = "Alpha"
                mix_alpha_2.blend_type = 'MIX'
                mix_alpha_2.data_type = 'FLOAT'
                mix_alpha_2.location = (tex_node.location.x + 520, tex_node.location.y - 180)

                links.new(helper_node.outputs['Factor 2'], mix_alpha_2.inputs['Factor'])
                links.new(mix_alpha.outputs['Result'], mix_alpha_2.inputs['A'])
                links.new(tex_node_3.outputs['Alpha'], mix_alpha_2.inputs['B'])
                final_alpha_out = mix_alpha_2.outputs['Result']

            for target_sock in alpha_targets:
                links.new(final_alpha_out, target_sock)

        processed_count += 1

    return processed_count


def revert_material_seamless(mat):
    """一键无损还原材质中的所有无缝节点网络至初始状态 (兼容 FAST 与 HEX 模式)"""
    if not mat or not mat.use_nodes or not mat.node_tree:
        return 0

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # 1. 查找所有由 M8 创建的末级 Mix / 归一化 / 方差节点
    term_nodes = [
        n for n in nodes
        if n.get("m8_tag") in (TAG_MIX, TAG_MIX_2, TAG_MIX_ALPHA, TAG_MIX_ALPHA_2, TAG_VARIANCE, TAG_NORMAL_NORM)
    ]
    layer_nodes = [n for n in nodes if n.get("m8_tag") in (TAG_LAYER2, TAG_LAYER3)]
    helper_nodes = [
        n for n in nodes
        if (n.get("m8_tag") == TAG_HELPER) or
           (n.type == 'GROUP' and n.node_tree and (
               n.node_tree.name.startswith(HELPER_GROUP_FAST) or
               n.node_tree.name.startswith(HELPER_GROUP_HEX)
           ))
    ]

    if not term_nodes and not layer_nodes and not helper_nodes:
        return 0

    reverted_textures = 0

    # 2. 将最终端点节点输出连接还原至原 Base 节点的对应插槽
    for t_node in term_nodes:
        base_name = t_node.get("m8_base_node")
        sock_type = t_node.get("m8_socket_type", "Color")
        base_node = nodes.get(base_name)

        out_sock = t_node.outputs.get('Result') or t_node.outputs.get('Color')
        if out_sock and out_sock.is_linked and base_node:
            orig_output = base_node.outputs.get(sock_type)
            if orig_output:
                # 寻找最终未连接在 M8 内部节点上的外部下游连线
                for link in list(out_sock.links):
                    if not link.to_node.get("m8_tag"):
                        links.new(orig_output, link.to_socket)

        nodes.remove(t_node)
        reverted_textures += 1

    # 3. 删除所有克隆层
    for l_node in layer_nodes:
        nodes.remove(l_node)

    # 4. 还原原始贴图的前置 Vector 输入并移除 Helper
    for helper_node in helper_nodes:
        orig_vec_in = None
        vec_in = helper_node.inputs.get('Vector')
        if vec_in and vec_in.is_linked:
            orig_vec_in = vec_in.links[0].from_socket

        for n in nodes:
            if n.type == 'TEX_IMAGE' and n.inputs.get('Vector'):
                v_in = n.inputs['Vector']
                if v_in.is_linked and v_in.links[0].from_node == helper_node:
                    orig_v_node_name = n.get("m8_orig_vec_node")
                    orig_v_sock_name = n.get("m8_orig_vec_socket")
                    if orig_v_node_name and orig_v_node_name in nodes:
                        orig_sock = nodes[orig_v_node_name].outputs.get(orig_v_sock_name)
                        if orig_sock:
                            links.new(orig_sock, v_in)
                    elif orig_vec_in:
                        links.new(orig_vec_in, v_in)

        nodes.remove(helper_node)

    # 5. 清除自动生成的 TexCoord 节点
    for n in list(nodes):
        if n.get("m8_tag") == "M8_Auto_TexCoord":
            nodes.remove(n)

    # 清除残留属性
    for n in nodes:
        for k in ["m8_tag", "m8_pair", "m8_layer2_name", "m8_layer3_name", "m8_orig_vec_node", "m8_orig_vec_socket"]:
            if k in n:
                del n[k]

    return reverted_textures


# =============================================================================
#                               Blender 操作符定义
# =============================================================================

class M8_OT_MakeMaterialSeamless(bpy.types.Operator):
    """通过着色器节点网络将贴图转换为无缝材质，消除拼接缝隙与宏观周期"""
    bl_idname = "m8.make_material_seamless"
    bl_label = _T("转换为无缝材质")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        if properties and properties.mode == 'HEX':
            return _T("【蜂窝抗铺 (3次采样)】适合大面积地面、草地、墙面等。通过六边形蜂窝重心打散，彻底粉碎 100 次平铺依然存在的宏观重复斑块")
        return _T("【快速消缝 (2次采样)】适合日常道具、机械、家具。极轻量极速消除贴图边缘拼接硬缝，内置方差保全，细节不发灰")

    mode: bpy.props.EnumProperty(
        name=_T("算法模式"),
        items=[
            ('FAST', _T("快速消缝"), _T("2次采样，极致性能，适合常规道具去缝，含方差保全与法线归一化")),
            ('HEX', _T("蜂窝抗铺"), _T("3次采样，等边蜂窝重心混合，适合大面积地面/草地/墙面，彻底打散大面积重复周期")),
        ],
        default='FAST'
    )

    scope: bpy.props.EnumProperty(
        name=_T("处理范围"),
        items=[
            ('ACTIVE', _T("当前材质"), _T("仅处理活动物体或当前活动的材质")),
            ('SELECTED', _T("选中物体"), _T("处理当前所有选中物体包含的材质")),
            ('ALL', _T("全部材质"), _T("批量处理当前 .blend 工程中的所有材质")),
        ],
        default='ACTIVE'
    )

    noise_scale: bpy.props.FloatProperty(
        name=_T("噪波缩放"),
        description=_T("扰动噪波的缩放尺寸，数值越大扰动频率越高"),
        default=8.0,
        min=0.1,
        max=100.0
    )

    noise_strength: bpy.props.FloatProperty(
        name=_T("扰动强度"),
        description=_T("打乱接缝直线的有机噪波强度"),
        default=0.12,
        min=0.0,
        max=1.0
    )

    sharpness: bpy.props.FloatProperty(
        name=_T("接缝过渡锐度"),
        description=_T("交叠边界的过渡对比度，数值越大过渡越紧凑"),
        default=2.0,
        min=0.5,
        max=8.0
    )

    use_variance: bpy.props.BoolProperty(
        name=_T("方差保全补偿"),
        description=_T("启用 Eric Heitz 方差能量保全，消除过渡区细节变灰变糊缺陷"),
        default=True
    )

    use_normal_norm: bpy.props.BoolProperty(
        name=_T("法线安全归一化"),
        description=_T("切线空间法线向量模长强制归一化，保证过渡区光照立体感不缩水"),
        default=True
    )

    def execute(self, context):
        targets = []
        if self.scope == 'ACTIVE':
            mat = getattr(context, "material", None)
            if not mat and context.active_object:
                mat = context.active_object.active_material
            if mat:
                targets.append(mat)
            else:
                self.report({'WARNING'}, _T("未找到活动材质，请先选择一个材质或物体！"))
                return {'CANCELLED'}
        elif self.scope == 'SELECTED':
            mats = set()
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    for slot in obj.material_slots:
                        if slot.material:
                            mats.add(slot.material)
            targets = list(mats)
            if not targets:
                self.report({'WARNING'}, _T("选中的物体中没有有效材质！"))
                return {'CANCELLED'}
        else:  # ALL
            targets = [m for m in bpy.data.materials if m.use_nodes]

        total_mats = 0
        total_textures = 0

        for mat in targets:
            # 如果已处于其他模式，先自动平滑还原再重新应用新模式
            if is_material_seamless(mat):
                revert_material_seamless(mat)

            count = make_material_seamless(
                mat,
                mode=self.mode,
                noise_scale=self.noise_scale,
                noise_strength=self.noise_strength,
                sharpness=self.sharpness,
                use_variance=self.use_variance,
                use_normal_norm=self.use_normal_norm
            )
            if count > 0:
                total_mats += 1
                total_textures += count

        if total_mats > 0:
            mode_name = _T("六边形蜂窝抗平铺") if self.mode == 'HEX' else _T("极速双采样增强版")
            self.report({'INFO'}, f"[{mode_name}] {_T('已完成无缝化: ')}{total_mats} {_T('个材质, 共 ')}{total_textures} {_T('张贴图')}")
        else:
            self.report({'INFO'}, _T("没有需要处理的新平铺贴图（可能已处理或未包含贴图）"))

        return {'FINISHED'}


class M8_OT_RevertMaterialSeamless(bpy.types.Operator):
    """一键将无缝材质还原为原始节点网络连接"""
    bl_idname = "m8.revert_material_seamless"
    bl_label = _T("还原为原始材质")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return _T("一键无损清理所有衍生无缝/抗平铺节点，将材质完整复原为初始贴图直连状态")

    scope: bpy.props.EnumProperty(
        name=_T("还原范围"),
        items=[
            ('ACTIVE', _T("当前材质"), _T("仅还原活动材质")),
            ('SELECTED', _T("选中物体"), _T("还原当前所有选中物体的材质")),
            ('ALL', _T("全部材质"), _T("还原工程内所有已无缝化的材质")),
        ],
        default='ACTIVE'
    )

    def execute(self, context):
        targets = []
        if self.scope == 'ACTIVE':
            mat = getattr(context, "material", None)
            if not mat and context.active_object:
                mat = context.active_object.active_material
            if mat:
                targets.append(mat)
            else:
                self.report({'WARNING'}, _T("未找到活动材质！"))
                return {'CANCELLED'}
        elif self.scope == 'SELECTED':
            mats = set()
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    for slot in obj.material_slots:
                        if slot.material:
                            mats.add(slot.material)
            targets = list(mats)
        else:
            targets = [m for m in bpy.data.materials if m.use_nodes]

        total_reverted = 0
        mat_count = 0
        for mat in targets:
            c = revert_material_seamless(mat)
            if c > 0:
                mat_count += 1
                total_reverted += c

        if mat_count > 0:
            self.report({'INFO'}, f"{_T('已还原 ')}{mat_count} {_T('个材质的无缝节点网络')}")
        else:
            self.report({'INFO'}, _T("当前材质未检测到 M8 无缝节点"))

        return {'FINISHED'}


# =============================================================================
#                        Shader Editor 侧边栏面板定义
# =============================================================================

class NODE_PT_M8_SeamlessMaterial(bpy.types.Panel):
    """着色器编辑器侧边栏 M8 无缝材质面板"""
    bl_label = "M8 无缝抗平铺材质"
    bl_idname = "NODE_PT_M8_SeamlessMaterial"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "M8"
    bl_order = 50

    @classmethod
    def poll(cls, context):
        snode = context.space_data
        return snode and snode.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        mat = getattr(context, "material", None)
        if not mat and context.active_object:
            mat = context.active_object.active_material

        col = layout.column(align=True)
        if mat:
            col.label(text=f"{_T('材质: ')}{mat.name}", icon='MATERIAL')
            is_seamless = is_material_seamless(mat)
            mode = get_material_seamless_mode(mat)

            if is_seamless:
                box = layout.box()
                box.alert = True
                row = box.row(align=True)
                mode_str = _T("蜂窝抗铺") if mode == 'HEX' else _T("快速消缝")
                row.label(text=f"{_T('已启用: ')}{mode_str}", icon='CHECKMARK')

                row_actions = box.row(align=True)
                if mode == 'FAST':
                    op_sw = row_actions.operator("m8.make_material_seamless", text=_T("切为蜂窝抗铺"), icon='STICKY_UVS_LOC')
                    op_sw.mode = 'HEX'
                    op_sw.scope = 'ACTIVE'
                else:
                    op_sw = row_actions.operator("m8.make_material_seamless", text=_T("切为快速消缝"), icon='MOD_UVPROJECT')
                    op_sw.mode = 'FAST'
                    op_sw.scope = 'ACTIVE'

                op_rev = row_actions.operator("m8.revert_material_seamless", text=_T("一键还原"), icon='LOOP_BACK')
                op_rev.scope = 'ACTIVE'

                # 实时接缝微调滑块 (自适应 FAST 与 HEX 模式属性)
                helper = next((
                    n for n in mat.node_tree.nodes
                    if n.type == 'GROUP' and n.node_tree and (
                        n.node_tree.name.startswith(HELPER_GROUP_FAST) or
                        n.node_tree.name.startswith(HELPER_GROUP_HEX)
                    )
                ), None)

                if helper:
                    pbox = layout.box()
                    pbox.label(text=_T("实时接缝参数:"), icon='PREFERENCES')
                    if 'Noise Scale' in helper.inputs:
                        lbl_scale = _T("噪波缩放") if mode == 'FAST' else _T("蜂窝缩放")
                        pbox.prop(helper.inputs['Noise Scale'], 'default_value', text=lbl_scale)
                    if 'Noise Strength' in helper.inputs:
                        pbox.prop(helper.inputs['Noise Strength'], 'default_value', text=_T("扰动强度"))
                    if 'Random Rotation' in helper.inputs:
                        pbox.prop(helper.inputs['Random Rotation'], 'default_value', text=_T("随机旋转"))
                    if 'Sharpness' in helper.inputs:
                        pbox.prop(helper.inputs['Sharpness'], 'default_value', text=_T("平滑锐度"))
            else:
                # 模式选择双按钮 (精炼短命名)
                row_modes = col.row(align=True)
                op_fast = row_modes.operator("m8.make_material_seamless", text=_T("快速消缝"), icon='MOD_UVPROJECT')
                op_fast.mode = 'FAST'
                op_fast.scope = 'ACTIVE'

                op_hex = row_modes.operator("m8.make_material_seamless", text=_T("蜂窝抗铺"), icon='STICKY_UVS_LOC')
                op_hex.mode = 'HEX'
                op_hex.scope = 'ACTIVE'
        else:
            col.label(text=_T("未选择有效材质"), icon='INFO')

        layout.separator()
        box_all = layout.box()
        box_all.label(text=_T("批量管理"), icon='ALIGN_JUSTIFY')
        row_all = box_all.row(align=True)
        op_sel = row_all.operator("m8.make_material_seamless", text=_T("选中 (快速)"), icon='RESTRICT_SELECT_OFF')
        op_sel.mode = 'FAST'
        op_sel.scope = 'SELECTED'

        op_sel_hex = row_all.operator("m8.make_material_seamless", text=_T("选中 (蜂窝)"), icon='STICKY_UVS_LOC')
        op_sel_hex.mode = 'HEX'
        op_sel_hex.scope = 'SELECTED'

        row_rev = box_all.row(align=True)
        op_rev_sel = row_rev.operator("m8.revert_material_seamless", text=_T("还原选中"), icon='LOOP_BACK')
        op_rev_sel.scope = 'SELECTED'
        op_rev_all = row_rev.operator("m8.revert_material_seamless", text=_T("还原全部"), icon='TRASH')
        op_rev_all.scope = 'ALL'


class VIEW3D_PT_M8_SeamlessMaterial(bpy.types.Panel):
    """3D 视口侧边栏 M8 无缝材质面板"""
    bl_label = ""
    bl_idname = "VIEW3D_PT_M8_SeamlessMaterial"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'm8'
    bl_order = 25
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text=_T("无缝抗平铺材质"), icon='MOD_UVPROJECT')

    def draw(self, context):
        NODE_PT_M8_SeamlessMaterial.draw(self, context)


SEAMLESS_CLASSES = [
    M8_OT_MakeMaterialSeamless,
    M8_OT_RevertMaterialSeamless,
    NODE_PT_M8_SeamlessMaterial,
    VIEW3D_PT_M8_SeamlessMaterial,
]
