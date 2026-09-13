import bpy

from ...utils.i18n import _T


def find_adjacent_view3d_for_asset(screen, asset_area):
    """查找与 asset_area 在同一列且垂直直接相邻的 VIEW_3D 区域。"""
    tol = 10
    for a in screen.areas:
        if a.type != 'VIEW_3D':
            continue
        if abs(a.x - asset_area.x) <= tol and abs(a.width - asset_area.width) <= tol:
            if abs(a.y - (asset_area.y + asset_area.height)) <= tol:
                return a
            if abs((a.y + a.height) - asset_area.y) <= tol:
                return a

    for a in screen.areas:
        if a.type != 'VIEW_3D':
            continue
        if abs(a.y - (asset_area.y + asset_area.height)) <= tol or abs((a.y + a.height) - asset_area.y) <= tol:
            return a

    v3d_list = [a for a in screen.areas if a.type == 'VIEW_3D']
    return v3d_list[0] if v3d_list else None


def find_adjacent_asset_browser(screen, v3d_area, at_top=None):
    """查找与 v3d_area 相邻的资产浏览器区域。"""
    tol = 10
    for a in screen.areas:
        if a == v3d_area:
            continue
        if getattr(a, "ui_type", "") != 'ASSETS' and a.type != 'FILE_BROWSER':
            continue

        # 刚生成的区域在当前帧未完成重绘时坐标为 0，视为新创建的候选区域
        if a.width == 0 and a.height == 0:
            return a

        if abs(a.x - v3d_area.x) > tol or abs(a.width - v3d_area.width) > tol:
            continue
        is_above = abs(a.y - (v3d_area.y + v3d_area.height)) <= tol
        is_below = abs((a.y + a.height) - v3d_area.y) <= tol
        if at_top is True and is_above:
            return a
        if at_top is False and is_below:
            return a
        if at_top is None and (is_above or is_below):
            return a

    # 次级宽松匹配
    for a in screen.areas:
        if a != v3d_area and getattr(a, "ui_type", "") == 'ASSETS':
            return a

    return None


def join_and_close_asset_area(context, v3d_area, asset_area):
    """使用精准 area_join 将资产浏览器合并回 v3d 视口，避免盲目 area_close 误合进时间轴导致视口上移漂移。"""
    screen = context.screen
    if asset_area.width == 0 or asset_area.height == 0:
        try:
            with context.temp_override(area=asset_area, screen=screen):
                bpy.ops.screen.area_close()
            return True
        except Exception:
            return False

    src_x = int(v3d_area.x + v3d_area.width / 2)
    src_y = int(v3d_area.y + v3d_area.height / 2)
    tgt_x = int(asset_area.x + asset_area.width / 2)
    tgt_y = int(asset_area.y + asset_area.height / 2)
    try:
        with context.temp_override(area=v3d_area, screen=screen):
            bpy.ops.screen.area_join(source_xy=(src_x, src_y), target_xy=(tgt_x, tgt_y))
        return True
    except Exception:
        try:
            with context.temp_override(area=asset_area, screen=screen):
                bpy.ops.screen.area_close()
            return True
        except Exception:
            return False


def open_asset_browser_drawer(context, v3d_area, at_top, split_factor=0.25, wrap_mouse=False):
    """在 3D 视口顶部或底部展开抽屉式资产浏览器，保持原 3D 视口本体不被篡改。"""
    screen = context.screen
    effective_factor = (1.0 - split_factor) if at_top else split_factor
    old_areas = set(screen.areas)
    try:
        with context.temp_override(area=v3d_area, screen=screen):
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=effective_factor)
    except Exception:
        return False

    new_areas = set(screen.areas) - old_areas
    if not new_areas:
        return False

    new_area = list(new_areas)[0]
    try:
        new_area.type = 'FILE_BROWSER'
        new_area.ui_type = 'ASSETS'
    except Exception:
        pass

    if wrap_mouse:
        try:
            cx = new_area.x + new_area.width / 2
            cy = new_area.y + new_area.height / 2
            context.window.cursor_warp(int(cx), int(cy))
        except Exception:
            pass

    return True


