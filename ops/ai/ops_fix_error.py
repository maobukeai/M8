"""Operator for AI error diagnosis and automated code fixing."""

import time
from datetime import datetime
import bpy
from ...utils.i18n import _T
from ...property.keymap_helpers import _get_addon_prefs
from ...utils.ai_client import request_chat_completion_async, clean_markdown_code, split_markdown_response
from ...utils.adapter import tag_redraw_all_areas


class M8_OT_AI_FixError(bpy.types.Operator):
    """提取最近的运行报错并让 AI 自动分析与修复代码"""
    bl_idname = "m8.ai_fix_error"
    bl_label = _T("一键报错修复")
    bl_description = _T("将当前脚本和最近的报错信息发送给 AI，获取诊断与修复后的代码")
    bl_options = {'REGISTER', 'UNDO'}

    custom_error: bpy.props.StringProperty(
        name=_T("自定义报错"),
        description=_T("可选手动粘贴报错信息"),
        default=""
    )

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            self.report({'WARNING'}, _T("请先在偏好设置中配置 AI 厂商与模型"))
            return {'CANCELLED'}

        active_prov_id = getattr(prefs, "active_provider_id", "")
        active_model_id = getattr(prefs, "active_model_id", "").strip()

        target_provider = None
        for p in prefs.ai_providers:
            if p.id == active_prov_id:
                target_provider = p
                break

        if not target_provider and prefs.ai_providers:
            target_provider = prefs.ai_providers[0]

        if not target_provider:
            self.report({'WARNING'}, _T("未找到可用的 AI 厂商"))
            return {'CANCELLED'}

        if not active_model_id:
            models = [m.strip() for m in target_provider.models.split(",") if m.strip()]
            if models:
                active_model_id = models[0]
                if prefs:
                    prefs.active_model_id = active_model_id
            else:
                self.report({'WARNING'}, f"{_T('厂商')} '{target_provider.name}' {_T('尚未配置任何可用模型，请在首选项选择或添加模型')}")
                return {'CANCELLED'}

        is_local = (target_provider.id == "ollama" or "localhost" in target_provider.base_url or "127.0.0.1" in target_provider.base_url)
        if not is_local and not target_provider.api_key.strip():
            self.report({'ERROR'}, f"{_T('厂商')} '{target_provider.name}' {_T('尚未配置 API Key，请前往首选项填写')}")
            return {'CANCELLED'}

        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if not ai_props:
            return {'CANCELLED'}

        edit_text = getattr(context, "edit_text", None)
        if not edit_text and bpy.data.texts:
            edit_text = bpy.data.texts[0]

        if not edit_text:
            self.report({'WARNING'}, _T("未找到活动的脚本文件"))
            return {'CANCELLED'}

        current_script = edit_text.as_string()
        if not current_script.strip():
            self.report({'WARNING'}, _T("当前脚本为空"))
            return {'CANCELLED'}

        error_content = self.custom_error.strip() or ai_props.last_error.strip()
        if not error_content:
            error_content = _T("运行时发生异常，请检查代码语法、未引用的模块、API废弃或非法数据访问。")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名精通 Blender Python (bpy) 的资深专家。当前运行环境为 Blender 4.2+ / 5.x。"
                    "请根据用户提供的报错堆栈（Traceback）和源代码，分析报错原因，并直接给出修复后的完整正确代码。"
                    "要求：遵守最新 Blender API 规范，修复所有潜在隐患，只输出纯 Python 代码，并在修改处附带简明中文注释。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"【报错信息 / Traceback】\n{error_content}\n\n"
                    f"【原始 Python 代码】\n```python\n{current_script}\n```\n\n"
                    "请输出修复后的完整可用代码。"
                ),
            },
        ]

        # 1. 录入对话流：用户诊断请求
        u_msg = ai_props.chat_history.add()
        u_msg.role = 'user'
        u_msg.content = f"【一键诊断与修复报错】\n{error_content[:200]}"
        u_msg.timestamp = datetime.now().strftime("%H:%M:%S")
        u_msg.action_type = "FIX"

        # 2. 录入对话流：助手预占气泡
        a_msg = ai_props.chat_history.add()
        a_msg.role = 'assistant'
        a_msg.content = ""
        a_msg.code = ""
        a_msg.thinking = f"正在分析报错堆栈并检索 Blender 5.x 适配代码..."
        a_msg.show_thinking = True
        a_msg.is_thinking_active = True
        a_msg.timestamp = datetime.now().strftime("%H:%M:%S")
        a_msg.model_name = active_model_id
        a_msg.action_type = "FIX"

        ai_props.is_generating = True
        ai_props.status_message = f"{_T('正在诊断修复')} ({active_model_id})..."
        tag_redraw_all_areas({'TEXT_EDITOR'})

        def _on_success(raw_content):
            ai_props.is_generating = False
            ai_props.status_message = _T("修复完成！已更新脚本")
            ai_props.last_error = ""

            fixed_code = clean_markdown_code(raw_content)
            if not fixed_code:
                fixed_code = raw_content

            # 更新助手气泡
            a_msg.is_thinking_active = False
            a_msg.show_thinking = False
            explanation, extracted_code = split_markdown_response(raw_content)
            a_msg.content = explanation or raw_content
            a_msg.code = fixed_code or extracted_code

            # 同步写入文本编辑器
            try:
                edit_text.clear()
                edit_text.write(fixed_code)
            except Exception:
                pass

            tag_redraw_all_areas({'TEXT_EDITOR', 'VIEW_3D', 'OUTLINER'})

        def _on_error(err):
            ai_props.is_generating = False
            ai_props.status_message = f"{_T('修复请求失败')}: {err}"
            a_msg.is_thinking_active = False
            a_msg.show_thinking = False
            a_msg.show_full_thinking = False
            a_msg.content = f"❌ 修复请求失败: {err}"
            a_msg.error_msg = str(err)
            tag_redraw_all_areas({'TEXT_EDITOR'})

        request_chat_completion_async(
            base_url=target_provider.base_url,
            api_key=target_provider.api_key,
            model=active_model_id,
            messages=messages,
            temperature=0.2,
            on_success=_on_success,
            on_error=_on_error,
        )

        return {'FINISHED'}


CLASSES = (
    M8_OT_AI_FixError,
)
