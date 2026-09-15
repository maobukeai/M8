"""Operators and cascading menus for AI Provider and Model selection."""

import bpy
from ...utils.i18n import _T
from ...utils.adapter import get_adapter_blender_icon as _ICON, tag_redraw_all_areas
from ...property.keymap_helpers import _get_addon_prefs
from ...property.ai_properties import DEFAULT_PROVIDERS


class M8_OT_AI_SelectModel(bpy.types.Operator):
    """切换当前使用的 AI 厂商与模型"""
    bl_idname = "m8.ai_select_model"
    bl_label = _T("选择模型")
    bl_description = _T("将选中的模型设为当前活跃模型")
    bl_options = {'INTERNAL'}

    provider_id: bpy.props.StringProperty(name="厂商ID")
    model_id: bpy.props.StringProperty(name="模型ID")

    def execute(self, context):
        prefs = _get_addon_prefs()
        if prefs:
            prefs.active_provider_id = self.provider_id
            prefs.active_model_id = self.model_id

        # Update scene status
        scene = context.scene
        if hasattr(scene, "m8_ai"):
            scene.m8_ai.status_message = f"{_T('已选择')}: {self.model_id}"

        # Request redraw across all windows
        tag_redraw_all_areas({'TEXT_EDITOR', 'PREFERENCES'})

        self.report({'INFO'}, f"{_T('已切换模型')}: {self.provider_id} > {self.model_id}")
        return {'FINISHED'}


class M8_OT_AI_AddProvider(bpy.types.Operator):
    """添加一个新的 AI 厂商配置"""
    bl_idname = "m8.ai_add_provider"
    bl_label = _T("添加厂商")
    bl_description = _T("添加一个新的自定义 AI 厂商配置项")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        item = prefs.ai_providers.add()
        item.id = f"custom_{len(prefs.ai_providers)}"
        item.name = _T("新厂商")
        item.base_url = "https://api.openai.com/v1"
        item.models = ""
        item.enabled = True
        prefs.ai_providers_active_index = len(prefs.ai_providers) - 1

        self.report({'INFO'}, _T("已添加新厂商"))
        return {'FINISHED'}


class M8_OT_AI_RemoveProvider(bpy.types.Operator):
    """删除当前选中的 AI 厂商配置"""
    bl_idname = "m8.ai_remove_provider"
    bl_label = _T("删除厂商")
    bl_description = _T("删除选中的 AI 厂商配置")
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty(name="索引", default=-1)

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            return {'CANCELLED'}

        idx = self.index if self.index >= 0 else prefs.ai_providers_active_index
        if 0 <= idx < len(prefs.ai_providers):
            p_name = prefs.ai_providers[idx].name
            prefs.ai_providers.remove(idx)
            prefs.ai_providers_active_index = max(0, min(idx, len(prefs.ai_providers) - 1))
            self.report({'INFO'}, f"{_T('已删除厂商')}: {p_name}")
            return {'FINISHED'}

        return {'CANCELLED'}


class M8_OT_AI_MoveProvider(bpy.types.Operator):
    """上下移动厂商配置项"""
    bl_idname = "m8.ai_move_provider"
    bl_label = _T("移动厂商")
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")],
        default='UP'
    )

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            return {'CANCELLED'}

        idx = prefs.ai_providers_active_index
        total = len(prefs.ai_providers)

        if self.direction == 'UP' and idx > 0:
            prefs.ai_providers.move(idx, idx - 1)
            prefs.ai_providers_active_index = idx - 1
            return {'FINISHED'}
        elif self.direction == 'DOWN' and idx < total - 1:
            prefs.ai_providers.move(idx, idx + 1)
            prefs.ai_providers_active_index = idx + 1
            return {'FINISHED'}

        return {'CANCELLED'}


