"""Operators for AI chat dialogue, code generation, thinking trace, and execution."""

import time
from datetime import datetime
import bpy
from ...utils.i18n import _T
from ...property.keymap_helpers import _get_addon_prefs
from ...utils.ai_client import request_chat_completion_async, clean_markdown_code
from ...utils.adapter import tag_redraw_all_areas

_active_generation_id = 0
_is_unregistered = False


def reset_ai_state():
    """Reset AI lifecycle state on registration."""
    global _active_generation_id, _is_unregistered
    _is_unregistered = False


def cleanup_ai_state():
    """Cancel all active AI tickers and invalidate pending callbacks on addon unregister."""
    global _active_generation_id, _is_unregistered
    _is_unregistered = True
    _active_generation_id += 1



def apply_code_to_text_editor(code: str, mode: str = 'REPLACE', base_name: str = "M8_Script.py"):
    """Write generated code into Blender Text Editor and ensure it is visibly focused."""
    if not code:
        return None

    clean_code = clean_markdown_code(code)
    target_text = None

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'TEXT_EDITOR':
                st = area.spaces.active
                if st and st.text:
                    target_text = st.text
                    break
        if target_text:
            break

    if not target_text and bpy.data.texts:
        target_text = bpy.data.texts[0]

    if mode == 'NEW' or not target_text:
        target_text = bpy.data.texts.new(name=base_name)
        target_text.write(clean_code)
    elif mode == 'REPLACE':
        target_text.clear()
        target_text.write(clean_code)
    elif mode == 'APPEND':
        current = target_text.as_string()
        sep = "\n\n" if current.strip() else ""
        target_text.write(sep + clean_code)
    elif mode == 'INSERT':
        target_text.write(clean_code)

    # Bind target_text to all TEXT_EDITOR spaces so it is immediately visible
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'TEXT_EDITOR':
                st = area.spaces.active
                if st:
                    st.text = target_text
                area.tag_redraw()

    return target_text


