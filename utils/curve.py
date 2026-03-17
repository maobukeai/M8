import bpy

def check_curve_select(curve: bpy.types.Curve) -> bool:
    """检查曲线是否选中"""
    for spline in curve.splines:
        for p in spline.points:
            if p.select:
                return True
        for bp in spline.bezier_points:
            if bp.select_control_point:
                return True
            
    return False