class M8_OT_AI_ResetProviders(bpy.types.Operator):
    """恢复默认的内置厂商和模型预设"""
    bl_idname = "m8.ai_reset_providers"
    bl_label = _T("恢复默认厂商预设")
    bl_description = _T("清空并重新初始化内置的厂商列表（SenseNova, 谷歌, DeepSeek, OpenAI, 智谱, Ollama等）")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        prefs.ai_providers.clear()
        for p in DEFAULT_PROVIDERS:
            item = prefs.ai_providers.add()
            item.id = p["id"]
            item.name = p["name"]
            item.base_url = p["base_url"]
            item.api_key = p["api_key"]
            item.models = p["models"]
            item.fetched_models = p.get("fetched_models", p["models"])
            item.enabled = p["enabled"]

        prefs.ai_providers_active_index = 0
        prefs.active_provider_id = "sensenova"
        prefs.active_model_id = ""

        self.report({'INFO'}, _T("已恢复默认厂商列表（无预设模型）"))
        return {'FINISHED'}


class M8_OT_AI_ClearAllProviderModels(bpy.types.Operator):
    """一键清空所有厂商已配置和已获取的模型列表（保留 API Key 和基础配置）"""
    bl_idname = "m8.ai_clear_all_provider_models"
    bl_label = _T("清空所有模型")
    bl_description = _T("清空所有厂商的模型列表，回归零内置模型状态（保留您填写的 API Key 和端点）")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            return {'CANCELLED'}

        for p in prefs.ai_providers:
            p.models = ""
            p.fetched_models = ""
            p.fetch_status = ""
            p.fetch_message = ""
            p.test_status = ""
            p.test_message = ""

        prefs.active_model_id = ""

        for area in context.screen.areas:
            if area.type in {'PREFERENCES', 'TEXT_EDITOR'}:
                area.tag_redraw()

        self.report({'INFO'}, _T("已清空所有厂商的模型列表（保留 API Key）"))
        return {'FINISHED'}


class M8_OT_AI_ClearProviderModels(bpy.types.Operator):
    """清空当前选定厂商的已配置模型列表"""
    bl_idname = "m8.ai_clear_provider_models"
    bl_label = _T("清空模型列表")
    bl_description = _T("清空当前选定厂商的所有已配置模型")
    bl_options = {'INTERNAL'}

    provider_id: bpy.props.StringProperty(name="厂商ID", default="")

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            return {'CANCELLED'}

        target_p = None
        if self.provider_id:
            for p in prefs.ai_providers:
                if p.id == self.provider_id:
                    target_p = p
                    break
        if not target_p and 0 <= prefs.ai_providers_active_index < len(prefs.ai_providers):
            target_p = prefs.ai_providers[prefs.ai_providers_active_index]

        if not target_p:
            return {'CANCELLED'}

        target_p.models = ""
        if prefs.active_provider_id == target_p.id:
            prefs.active_model_id = ""

        tag_redraw_all_areas({'PREFERENCES', 'TEXT_EDITOR'})
        self.report({'INFO'}, f"{_T('已清空厂商')} '{target_p.name}' {_T('的模型列表')}")
        return {'FINISHED'}