class M8_OT_AI_GenerateCode(bpy.types.Operator):
    """发送需求到 AI 助手，展示思考过程并生成 Blender Python 脚本"""
    bl_idname = "m8.ai_generate_code"
    bl_label = _T("发送需求")
    bl_description = _T("调用选中的 AI 模型生成代码并展示思考与干活过程")
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        name=_T("动作类型"),
        items=[
            ('GENERATE', _T("生成代码"), _T("根据需求生成全新脚本")),
            ('EXPLAIN', _T("解释代码"), _T("对选中的代码进行深入解释")),
            ('REFACTOR', _T("优化重构"), _T("重构并优化当前脚本")),
        ],
        default='GENERATE'
    )

    def execute(self, context):
        action_type = str(self.action)
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            self.report({'WARNING'}, _T("请先在偏好设置中配置 AI 厂商与模型"))
            return {'CANCELLED'}

        active_prov_id = getattr(prefs, "active_provider_id", "")
        active_model_id = getattr(prefs, "active_model_id", "")

        target_provider = None
        for p in prefs.ai_providers:
            if p.id == active_prov_id:
                target_provider = p
                break

        if not target_provider and prefs.ai_providers:
            target_provider = prefs.ai_providers[0]
            active_prov_id = target_provider.id

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

        # Validate key for non-local providers
        is_local = (target_provider.id == "ollama" or "localhost" in target_provider.base_url or "127.0.0.1" in target_provider.base_url)
        if not is_local and not target_provider.api_key.strip():
            self.report({'ERROR'}, f"{_T('厂商')} '{target_provider.name}' {_T('尚未配置 API Key，请前往首选项填写')}")
            return {'CANCELLED'}

        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if not ai_props:
            self.report({'ERROR'}, _T("未找到 AI 场景属性"))
            return {'CANCELLED'}

        prompt = ai_props.prompt.strip()
        system_prompt = ai_props.system_prompt.strip()
        target_mode = ai_props.target_mode

        # Get active text block
        edit_text = getattr(context, "edit_text", None)
        if not edit_text and bpy.data.texts:
            edit_text = bpy.data.texts[0]

        current_script = edit_text.as_string() if edit_text else ""

        # Prepare messages
        messages = [{"role": "system", "content": system_prompt}]

        # Include recent conversation turns for multi-turn dialogue context
        if hasattr(ai_props, "chat_history") and len(ai_props.chat_history) > 0:
            for h_msg in ai_props.chat_history[-4:]:
                if h_msg.role == 'user':
                    messages.append({"role": "user", "content": h_msg.content})
                elif h_msg.role == 'assistant' and h_msg.code:
                    messages.append({"role": "assistant", "content": f"```python\n{h_msg.code}\n```"})

        user_display_text = prompt
        if self.action == 'GENERATE':
            if not prompt:
                self.report({'WARNING'}, _T("请输入提示词或需求描述"))
                return {'CANCELLED'}

            user_msg = f"需求描述：\n{prompt}\n\n"
            if current_script and target_mode in {'APPEND', 'INSERT'}:
                user_msg += f"当前已有脚本上下文（仅供参考）：\n```python\n{current_script[:1500]}\n```\n"
            user_msg += "请直接编写对应的完整 Blender Python 代码，确保语法严谨且适配 Blender 4.x/5.x。"
            messages.append({"role": "user", "content": user_msg})

        elif self.action == 'EXPLAIN':
            if not current_script.strip():
                self.report({'WARNING'}, _T("当前文本编辑器中没有可解释的代码"))
                return {'CANCELLED'}
            user_display_text = f"解释当前代码: {edit_text.name if edit_text else 'Script'}"
            user_msg = (
                f"请详细解释以下 Blender Python 脚本的实现逻辑、关键 API 与工作原理（请使用中文分点清晰阐述）：\n\n"
                f"```python\n{current_script}\n```"
            )
            messages.append({"role": "user", "content": user_msg})

        elif self.action == 'REFACTOR':
            if not current_script.strip():
                self.report({'WARNING'}, _T("当前文本编辑器中没有可重构的代码"))
                return {'CANCELLED'}
            user_display_text = f"重构优化代码: {edit_text.name if edit_text else 'Script'}"
            user_msg = (
                f"请重构并优化以下 Blender Python 代码。提高执行效率、规范异常处理、升级为 Blender 最新标准 API：\n\n"
                f"```python\n{current_script}\n```\n\n"
                f"附加要求：\n{prompt if prompt else '优化代码结构与性能，输出完整无误的 Python 代码'}"
            )
            messages.append({"role": "user", "content": user_msg})

        # 1. 记录用户消息到对话流
        u_msg = ai_props.chat_history.add()
        u_msg.role = 'user'
        u_msg.content = user_display_text
        u_msg.timestamp = datetime.now().strftime("%H:%M:%S")
        u_msg.action_type = action_type

        # 2. 预先添加 Assistant 气泡，让打字效果能够实时在气泡内呈现
        a_msg = ai_props.chat_history.add()
        a_msg.role = 'assistant'
        a_msg.content = ""
        a_msg.code = ""
        a_msg.thinking = ""
        a_msg.show_thinking = True
        a_msg.is_thinking_active = True
        a_msg.timestamp = datetime.now().strftime("%H:%M:%S")
        a_msg.model_name = active_model_id
        a_msg.action_type = action_type

        msg_index = len(ai_props.chat_history) - 1

        global _active_generation_id, _is_unregistered
        _is_unregistered = False
        _active_generation_id += 1
        current_gen_id = _active_generation_id

        # 清空输入框
        ai_props.prompt = ""

        # 设置生成中全局状态
        ai_props.is_generating = True
        ai_props.live_thinking_seconds = 0.0
        ai_props.live_thinking_step = f"正在呼叫 {target_provider.name} ({active_model_id})..."
        ai_props.status_message = f"{_T('正在思考')}..."

        start_time = time.time()

        # 打字机缓冲队列与流式状态机
        thinking_char_queue = []
        content_char_queue = []
        stream_state = {
            "has_received_chunks": False,
            "thinking_phase_ended": False,
            "stream_completed": False,
            "terminated": False,
            "failed": False,
            "post_thinking_wait_ticks": 0,
            "final_response": None,
        }

        def _on_chunk(c, r):
            if _is_unregistered or current_gen_id != _active_generation_id:
                return
            if stream_state.get("terminated") or stream_state.get("failed"):
                return
            stream_state["has_received_chunks"] = True
            if r:
                thinking_char_queue.extend(list(r))
            if c:
                if not stream_state["thinking_phase_ended"]:
                    stream_state["thinking_phase_ended"] = True
                content_char_queue.extend(list(c))

        def _typewriter_ticker():
            if _is_unregistered or current_gen_id != _active_generation_id:
                return None

            if stream_state.get("terminated") or stream_state.get("failed"):
                return None

            if not getattr(ai_props, "is_generating", False) and stream_state.get("stream_completed") and not thinking_char_queue and not content_char_queue:
                return None

            try:
                elapsed = time.time() - start_time
                ai_props.live_thinking_seconds = elapsed

                # 安全获取助手消息实例
                if not (0 <= msg_index < len(ai_props.chat_history)):
                    return None
                curr_msg = ai_props.chat_history[msg_index]
            except (ReferenceError, AttributeError):
                return None

            updated = False

            # 1. 逐步吐出思考字符（实现慢慢打字出来的效果）
            if thinking_char_queue:
                chunk_len = min(len(thinking_char_queue), 6)
                popped = "".join(thinking_char_queue[:chunk_len])
                del thinking_char_queue[:chunk_len]
                curr_msg.thinking += popped
                curr_msg.is_thinking_active = True
                curr_msg.show_thinking = True
                updated = True

            # 2. 思考字符全部吐完，且进入代码/正文阶段：自动收缩折叠！
            elif stream_state["thinking_phase_ended"] and curr_msg.is_thinking_active:
                stream_state["post_thinking_wait_ticks"] += 1
                # 停留约 0.5 秒让用户看到思考结论，随后写完自动收缩（若无思考过程则立即收起）
                if stream_state["post_thinking_wait_ticks"] >= 12 or not curr_msg.thinking.strip():
                    curr_msg.is_thinking_active = False
                    curr_msg.show_thinking = False  # <--- 写完自动收缩！
                    updated = True

            # 3. 逐步吐出正文与代码内容
            if content_char_queue and not curr_msg.is_thinking_active:
                chunk_len = min(len(content_char_queue), 12)
                popped = "".join(content_char_queue[:chunk_len])
                del content_char_queue[:chunk_len]
                curr_msg.content += popped
                updated = True

            # 4. 流式结束且两端队列均已完全呈现
            if stream_state["stream_completed"] and not thinking_char_queue and not content_char_queue:
                _finalize_generation()
                return None

            if updated:
                try:
                    for window in bpy.context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type == 'TEXT_EDITOR':
                                area.tag_redraw()
                except Exception:
                    pass

            return 0.035

        def _finalize_generation():
            if _is_unregistered or current_gen_id != _active_generation_id:
                return
            if stream_state.get("terminated") or stream_state.get("failed"):
                return
            try:
                ai_props.is_generating = False
                ai_props.status_message = _T("已完成！")
                if 0 <= msg_index < len(ai_props.chat_history):
                    curr_msg = ai_props.chat_history[msg_index]
                    curr_msg.is_thinking_active = False
                    curr_msg.show_thinking = False  # 确保自动收缩保持折叠状态

                    full_text = curr_msg.content.strip()
                    if not full_text and stream_state.get("final_raw_text"):
                        full_text = stream_state["final_raw_text"].strip()
                        curr_msg.content = full_text

                    clean_code = clean_markdown_code(full_text)
                    curr_msg.code = clean_code if action_type != 'EXPLAIN' else ""

                    if getattr(ai_props, "auto_apply_to_editor", True):
                        if action_type == 'EXPLAIN':
                            apply_code_to_text_editor(full_text, mode='NEW', base_name="M8_AI_Explanation.txt")
                        elif clean_code:
                            apply_code_to_text_editor(clean_code, mode=target_mode, base_name="M8_Generated_Script.py")

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'TEXT_EDITOR':
                            area.tag_redraw()
            except (ReferenceError, AttributeError):
                pass
            except Exception as fin_err:
                from ...utils.logger import get_logger
                get_logger().error(f"Error in _finalize_generation: {fin_err}", exc_info=True)

        bpy.app.timers.register(_typewriter_ticker, first_interval=0.03)

        def _on_success(raw_response):
            if _is_unregistered or current_gen_id != _active_generation_id:
                return
            if stream_state.get("terminated") or stream_state.get("failed"):
                return
            try:
                raw_text = str(raw_response)
                thinking_text = getattr(raw_response, "thinking", "").strip()
                stream_state["final_raw_text"] = raw_text

                if 0 <= msg_index < len(ai_props.chat_history):
                    curr_msg = ai_props.chat_history[msg_index]

                    # 若后端未分块流式返回思考过程（如非流式或无 reasoning 字段的模型）：
                    if not stream_state["has_received_chunks"]:
                        if not thinking_text:
                            elapsed = time.time() - start_time
                            thinking_text = (
                                f"1. 分析需求：{user_display_text}\n"
                                f"2. 组织 Blender 5.x `bpy` 核心接口与参数\n"
                                f"3. 耗时 {elapsed:.1f}s，开始格式化与输出代码"
                            )
                        # 注入打字机队列，让用户同样体验流式打字与自动收缩
                        thinking_char_queue.extend(list(thinking_text))
                        content_char_queue.extend(list(raw_text))
                        stream_state["thinking_phase_ended"] = True
                    else:
                        # 流式分块已在打字机队列中平滑输出，仅标记思考阶段已结束
                        stream_state["thinking_phase_ended"] = True

                stream_state["final_response"] = raw_response
                stream_state["stream_completed"] = True
            except (ReferenceError, AttributeError):
                pass
            except Exception as e:
                from ...utils.logger import get_logger
                get_logger().error(f"Error in _on_success: {e}", exc_info=True)

        def _on_error(err):
            if _is_unregistered or current_gen_id != _active_generation_id:
                return
            try:
                stream_state["terminated"] = True
                stream_state["failed"] = True
                stream_state["stream_completed"] = False
                thinking_char_queue.clear()
                content_char_queue.clear()

                ai_props.is_generating = False
                ai_props.status_message = f"{_T('生成失败')}: {err}"
                if 0 <= msg_index < len(ai_props.chat_history):
                    curr_msg = ai_props.chat_history[msg_index]
                    curr_msg.is_thinking_active = False
                    curr_msg.show_thinking = False
                    curr_msg.content = f"❌ 请求失败: {err}"
                    curr_msg.error_msg = str(err)

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'TEXT_EDITOR':
                            area.tag_redraw()
            except (ReferenceError, AttributeError):
                pass
            except Exception as e:
                from ...utils.logger import get_logger
                get_logger().error(f"Error in _on_error: {e}", exc_info=True)

        request_chat_completion_async(
            base_url=target_provider.base_url,
            api_key=target_provider.api_key,
            model=active_model_id,
            messages=messages,
            temperature=ai_props.temperature,
            stream=True,
            on_chunk=_on_chunk,
            on_success=_on_success,
            on_error=_on_error,
        )

        return {'FINISHED'}


