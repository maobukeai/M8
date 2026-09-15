"""Operator to execute current script safely and capture errors for AI diagnostics."""

import traceback
import bpy
from ...utils.i18n import _T
from ...utils.logger import get_logger
from ...utils.adapter import tag_redraw_all_areas

logger = get_logger()


class M8_OT_AI_RunScript(bpy.types.Operator):
    """运行当前文本编辑器中的脚本并捕获执行状态"""
    bl_idname = "m8.ai_run_script"
    bl_label = _T("运行脚本")
    bl_description = _T("在 Blender 中执行当前脚本，若报错将自动捕获供 AI 分析修复")
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)

        edit_text = getattr(context, "edit_text", None)
        if not edit_text and bpy.data.texts:
            edit_text = bpy.data.texts[0]

        if not edit_text:
            self.report({'WARNING'}, _T("没有可执行的脚本"))
            return {'CANCELLED'}

        code_str = edit_text.as_string()
        if not code_str.strip():
            self.report({'WARNING'}, _T("脚本内容为空"))
            return {'CANCELLED'}

        global_scope = {
            "__name__": "__main__",
            "bpy": bpy,
        }

        try:
            compiled = compile(code_str, edit_text.name, 'exec')
            exec(compiled, global_scope)

            if ai_props:
                ai_props.last_error = ""
                ai_props.status_message = _T("脚本执行成功！")

            self.report({'INFO'}, f"{_T('脚本执行成功')}: {edit_text.name}")

            tag_redraw_all_areas({'TEXT_EDITOR', 'VIEW_3D', 'OUTLINER'})

            return {'FINISHED'}

        except Exception as err:
            tb_str = traceback.format_exc()
            logger.error(f"Script execution error:\n{tb_str}")

            if ai_props:
                ai_props.last_error = tb_str
                ai_props.status_message = f"{_T('执行出错')}: {err}"

            self.report({'ERROR'}, f"{_T('执行报错')}: {err}")

            tag_redraw_all_areas({'TEXT_EDITOR'})

            return {'CANCELLED'}


CLASSES = (
    M8_OT_AI_RunScript,
)