class M8_OT_ToggleArea(bpy.types.Operator):
    bl_idname = "m8.toggle_area"
    bl_label = _T("切换区域")
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        area = context.area
        if not area:
            return {'CANCELLED'}

        # 1. 如果当前光标处于资产浏览器（FILE_BROWSER），直接按 T 将自己一键收回合并进相邻 3D 视图！
        if area.type == 'FILE_BROWSER' or getattr(area, "ui_type", "") == 'ASSETS':
            v3d = find_adjacent_view3d_for_asset(context.screen, area)
            if v3d and join_and_close_asset_area(context, v3d, area):
                return {'FINISHED'}
            try:
                with context.temp_override(area=area, screen=context.screen):
                    bpy.ops.screen.area_close()
                return {'FINISHED'}
            except Exception:
                return {'CANCELLED'}

        from ...property.preferences import _get_addon_prefs
        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        # 非 3D 视图（例如节点编辑器、图像编辑器）纯粹切换工具栏/侧边栏
        if area.type in {'NODE_EDITOR', 'IMAGE_EDITOR'}:
            mx = event.mouse_x - area.x
            w = area.width
            if w <= 0:
                return {'CANCELLED'}
            if (mx / w) < 0.5:
                try:
                    bpy.ops.screen.region_toggle(region_type='TOOLS')
                    return {'FINISHED'}
                except Exception:
                    return {'CANCELLED'}
            else:
                try:
                    bpy.ops.screen.region_toggle(region_type='UI')
                    return {'FINISHED'}
                except Exception:
                    return {'CANCELLED'}

        # 获取首选项设置
        close_range = getattr(prefs, "toggle_area_close_range", 30.0) / 100.0
        prefer_lr = getattr(prefs, "toggle_area_prefer_left_right", True)
        toggle_shelf = getattr(prefs, "toggle_area_asset_shelf", False)
        do_top = getattr(prefs, "toggle_area_asset_browser_top", True)
        do_bottom = getattr(prefs, "toggle_area_asset_browser_bottom", True)
        split_factor = getattr(prefs, "toggle_area_split_factor", 0.25)
        wrap_mouse = getattr(prefs, "toggle_area_wrap_mouse", False)

        # 检查区域高度
        if area.height < 100:
            self.report({'WARNING'}, f"{_T('区域太小 (高度')}{area.height}px{_T(')，请在主视图内操作')}")
            return {'CANCELLED'}

        # 计算鼠标相对归一化位置
        mx = event.mouse_x - area.x
        my = event.mouse_y - area.y
        w = area.width
        h = area.height

        if w <= 0 or h <= 0:
            return {'CANCELLED'}

        nx = mx / w
        ny = my / h

        # 边缘判定
        is_left = nx < close_range
        is_right = nx > (1.0 - close_range)
        is_bottom = ny < close_range
        is_top = ny > (1.0 - close_range)

        def toggle_tools():
            try:
                bpy.ops.screen.region_toggle(region_type='TOOLS')
                return True
            except Exception:
                return False

        def toggle_ui():
            try:
                bpy.ops.screen.region_toggle(region_type='UI')
                return True
            except Exception:
                return False

        def toggle_asset_shelf_fn():
            if not toggle_shelf:
                return False
            shelf_avail = False
            for r in area.regions:
                if r.type == 'ASSET_SHELF_HEADER' and r.height > 1:
                    shelf_avail = True
                    break
            if not shelf_avail:
                return False
            try:
                bpy.ops.screen.region_toggle(region_type='ASSET_SHELF')
                return True
            except Exception:
                return False

        def toggle_asset_browser_top():
            # 1. 若顶部已打开资产浏览器，则一键精准合并收回
            existing = find_adjacent_asset_browser(context.screen, area, at_top=True)
            if existing:
                return join_and_close_asset_area(context, area, existing)
            # 2. 若未打开且允许顶部打开，则呼出
            if do_top:
                return open_asset_browser_drawer(context, area, at_top=True, split_factor=split_factor, wrap_mouse=wrap_mouse)
            return False

        def toggle_asset_browser_bottom():
            # 1. 若底部已打开资产浏览器，则一键精准合并收回
            existing = find_adjacent_asset_browser(context.screen, area, at_top=False)
            if existing:
                return join_and_close_asset_area(context, area, existing)
            # 2. 检查资产架
            if toggle_shelf and toggle_asset_shelf_fn():
                return True
            # 3. 若未打开且允许底部打开，则呼出
            if do_bottom:
                return open_asset_browser_drawer(context, area, at_top=False, split_factor=split_factor, wrap_mouse=wrap_mouse)
            return False

        ops_queue = []

        if prefer_lr:
            if is_left:
                ops_queue.append(toggle_tools)
            if is_right:
                ops_queue.append(toggle_ui)
            if is_bottom:
                ops_queue.append(toggle_asset_browser_bottom)
            if is_top:
                ops_queue.append(toggle_asset_browser_top)
        else:
            if is_bottom:
                ops_queue.append(toggle_asset_browser_bottom)
            if is_top:
                ops_queue.append(toggle_asset_browser_top)
            if is_left:
                ops_queue.append(toggle_tools)
            if is_right:
                ops_queue.append(toggle_ui)

        for op in ops_queue:
            if op():
                return {'FINISHED'}

        # 回退：切换工具栏
        if toggle_tools():
            return {'FINISHED'}

        return {'CANCELLED'}


