from functools import cache

import bpy


@cache
def check_center(index, count) -> bool:
    """检查是否为中间的晶格"""
    bisect = count // 2
    if bisect:
        return count % 2 + 1 == index
    return True


def get_select_mirror_info(lattice):
    """
    UVW,XYZ
    bpy.data.lattices["Lattice"].points_u
    """
    u_count, v_count, w_count = lattice.points_u, lattice.points_v, lattice.points_w
    # print(lattice)
    mirror = {
        # index:{"U":index,"V":index,"W":index}
    }
    for w_i in range(w_count):  # z
        # if check_center(w_i, w_count):
        #     continue
        for v_i in range(v_count):  # y
            # if check_center(v_i, v_count):
            #     continue
            for u_i in range(u_count):  # x
                # if check_center(u_i, u_count):
                #     continue
                u = u_i
                v = v_i * u_count
                w = w_i * (u_count * v_count)
                index = u + v + w
                # print("index", index, lattice.points[index].select, "\t", u, v, w, "\t", u_i, v_i, w_i)

                u_is_positive = u_i > (u_count / 2)

                a = (u_count - 1) - u_i if u_is_positive else u_count - (u_i + 1)
                um = w + v + a
                ut = "CENTER" if um == index else ("POSITIVE" if u_is_positive else "NEGATIVE")

                v_is_positive = v_i > (v_count / 2)
                b = (v_count - 1) - v_i if v_is_positive else v_count - (v_i + 1)
                vm = w + u + b * u_count
                vt = "CENTER" if vm == index else ("POSITIVE" if v_is_positive else "NEGATIVE")

                w_is_positive = w_i > (w_count / 2)
                c = (w_count - 1) - w_i if w_is_positive else w_count - (w_i + 1)
                wm = u + v + c * (u_count * v_count)
                wt = "CENTER" if wm == index else ("POSITIVE" if w_is_positive else "NEGATIVE")
                # if lattice.points[index].select:
                #     print(u_i, v_i, w_i, index, "  ", u, v, w, u_is_positive, a, b, c, "\t", um, vm, wm, )
                #     lattice.points[wm].select = True
                #     return
                mirror[index] = {
                    "U": um,
                    "U_TYPE": ut,

                    "V": vm,
                    "V_TYPE": vt,

                    "W": wm,
                    "W_TYPE": wt,
                }
    # print(len(mirror), mirror.__repr__())
    return mirror


if __name__ == "__main__":
    get_select_mirror_info(bpy.context.object.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