class M8_OT_AI_TestConnection(bpy.types.Operator):
    """测试当前厂商 API 连通性"""
    bl_idname = "m8.ai_test_connection"
    bl_label = _T("测试连通性")
    bl_description = _T("向该厂商发送简单 Ping 请求以验证 Base URL 与 API Key 是否有效")
    bl_options = {'INTERNAL'}

    provider_id: bpy.props.StringProperty(name="厂商ID", default="")

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            self.report({'WARNING'}, _T("未配置厂商"))
            return {'CANCELLED'}

        # Find provider
        target_p = None
        if self.provider_id:
            for p in prefs.ai_providers:
                if p.id == self.provider_id:
                    target_p = p
                    break

        if not target_p:
            idx = prefs.ai_providers_active_index
            if 0 <= idx < len(prefs.ai_providers):
                target_p = prefs.ai_providers[idx]

        if not target_p:
            self.report({'WARNING'}, _T("未找到有效厂商"))
            return {'CANCELLED'}

        test_model = ""
        if getattr(prefs, "active_provider_id", "") == target_p.id and getattr(prefs, "active_model_id", "").strip():
            test_model = prefs.active_model_id.strip()

        if not test_model:
            models = [m.strip() for m in target_p.models.split(",") if m.strip()]
            if models:
                test_model = models[0]

        if not test_model and getattr(target_p, "fetched_models", "").strip():
            fetched = [m.strip() for m in target_p.fetched_models.split(",") if m.strip()]
            if fetched:
                test_model = fetched[0]

        if not test_model:
            target_p.test_status = "ERROR"
            target_p.test_message = _T("未配置模型：请先点击【🔄 从 API 获取可用模型】或【+ 手动添加】至少一个模型后再测试")
            self.report({'WARNING'}, _T("当前厂商尚未配置任何模型，请先获取或手动添加模型"))
            for area in context.screen.areas:
                if area.type in {'PREFERENCES', 'TEXT_EDITOR'}:
                    area.tag_redraw()
            return {'CANCELLED'}

        p_id = target_p.id
        p_name = target_p.name
        target_p.is_testing_connection = True
        target_p.test_status = ""
        target_p.test_message = f"{_T('正在向')} {p_name} ({test_model}) {_T('发起 Ping 请求...')}"
        target_p.test_model_used = test_model

        for area in context.screen.areas:
            if area.type in {'PREFERENCES', 'TEXT_EDITOR'}:
                area.tag_redraw()

        self.report({'INFO'}, f"{_T('正在测试连接')}: {target_p.name} ({test_model})...")

        from ...utils.ai_client import test_api_connection

        def _on_result(success, message):
            import time
            cur_prefs = _get_addon_prefs()
            if cur_prefs and cur_prefs.ai_providers:
                for p in cur_prefs.ai_providers:
                    if p.id == p_id:
                        p.is_testing_connection = False
                        p.test_status = "SUCCESS" if success else "ERROR"
                        p.test_message = message
                        p.test_time = time.strftime("%H:%M:%S")
                        break

            scene = bpy.context.scene
            if hasattr(scene, "m8_ai"):
                scene.m8_ai.status_message = message
            tag_redraw_all_areas({'TEXT_EDITOR', 'PREFERENCES'})

        test_api_connection(
            base_url=target_p.base_url,
            api_key=target_p.api_key,
            model=test_model,
            callback=_on_result,
        )

        return {'FINISHED'}


