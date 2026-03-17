from mathutils import Vector

from .measure import MeasureObjects
from .to_matrix import location_to_matrix

DEBUG_ALIGN = False


class ToAlign:
    def align_to_align(self, context):
        dep = context.evaluated_depsgraph_get()
        dep_objs = [obj.evaluated_get(dep) for obj in context.selected_objects]
        measures = MeasureObjects(dep_objs)

        to_loc = self.__mix_mcm_loc__([measures.min, measures.center, measures.max])
        to_mat = location_to_matrix(to_loc)
        if DEBUG_ALIGN:
            print("to_loc =", to_loc.__repr__())
            count = 0
        for m in measures:
            obj = m.__object__
            from_loc = self.__mix_mcm_loc__([m.min, m.center, m.max])

            tran_loc = self.__mix_two_loc__(from_loc, to_loc)
            tran_mat = location_to_matrix(tran_loc).inverted()
            if DEBUG_ALIGN:
                print(obj.name)
                print(f"from_loc_{count} =", from_loc.__repr__())
                print(f"tran_loc_{count} =", tran_loc.__repr__())
                count += 1
            context.view_layer.update()
            mat = tran_mat @ to_mat
            context.scene.objects[m.name].matrix_world = mat @ context.scene.objects[m.name].matrix_world
            context.view_layer.update()

    def __mix_mcm_loc__(self, loc_items):
        """混合最大中间最小位置"""
        items = ["MIN", "CENTER", "MAX"]
        x = items.index(self.align_x_method)
        y = items.index(self.align_y_method)
        z = items.index(self.align_z_method)
        return Vector((
            loc_items[x].x,
            loc_items[y].y,
            loc_items[z].z
        ))