class M8_OT_ToggleAssetBrowser(bpy.types.Operator):
    bl_idname = "m8.toggle_asset_browser"
    bl_label = _T("切换资产浏览器抽屉")
    bl_description = _T("抽屉式展开或收起资产浏览器，在资产浏览器内按快捷键一键收回，不破坏视口布局")
    bl_options = {'REGISTER', 'UNDO'}

    position: bpy.props.EnumProperty(
        name=_T("位置"),
        items=[
            ('BOTTOM', _T("底部"), _T("在视口下方弹出资产浏览器")),
            ('TOP', _T("顶部"), _T("在视口上方弹出资产浏览器")),
        ],
        default='BOTTOM',
    )

    def execute(self, context):
        area = context.area
        if not area:
            return {'CANCELLED'}

        from ...property.preferences import _get_addon_prefs
        prefs = _get_addon_prefs()
        split_factor = getattr(prefs, "toggle_area_split_factor", 0.25) if prefs else 0.25
        wrap_mouse = getattr(prefs, "toggle_area_wrap_mouse", False) if prefs else False

        # 1. 若当前光标位于资产浏览器内，执行一键收回
        if area.type == 'FILE_BROWSER' or getattr(area, "ui_type", "") == 'ASSETS':
            v3d = find_adjacent_view3d_for_asset(context.screen, area)
            if v3d and join_and_close_asset_area(context, v3d, area):
                return {'FINISHED'}
            try:
                with context.temp_override(area=area, screen=context.screen):
                    bpy.ops.screen.area_close()
                return {'FINISHED'}
            except Exception:
                return {'CANCELLED'}

        # 2. 定位目标 3D 视图
        target_v3d = area if area.type == 'VIEW_3D' else None
        if not target_v3d:
            v3d_list = [a for a in context.screen.areas if a.type == 'VIEW_3D']
            if v3d_list:
                target_v3d = v3d_list[0]

        if not target_v3d:
            self.report({'WARNING'}, _T("未找到 3D 视口"))
            return {'CANCELLED'}

        at_top = (self.position == 'TOP')

        # 3. 检测是否已有紧邻的资产浏览器打开
        existing = find_adjacent_asset_browser(context.screen, target_v3d, at_top=at_top)
        if not existing:
            existing = find_adjacent_asset_browser(context.screen, target_v3d, at_top=None)

        if existing:
            # 存在则一键关闭收回
            if join_and_close_asset_area(context, target_v3d, existing):
                return {'FINISHED'}
            return {'CANCELLED'}
        else:
            # 不存在则弹出抽屉
            if open_asset_browser_drawer(context, target_v3d, at_top=at_top, split_factor=split_factor, wrap_mouse=wrap_mouse):
                return {'FINISHED'}
            return {'CANCELLED'}