class M8_OT_AI_FetchModels(bpy.types.Operator):
    """从 API 自动拉取当前厂商支持的可用模型列表"""
    bl_idname = "m8.ai_fetch_models"
    bl_label = _T("从 API 获取可用模型")
    bl_description = _T("向厂商 API 发送请求，自动查询并获取该服务支持的所有可用模型列表")
    bl_options = {'INTERNAL'}

    provider_id: bpy.props.StringProperty(name="厂商ID", default="")

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            self.report({'WARNING'}, _T("未配置厂商"))
            return {'CANCELLED'}

        target_p = None
        if self.provider_id:
            for p in prefs.ai_providers:
                if p.id == self.provider_id:
                    target_p = p
                    break

        if not target_p:
            idx = prefs.ai_providers_active_index
            if 0 <= idx < len(prefs.ai_providers):
                target_p = prefs.ai_providers[idx]

        if not target_p:
            self.report({'WARNING'}, _T("未找到有效厂商"))
            return {'CANCELLED'}

        if not target_p.base_url.strip():
            self.report({'WARNING'}, _T("API 端点 (Base URL) 不能为空"))
            return {'CANCELLED'}

        target_p.is_fetching_models = True
        target_p.fetch_status = ""
        p_name = target_p.name
        p_id = target_p.id
        target_p.fetch_message = f"{_T('正在从')} {p_name} {_T('拉取可用模型...')}"

        for area in context.screen.areas:
            if area.type in {'PREFERENCES', 'TEXT_EDITOR'}:
                area.tag_redraw()

        self.report({'INFO'}, f"{_T('正在从')} {p_name} {_T('获取模型列表...')}")

        from ...utils.ai_client import fetch_models_async

        def _on_success(models):
            import time
            cur_prefs = _get_addon_prefs()
            if not cur_prefs or not cur_prefs.ai_providers:
                return

            p_obj = None
            for p in cur_prefs.ai_providers:
                if p.id == p_id:
                    p_obj = p
                    break

            if p_obj:
                p_obj.is_fetching_models = False
                p_obj.fetched_models = ", ".join(models)
                p_obj.fetch_status = "SUCCESS"
                p_obj.fetch_time = time.strftime("%H:%M:%S")
                p_obj.fetch_message = f"{_T('成功获取')} {len(models)} {_T('个可用模型，请在下方选择添加')}"

            scene = bpy.context.scene
            if hasattr(scene, "m8_ai"):
                scene.m8_ai.status_message = f"{_T('成功获取')} {len(models)} {_T('个可用模型')}"

            tag_redraw_all_areas({'PREFERENCES', 'TEXT_EDITOR'})

        def _on_error(err):
            import time
            cur_prefs = _get_addon_prefs()
            if cur_prefs and cur_prefs.ai_providers:
                for p in cur_prefs.ai_providers:
                    if p.id == p_id:
                        p.is_fetching_models = False
                        p.fetch_status = "ERROR"
                        p.fetch_time = time.strftime("%H:%M:%S")
                        clean_err = str(err).strip().replace("\r", " ").replace("\n", " ")
                        if len(clean_err) > 80:
                            clean_err = clean_err[:80] + "..."
                        p.fetch_message = f"{_T('获取失败')}: {clean_err}"
                        break

            scene = bpy.context.scene
            if hasattr(scene, "m8_ai"):
                scene.m8_ai.status_message = f"{_T('获取模型失败')}: {err}"

            tag_redraw_all_areas({'PREFERENCES', 'TEXT_EDITOR'})

        fetch_models_async(
            base_url=target_p.base_url,
            api_key=target_p.api_key,
            timeout=15,
            on_success=_on_success,
            on_error=_on_error,
        )

        return {'FINISHED'}


class M8_OT_AI_AddModelToProvider(bpy.types.Operator):
    """向指定厂商添加一个模型"""
    bl_idname = "m8.ai_add_model_to_provider"
    bl_label = _T("添加模型")
    bl_description = _T("将选定模型添加到该厂商的模型列表中")
    bl_options = {'REGISTER', 'UNDO'}

    provider_id: bpy.props.StringProperty(name="厂商ID", default="")
    model_name: bpy.props.StringProperty(name="模型名称", default="")

    def execute(self, context):
        name = self.model_name.strip()
        if not name:
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        target_p = None
        if self.provider_id:
            for p in prefs.ai_providers:
                if p.id == self.provider_id:
                    target_p = p
                    break
        if not target_p and 0 <= prefs.ai_providers_active_index < len(prefs.ai_providers):
            target_p = prefs.ai_providers[prefs.ai_providers_active_index]

        if not target_p:
            return {'CANCELLED'}

        models = [m.strip() for m in target_p.models.split(",") if m.strip()]
        if name in models:
            self.report({'INFO'}, f"{_T('模型已存在')}: {name}")
            return {'FINISHED'}

        # Remove default placeholders
        models = [m for m in models if m not in ("model-1", "model-2")]
        models.append(name)
        target_p.models = ", ".join(models)

        if len(models) == 1 and (not getattr(prefs, "active_model_id", "") or getattr(prefs, "active_provider_id", "") == target_p.id):
            prefs.active_provider_id = target_p.id
            prefs.active_model_id = name

        tag_redraw_all_areas({'PREFERENCES', 'TEXT_EDITOR'})

        self.report({'INFO'}, f"{_T('已添加模型')}: {name}")
        return {'FINISHED'}


