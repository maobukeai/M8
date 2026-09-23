import textwrap
import bpy
from ...utils.i18n import _T
from ...utils.adapter import get_adapter_blender_icon as _ICON
from ...property.keymap_helpers import _get_addon_prefs


def wrap_text_smart(text: str, max_width: int = 24):
    """Wrap text smartly by word boundary and character width, avoiding awkward word chops."""
    if not text:
        return []
    lines = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in line)
        eff_width = 18 if has_cjk else max_width
        wrapped = textwrap.wrap(
            line,
            width=eff_width,
            break_long_words=True,
            break_on_hyphens=False
        )
        if wrapped:
            lines.extend(wrapped)
        else:
            lines.append(line)
    return lines


def _draw_wrapped_text(layout, text: str, max_chars: int = 24):
    """Draw text cleanly wrapped across multiple labels to prevent ellipsis truncation."""
    if not text:
        return
    col = layout.column(align=True)
    lines = wrap_text_smart(text, max_width=max_chars)
    for line in lines:
        col.label(text=line)


class TEXT_PT_M8_AI_Assistant(bpy.types.Panel):
    """M8 AI 脚本助手侧边栏面板"""
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'M8 AI'
    bl_label = _T("M8 AI 助手")
    bl_order = 0

    @classmethod
    def poll(cls, context):
        prefs = _get_addon_prefs()
        return getattr(prefs, "activate_ai_assistant", True)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        try:
            self._draw_panel(context, layout)
        except Exception as e:
            from ...utils.logger import get_logger
            get_logger().error(f"Error drawing TEXT_PT_M8_AI_Assistant: {e}", exc_info=True)
            box_err = layout.box()
            box_err.alert = True
            box_err.label(text=_T("AI 面板加载中..."), icon=_ICON("INFO"))
            box_err.label(text=_T("若刚更新，请重启 Blender 一次以生效"))
            box_err.operator("m8.ai_clear_chat", text=_T("重置对话状态"), icon=_ICON("FILE_REFRESH"))

    def _draw_panel(self, context, layout):
        prefs = _get_addon_prefs()
        scene = context.scene
        ai_props = getattr(scene, "m8_ai", None)

        if not ai_props:
            layout.label(text=_T("AI 模块属性未注册，请重启 Blender"), icon="ERROR")
            return

        # -------------------------------------------------------------
        # 1. 顶部状态栏（模型级联切换、清空对话、刷新）
        # -------------------------------------------------------------
        active_prov_id = getattr(prefs, "active_provider_id", "sensenova") if prefs else "sensenova"
        active_model_id = getattr(prefs, "active_model_id", "").strip() if prefs else ""

        prov_name = active_prov_id
        target_p = None
        if prefs and prefs.ai_providers:
            for p in prefs.ai_providers:
                if p.id == active_prov_id:
                    prov_name = p.name
                    target_p = p
                    break

        display_model_id = active_model_id
        if not display_model_id and target_p:
            models = [m.strip() for m in target_p.models.split(",") if m.strip()]
            if models:
                display_model_id = models[0]

        box_top = layout.box()
        row_top = box_top.row(align=True)
        row_top.scale_y = 1.2

        if not display_model_id:
            menu_label = f"{prov_name} : {_T('未配置模型')}"
        else:
            short_model = display_model_id.replace("sensenova-", "").replace("deepseek-", "")
            menu_label = f"{prov_name} : {short_model}"
        row_top.menu("M8_MT_ai_model_menu", text=menu_label, icon=_ICON("CONSOLE"))

        op_fetch = row_top.operator("m8.ai_fetch_models", text="", icon=_ICON("FILE_REFRESH"))
        op_fetch.provider_id = active_prov_id

        row_top.operator("m8.ai_open_preferences", text="", icon=_ICON("PREFERENCES"))
        row_top.operator("m8.ai_clear_chat", text="", icon=_ICON("TRASH"))

        # -------------------------------------------------------------
        # 2. 对话流区域 (Chat Stream)
        # -------------------------------------------------------------
        chat_history = getattr(ai_props, "chat_history", None)
        has_messages = (len(chat_history) > 0) if chat_history is not None else False
        is_generating = getattr(ai_props, "is_generating", False)

        if not has_messages and not is_generating:
            # 空状态欢迎卡片与快速需求芯片
            box_welcome = layout.box()
            row_w_head = box_welcome.row(align=True)
            row_w_head.label(text=_T("👋 M8 AI 编程助手已就绪"), icon=_ICON("INFO"))

            box_welcome.label(text=_T("点击下方预设需求，或在底栏输入指令："))

            col_chips = box_welcome.column(align=True)
            row_c1 = col_chips.row(align=True)
            op1 = row_c1.operator("m8.ai_send_quick_prompt", text=_T("📦 随机立方体群"))
            op1.prompt_text = "写一个脚本：在原点周围生成 10 个随机大小和位置的立方体"
            op2 = row_c1.operator("m8.ai_send_quick_prompt", text=_T("🎨 金色金属材质"))
            op2.prompt_text = "写一个脚本：为当前活动物体创建高质量金色金属 PBR 材质并启用节点"

            row_c2 = col_chips.row(align=True)
            op3 = row_c2.operator("m8.ai_send_quick_prompt", text=_T("📐 螺旋曲线管道"))
            op3.prompt_text = "写一个脚本：使用 bpy.ops.curve 生成螺旋曲线并设置倒角深度做成管道"
            op4 = row_c2.operator("m8.ai_send_quick_prompt", text=_T("🧹 清理孤立数据"))
            op4.prompt_text = "写一个脚本：清理当前工程中所有未使用的材质、网格和材质节点"

        elif chat_history is not None and len(chat_history) > 0:
            # 渲染历史对话消息流（展示最近几轮对话）
            display_messages = list(enumerate(chat_history))[-6:]

            from ...utils.ai_client import split_markdown_response, clean_markdown_code

            for idx, msg in display_messages:
                role = getattr(msg, "role", "")
                if role == 'user':
                    box_u = layout.box()
                    row_u = box_u.row(align=True)
                    row_u.label(text=_T("你:"), icon=_ICON("USER"))
                    if getattr(msg, "timestamp", ""):
                        row_u.label(text=msg.timestamp)
                    _draw_wrapped_text(box_u, getattr(msg, "content", ""), max_chars=18)

                elif role == 'assistant':
                    box_a = layout.box()
                    row_a = box_a.row(align=True)
                    m_name = getattr(msg, "model_name", "") or display_model_id
                    short_m = m_name.replace("sensenova-", "").replace("deepseek-", "")
                    row_a.label(text=f"M8 AI ({short_m})", icon=_ICON("CONSOLE"))
                    if getattr(msg, "timestamp", ""):
                        row_a.label(text=msg.timestamp)

                    # 1. 思考过程模块
                    thinking = getattr(msg, "thinking", "").strip()
                    is_active = getattr(msg, "is_thinking_active", False)
                    if thinking or is_active:
                        box_th = box_a.box()
                        row_th_btn = box_th.row(align=True)
                        show_th = getattr(msg, "show_thinking", False)

                        if is_active:
                            row_th_btn.label(text=_T("💭 思考中 (实时输出)..."), icon=_ICON("TIME"))
                        else:
                            th_icon = _ICON("DOWNARROW_HLT") if show_th else _ICON("RIGHTARROW")
                            th_text = _T("💭 思考过程 (收起)") if show_th else _T("💭 思考过程 (展开)")
                            op_th = row_th_btn.operator("m8.ai_toggle_thinking", text=th_text, icon=th_icon, emboss=False)
                            op_th.msg_index = idx

                        if show_th or is_active:
                            col_th_content = box_th.column(align=True)
                            th_lines = wrap_text_smart(thinking, max_width=24) if thinking else []

                            if is_active:
                                # 实时生成中：显示最新 5~6 行滚动窗口，保持框体高度稳定
                                display_lines = th_lines[-6:] if len(th_lines) > 6 else th_lines
                                for line in display_lines:
                                    col_th_content.label(text=line)
                                row_cur = col_th_content.row(align=True)
                                row_cur.label(text="▌", icon=_ICON("TIME"))
                            else:
                                # 已完成思考：限制显示前 6 行，支持展开全部与折叠限制
                                show_full_th = getattr(msg, "show_full_thinking", False)
                                if len(th_lines) > 6:
                                    display_lines = th_lines if show_full_th else th_lines[:6]
                                    for line in display_lines:
                                        col_th_content.label(text=line)
                                    row_th_lim = col_th_content.row(align=True)
                                    lim_text = _T("🔼 限制长度 (折叠为 6 行)") if show_full_th else f"... ({_T('展开剩余')} {len(th_lines) - 6} {_T('行思考')})"
                                    lim_icon = _ICON("TRIA_UP") if show_full_th else _ICON("TRIA_DOWN")
                                    op_th_lim = row_th_lim.operator("m8.ai_toggle_full_thinking", text=lim_text, icon=lim_icon, emboss=False)
                                    op_th_lim.msg_index = idx
                                else:
                                    for line in th_lines:
                                        col_th_content.label(text=line)

                    # 2. 提取文本说明与 Python 代码
                    content = getattr(msg, "content", "").strip()
                    code = getattr(msg, "code", "").strip()
                    explanation, extracted_code = split_markdown_response(content)
                    if not code:
                        code = extracted_code or clean_markdown_code(content)

                    # 3. 渲染说明文本
                    if explanation:
                        box_exp = box_a.box()
                        _draw_wrapped_text(box_exp, explanation, max_chars=20)

                    # 4. 渲染代码预览卡片与操作按钮
                    if code:
                        box_code = box_a.box()
                        code_lines = code.strip().splitlines()
                        row_c_head = box_code.row(align=True)
                        row_c_head.label(text=_T("🐍 Python 代码 (%d 行)") % len(code_lines), icon=_ICON("FILE_SCRIPT"))

                        col_c_preview = box_code.column(align=True)
                        show_full = getattr(msg, "show_full_code", False)
                        preview_lines = code_lines if show_full else code_lines[:4]
                        for cl in preview_lines:
                            col_c_preview.label(text=cl[:34])
                        if len(code_lines) > 4:
                            row_tog = col_c_preview.row(align=True)
                            tog_text = _T("🔼 折叠代码") if show_full else (_T("... (展开剩余 %d 行)") % (len(code_lines) - 4))
                            tog_icon = _ICON("TRIA_UP") if show_full else _ICON("TRIA_DOWN")
                            op_tog = row_tog.operator("m8.ai_toggle_full_code", text=tog_text, icon=tog_icon, emboss=False)
                            op_tog.msg_index = idx

                        # 消息级快捷操作栏
                        row_acts = box_a.row(align=True)
                        row_acts.scale_y = 1.15
                        op_apply = row_acts.operator("m8.ai_apply_message_code", text=_T("写入脚本"), icon=_ICON("FILE_SCRIPT"))
                        op_apply.msg_index = idx
                        op_run = row_acts.operator("m8.ai_run_message_code", text=_T("运行测试"), icon=_ICON("PLAY"))
                        op_run.msg_index = idx
                        op_copy = row_acts.operator("m8.ai_copy_message_code", text=_T("复制"), icon=_ICON("COPYDOWN"))
                        op_copy.msg_index = idx

                    # 5. 错误信息呈现
                    error_msg = getattr(msg, "error_msg", "").strip()
                    if error_msg:
                        box_err_msg = box_a.box()
                        box_err_msg.alert = True
                        row_err_title = box_err_msg.row(align=True)
                        row_err_title.label(text=_T("❌ 请求异常:"), icon=_ICON("ERROR"))
                        _draw_wrapped_text(box_err_msg, error_msg, max_chars=20)

        # -------------------------------------------------------------
        # 3. 正在思考干活状态栏 (Live Thinking State)
        # -------------------------------------------------------------
        has_active_bubble = (chat_history is not None and len(chat_history) > 0 and getattr(chat_history[-1], "is_thinking_active", False))
        if is_generating and not has_active_bubble:
            box_live = layout.box()
            row_l_head = box_live.row(align=True)
            row_l_head.label(text=_T("🧠 M8 AI 正在深入思考与编写中..."), icon=_ICON("TIME"))
            sec = getattr(ai_props, "live_thinking_seconds", 0.0)
            if sec > 0:
                row_l_head.label(text=f"{sec:.1f}s")

            step = getattr(ai_props, "live_thinking_step", "")
            if step:
                col_steps = box_live.column(align=True)
                _draw_wrapped_text(col_steps, f"» {step}", max_chars=22)

        # -------------------------------------------------------------
        # 4. 底栏对话输入框 (Bottom Chat Input Bar)
        # -------------------------------------------------------------
        layout.separator(factor=0.4)
        box_chat_input = layout.box()

        col_p = box_chat_input.column(align=True)
        col_p.label(text=_T("需求描述 / 对话指令:"), icon=_ICON("TEXT"))
        if hasattr(ai_props, "prompt"):
            col_p.prop(ai_props, "prompt", text="")

        row_send_line = box_chat_input.row(align=True)
        row_send_line.scale_y = 1.25

        if hasattr(ai_props, "target_mode"):
            row_send_line.prop(ai_props, "target_mode", text="")

        if is_generating:
            row_send_line.label(text=_T("⏳ 正在思考与生成中..."), icon=_ICON("TIME"))
        else:
            op_send = row_send_line.operator("m8.ai_generate_code", text=_T("🚀 发送需求"), icon=_ICON("LIGHT"))
            op_send.action = 'GENERATE'

        # 辅助功能行
        row_helpers = box_chat_input.row(align=True)
        row_helpers.operator("m8.ai_fix_error", text=_T("🛠️ 诊断报错"), icon=_ICON("TOOL_SETTINGS"))
        op_explain = row_helpers.operator("m8.ai_generate_code", text=_T("🔍 解释代码"), icon=_ICON("HELP"))
        op_explain.action = 'EXPLAIN'
        op_refactor = row_helpers.operator("m8.ai_generate_code", text=_T("⚡ 优化重构"), icon=_ICON("AUTO"))
        op_refactor.action = 'REFACTOR'

        # 生成参数微调行
        row_cfg = box_chat_input.row(align=True)
        if hasattr(ai_props, "auto_apply_to_editor"):
            row_cfg.prop(ai_props, "auto_apply_to_editor", text=_T("自动写入编辑器"))
        if hasattr(ai_props, "temperature"):
            row_cfg.prop(ai_props, "temperature", text=_T("随机度"), slider=True)

        # -------------------------------------------------------------
        # 5. 最近报错展开诊断
        # -------------------------------------------------------------
        last_error = getattr(ai_props, "last_error", "")
        if last_error:
            box_err = layout.box()
            box_err.alert = True
            row_err_header = box_err.row(align=True)
            row_err_header.label(text=_T("检测到最近脚本异常"), icon=_ICON("ERROR"))
            row_err_header.operator("m8.ai_fix_error", text=_T("一键修复"), icon=_ICON("TOOL_SETTINGS"))

            last_line = last_error.strip().splitlines()[-1] if last_error else ""
            if last_line:
                _draw_wrapped_text(box_err, last_line, max_chars=22)


CLASSES = (
    TEXT_PT_M8_AI_Assistant,
)