class M8_OT_AI_ApplyMessageCode(bpy.types.Operator):
    """将对话气泡中的代码应用写入当前文本编辑器"""
    bl_idname = "m8.ai_apply_message_code"
    bl_label = _T("应用到编辑器")
    bl_description = _T("将该对话消息生成的代码写入当前文本编辑器")
    bl_options = {'REGISTER', 'UNDO'}

    msg_index: bpy.props.IntProperty(name="消息索引", default=-1)
    mode: bpy.props.StringProperty(name="写入模式", default="")

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if not ai_props or not ai_props.chat_history:
            return {'CANCELLED'}

        idx = self.msg_index if self.msg_index >= 0 else len(ai_props.chat_history) - 1
        if not (0 <= idx < len(ai_props.chat_history)):
            return {'CANCELLED'}

        msg = ai_props.chat_history[idx]
        code_to_write = clean_markdown_code(msg.code.strip() or msg.content.strip())
        if not code_to_write:
            self.report({'WARNING'}, _T("该消息中没有可写入的代码"))
            return {'CANCELLED'}

        target_mode = self.mode or ai_props.target_mode
        apply_code_to_text_editor(code_to_write, mode=target_mode, base_name="M8_AI_Script.py")

        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.tag_redraw()

        self.report({'INFO'}, f"{_T('已成功写入代码到编辑器')} ({target_mode})")
        return {'FINISHED'}