class M8_OT_AI_RemoveModelFromProvider(bpy.types.Operator):
    """从指定厂商中删除一个模型"""
    bl_idname = "m8.ai_remove_model_from_provider"
    bl_label = _T("删除模型")
    bl_description = _T("从该厂商的模型列表中移除此模型")
    bl_options = {'REGISTER', 'UNDO'}

    provider_id: bpy.props.StringProperty(name="厂商ID", default="")
    model_name: bpy.props.StringProperty(name="模型名称", default="")

    def execute(self, context):
        name = self.model_name.strip()
        if not name:
            return {'CANCELLED'}

        prefs = _get_addon_prefs()
        if not prefs:
            return {'CANCELLED'}

        target_p = None
        if self.provider_id:
            for p in prefs.ai_providers:
                if p.id == self.provider_id:
                    target_p = p
                    break
        if not target_p and 0 <= prefs.ai_providers_active_index < len(prefs.ai_providers):
            target_p = prefs.ai_providers[prefs.ai_providers_active_index]

        if not target_p:
            return {'CANCELLED'}

        models = [m.strip() for m in target_p.models.split(",") if m.strip()]
        if name in models:
            models.remove(name)
            target_p.models = ", ".join(models)

            # If the removed model was active, update active model
            if prefs.active_provider_id == target_p.id and prefs.active_model_id == name:
                prefs.active_model_id = models[0] if models else ""

            tag_redraw_all_areas({'PREFERENCES', 'TEXT_EDITOR'})

            self.report({'INFO'}, f"{_T('已移除模型')}: {name}")
            return {'FINISHED'}

        return {'CANCELLED'}


class M8_OT_AI_PromptAddModel(bpy.types.Operator):
    """弹窗手动输入添加模型"""
    bl_idname = "m8.ai_prompt_add_model"
    bl_label = _T("手动添加模型")
    bl_description = _T("弹出输入框手动填写并添加一个自定义模型标识")
    bl_options = {'REGISTER', 'UNDO'}

    provider_id: bpy.props.StringProperty(name="厂商ID", default="")
    model_name: bpy.props.StringProperty(
        name=_T("模型标识 (Model ID)"),
        description=_T("输入您想要添加的模型名称，如 deepseek-chat、gpt-4o、qwen2.5-coder:7b"),
        default=""
    )

    def invoke(self, context, event):
        self.model_name = ""
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=_T("输入需要添加的模型 ID："), icon=_ICON("INFO"))
        col.prop(self, "model_name", text="")

    def execute(self, context):
        name = self.model_name.strip()
        if not name:
            self.report({'WARNING'}, _T("模型名称不能为空"))
            return {'CANCELLED'}

        op = bpy.ops.m8.ai_add_model_to_provider(provider_id=self.provider_id, model_name=name)
        return {'FINISHED'}


