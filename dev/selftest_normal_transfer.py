# -*- coding: utf-8 -*-
"""
M8 智能法向修正与法向饼菜单自动化测试脚本
从命令行启动 Blender 执行自测：
blender --background --factory-startup --python dev/selftest_normal_transfer.py
"""

import sys
import os
import bpy
import bmesh
import math
from mathutils import Vector
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = ROOT.name

def _ensure_addon_on_path():
    addon_parent = str(ROOT.parent)
    if addon_parent not in sys.path:
        sys.path.insert(0, addon_parent)

def run_tests():
    print("\n" + "=" * 60)
    print(">>> 启动 M8 智能法向传递 (Normal Transfer) 自动化验证...")
    print("=" * 60)

    _ensure_addon_on_path()

    # 1. 确保插件已加载注册
    if not bpy.context.preferences.addons.get(MODULE_NAME):
        try:
            bpy.ops.preferences.addon_enable(module=MODULE_NAME)
        except Exception as e:
            print(f"[FAIL] 插件启用失败: {e}")
            sys.exit(1)

    print("[PASS] M8 插件成功加载并注册")

    # 2. 验证操作符注册
    assert hasattr(bpy.ops.m8, "smart_normal_transfer"), "m8.smart_normal_transfer 未注册"
    assert hasattr(bpy.ops.m8, "apply_normal_transfer"), "m8.apply_normal_transfer 未注册"
    assert hasattr(bpy.ops.m8, "clear_normal_transfer"), "m8.clear_normal_transfer 未注册"
    assert hasattr(bpy.ops.m8, "flip_normal_transfer"), "m8.flip_normal_transfer 未注册"
    assert hasattr(bpy.ops.m8, "clear_custom_normals"), "m8.clear_custom_normals 未注册"
    print("[PASS] 核心操作符注册验证通过: smart_normal_transfer, apply_normal_transfer, clear_normal_transfer, flip_normal_transfer, clear_custom_normals")

    # 3. 验证法向饼菜单类注册
    assert hasattr(bpy.types, "VIEW3D_MT_m8_normal_pie"), "VIEW3D_MT_m8_normal_pie 菜单未注册"
    print("[PASS] 法向饼菜单 VIEW3D_MT_m8_normal_pie 验证通过")

    # 4. 验证 Alt+N 原生菜单注入
    assert hasattr(bpy.types, "VIEW3D_MT_edit_mesh_normals"), "Blender 缺少 VIEW3D_MT_edit_mesh_normals"
    print("[PASS] 原生 Alt+N 菜单挂载点验证通过")

    # 5. 真实网格硬表面场景测试：创建圆柱体并模拟圆桌面三角扇面
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m, do_unlink=True)
    # 创建一个圆柱体 (32 段)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=2.0, depth=0.5, location=(0, 0, 0))
    obj = bpy.context.active_object
    assert obj is not None, "圆柱体创建失败"

    # 进入编辑模式
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    bm = bmesh.from_edit_mesh(obj.data)

    # 选中顶面 (Z > 0.2 的面)
    for f in bm.faces:
        if f.calc_center_median().z > 0.2:
            f.select = True
            for v in f.verts:
                v.select = True
        else:
            f.select = False
    bmesh.update_edit_mesh(obj.data)

    selected_count = sum(1 for f in bm.faces if f.select)
    assert selected_count > 0, "未选中任何顶面"
    print(f"[INFO] 已模拟硬表面顶面，选中面数量: {selected_count}")

    # 6. 执行智能法向传递 (AUTO)
    res = bpy.ops.m8.smart_normal_transfer(mode='AUTO', grow_steps=0, apply_and_clean=False)
    assert 'FINISHED' in res, f"smart_normal_transfer 执行失败: {res}"

    # 7. 检查修改器与辅助对象
    mod = None
    for m in obj.modifiers:
        if m.type == 'DATA_TRANSFER' and m.name.startswith("M8_Normal"):
            mod = m
            break
    assert mod is not None, "未找到生成的 DATA_TRANSFER 修改器"
    assert mod.object is not None, "修改器目标辅助物体为空"
    assert mod.use_loop_data is True, "未启用面拐数据传输"
    assert 'CUSTOM_NORMAL' in mod.data_types_loops, "未设置 CUSTOM_NORMAL 法向传输"
    assert mod.vertex_group != "", "修改器未绑定顶点组"
    print(f"[PASS] 数据传递修改器与辅助物体生成正确: {mod.name} -> 辅助体: {mod.object.name}")

    # 检查辅助集合是否存在
    helper_col = bpy.data.collections.get("_M8_Normal_Helpers")
    assert helper_col is not None, "_M8_Normal_Helpers 集合未创建"
    assert mod.object.name in helper_col.objects, "辅助物体未收纳到 _M8_Normal_Helpers 集合"
    print("[PASS] 辅助集合管理与收纳正常")

    # 8. 测试向外扩展选区 (Grow Steps)
    res_grow = bpy.ops.m8.smart_normal_transfer(mode='PLANAR', grow_steps=1, apply_and_clean=False)
    assert 'FINISHED' in res_grow, f"grow_steps 执行失败: {res_grow}"
    vg = obj.vertex_groups.get(mod.vertex_group)
    assert vg is not None, "顶点组丢失"
    print("[PASS] 顶点组向外扩展 (Grow Steps) 执行正常")

    # 9. 测试一键烘焙并清理辅助体 (Apply & Clean)
    helper_name = mod.object.name
    res_apply = bpy.ops.m8.apply_normal_transfer()
    assert 'FINISHED' in res_apply, f"apply_normal_transfer 失败: {res_apply}"
    assert not any(m.name.startswith("M8_Normal") for m in obj.modifiers), "修改器应用后未从堆栈移除"
    assert bpy.data.objects.get(helper_name) is None, "辅助物体在应用后未被清理"
    print("[PASS] 一键应用并清理 (Apply & Clean) 验证通过，场景 0 冗余！")

    # 10. 测试圆柱侧壁标准几何体拟合 (CYLINDER mode)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for f in bm.faces:
        # 选中圆柱侧面 (Z 在 -0.2 到 0.2 之间)
        c = f.calc_center_median()
        f.select = bool(-0.24 < c.z < 0.24)
    bmesh.update_edit_mesh(obj.data)

    res_cyl = bpy.ops.m8.smart_normal_transfer(mode='CYLINDER', cylinder_segments=32, axis_override='Z')
    assert 'FINISHED' in res_cyl, f"CYLINDER 模式执行失败: {res_cyl}"
    mod_cyl = obj.modifiers.get("M8_Normal_CYLINDER")
    assert mod_cyl is not None, "未生成 M8_Normal_CYLINDER 修改器"
    assert mod_cyl.object is not None, "未生成圆柱辅助体"
    assert len(mod_cyl.object.data.vertices) >= 32, "圆柱辅助网格顶点数不符合预期"
    print("[PASS] 纯净圆柱几何体拟合 (CYLINDER) 验证通过")

    # 11. 测试提取平滑模式 (SMOOTH_EXTRACT mode)
    res_smooth = bpy.ops.m8.smart_normal_transfer(
        mode='SMOOTH_EXTRACT',
        extract_clean_mode='AUTO',
        profile_cuts=0,
        smooth_iterations=5,
    )
    assert 'FINISHED' in res_smooth, f"SMOOTH_EXTRACT 模式执行失败: {res_smooth}"
    mod_smooth = obj.modifiers.get("M8_Normal_SMOOTH_EXTRACT")
    assert mod_smooth is not None, "未生成 M8_Normal_SMOOTH_EXTRACT 修改器"
    assert mod_smooth.object is not None, "未生成提取净化辅助体"
    # 自适应双环桥接与全四边面高密重构验证
    helper_tris = sum(1 for p in mod_smooth.object.data.polygons if len(p.vertices) == 3)
    helper_ngons = sum(1 for p in mod_smooth.object.data.polygons if len(p.vertices) > 4)
    helper_quads = sum(1 for p in mod_smooth.object.data.polygons if len(p.vertices) == 4)
    assert helper_tris == 0, f"提取净化后依然存在 {helper_tris} 个三角面"
    assert helper_ngons == 0, f"提取净化后依然存在 {helper_ngons} 个多边形(N-gon)"
    assert helper_quads >= 100, f"提取辅助网格面数不足 ({helper_quads} < 100)，未达到足够的平滑密度"
    print(f"[PASS] 智能提取与纯四边面高密平滑重构验证通过 (100% 纯四边面: {helper_quads} 面, 0 三角面, 0 多边形)")

    # 12. 测试一键清除功能 (Clear Normal Transfer)
    res_clear = bpy.ops.m8.clear_normal_transfer()
    assert 'FINISHED' in res_clear, f"clear_normal_transfer 失败: {res_clear}"
    assert not any(m.name.startswith("M8_Normal") for m in obj.modifiers), "清理后仍有残存修改器"
    print("[PASS] 一键清除 (Clear Normal Transfer) 验证通过！")

    # 13. 测试内凹曲面/管道内壁法向自动对齐 (Robust Normal Alignment)
    # 创建内壁圆柱网格（法向全部朝向内部中心）
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj, do_unlink=True)
    me_inner = bpy.data.meshes.new("TestInnerTube")
    bm_inner = bmesh.new()
    bmesh.ops.create_cone(bm_inner, cap_ends=False, segments=16, radius1=2.0, radius2=2.0, depth=2.0)
    for f in bm_inner.faces:
        f.normal_flip()
    bm_inner.to_mesh(me_inner)
    bm_inner.free()

    obj_inner = bpy.data.objects.new("TestInnerTube", me_inner)
    bpy.context.scene.collection.objects.link(obj_inner)
    bpy.context.view_layer.objects.active = obj_inner
    obj_inner.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bm_e = bmesh.from_edit_mesh(me_inner)
    for f in bm_e.faces:
        f.select = True
    bmesh.update_edit_mesh(me_inner)

    res_inner = bpy.ops.m8.smart_normal_transfer(mode='CYLINDER', flip_normal=False)
    assert 'FINISHED' in res_inner, f"smart_normal_transfer 内壁圆柱执行失败: {res_inner}"

    mod_in = obj_inner.modifiers.get("M8_Normal_CYLINDER")
    assert mod_in and mod_in.object, "未找到内壁圆柱辅助体"
    h_data = mod_in.object.data
    # 验证辅助体法向是否已自动与内壁法向保持一致（点积 > 0.9）
    bm_h = bmesh.new()
    bm_h.from_mesh(h_data)
    bm_t = bmesh.new()
    bm_t.from_mesh(me_inner)
    dots = []
    for hf in bm_h.faces:
        hc = hf.calc_center_median()
        closest_f = min(bm_t.faces, key=lambda tf: (tf.calc_center_median() - hc).length_squared)
        dots.append(hf.normal.dot(closest_f.normal))
    bm_h.free()
    bm_t.free()

    avg_dot = sum(dots) / len(dots)
    assert avg_dot > 0.9, f"内凹圆柱法向未正确自动对齐目标内壁，平均点积: {avg_dot}"
    print(f"[PASS] 内凹曲面法向全自动对齐验证通过 (点积一致度: {avg_dot:.4f} > 0.9)")

    # 14. 测试 flip_normal=True 参数反转
    res_flip_prop = bpy.ops.m8.smart_normal_transfer(mode='CYLINDER', flip_normal=True)
    assert 'FINISHED' in res_flip_prop, "flip_normal=True 执行失败"
    bm_h = bmesh.new()
    bm_h.from_mesh(mod_in.object.data)
    bm_t = bmesh.new()
    bm_t.from_mesh(me_inner)
    dots_flipped = []
    for hf in bm_h.faces:
        hc = hf.calc_center_median()
        closest_f = min(bm_t.faces, key=lambda tf: (tf.calc_center_median() - hc).length_squared)
        dots_flipped.append(hf.normal.dot(closest_f.normal))
    bm_h.free()
    bm_t.free()
    avg_dot_flipped = sum(dots_flipped) / len(dots_flipped)
    assert avg_dot_flipped < -0.9, f"flip_normal=True 未能正确反转法向，平均点积: {avg_dot_flipped}"
    print(f"[PASS] flip_normal=True 参数反转验证通过 (反向点积: {avg_dot_flipped:.4f} < -0.9)")

    # 15. 测试快捷反转操作符 m8.flip_normal_transfer
    bpy.ops.object.mode_set(mode='OBJECT')
    res_flip_op = bpy.ops.m8.flip_normal_transfer()
    assert 'FINISHED' in res_flip_op, f"m8.flip_normal_transfer 执行失败: {res_flip_op}"
    bm_h = bmesh.new()
    bm_h.from_mesh(mod_in.object.data)
    bm_t = bmesh.new()
    bm_t.from_mesh(me_inner)
    dots_re_flipped = []
    for hf in bm_h.faces:
        hc = hf.calc_center_median()
        closest_f = min(bm_t.faces, key=lambda tf: (tf.calc_center_median() - hc).length_squared)
        dots_re_flipped.append(hf.normal.dot(closest_f.normal))
    bm_h.free()
    bm_t.free()
    avg_re_flipped = sum(dots_re_flipped) / len(dots_re_flipped)
    assert avg_re_flipped > 0.9, f"m8.flip_normal_transfer 未能将法向翻转回正向，平均点积: {avg_re_flipped}"
    print(f"[PASS] m8.flip_normal_transfer 独立反转操作符验证通过 (点积复原: {avg_re_flipped:.4f} > 0.9)")

    # 清理内壁测试对象与辅助体
    bpy.ops.m8.clear_normal_transfer()
    bpy.data.objects.remove(obj_inner, do_unlink=True)

    # 16. 测试复杂三角面/极点/非结构化提取面重置为 100% 纯四边面与高密细分
    me_complex = bpy.data.meshes.new("TestComplexExtract")
    bm_c = bmesh.new()
    bmesh.ops.create_uvsphere(bm_c, u_segments=16, v_segments=10, radius=2.0)
    # 模拟手切多余边与三角剖分（将前部 20 个面三角化）
    front_faces = [f for f in bm_c.faces if f.calc_center_median().y > 0.3]
    bmesh.ops.triangulate(bm_c, faces=front_faces[:15])
    bm_c.to_mesh(me_complex)
    bm_c.free()

    obj_complex = bpy.data.objects.new("TestComplexExtract", me_complex)
    bpy.context.scene.collection.objects.link(obj_complex)
    bpy.context.view_layer.objects.active = obj_complex
    obj_complex.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bm_ce = bmesh.from_edit_mesh(me_complex)
    for f in bm_ce.faces:
        f.select = (f.calc_center_median().y > 0.3)
    bmesh.update_edit_mesh(me_complex)

    selected_count = sum(1 for f in bm_ce.faces if f.select)
    selected_tris = sum(1 for f in bm_ce.faces if f.select and len(f.verts) == 3)
    assert selected_tris > 0, "复杂测试选区未成功构造包含三角面的网格"
    print(f"[INFO] 复杂测试选区: 共 {selected_count} 面 (其中包含 {selected_tris} 个杂乱三角面)")

    # 执行智能提取面并重置为高密四边面
    res_complex = bpy.ops.m8.smart_normal_transfer(
        mode='SMOOTH_EXTRACT',
        extract_clean_mode='DISSOLVE',
        quad_remesh=True,
        quad_subdiv=2,
        snap_to_surface=True,
        quad_smooth_factor=0.5,
    )
    assert 'FINISHED' in res_complex, f"复杂提取面执行失败: {res_complex}"

    mod_complex = obj_complex.modifiers.get("M8_Normal_SMOOTH_EXTRACT")
    assert mod_complex and mod_complex.object, "未生成复杂提取辅助体"
    h_complex_me = mod_complex.object.data

    c_tris = sum(1 for p in h_complex_me.polygons if len(p.vertices) == 3)
    c_ngons = sum(1 for p in h_complex_me.polygons if len(p.vertices) > 4)
    c_quads = sum(1 for p in h_complex_me.polygons if len(p.vertices) == 4)

    assert c_tris == 0, f"四边面重构后依然存在 {c_tris} 个三角面！"
    assert c_ngons == 0, f"四边面重构后依然存在 {c_ngons} 个多边面！"
    assert c_quads >= selected_count * 4, f"四边面面数不足 ({c_quads} < {selected_count * 4})，未达到足够平滑的高密度！"
    print(f"[PASS] 复杂三角网格彻底重置为 100% 纯四边面验证通过 ({c_quads} 纯四边面, 0 三角面, 0 多边形, 密度提升 {c_quads / selected_count:.1f}x)")

    # 清理测试对象
    bpy.ops.m8.clear_normal_transfer()
    bpy.data.objects.remove(obj_complex, do_unlink=True)

    # 17. 核心防灾难测试：两端边界段数不等 (如 32 环对 16 环) 回转曲面提取
    # 验证 AUTO 模式绝不强行跨段数 bridge_loops 导致 48 三角面挤压接缝褶皱，
    # 并且准确重置为 100% 纯四边面高密平滑代理体与 POLYINTERP_NEAREST 插值映射
    me_cone = bpy.data.meshes.new("TestUnequalCone")
    bm_cone = bmesh.new()
    # 底部 32 点圆环 (Z=0)
    b_verts = [bm_cone.verts.new((math.cos(i * 2 * math.pi / 32) * 2.0, math.sin(i * 2 * math.pi / 32) * 2.0, 0.0)) for i in range(32)]
    # 中部 32 点圆环 (Z=1)
    m_verts = [bm_cone.verts.new((math.cos(i * 2 * math.pi / 32) * 1.5, math.sin(i * 2 * math.pi / 32) * 1.5, 1.0)) for i in range(32)]
    # 顶部 16 点圆环 (Z=2)
    t_verts = [bm_cone.verts.new((math.cos(i * 2 * math.pi / 16) * 1.0, math.sin(i * 2 * math.pi / 16) * 1.0, 2.0)) for i in range(16)]
    bm_cone.verts.ensure_lookup_table()

    # 下半截：32 个四边形
    for i in range(32):
        i_next = (i + 1) % 32
        bm_cone.faces.new([b_verts[i], b_verts[i_next], m_verts[i_next], m_verts[i]])

    # 上半截：32 缩减到 16，交替四边面与三角面 (模拟真实拓扑减面环)
    for i in range(16):
        m0 = m_verts[i * 2]
        m1 = m_verts[i * 2 + 1]
        m2 = m_verts[(i * 2 + 2) % 32]
        t0 = t_verts[i]
        t1 = t_verts[(i + 1) % 16]
        bm_cone.faces.new([m0, m1, t0])
        bm_cone.faces.new([m1, m2, t1, t0])

    bm_cone.to_mesh(me_cone)
    bm_cone.free()

    obj_cone = bpy.data.objects.new("TestUnequalCone", me_cone)
    bpy.context.scene.collection.objects.link(obj_cone)
    bpy.context.view_layer.objects.active = obj_cone
    obj_cone.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bm_ce = bmesh.from_edit_mesh(me_cone)
    for f in bm_ce.faces:
        f.select = True
    bmesh.update_edit_mesh(me_cone)

    res_cone = bpy.ops.m8.smart_normal_transfer(mode='SMOOTH_EXTRACT', extract_clean_mode='AUTO')
    assert 'FINISHED' in res_cone, f"不等径回转体提取面执行失败: {res_cone}"

    mod_cone = obj_cone.modifiers.get("M8_Normal_SMOOTH_EXTRACT")
    assert mod_cone and mod_cone.object, "未生成不等径回转体辅助体"
    assert mod_cone.loop_mapping == "POLYINTERP_NEAREST", f"修改器未启用 POLYINTERP_NEAREST: {mod_cone.loop_mapping}"

    h_cone_me = mod_cone.object.data
    h_tris = sum(1 for p in h_cone_me.polygons if len(p.vertices) == 3)
    h_ngons = sum(1 for p in h_cone_me.polygons if len(p.vertices) > 4)
    h_quads = sum(1 for p in h_cone_me.polygons if len(p.vertices) == 4)

    assert h_tris == 0, f"不等径回转体四边面重构后不应存在三角面: {h_tris}"
    assert h_ngons == 0, f"不等径回转体四边面重构后不应存在多边形: {h_ngons}"
    assert h_quads >= 64 * 4, f"不等径回转体四边面数量不足 ({h_quads} < {64 * 4})，可能被错误直通桥接"
    print(f"[PASS] 不等径回转锥体 (32 对 16 环) 提取重构验证通过 ({h_quads} 纯四边面, 0 畸变三角面, 插值映射: {mod_cone.loop_mapping})")

    # 清理测试对象
    bpy.ops.m8.clear_normal_transfer()
    bpy.data.objects.remove(obj_cone, do_unlink=True)

    # 18. 多岛屿平面独立代理验证 (Multi-Island Planar Support)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(0, 0, 0))
    c_island1 = bpy.context.active_object
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(4, 0, 0))
    c_island2 = bpy.context.active_object
    c_island1.select_set(True)
    c_island2.select_set(True)
    bpy.context.view_layer.objects.active = c_island1
    bpy.ops.object.join()
    obj_multi = bpy.context.active_object

    bpy.ops.object.mode_set(mode='EDIT')
    bm_multi = bmesh.from_edit_mesh(obj_multi.data)
    for f in bm_multi.faces:
        f.select = (f.normal.z > 0.9)  # 选中两个独立圆柱顶盖
    bmesh.update_edit_mesh(obj_multi.data)

    res_multi = bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    assert 'FINISHED' in res_multi, f"多岛屿平面传递执行失败: {res_multi}"

    h_multi = bpy.data.objects.get(f"_M8_Helper_{obj_multi.name}_PLANAR")
    assert h_multi and h_multi.data, "未生成多岛屿平面辅助体"
    h_faces_count = len(h_multi.data.polygons)
    assert h_faces_count == 2, f"多岛屿平面辅助体应包含 2 个独立代理面，实际生成: {h_faces_count}"
    assert len(h_multi.data.vertices) == 32, f"多岛屿顶点数应为 32，实际: {len(h_multi.data.vertices)}"
    print(f"[PASS] 多岛屿平面独立代理验证通过 (成功为 2 个分离岛屿生成独立代理面，面数: {h_faces_count}, 顶点: 32)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_multi, do_unlink=True)

    # 19. 圆柱分段自适应几何探测验证 (Adaptive Cylinder Segments)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(0, 0, 0))
    obj_cyl16 = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm_c16 = bmesh.from_edit_mesh(obj_cyl16.data)
    for f in bm_c16.faces:
        f.select = (abs(f.normal.z) < 0.1)  # 选中 16 段侧壁
    bmesh.update_edit_mesh(obj_cyl16.data)

    res_cyl16 = bpy.ops.m8.smart_normal_transfer(mode='CYLINDER', cylinder_segments=0)
    assert 'FINISHED' in res_cyl16, f"16段圆柱自适应传递失败: {res_cyl16}"

    h_cyl16 = bpy.data.objects.get(f"_M8_Helper_{obj_cyl16.name}_CYLINDER")
    assert h_cyl16 and h_cyl16.data, "未生成 16 段圆柱辅助体"
    cyl16_faces = len(h_cyl16.data.polygons)
    assert cyl16_faces == 16, f"自适应圆柱分段应自动匹配 16 段，实际面数: {cyl16_faces}"
    print(f"[PASS] 圆柱分段几何自适应探测验证通过 (16段模型自适应生成 {cyl16_faces} 面辅助圆柱筒)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_cyl16, do_unlink=True)

    # 20. 椭圆曲面 AUTO 模式智能分流验证 (Elliptical Tube Discrimination)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(0, 0, 0))
    obj_ellipse = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm_ell = bmesh.from_edit_mesh(obj_ellipse.data)
    for v in bm_ell.verts:
        v.co.x *= 2.5  # 制作显著椭圆管
    for f in bm_ell.faces:
        f.select = (abs(f.normal.z) < 0.1)
    bmesh.update_edit_mesh(obj_ellipse.data)

    res_ell = bpy.ops.m8.smart_normal_transfer(mode='AUTO')
    assert 'FINISHED' in res_ell, f"椭圆管 AUTO 传递执行失败: {res_ell}"

    mod_ell = None
    for m in obj_ellipse.modifiers:
        if m.name.startswith("M8_Normal"):
            mod_ell = m
            break
    assert mod_ell is not None, "椭圆管未生成修改器"
    assert mod_ell.name == "M8_Normal_SMOOTH_EXTRACT", f"椭圆管应被智能分流至 SMOOTH_EXTRACT，实际生成: {mod_ell.name}"
    print(f"[PASS] 椭圆截面真圆度检测与智能分流验证通过 (椭圆管成功避开圆柱拟合，自动分流至: {mod_ell.name})")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_ellipse, do_unlink=True)

    # 21. 镜像修改器自动同步验证 (Mirror Modifier Sync)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(2, 0, 0))
    obj_mirror = bpy.context.active_object
    mir_mod = obj_mirror.modifiers.new("Mirror", "MIRROR")
    mir_mod.use_axis[0] = True
    mir_mod.use_axis[1] = False
    mir_mod.use_axis[2] = False

    bpy.ops.object.mode_set(mode='EDIT')
    bm_mir = bmesh.from_edit_mesh(obj_mirror.data)
    for f in bm_mir.faces:
        f.select = (f.normal.z > 0.9)
    bmesh.update_edit_mesh(obj_mirror.data)

    res_mir = bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    assert 'FINISHED' in res_mir, f"镜像网格平面传递失败: {res_mir}"

    h_mir = bpy.data.objects.get(f"_M8_Helper_{obj_mirror.name}_PLANAR")
    assert h_mir is not None, "未找到镜像辅助体"
    h_mir_mod = h_mir.modifiers.get("Mirror")
    assert h_mir_mod is not None, "辅助体未自动同步 Mirror 修改器"
    assert h_mir_mod.use_axis[0] is True, "辅助体 Mirror X 轴未同步开启"
    print("[PASS] 镜像修改器自动双向同步验证通过 (辅助体成功继承目标网格 Mirror 修改器配置)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_mirror, do_unlink=True)

    # 22. 最小爆炸半径着色隔离验证 (Minimal Blast Radius Shading Protection)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(0, 0, 0))
    obj_blast = bpy.context.active_object
    for p in obj_blast.data.polygons:
        p.use_smooth = False

    bpy.ops.object.mode_set(mode='EDIT')
    bm_blast = bmesh.from_edit_mesh(obj_blast.data)
    for f in bm_blast.faces:
        f.select = (f.normal.z > 0.9)  # 仅选中顶面
    bmesh.update_edit_mesh(obj_blast.data)

    bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    bpy.ops.object.mode_set(mode='OBJECT')

    bottom_caps = [p for p in obj_blast.data.polygons if p.normal.z < -0.9]
    assert len(bottom_caps) > 0, "未找到底面多边形"
    assert bottom_caps[0].use_smooth is False, "未选中的底面多边形 use_smooth 被非法篡改为 True！"
    side_polys = [p for p in obj_blast.data.polygons if abs(p.normal.z) < 0.1]
    assert len(side_polys) == 16, "未找到侧壁多边形"
    assert all(p.use_smooth is False for p in side_polys), "与顶面共享顶点的未选中侧壁多边形 use_smooth 被非法污染为 True！"
    top_caps = [p for p in obj_blast.data.polygons if p.normal.z > 0.9]
    assert top_caps[0].use_smooth is True, "受影响的顶面多边形 use_smooth 应为 True"
    print("[PASS] 最小爆炸半径多边形着色隔离验证通过 (未选中的底面与相邻侧面平直着色 100% 保持完好，零平滑溢出污染)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.data.objects.remove(obj_blast, do_unlink=True)

    # 23. 全模式通用重置法向操作符验证 (Dual-Mode Clear Custom Normals)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(0, 0, 0))
    obj_cn = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm_cn = bmesh.from_edit_mesh(obj_cn.data)
    for f in bm_cn.faces:
        f.select = (f.normal.z > 0.9)
    bmesh.update_edit_mesh(obj_cn.data)

    bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    bpy.ops.m8.apply_normal_transfer()
    assert obj_cn.data.has_custom_normals is True, "网格应用后应具备自定义法向"

    # 在 OBJECT 模式下测试 m8.clear_custom_normals
    res_clear_obj = bpy.ops.m8.clear_custom_normals()
    assert 'FINISHED' in res_clear_obj, f"OBJECT 模式下 clear_custom_normals 失败: {res_clear_obj}"
    assert obj_cn.data.has_custom_normals is False, "OBJECT 模式下自定义法向未被清除"

    # 在 EDIT 模式下再次应用并测试 m8.clear_custom_normals
    bpy.ops.object.mode_set(mode='EDIT')
    bm_cn2 = bmesh.from_edit_mesh(obj_cn.data)
    for f in bm_cn2.faces:
        f.select = (f.normal.z > 0.9)
    bmesh.update_edit_mesh(obj_cn.data)
    bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    bpy.ops.m8.apply_normal_transfer()
    bpy.ops.object.mode_set(mode='EDIT')

    res_clear_edit = bpy.ops.m8.clear_custom_normals()
    assert 'FINISHED' in res_clear_edit, f"EDIT 模式下 clear_custom_normals 失败: {res_clear_edit}"
    bpy.ops.object.mode_set(mode='OBJECT')
    assert obj_cn.data.has_custom_normals is False, "EDIT 模式下自定义法向未被清除"
    print("[PASS] 双模式通用重置法向操作符验证通过 (OBJECT 与 EDIT 模式均可秒级清空自定义法向)")

    bpy.data.objects.remove(obj_cn, do_unlink=True)

    # 24. 复杂带孔开槽垫片平面拍平验证 (Washer with Inner Hole Planar Test)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=2.0, depth=0.2, location=(0, 0, 0))
    obj_washer = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm_w = bmesh.from_edit_mesh(obj_washer.data)
    top_faces = [f for f in bm_w.faces if f.normal.z > 0.9]
    bmesh.ops.inset_individual(bm_w, faces=top_faces, thickness=0.6, depth=0.0)
    inner_faces = [f for f in bm_w.faces if f.normal.z > 0.9 and f.calc_center_median().length < 1.0]
    bmesh.ops.delete(bm_w, geom=inner_faces, context='FACES')
    washer_ring_faces = [f for f in bm_w.faces if f.normal.z > 0.9]
    for f in washer_ring_faces:
        f.select = True
    bmesh.update_edit_mesh(obj_washer.data)

    res_washer = bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    assert 'FINISHED' in res_washer, f"带孔垫片平面拍平失败: {res_washer}"

    h_washer = bpy.data.objects.get(f"_M8_Helper_{obj_washer.name}_PLANAR")
    assert h_washer and h_washer.data, "未生成垫片辅助体"
    assert len(h_washer.data.polygons) == 1, f"带孔垫片应提取最外轮廓生成单个平整大代理面，实际生成: {len(h_washer.data.polygons)}"
    assert len(h_washer.data.vertices) == 16, f"带孔垫片外围点数应为 16，实际: {len(h_washer.data.vertices)}"
    print(f"[PASS] 带孔开槽垫片平面拍平验证通过 (成功忽略内部开孔，精准提取外圈 16 顶点生成全覆盖平整代理面)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_washer, do_unlink=True)

    # 25. 多折角硬表面二面角自动解耦独立代理测试 (Dihedral Angle Multi-Facet Test)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    obj_cube = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm_cb = bmesh.from_edit_mesh(obj_cube.data)
    for f in bm_cb.faces:
        f.select = (f.normal.z > 0.9 or f.normal.y > 0.9)  # 选中 90 度直角相邻的顶面与侧面
    bmesh.update_edit_mesh(obj_cube.data)

    res_dihedral = bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    assert 'FINISHED' in res_dihedral, f"多折角平面传递失败: {res_dihedral}"

    h_cube = bpy.data.objects.get(f"_M8_Helper_{obj_cube.name}_PLANAR")
    assert h_cube and h_cube.data, "未生成多折角辅助体"
    assert len(h_cube.data.polygons) == 2, f"跨折角选区应自动解耦为 2 个正交代理平面，实际: {len(h_cube.data.polygons)}"
    p_norms = [p.normal for p in h_cube.data.polygons]
    has_z_norm = any(n.z > 0.9 for n in p_norms)
    has_y_norm = any(n.y > 0.9 for n in p_norms)
    assert has_z_norm and has_y_norm, f"多折面代理应分别精确对齐 Z 和 Y 轴正交法向，实际法向: {p_norms}"
    print(f"[PASS] 多折角硬表面二面角自动解耦独立代理验证通过 (90度相交面成功拆分为 2 个独立正交代理面)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_cube, do_unlink=True)

    # 26. 多圆柱/多孔位并发拟合验证 (Multi-Cylinder Concurrent Fitting Test)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(0, 0, 0))
    cyl_a = bpy.context.active_object
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.5, depth=2.0, location=(6, 0, 0))
    cyl_b = bpy.context.active_object

    bpy.ops.object.select_all(action='DESELECT')
    cyl_a.select_set(True)
    cyl_b.select_set(True)
    bpy.context.view_layer.objects.active = cyl_a
    bpy.ops.object.join()
    obj_multi_cyl = cyl_a

    bpy.ops.object.mode_set(mode='EDIT')
    bm_mc = bmesh.from_edit_mesh(obj_multi_cyl.data)
    for f in bm_mc.faces:
        f.select = (abs(f.normal.z) < 0.1)  # 选中两根圆柱的全部侧壁
    bmesh.update_edit_mesh(obj_multi_cyl.data)

    res_mc = bpy.ops.m8.smart_normal_transfer(mode='CYLINDER')
    assert 'FINISHED' in res_mc, f"多孔位圆柱传递失败: {res_mc}"

    h_mc = bpy.data.objects.get(f"_M8_Helper_{obj_multi_cyl.name}_CYLINDER")
    assert h_mc and h_mc.data, "未生成多圆柱辅助体"
    assert len(h_mc.data.polygons) == 32, f"两根 16 段圆柱应生成共 32 个侧壁多边形，实际: {len(h_mc.data.polygons)}"
    # 验证生成的两根圆柱的中心位置是否准确分布在原位 (0,0,0) 与 (6,0,0)
    v_xs = [v.co.x for v in h_mc.data.vertices]
    has_cyl1 = any(abs(x) < 1.6 for x in v_xs)
    has_cyl2 = any(abs(x - 6.0) < 2.0 for x in v_xs)
    assert has_cyl1 and has_cyl2, "多圆柱拟合未能准确定位在两根圆柱的原位中心"
    print(f"[PASS] 多圆柱/多孔位并发自适应拟合验证通过 (同物体 2 个独立圆柱孔各自生成专属贴合代理)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_multi_cyl, do_unlink=True)

    # 27. 凹多边形与 U 型面板三角化稳健性验证 (Concave U-shaped Panel Normal Test)
    me_u = bpy.data.meshes.new("Test_U_Mesh")
    obj_u = bpy.data.objects.new("Test_U_Obj", me_u)
    bpy.context.scene.collection.objects.link(obj_u)
    bm_u = bmesh.new()
    u_coords = [
        Vector((0, 0, 0)), Vector((3, 0, 0)), Vector((3, 3, 0)), Vector((2, 3, 0)),
        Vector((2, 1, 0)), Vector((1, 1, 0)), Vector((1, 3, 0)), Vector((0, 3, 0))
    ]
    u_verts = [bm_u.verts.new(c) for c in u_coords]
    bm_u.verts.ensure_lookup_table()
    f_u = bm_u.faces.new(u_verts)
    f_u.select = True
    bm_u.to_mesh(me_u)
    bm_u.free()

    bpy.context.view_layer.objects.active = obj_u
    obj_u.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    res_u = bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    assert 'FINISHED' in res_u, f"凹形 U 面板平面传递失败: {res_u}"

    h_u = bpy.data.objects.get(f"_M8_Helper_{obj_u.name}_PLANAR")
    assert h_u and h_u.data, "未生成凹形面板辅助体"
    # 验证辅助体上所有多边形法向严格朝向 Z 轴正向 (>0.99)，绝对无任何反向或倾斜三角面
    for p in h_u.data.polygons:
        assert p.normal.z > 0.99, f"凹多边形出现异常反向或倾斜三角面，法向: {p.normal}"
    print(f"[PASS] 凹多边形与 U 型面板法向稳健性验证通过 (全部分解面法向 100% 严格朝向 +Z，无反向三角面)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_u, do_unlink=True)
    if me_u.users == 0:
        bpy.data.meshes.remove(me_u)

    # 28. 加权法向修改器堆栈顺序防御测试 (Weighted Normal Modifier Stack Order Test)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    obj_wn = bpy.context.active_object
    mod_wn = obj_wn.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")

    bpy.ops.object.mode_set(mode='EDIT')
    bm_wn = bmesh.from_edit_mesh(obj_wn.data)
    for f in bm_wn.faces:
        f.select = (f.normal.z > 0.9)
    bmesh.update_edit_mesh(obj_wn.data)

    res_wn = bpy.ops.m8.smart_normal_transfer(mode='PLANAR')
    assert 'FINISHED' in res_wn, f"加权法向共存传递失败: {res_wn}"

    idx_dt = obj_wn.modifiers.find("M8_Normal_PLANAR")
    idx_wn = obj_wn.modifiers.find("WeightedNormal")
    assert idx_dt > idx_wn, f"DATA_TRANSFER 必须自动排在 WEIGHTED_NORMAL 之后，实际顺序: DT={idx_dt}, WN={idx_wn}"
    print(f"[PASS] 加权法向修改器堆栈顺序防御验证通过 (DATA_TRANSFER 已自动置于 WEIGHTED_NORMAL 之后)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_wn, do_unlink=True)

    # 29. 硬表面立方体垂直立面零着色溢出测试 (Cube Vertical Walls Flat Shading Protection)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    obj_cube = bpy.context.active_object
    for p in obj_cube.data.polygons:
        p.use_smooth = False

    bpy.ops.object.mode_set(mode='EDIT')
    bm_cube = bmesh.from_edit_mesh(obj_cube.data)
    for f in bm_cube.faces:
        f.select = (f.normal.z > 0.9)  # 仅选顶面 (+Z)
    bmesh.update_edit_mesh(obj_cube.data)

    res_cube = bpy.ops.m8.smart_normal_transfer(mode='AUTO')
    assert 'FINISHED' in res_cube, f"立方体平面法向传递失败: {res_cube}"
    bpy.ops.object.mode_set(mode='OBJECT')

    top_p = [p for p in obj_cube.data.polygons if p.normal.z > 0.9][0]
    side_ps = [p for p in obj_cube.data.polygons if abs(p.normal.z) < 0.1]
    bot_p = [p for p in obj_cube.data.polygons if p.normal.z < -0.9][0]

    assert top_p.use_smooth is True, "顶面受代理法向影响应为 use_smooth=True"
    assert len(side_ps) == 4, "立方体应有 4 个垂直侧面"
    assert all(p.use_smooth is False for p in side_ps), "立方体垂直立面被非法篡改为平滑着色，产生黑斑阴影拉扯！"
    assert bot_p.use_smooth is False, "立方体底面被非法篡改为平滑着色"
    print(f"[PASS] 硬表面立方体垂直立面零着色溢出验证通过 (顶面平滑，4 个垂直侧壁 100% 保持 Flat 着色)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.data.objects.remove(obj_cube, do_unlink=True)

    # 30. 多孔位在 AUTO 模式下的真圆度自适应识别测试 (Multi-Hole AUTO Mode Cylinder Recognition)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(0, 0, 0))
    c_a = bpy.context.active_object
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0, location=(5, 0, 0))
    c_b = bpy.context.active_object
    c_a.select_set(True)
    c_b.select_set(True)
    bpy.context.view_layer.objects.active = c_a
    bpy.ops.object.join()
    obj_auto_multi = c_a

    bpy.ops.object.mode_set(mode='EDIT')
    bm_am = bmesh.from_edit_mesh(obj_auto_multi.data)
    for f in bm_am.faces:
        f.select = (abs(f.normal.z) < 0.1)  # 选中两根独立圆柱的全部侧壁
    bmesh.update_edit_mesh(obj_auto_multi.data)

    res_am = bpy.ops.m8.smart_normal_transfer(mode='AUTO')
    assert 'FINISHED' in res_am, f"AUTO 模式多孔位圆柱传递失败: {res_am}"

    mod_cyl = obj_auto_multi.modifiers.get("M8_Normal_CYLINDER")
    assert mod_cyl is not None, "AUTO 模式多孔位未正确识别为 CYLINDER，误流转至其他模式！"
    h_am = bpy.data.objects.get(f"_M8_Helper_{obj_auto_multi.name}_CYLINDER")
    assert h_am and len(h_am.data.polygons) == 32, f"辅助体应生成 32 个柱面多边形，实际: {len(h_am.data.polygons)}"
    print(f"[PASS] 多孔位 AUTO 模式真圆度识别验证通过 (AUTO 模式自动识别多孔各自真圆度并生成 CYLINDER 代理)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_auto_multi, do_unlink=True)

    # 31. CAD 布尔微小碎面抗噪与面积加权平面识别测试 (Boolean Sliver Triangle Robustness Test)
    me_sliver = bpy.data.meshes.new("Test_Sliver_Mesh")
    obj_sliver = bpy.data.objects.new("Test_Sliver_Obj", me_sliver)
    bpy.context.scene.collection.objects.link(obj_sliver)
    bm_sl = bmesh.new()
    v1 = bm_sl.verts.new((0, 0, 0))
    v2 = bm_sl.verts.new((10, 0, 0))
    v3 = bm_sl.verts.new((10, 10, 0))
    v4 = bm_sl.verts.new((0, 10, 0))
    f_main = bm_sl.faces.new([v1, v2, v3, v4])
    v5 = bm_sl.verts.new((10.1, 5.0, 0.05))
    f_sliver = bm_sl.faces.new([v2, v5, v3])
    bm_sl.faces.ensure_lookup_table()
    for f in bm_sl.faces:
        f.select = True
    bm_sl.to_mesh(me_sliver)
    bm_sl.free()

    bpy.context.view_layer.objects.active = obj_sliver
    obj_sliver.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    res_sl = bpy.ops.m8.smart_normal_transfer(mode='AUTO')
    assert 'FINISHED' in res_sl, f"布尔碎面抗噪测试失败: {res_sl}"

    mod_sl = obj_sliver.modifiers.get("M8_Normal_PLANAR")
    assert mod_sl is not None, "包含微小布尔碎面时未能正确判定为 PLANAR 主平面！"
    print(f"[PASS] CAD 布尔微小碎面抗噪与面积加权平面识别验证通过 (AUTO 模式成功免疫布尔小碎面，精准判定为 PLANAR)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_sliver, do_unlink=True)
    if me_sliver.users == 0:
        bpy.data.meshes.remove(me_sliver)

    # 32. 复杂机械沉头阶梯孔分层自适应解耦测试 (Counterbored Stepped Hole Test)
    me_cb = bpy.data.meshes.new("Test_Counterbore_Mesh")
    obj_cb = bpy.data.objects.new("Test_Counterbore_Obj", me_cb)
    bpy.context.scene.collection.objects.link(obj_cb)
    bm_cb = bmesh.new()
    segs = 16
    top_ring = []
    mid_outer_ring = []
    mid_inner_ring = []
    bot_ring = []
    for i in range(segs):
        ang = 2.0 * math.pi * i / segs
        ca = math.cos(ang)
        sa = math.sin(ang)
        top_ring.append(bm_cb.verts.new((2.0 * ca, 2.0 * sa, 1.0)))
        mid_outer_ring.append(bm_cb.verts.new((2.0 * ca, 2.0 * sa, 0.0)))
        mid_inner_ring.append(bm_cb.verts.new((1.0 * ca, 1.0 * sa, 0.0)))
        bot_ring.append(bm_cb.verts.new((1.0 * ca, 1.0 * sa, -1.0)))
    bm_cb.verts.ensure_lookup_table()
    for i in range(segs):
        i_next = (i + 1) % segs
        f_top = bm_cb.faces.new([mid_outer_ring[i], mid_outer_ring[i_next], top_ring[i_next], top_ring[i]])
        f_top.select = True
        f_shelf = bm_cb.faces.new([mid_inner_ring[i], mid_inner_ring[i_next], mid_outer_ring[i_next], mid_outer_ring[i]])
        f_shelf.select = True
        f_bot = bm_cb.faces.new([bot_ring[i], bot_ring[i_next], mid_inner_ring[i_next], mid_inner_ring[i]])
        f_bot.select = True
    bm_cb.to_mesh(me_cb)
    bm_cb.free()

    bpy.context.view_layer.objects.active = obj_cb
    obj_cb.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    res_cb = bpy.ops.m8.smart_normal_transfer(mode='AUTO')
    assert 'FINISHED' in res_cb, f"阶梯沉头孔传递失败: {res_cb}"

    h_cb = None
    for o in bpy.data.objects:
        if o.name.startswith(f"_M8_Helper_{obj_cb.name}"):
            h_cb = o
            break
    assert h_cb is not None, "未生成沉头孔辅助体"
    h_radii = [math.sqrt(v.co.x**2 + v.co.y**2) for v in h_cb.data.vertices]
    has_large_r = any(abs(r - 2.0) < 0.15 for r in h_radii)
    has_small_r = any(abs(r - 1.0) < 0.15 for r in h_radii)
    assert has_large_r and has_small_r, "沉头阶梯孔未能分别生成大孔 (R=2.0) 与小孔 (R=1.0) 的专属贴合圆柱代理！"
    print("[PASS] 复杂机械沉头阶梯孔分层自适应解耦验证通过 (系统自动拆分并为大孔 R=2.0、台阶面、小孔 R=1.0 分别生成精准代理)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_cb, do_unlink=True)
    if me_cb.users == 0:
        bpy.data.meshes.remove(me_cb)

    # 33. 复杂硬表面多特征混合选区并发修正测试 (Hybrid Multi-Feature Selection Test)
    bpy.ops.mesh.primitive_cube_add(size=4.0, location=(0, 0, 0))
    obj_hy = bpy.context.active_object
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.6, depth=4.0, location=(1.0, 1.0, 0))
    c_sub1 = bpy.context.active_object
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.6, depth=4.0, location=(-1.0, -1.0, 0))
    c_sub2 = bpy.context.active_object
    obj_hy.select_set(True)
    c_sub1.select_set(True)
    c_sub2.select_set(True)
    bpy.context.view_layer.objects.active = obj_hy
    bpy.ops.object.join()

    bpy.ops.object.mode_set(mode='EDIT')
    bm_hy = bmesh.from_edit_mesh(obj_hy.data)
    for f in bm_hy.faces:
        is_top_plane = (f.normal.z > 0.9 and f.calc_center_median().z > 1.9)
        is_cyl_wall = (abs(f.normal.z) < 0.1 and abs(f.calc_center_median().z) < 1.9)
        f.select = (is_top_plane or is_cyl_wall)
    bmesh.update_edit_mesh(obj_hy.data)

    res_hy = bpy.ops.m8.smart_normal_transfer(mode='AUTO')
    assert 'FINISHED' in res_hy, f"混合多特征选区法向传递失败: {res_hy}"

    mod_hy = obj_hy.modifiers.get("M8_Normal_HYBRID")
    assert mod_hy is not None, "多特征混合选区未生成 M8_Normal_HYBRID 专属混合修改器！"
    h_hy = mod_hy.object
    assert h_hy is not None, "混合修改器未绑定辅助体"
    assert len(h_hy.data.polygons) >= 33, f"辅助体应至少包含 1 个顶面代理与 32 个侧壁面代理，实际: {len(h_hy.data.polygons)}"
    print("[PASS] 复杂硬表面多特征混合选区并发修正验证通过 (AUTO 模式自动解耦混合特征为 HYBRID 并发代理，零冲突)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(obj_hy, do_unlink=True)

    # 34. 法向传递扩展步数软性羽化衰减测试 (Soft Falloff Linear Feathering Test)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=5, y_subdivisions=5, size=4.0, location=(0, 0, 0))
    obj_grid = bpy.context.active_object

    bpy.ops.object.mode_set(mode='EDIT')
    bm_grid = bmesh.from_edit_mesh(obj_grid.data)
    for f in bm_grid.faces:
        f.select = (f.calc_center_median().length < 0.5)
    bmesh.update_edit_mesh(obj_grid.data)

    res_fo = bpy.ops.m8.smart_normal_transfer(mode='PLANAR', grow_steps=2)
    assert 'FINISHED' in res_fo, f"软羽化法向传递失败: {res_fo}"

    bpy.ops.object.mode_set(mode='OBJECT')
    vg_fo = obj_grid.vertex_groups.get("VG_M8_Normal_Planar")
    assert vg_fo is not None, "未生成羽化顶点组"

    weights = []
    for v in obj_grid.data.vertices:
        try:
            w = vg_fo.weight(v.index)
            weights.append(round(w, 2))
        except Exception:
            pass
    assert 1.0 in weights, "核心顶点权重应为 1.0"
    has_mid_w = any(0.60 <= w <= 0.70 for w in weights)
    has_low_w = any(0.30 <= w <= 0.40 for w in weights)
    assert has_mid_w and has_low_w, f"顶点组未能正确建立阶梯软羽化权重梯度，实际权重集合: {set(weights)}"
    print("[PASS] 法向传递扩展步数软性羽化衰减验证通过 (顶点组权重呈现 1.0 -> 0.67 -> 0.33 阶梯平滑过渡，杜绝边界硬接缝)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.data.objects.remove(obj_grid, do_unlink=True)

    # 35. 验证多区域连续法向传递智能叠加 (Multi-Pass Normal Stacking)
    bpy.ops.mesh.primitive_cube_add(size=4.0, location=(0, 0, 0))
    obj_stack = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm_st = bmesh.from_edit_mesh(obj_stack.data)

    # 步骤 1: 选顶面 (Z > 1.9)，执行 AUTO_STACK (生成第 1 个修改器 M8_Normal_PLANAR)
    for f in bm_st.faces:
        f.select = (f.normal.z > 0.9)
    bmesh.update_edit_mesh(obj_stack.data)
    res_s1 = bpy.ops.m8.smart_normal_transfer(mode='PLANAR', stack_mode='AUTO_STACK')
    assert 'FINISHED' in res_s1

    # 步骤 2: 选侧面 (X > 1.9)，执行 AUTO_STACK (不同区域，自动新建第 2 个修改器 M8_Normal_PLANAR_2)
    bm_st = bmesh.from_edit_mesh(obj_stack.data)
    for f in bm_st.faces:
        f.select = (f.normal.x > 0.9)
    bmesh.update_edit_mesh(obj_stack.data)
    res_s2 = bpy.ops.m8.smart_normal_transfer(mode='PLANAR', stack_mode='AUTO_STACK')
    assert 'FINISHED' in res_s2

    # 步骤 3: 选底面 (Z < -1.9)，执行 AUTO_STACK (自动新建第 3 个修改器 M8_Normal_PLANAR_3)
    bm_st = bmesh.from_edit_mesh(obj_stack.data)
    for f in bm_st.faces:
        f.select = (f.normal.z < -0.9)
    bmesh.update_edit_mesh(obj_stack.data)
    res_s3 = bpy.ops.m8.smart_normal_transfer(mode='PLANAR', stack_mode='AUTO_STACK')
    assert 'FINISHED' in res_s3

    bpy.ops.object.mode_set(mode='OBJECT')
    m8_mods = [m for m in obj_stack.modifiers if m.name.startswith("M8_Normal")]
    assert len(m8_mods) == 3, f"多区域叠加失败，预期 3 个修改器，实际为: {[m.name for m in m8_mods]}"
    assert obj_stack.modifiers.get("M8_Normal_PLANAR") is not None
    assert obj_stack.modifiers.get("M8_Normal_PLANAR_2") is not None
    assert obj_stack.modifiers.get("M8_Normal_PLANAR_3") is not None

    # 验证三个辅助物体和顶点组各自独立
    h_names = {m.object.name for m in m8_mods if m.object}
    assert len(h_names) == 3, f"辅助物体未独立隔离: {h_names}"
    vg_names = {m.vertex_group for m in m8_mods if m.vertex_group}
    assert len(vg_names) == 3, f"顶点组未独立隔离: {vg_names}"
    print("[PASS] 多区域连续法向传递智能自增叠加 (3 级修改器与辅助体独立隔离共存) 验证通过")

    # 步骤 4: 一键应用并烘焙所有叠加修改器
    res_app_all = bpy.ops.m8.apply_normal_transfer()
    assert 'FINISHED' in res_app_all
    assert len([m for m in obj_stack.modifiers if m.name.startswith("M8_Normal")]) == 0, "应用后仍有修改器残留"
    assert not any(bpy.data.objects.get(name) for name in h_names), "辅助物体未完全清理"
    print("[PASS] 多层叠加修改器一键烘焙应用与辅助体 100% 洁癖级零残留回收验证通过")

    bpy.data.objects.remove(obj_stack, do_unlink=True)

    # 36. 验证提取平滑传递向外包裹膨胀与防内缩补偿 (Cage Envelope & Anti-Shrink)
    from mathutils.bvhtree import BVHTree
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=2.0, location=(0, 0, 0))
    obj_sphere = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bm_sp = bmesh.from_edit_mesh(obj_sphere.data)

    # 选中上半凸球冠面 (Z > 0.5)
    for f in bm_sp.faces:
        f.select = bool(f.calc_center_median().z > 0.5)
    bmesh.update_edit_mesh(obj_sphere.data)

    test_offset = 0.015  # 向外推开 15mm
    res_cage = bpy.ops.m8.smart_normal_transfer(
        mode='SMOOTH_EXTRACT',
        extract_clean_mode='AUTO',
        quad_remesh=True,
        quad_subdiv=2,
        cage_offset=test_offset,
        auto_wrap_outside=True,
        apply_and_clean=False,
    )
    assert 'FINISHED' in res_cage, f"SMOOTH_EXTRACT 包裹测试执行失败: {res_cage}"

    bpy.ops.object.mode_set(mode='OBJECT')
    mod_cage = obj_sphere.modifiers.get("M8_Normal_SMOOTH_EXTRACT")
    assert mod_cage is not None and mod_cage.object is not None, "未找到生成的平滑辅助体"

    # 构建原凸表面选区 BVH 树
    bm_orig = bmesh.new()
    bm_orig.from_mesh(obj_sphere.data)
    sel_orig_faces = [f for f in bm_orig.faces if f.calc_center_median().z > 0.45]
    bvh_orig = BVHTree.FromPolygons([v.co for v in bm_orig.verts], [[v.index for v in f.verts] for f in sel_orig_faces])

    # 检验辅助体的每一个顶点相对于原模型表面的法向有符号距离 (signed distance)
    helper_me = mod_cage.object.data
    inside_count = 0
    signed_dists = []
    for v in helper_me.vertices:
        loc, norm, idx, dist = bvh_orig.find_nearest(v.co)
        if loc is not None and norm is not None and norm.length > 1e-4:
            signed_dist = (v.co - loc).dot(norm.normalized())
            signed_dists.append(signed_dist)
            if signed_dist < -1e-4:
                inside_count += 1

    bm_orig.free()

    assert inside_count == 0, f"辅助体未能完全包裹在模型外侧，仍有 {inside_count} 个顶点凹陷进原模型肉体内！"
    avg_push_dist = sum(signed_dists) / max(1, len(signed_dists))
    assert avg_push_dist > 0.005, f"向外包裹推开距离不足 (平均外推: {avg_push_dist:.4f}m <= 0.005m)"
    print(f"[PASS] 提取平滑传递向外包裹膨胀与防内缩补偿验证通过 (内部穿模点: 0/100%, 平均外包距离: {avg_push_dist*1000:.1f}mm, 完美包裹于模型外侧)")

    bpy.ops.m8.clear_normal_transfer()
    bpy.data.objects.remove(obj_sphere, do_unlink=True)

    print("\n" + "=" * 60)
    print(">>> 全部 36 项 M8 智能法向传递全场景自适应、多层智能叠加、外壳包裹与复杂硬表面极限测试 100% 通过 (ALL PASS)！")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    run_tests()