class M8_OT_AI_RunMessageCode(bpy.types.Operator):
    """直接在 Blender 中运行此对话生成的代码"""
    bl_idname = "m8.ai_run_message_code"
    bl_label = _T("立即运行")
    bl_description = _T("直接在当前 Blender 进程中执行该代码块")
    bl_options = {'REGISTER', 'UNDO'}

    msg_index: bpy.props.IntProperty(name="消息索引", default=-1)

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if not ai_props or not ai_props.chat_history:
            return {'CANCELLED'}

        idx = self.msg_index if self.msg_index >= 0 else len(ai_props.chat_history) - 1
        if not (0 <= idx < len(ai_props.chat_history)):
            return {'CANCELLED'}

        msg = ai_props.chat_history[idx]
        code = clean_markdown_code(msg.code.strip() or msg.content.strip())
        if not code:
            self.report({'WARNING'}, _T("没有可执行的代码"))
            return {'CANCELLED'}

        # Ensure active text editor has the code loaded
        apply_code_to_text_editor(code, mode='REPLACE', base_name="M8_AI_Run.py")

        import traceback
        try:
            exec_namespace = {"bpy": bpy, "context": context}
            exec(compile(code, "<m8_ai_chat_exec>", "exec"), exec_namespace)
            self.report({'INFO'}, _T("脚本执行成功！"))
            ai_props.status_message = _T("脚本运行成功！")
        except Exception as e:
            tb = traceback.format_exc()
            ai_props.last_error = tb
            ai_props.status_message = f"{_T('运行报错')}: {e}"
            self.report({'ERROR'}, f"{_T('脚本执行报错')}: {e}")

        tag_redraw_all_areas({'TEXT_EDITOR', 'VIEW_3D', 'OUTLINER'})

        return {'FINISHED'}