class M8_OT_AI_AddAllFetchedModels(bpy.types.Operator):
    """一键将所有从 API 获取到的模型加入配置列表"""
    bl_idname = "m8.ai_add_all_fetched_models"
    bl_label = _T("一键添加全部已获取模型")
    bl_description = _T("将当前从 API 拉取到的所有可用模型批量追加到配置列表中")
    bl_options = {'REGISTER', 'UNDO'}

    provider_id: bpy.props.StringProperty(name="厂商ID", default="")

    def execute(self, context):
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            return {'CANCELLED'}

        target_p = None
        if self.provider_id:
            for p in prefs.ai_providers:
                if p.id == self.provider_id:
                    target_p = p
                    break
        if not target_p and 0 <= prefs.ai_providers_active_index < len(prefs.ai_providers):
            target_p = prefs.ai_providers[prefs.ai_providers_active_index]

        if not target_p:
            return {'CANCELLED'}

        fetched = [m.strip() for m in target_p.fetched_models.split(",") if m.strip()]
        if not fetched:
            self.report({'WARNING'}, _T("尚未从 API 获取到模型，请先点击获取按钮"))
            return {'CANCELLED'}

        cur_models = [m.strip() for m in target_p.models.split(",") if m.strip()]
        cur_models = [m for m in cur_models if m not in ("model-1", "model-2")]

        added_count = 0
        for m in fetched:
            if m not in cur_models:
                cur_models.append(m)
                added_count += 1

        target_p.models = ", ".join(cur_models)
        if cur_models and (not getattr(prefs, "active_model_id", "") or getattr(prefs, "active_provider_id", "") == target_p.id):
            prefs.active_provider_id = target_p.id
            prefs.active_model_id = cur_models[0]

        tag_redraw_all_areas({'PREFERENCES', 'TEXT_EDITOR'})

        self.report({'INFO'}, f"{_T('成功添加')} {added_count} {_T('个新模型')}")
        return {'FINISHED'}


class M8_MT_AI_AddFetchedModelMenu(bpy.types.Menu):
    """从已获取模型列表中选择添加的下拉菜单"""
    bl_idname = "M8_MT_ai_add_fetched_model_menu"
    bl_label = _T("从已获取模型中添加")

    def draw(self, context):
        layout = self.layout
        prefs = _get_addon_prefs()
        if not prefs or not prefs.ai_providers:
            layout.label(text=_T("未找到厂商信息"), icon="INFO")
            return

        idx = prefs.ai_providers_active_index
        if not (0 <= idx < len(prefs.ai_providers)):
            layout.label(text=_T("未选中厂商"), icon="INFO")
            return

        cur_p = prefs.ai_providers[idx]
        fetched_raw = cur_p.fetched_models
        fetched = [m.strip() for m in fetched_raw.split(",") if m.strip()]

        if not fetched:
            layout.label(text=_T("尚未获取模型，请先点击获取按钮"), icon="INFO")
            op = layout.operator("m8.ai_fetch_models", text=_T("从 API 获取可用模型"), icon="FILE_REFRESH")
            op.provider_id = cur_p.id
            return

        cur_models = [m.strip() for m in cur_p.models.split(",") if m.strip()]

        op_all = layout.operator("m8.ai_add_all_fetched_models", text=_T("【一键添加全部已获取模型】"), icon=_ICON("CHECKMARK"))
        op_all.provider_id = cur_p.id
        layout.separator()

        for m in fetched:
            if m in cur_models:
                row = layout.row()
                row.enabled = False
                row.label(text=f"{m} ({_T('已在列表')})", icon=_ICON("CHECKBOX_HLT"))
            else:
                op = layout.operator("m8.ai_add_model_to_provider", text=f"+ {m}", icon=_ICON("ADD"))
                op.provider_id = cur_p.id
                op.model_name = m


class M8_OT_AI_OpenPreferences(bpy.types.Operator):
    """打开 Blender 偏好设置并直达 M8 AI 助手配置页"""
    bl_idname = "m8.ai_open_preferences"
    bl_label = _T("打开 AI 配置首选项")
    bl_description = _T("跳转到偏好设置以配置 API Key、添加或获取模型")
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
            prefs = _get_addon_prefs()
            if prefs and hasattr(prefs, "navigation_tab"):
                prefs.navigation_tab = "AI_ASSISTANT"
        except Exception:
            pass
        return {'FINISHED'}


