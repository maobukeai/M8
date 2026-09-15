"""Data models and property groups for M8 AI Assistant."""

import bpy
from ..utils.i18n import _T
from ..utils.adapter import get_adapter_blender_icon as _ICON

DEFAULT_PROVIDERS = [
    {
        "id": "sensenova",
        "name": "sensenova",
        "base_url": "https://api.sensenova.cn/compatible-mode/v1",
        "api_key": "",
        "models": "",
        "fetched_models": "",
        "enabled": True,
    },
    {
        "id": "google",
        "name": "谷歌",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "models": "",
        "fetched_models": "",
        "enabled": True,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "models": "",
        "fetched_models": "",
        "enabled": True,
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "models": "",
        "fetched_models": "",
        "enabled": True,
    },
    {
        "id": "zhipu",
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "models": "",
        "fetched_models": "",
        "enabled": True,
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "api_key": "",
        "models": "",
        "fetched_models": "",
        "enabled": True,
    },
]


class M8_AI_Provider_Item(bpy.types.PropertyGroup):
    """Configuration item for an AI Provider and its models."""
    id: bpy.props.StringProperty(name="厂商ID", default="")
    name: bpy.props.StringProperty(name="厂商名称", default="Custom")
    base_url: bpy.props.StringProperty(name="API 端点", default="https://api.openai.com/v1")
    api_key: bpy.props.StringProperty(name="API Key", subtype='PASSWORD', default="")
    models: bpy.props.StringProperty(
        name="模型列表",
        default="",
        description=_T("支持的模型列表，以英文逗号分隔")
    )
    fetched_models: bpy.props.StringProperty(
        name="已获取模型缓存",
        default="",
        description=_T("从 API 获取到的可用模型列表，以英文逗号分隔")
    )
    is_fetching_models: bpy.props.BoolProperty(
        name="正在获取模型",
        default=False
    )
    fetch_status: bpy.props.StringProperty(
        name="获取模型状态",
        default=""
    )
    fetch_message: bpy.props.StringProperty(
        name="获取模型信息",
        default=""
    )
    fetch_time: bpy.props.StringProperty(
        name="获取模型时间",
        default=""
    )
    is_testing_connection: bpy.props.BoolProperty(
        name="正在测试连通性",
        default=False
    )
    test_status: bpy.props.StringProperty(
        name="连通性测试状态",
        default=""
    )
    test_message: bpy.props.StringProperty(
        name="连通性测试信息",
        default=""
    )
    test_time: bpy.props.StringProperty(
        name="连通性测试时间",
        default=""
    )
    test_model_used: bpy.props.StringProperty(
        name="测试所用模型",
        default=""
    )
    show_advanced_models_edit: bpy.props.BoolProperty(
        name="批量文本编辑",
        default=False,
        description=_T("展开原始文本框以进行批量复制粘贴")
    )
    enabled: bpy.props.BoolProperty(name="启用", default=True)