class M8_OT_AI_CopyMessageCode(bpy.types.Operator):
    """复制该消息的代码到系统剪贴板"""
    bl_idname = "m8.ai_copy_message_code"
    bl_label = _T("复制")
    bl_description = _T("将此消息中的代码复制到系统剪贴板")
    bl_options = {'INTERNAL'}

    msg_index: bpy.props.IntProperty(name="消息索引", default=-1)

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if not ai_props or not ai_props.chat_history:
            return {'CANCELLED'}

        idx = self.msg_index if self.msg_index >= 0 else len(ai_props.chat_history) - 1
        if not (0 <= idx < len(ai_props.chat_history)):
            return {'CANCELLED'}

        msg = ai_props.chat_history[idx]
        code = clean_markdown_code(msg.code.strip() or msg.content.strip())
        context.window_manager.clipboard = code
        self.report({'INFO'}, _T("代码已复制到剪贴板！"))
        return {'FINISHED'}


class M8_OT_AI_ToggleThinking(bpy.types.Operator):
    """展开或折叠该消息的思考过程"""
    bl_idname = "m8.ai_toggle_thinking"
    bl_label = _T("切换思考过程")
    bl_options = {'INTERNAL'}

    msg_index: bpy.props.IntProperty(name="消息索引", default=-1)

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if ai_props and 0 <= self.msg_index < len(ai_props.chat_history):
            msg = ai_props.chat_history[self.msg_index]
            msg.show_thinking = not msg.show_thinking
            tag_redraw_all_areas({'TEXT_EDITOR'})
            return {'FINISHED'}
        return {'CANCELLED'}