class M8_MT_AI_Model_Menu(bpy.types.Menu):
    """AI 模型级联菜单根菜单：列出所有厂商"""
    bl_idname = "M8_MT_ai_model_menu"
    bl_label = _T("选择 AI 模型")

    def draw(self, context):
        layout = self.layout
        prefs = _get_addon_prefs()

        if not prefs or not prefs.ai_providers:
            layout.label(text=_T("未配置任何厂商"), icon="INFO")
            layout.operator("m8.ai_open_preferences", text=_T("⚙️ 打开 AI 配置首选项"), icon="PREFERENCES")
            layout.operator("m8.ai_reset_providers", text=_T("加载默认厂商预设"), icon="FILE_REFRESH")
            return

        has_enabled = False
        for i, p in enumerate(prefs.ai_providers):
            if p.enabled and i < 32:
                has_enabled = True
                # Submenu name
                sub_idname = f"M8_MT_ai_provider_sub_{i}"
                layout.menu(sub_idname, text=p.name, icon=_ICON("CONSOLE"))

        if not has_enabled:
            layout.label(text=_T("所有厂商已被禁用"), icon="INFO")

        layout.separator()
        layout.operator("m8.ai_open_preferences", text=_T("⚙️ 打开 AI 配置首选项"), icon="PREFERENCES")
        layout.operator("m8.ai_reset_providers", text=_T("恢复默认预设"), icon="FILE_REFRESH")


def _create_submenu_class(slot_idx):
    """Factory creating individual submenus for each provider slot."""
    class M8_MT_AI_Provider_Submenu(bpy.types.Menu):
        bl_idname = f"M8_MT_ai_provider_sub_{slot_idx}"
        bl_label = f"Provider Submenu {slot_idx}"
        slot_index = slot_idx

        def draw(self, context):
            layout = self.layout
            prefs = _get_addon_prefs()
            if not prefs or self.slot_index >= len(prefs.ai_providers):
                layout.label(text=_T("未找到厂商信息"))
                return

            provider = prefs.ai_providers[self.slot_index]
            models_raw = provider.models
            models = [m.strip() for m in models_raw.split(",") if m.strip()]

            if not models:
                layout.label(text=_T("未配置可用模型"), icon="INFO")
                op_f = layout.operator("m8.ai_fetch_models", text=_T("🔄 从 API 获取可用模型"), icon=_ICON("FILE_REFRESH"))
                op_f.provider_id = provider.id
                layout.operator("m8.ai_open_preferences", text=_T("⚙️ 前往首选项配置"), icon="PREFERENCES")
                return

            active_prov = getattr(prefs, "active_provider_id", "")
            active_model = getattr(prefs, "active_model_id", "")

            for m in models:
                is_active = (provider.id == active_prov and m == active_model)
                icon = "CHECKMARK" if is_active else "NONE"
                op = layout.operator("m8.ai_select_model", text=m, icon=icon)
                op.provider_id = provider.id
                op.model_id = m

            layout.separator()
            op_f = layout.operator("m8.ai_fetch_models", text=_T("🔄 刷新/获取更多模型"), icon=_ICON("FILE_REFRESH"))
            op_f.provider_id = provider.id

    M8_MT_AI_Provider_Submenu.__name__ = f"M8_MT_AI_Provider_Sub_{slot_idx}"
    return M8_MT_AI_Provider_Submenu


SUBMENU_CLASSES = tuple(_create_submenu_class(i) for i in range(32))

OPERATOR_CLASSES = (
    M8_OT_AI_SelectModel,
    M8_OT_AI_AddProvider,
    M8_OT_AI_RemoveProvider,
    M8_OT_AI_MoveProvider,
    M8_OT_AI_ResetProviders,
    M8_OT_AI_ClearAllProviderModels,
    M8_OT_AI_ClearProviderModels,
    M8_OT_AI_TestConnection,
    M8_OT_AI_FetchModels,
    M8_OT_AI_AddModelToProvider,
    M8_OT_AI_RemoveModelFromProvider,
    M8_OT_AI_PromptAddModel,
    M8_OT_AI_AddAllFetchedModels,
    M8_OT_AI_OpenPreferences,
    M8_MT_AI_AddFetchedModelMenu,
    M8_MT_AI_Model_Menu,
)

CLASSES = OPERATOR_CLASSES + SUBMENU_CLASSES