class M8_UL_AI_Provider_List(bpy.types.UIList):
    """UIList to display and select AI Providers in Preferences."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # 1. 启用复选框
            row.prop(item, "enabled", text="", icon=_ICON("CHECKBOX_HLT") if item.enabled else _ICON("CHECKBOX_DEHLT"), emboss=False)

            # 2. 厂商名称（若已配置模型则追加紧凑数量，合并为单 Label 彻底杜绝文字挤压截断）
            models_list = [m.strip() for m in item.models.split(",") if m.strip()]
            display_name = item.name or _T("未命名厂商")
            if models_list:
                display_name = f"{display_name} ({len(models_list)})"

            row.label(text=display_name)

            # 3. 紧凑状态角标：已配Key(锁) / 未填Key(开锁) / 本地免Key(磁盘缓存)
            sub = row.row(align=True)
            sub.alignment = 'RIGHT'
            if item.id == "ollama" or "localhost" in item.base_url or "127.0.0.1" in item.base_url:
                sub.label(text="", icon=_ICON("FILE_CACHE"))
            elif item.api_key.strip():
                sub.label(text="", icon=_ICON("LOCKED"))
            else:
                sub.label(text="", icon=_ICON("UNLOCKED"))
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name or "Provider")


class M8_AI_ChatMessage_Item(bpy.types.PropertyGroup):
    """Single message item in M8 AI Chat conversation stream."""
    role: bpy.props.StringProperty(name="角色", default="user")  # 'user' | 'assistant'
    content: bpy.props.StringProperty(name="内容", default="", maxlen=0)
    code: bpy.props.StringProperty(name="提取代码", default="", maxlen=0)
    thinking: bpy.props.StringProperty(name="思考过程", default="", maxlen=0)
    show_thinking: bpy.props.BoolProperty(name="展开思考", default=False)
    show_full_thinking: bpy.props.BoolProperty(name="展开全部思考", default=False)
    show_full_code: bpy.props.BoolProperty(name="展开完整代码", default=False)
    is_thinking_active: bpy.props.BoolProperty(name="正在输出思考", default=False)
    timestamp: bpy.props.StringProperty(name="时间戳", default="")
    model_name: bpy.props.StringProperty(name="模型名称", default="")
    action_type: bpy.props.StringProperty(name="动作类型", default="GENERATE")  # GENERATE | EXPLAIN | REFACTOR | FIX
    error_msg: bpy.props.StringProperty(name="错误信息", default="", maxlen=0)


class M8_AI_Scene_Properties(bpy.types.PropertyGroup):
    """Scene-level state and parameters for M8 AI Assistant."""
    prompt: bpy.props.StringProperty(
        name=_T("需求描述"),
        description=_T("输入您希望生成的脚本需求或建模指令"),
        default=""
    )
    chat_history: bpy.props.CollectionProperty(type=M8_AI_ChatMessage_Item)
    chat_history_active_index: bpy.props.IntProperty(name="Active Message", default=-1)

    target_mode: bpy.props.EnumProperty(
        name=_T("目标模式"),
        items=[
            ('NEW', _T("新建"), _T("生成并创建为新的文本块")),
            ('REPLACE', _T("覆盖"), _T("替换当前文本块的内容")),
            ('APPEND', _T("追加"), _T("将生成内容追加到当前脚本末尾")),
            ('INSERT', _T("插入"), _T("在光标所在位置插入生成代码")),
        ],
        default='NEW'
    )
    auto_apply_to_editor: bpy.props.BoolProperty(
        name=_T("自动写入编辑器"),
        description=_T("代码生成后自动写入文本编辑器中"),
        default=True
    )
    status_message: bpy.props.StringProperty(
        name=_T("状态"),
        default=_T("就绪")
    )
    is_generating: bpy.props.BoolProperty(
        name=_T("生成中"),
        default=False
    )
    live_thinking_step: bpy.props.StringProperty(
        name=_T("当前思考步骤"),
        default=""
    )
    live_thinking_seconds: bpy.props.FloatProperty(
        name=_T("思考耗时"),
        default=0.0
    )
    last_error: bpy.props.StringProperty(
        name=_T("最近报错信息"),
        default=""
    )
    system_prompt: bpy.props.StringProperty(
        name=_T("系统提示词"),
        default=_T("你是一名精通 Blender Python (bpy) 的资深专家。当前运行环境为 Blender 4.2+ / 5.x。请严格遵守 Blender 最新 API 规范，直接输出高质量、健壮的纯 Python 代码。注意：基本网格必须使用 `bpy.ops.mesh.*_add`（如 `primitive_torus_add` 等，切勿写成 object 命名空间），不可传递 scale 关键字；平滑着色使用 bpy.ops.object.shade_smooth()；不要包含任何无关问候与冗余说明。")
    )
    temperature: bpy.props.FloatProperty(
        name=_T("随机度 (Temperature)"),
        default=0.3,
        min=0.0,
        max=2.0
    )


CLASSES = (
    M8_AI_Provider_Item,
    M8_UL_AI_Provider_List,
    M8_AI_ChatMessage_Item,
    M8_AI_Scene_Properties,
)


def register_scene_properties():
    bpy.types.Scene.m8_ai = bpy.props.PointerProperty(type=M8_AI_Scene_Properties)


def unregister_scene_properties():
    if hasattr(bpy.types.Scene, "m8_ai"):
        del bpy.types.Scene.m8_ai


def register():
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass
    register_scene_properties()


def unregister():
    unregister_scene_properties()
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