class M8_OT_AI_ToggleFullCode(bpy.types.Operator):
    """展开或折叠该消息的代码预览"""
    bl_idname = "m8.ai_toggle_full_code"
    bl_label = _T("展开/折叠代码")
    bl_options = {'INTERNAL'}

    msg_index: bpy.props.IntProperty(name="消息索引", default=-1)

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if ai_props and 0 <= self.msg_index < len(ai_props.chat_history):
            msg = ai_props.chat_history[self.msg_index]
            msg.show_full_code = not msg.show_full_code
            tag_redraw_all_areas({'TEXT_EDITOR'})
            return {'FINISHED'}
        return {'CANCELLED'}


class M8_OT_AI_ToggleFullThinking(bpy.types.Operator):
    """展开或折叠该消息思考过程的完整内容"""
    bl_idname = "m8.ai_toggle_full_thinking"
    bl_label = _T("展开/折叠思考")
    bl_options = {'INTERNAL'}

    msg_index: bpy.props.IntProperty(name="消息索引", default=-1)

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if ai_props and 0 <= self.msg_index < len(ai_props.chat_history):
            msg = ai_props.chat_history[self.msg_index]
            msg.show_full_thinking = not msg.show_full_thinking
            tag_redraw_all_areas({'TEXT_EDITOR'})
            return {'FINISHED'}
        return {'CANCELLED'}


class M8_OT_AI_ClearChat(bpy.types.Operator):
    """清空当前场景的所有 AI 对话与思考记录"""
    bl_idname = "m8.ai_clear_chat"
    bl_label = _T("清空对话")
    bl_description = _T("清空全部对话历史与思考过程记录")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if ai_props:
            ai_props.chat_history.clear()
            ai_props.status_message = _T("就绪")
            tag_redraw_all_areas({'TEXT_EDITOR'})
        self.report({'INFO'}, _T("已清空对话记录"))
        return {'FINISHED'}


class M8_OT_AI_SendQuickPrompt(bpy.types.Operator):
    """点击快速预设芯片发送需求"""
    bl_idname = "m8.ai_send_quick_prompt"
    bl_label = _T("快速需求")
    bl_description = _T("一键发送常见的建模或材质需求")
    bl_options = {'REGISTER', 'UNDO'}

    prompt_text: bpy.props.StringProperty(name="提示词", default="")

    def execute(self, context):
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)
        if not ai_props:
            return {'CANCELLED'}

        ai_props.prompt = self.prompt_text
        bpy.ops.m8.ai_generate_code(action='GENERATE')
        return {'FINISHED'}


CLASSES = (
    M8_OT_AI_GenerateCode,
    M8_OT_AI_ApplyMessageCode,
    M8_OT_AI_RunMessageCode,
    M8_OT_AI_CopyMessageCode,
    M8_OT_AI_ToggleThinking,
    M8_OT_AI_ToggleFullThinking,
    M8_OT_AI_ToggleFullCode,
    M8_OT_AI_ClearChat,
    M8_OT_AI_SendQuickPrompt,
)
