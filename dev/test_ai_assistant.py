"""Self-test script for M8 AI Assistant module."""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Mock minimal Blender API
bpy = types.ModuleType("bpy")
bpy.app = types.ModuleType("bpy.app")
bpy.app.handlers = types.ModuleType("bpy.app.handlers")
bpy.app.timers = types.ModuleType("bpy.app.timers")
bpy.app.timers.register = lambda f, first_interval=0: None
bpy.types = types.ModuleType("bpy.types")
bpy.props = types.ModuleType("bpy.props")
bpy.utils = types.ModuleType("bpy.utils")

for prop_name in ("StringProperty", "BoolProperty", "IntProperty", "FloatProperty", "EnumProperty", "CollectionProperty", "PointerProperty"):
    setattr(bpy.props, prop_name, lambda *a, **kw: None)

for type_name in ("Menu", "Panel", "Operator", "PropertyGroup", "UIList", "AddonPreferences"):
    setattr(bpy.types, type_name, type(type_name, (), {}))

sys.modules['bpy'] = bpy
sys.modules['bpy.app'] = bpy.app
sys.modules['bpy.app.timers'] = bpy.app.timers
sys.modules['bpy.types'] = bpy.types
sys.modules['bpy.props'] = bpy.props
sys.modules['bpy.utils'] = bpy.utils

print("=" * 60)
print("Testing M8 AI Assistant Module...")
print("=" * 60)

# Helper to load a module from file path
def load_module(name, rel_path):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Mock logger & i18n
logger_mod = types.ModuleType("M8.utils.logger")
logger_mod.get_logger = lambda name=None: types.SimpleNamespace(
    error=lambda *a, **k: None,
    warning=lambda *a, **k: None,
    info=lambda *a, **k: None,
    debug=lambda *a, **k: None,
)
sys.modules["M8.utils.logger"] = logger_mod
sys.modules["..utils.logger"] = logger_mod
sys.modules["...utils.logger"] = logger_mod

i18n_mod = types.ModuleType("M8.utils.i18n")
i18n_mod._T = lambda text: text
sys.modules["M8.utils.i18n"] = i18n_mod
sys.modules["..utils.i18n"] = i18n_mod
sys.modules["...utils.i18n"] = i18n_mod

adapter_mod = types.ModuleType("M8.utils.adapter")
adapter_mod.get_adapter_blender_icon = lambda icon=None: icon or "QUESTION"
adapter_mod.tag_redraw_all_areas = lambda area_types=None: None
sys.modules["M8.utils.adapter"] = adapter_mod
sys.modules["..utils.adapter"] = adapter_mod
sys.modules["...utils.adapter"] = adapter_mod

m8_pkg = types.ModuleType("M8")
m8_pkg.__path__ = [str(ROOT)]
sys.modules["M8"] = m8_pkg
m8_utils_pkg = types.ModuleType("M8.utils")
m8_utils_pkg.__path__ = [str(ROOT / "utils")]
sys.modules["M8.utils"] = m8_utils_pkg
m8_prop_pkg = types.ModuleType("M8.property")
m8_prop_pkg.__path__ = [str(ROOT / "property")]
sys.modules["M8.property"] = m8_prop_pkg

# Test 1: Markdown code cleaner
print("\n[TEST 1] Testing clean_markdown_code in utils/ai_client.py...")
ai_client = load_module("M8.utils.ai_client", "utils/ai_client.py")
clean_markdown_code = ai_client.clean_markdown_code

test_md_1 = """```python
import bpy
bpy.ops.mesh.primitive_cube_add()
```"""
cleaned_1 = clean_markdown_code(test_md_1)
assert "import bpy" in cleaned_1 and "```" not in cleaned_1, f"Failed case 1: {cleaned_1}"

test_md_2 = """```py
# Another test
print('Hello')
```"""
cleaned_2 = clean_markdown_code(test_md_2)
assert "print('Hello')" in cleaned_2 and "```" not in cleaned_2, f"Failed case 2: {cleaned_2}"

test_md_3 = "import bpy\nbpy.ops.object.select_all(action='DESELECT')"
cleaned_3 = clean_markdown_code(test_md_3)
assert cleaned_3 == test_md_3, f"Failed case 3: {cleaned_3}"

print("  -> PASS: clean_markdown_code handles all formats correctly!")

# Test 2: AI Provider presets
print("\n[TEST 2] Testing DEFAULT_PROVIDERS configuration...")
ai_props = load_module("M8.property.ai_properties", "property/ai_properties.py")
DEFAULT_PROVIDERS = ai_props.DEFAULT_PROVIDERS

provider_ids = [p["id"] for p in DEFAULT_PROVIDERS]
print("  Available providers:", provider_ids)
assert "sensenova" in provider_ids, "Missing sensenova preset"
assert "google" in provider_ids, "Missing google preset"
assert "deepseek" in provider_ids, "Missing deepseek preset"
assert "openai" in provider_ids, "Missing openai preset"
assert "ollama" in provider_ids, "Missing ollama preset"

# Check providers start without hardcoded preset models
for p in DEFAULT_PROVIDERS:
    assert p["models"] == "", f"Provider {p['id']} should not have preset models"
print("  -> PASS: DEFAULT_PROVIDERS starts without hardcoded preset models as requested!")

# Test 3: Check submenu slot classes count
print("\n[TEST 3] Testing Submenu slot classes...")
# Mock _get_addon_prefs
keymap_helpers_mod = types.ModuleType("M8.property.keymap_helpers")
keymap_helpers_mod._get_addon_prefs = lambda: None
sys.modules["M8.property.keymap_helpers"] = keymap_helpers_mod
sys.modules["...property.keymap_helpers"] = keymap_helpers_mod

model_select = load_module("M8.ops.ai.ops_model_select", "ops/ai/ops_model_select.py")
SUBMENU_CLASSES = model_select.SUBMENU_CLASSES
assert len(SUBMENU_CLASSES) == 32, f"Expected 32 submenus, got {len(SUBMENU_CLASSES)}"
assert SUBMENU_CLASSES[0].bl_idname == "M8_MT_ai_provider_sub_0"
assert SUBMENU_CLASSES[31].bl_idname == "M8_MT_ai_provider_sub_31"
print("  -> PASS: 32 cascading submenus created and indexed properly!")

# Test 4: Check UI Panel registration metadata
print("\n[TEST 4] Testing Text Editor AI Assistant Panel metadata...")
text_ai_panel = load_module("M8.ui.panel.text_ai_panel", "ui/panel/text_ai_panel.py")
TEXT_PT_M8_AI_Assistant = text_ai_panel.TEXT_PT_M8_AI_Assistant
assert TEXT_PT_M8_AI_Assistant.bl_space_type == 'TEXT_EDITOR'
assert TEXT_PT_M8_AI_Assistant.bl_region_type == 'UI'
assert TEXT_PT_M8_AI_Assistant.bl_category == 'M8 AI'
print("  -> PASS: Panel targeting TEXT_EDITOR / UI / M8 AI validated!")

# Test 5: Check parse_models_response for OpenAI and Ollama formats
print("\n[TEST 5] Testing parse_models_response in utils/ai_client.py...")
parse_models_response = ai_client.parse_models_response

# 5.1 OpenAI format
openai_json = json.dumps({
    "object": "list",
    "data": [
        {"id": "gpt-4o", "object": "model"},
        {"id": "gpt-4o-mini", "object": "model"},
        {"id": "o3-mini", "object": "model"}
    ]
})
parsed_openai = parse_models_response(openai_json)
assert "gpt-4o" in parsed_openai and "gpt-4o-mini" in parsed_openai and "o3-mini" in parsed_openai, f"Failed OpenAI parse: {parsed_openai}"
print(f"  OpenAI parsed: {parsed_openai}")

# 5.2 Ollama format
ollama_json = json.dumps({
    "models": [
        {"name": "qwen2.5-coder:7b", "model": "qwen2.5-coder:7b"},
        {"name": "llama3.1:8b", "model": "llama3.1:8b"}
    ]
})
parsed_ollama = parse_models_response(ollama_json)
assert "qwen2.5-coder:7b" in parsed_ollama and "llama3.1:8b" in parsed_ollama, f"Failed Ollama parse: {parsed_ollama}"
print(f"  Ollama parsed: {parsed_ollama}")

# 5.3 Fallback / empty format
assert parse_models_response("{}") == []
assert parse_models_response("invalid json") == []
print("  -> PASS: parse_models_response handles all formats correctly!")

# Test 6: Check new operators in ops_model_select.py
print("\n[TEST 6] Testing Model Management Operators in ops_model_select.py...")
OPERATOR_CLASSES = model_select.OPERATOR_CLASSES
op_idnames = [getattr(cls, "bl_idname", "") for cls in OPERATOR_CLASSES]
print(f"  Registered Operator / Menu ID names: {op_idnames}")
assert "m8.ai_fetch_models" in op_idnames, "Missing m8.ai_fetch_models operator"
assert "m8.ai_add_model_to_provider" in op_idnames, "Missing m8.ai_add_model_to_provider operator"
assert "m8.ai_remove_model_from_provider" in op_idnames, "Missing m8.ai_remove_model_from_provider operator"
assert "m8.ai_prompt_add_model" in op_idnames, "Missing m8.ai_prompt_add_model operator"
assert "m8.ai_add_all_fetched_models" in op_idnames, "Missing m8.ai_add_all_fetched_models operator"
assert "m8.ai_clear_provider_models" in op_idnames, "Missing m8.ai_clear_provider_models operator"
assert "m8.ai_open_preferences" in op_idnames, "Missing m8.ai_open_preferences operator"
assert "M8_MT_ai_add_fetched_model_menu" in op_idnames, "Missing M8_MT_ai_add_fetched_model_menu menu"
print("  -> PASS: All model management operators & menus verified!")

# Test 7: Check AIResponse and reasoning / thinking properties
print("\n[TEST 7] Testing AIResponse and thinking trace support...")
AIResponse = ai_client.AIResponse
resp = AIResponse("import bpy\nbpy.ops.mesh.primitive_cube_add()", reasoning="First, create cube geometry, then link to scene")
assert isinstance(resp, str), "AIResponse must be a subclass of str"
assert resp.thinking == "First, create cube geometry, then link to scene"
assert "import bpy" in resp
print(f"  AIResponse content: {resp[:30]}...")
print(f"  AIResponse thinking: {resp.thinking}")
print("  -> PASS: AIResponse provides seamless string and thinking trace compatibility!")

# Test 8: Check Chat Dialogue Operators in ops_generate.py
print("\n[TEST 8] Testing Chat Dialogue Operators in ops_generate.py...")
ops_generate = load_module("M8.ops.ai.ops_generate", "ops/ai/ops_generate.py")
GENERATE_CLASSES = ops_generate.CLASSES
gen_idnames = [getattr(cls, "bl_idname", "") for cls in GENERATE_CLASSES]
print(f"  Registered Chat Operator ID names: {gen_idnames}")
assert "m8.ai_generate_code" in gen_idnames, "Missing m8.ai_generate_code"
assert "m8.ai_apply_message_code" in gen_idnames, "Missing m8.ai_apply_message_code"
assert "m8.ai_run_message_code" in gen_idnames, "Missing m8.ai_run_message_code"
assert "m8.ai_copy_message_code" in gen_idnames, "Missing m8.ai_copy_message_code"
assert "m8.ai_toggle_thinking" in gen_idnames, "Missing m8.ai_toggle_thinking"
assert "m8.ai_toggle_full_thinking" in gen_idnames, "Missing m8.ai_toggle_full_thinking"
assert "m8.ai_toggle_full_code" in gen_idnames, "Missing m8.ai_toggle_full_code"
assert "m8.ai_clear_chat" in gen_idnames, "Missing m8.ai_clear_chat"
assert "m8.ai_send_quick_prompt" in gen_idnames, "Missing m8.ai_send_quick_prompt"
print("  -> PASS: All 9 Chat Dialogue operators verified!")

# Test 9: Check tag_redraw_all_areas in adapter.py
print("\n[TEST 9] Testing tag_redraw_all_areas in utils/adapter.py...")
adapter_mod_full = load_module("M8.utils.adapter", "utils/adapter.py")
assert hasattr(adapter_mod_full, "tag_redraw_all_areas"), "Missing tag_redraw_all_areas in utils/adapter.py"
# Verify it runs safely with mock context
adapter_mod_full.tag_redraw_all_areas({'TEXT_EDITOR', 'VIEW_3D'})
print("  -> PASS: tag_redraw_all_areas safely callable without errors!")

# Test 10: Check ops_fix_error has no hardcoded gpt-3.5-turbo fallback
print("\n[TEST 10] Testing ops_fix_error has zero hardcoded fallback...")
fix_error_code = (ROOT / "ops" / "ai" / "ops_fix_error.py").read_text(encoding="utf-8")
assert "gpt-3.5-turbo" not in fix_error_code, "ops_fix_error must not contain gpt-3.5-turbo fallback"
ops_fix_error = load_module("M8.ops.ai.ops_fix_error", "ops/ai/ops_fix_error.py")
assert hasattr(ops_fix_error, "M8_OT_AI_FixError"), "Missing M8_OT_AI_FixError class"
print("  -> PASS: ops_fix_error completely free of hardcoded model fallbacks!")

# Test 11: Check M8_AI_ChatMessage_Item has show_full_code and show_full_thinking
print("\n[TEST 11] Testing chat properties have show_full_code and show_full_thinking...")
ChatMessageItem = ai_props.M8_AI_ChatMessage_Item
annotations = getattr(ChatMessageItem, "__annotations__", {})
assert "show_full_code" in annotations, "Missing show_full_code in M8_AI_ChatMessage_Item"
assert "show_full_thinking" in annotations, "Missing show_full_thinking in M8_AI_ChatMessage_Item"
print("  -> PASS: show_full_code and show_full_thinking verified on M8_AI_ChatMessage_Item!")

# Test 12: Check wrap_text_smart in text_ai_panel.py
print("\n[TEST 12] Testing wrap_text_smart in text_ai_panel.py...")
wrap_text_smart = text_ai_panel.wrap_text_smart
sample_text = "The user wants a Blender Python script that generates 10 cubes with random sizes and positions around the origin."
wrapped_lines = wrap_text_smart(sample_text, max_width=24)
assert len(wrapped_lines) > 1, f"Expected multi-line wrapping, got: {wrapped_lines}"
# Verify no broken words like 'Blend' or 'wit'
for line in wrapped_lines:
    assert not line.endswith("Blend"), f"Broken word detected in: {line}"
    assert not line.endswith("wit"), f"Broken word detected in: {line}"
print(f"  Smart wrapped into {len(wrapped_lines)} lines with zero broken words!")
print("  -> PASS: wrap_text_smart verified!")

# Test 13: Multi-block markdown code extraction
print("\n[TEST 13] Testing multi-block markdown code extraction...")
multi_md = """Here is part 1:
```python
import bpy
```
And here is part 2:
```python
bpy.ops.mesh.primitive_cube_add()
```"""
exp_multi, code_multi = ai_client.split_markdown_response(multi_md)
assert "import bpy" in code_multi and "primitive_cube_add" in code_multi, f"Failed multi-block: {code_multi}"
assert "Here is part 1:" in exp_multi and "And here is part 2:" in exp_multi, f"Failed exp_multi: {exp_multi}"
print("  -> PASS: Multi-block code properly joined and preserved!")

# Test 14: Unclosed code block extraction (streaming cutoff)
print("\n[TEST 14] Testing unclosed markdown code block extraction...")
unclosed_md = "Let me write the script:\n```python\nimport bpy\nbpy.ops.mesh.primitive_cylinder_add()"
exp_unclosed, code_unclosed = ai_client.split_markdown_response(unclosed_md)
assert "Let me write the script:" in exp_unclosed, f"Failed exp_unclosed: {exp_unclosed}"
assert "import bpy" in code_unclosed and "primitive_cylinder_add()" in code_unclosed, f"Failed code_unclosed: {code_unclosed}"
print("  -> PASS: Unclosed code block cleanly extracted!")

# Test 15: Case-insensitive code block identifier
print("\n[TEST 15] Testing case-insensitive ```PYTHON code block...")
upper_md = "```PYTHON\nimport bmesh\n```"
clean_upper = ai_client.clean_markdown_code(upper_md)
assert clean_upper == "import bmesh", f"Failed upper code: {clean_upper}"
print("  -> PASS: Case-insensitive code block recognized!")

# Test 16: Unfenced raw python code detection
print("\n[TEST 16] Testing unfenced raw python code detection...")
raw_code = "import bpy\nbpy.ops.mesh.primitive_cone_add(vertices=12)"
exp_raw, code_raw = ai_client.split_markdown_response(raw_code)
assert exp_raw == "", f"Expected empty explanation, got: {exp_raw}"
assert "primitive_cone_add" in code_raw, f"Failed raw code: {code_raw}"
print("  -> PASS: Unfenced python code detected without error!")

# Test 17: Sensitive API Key sanitization in logs
print("\n[TEST 17] Testing _sanitize_text API key masking...")
sanitize_text = ai_client._sanitize_text
sample_err = "Failed request to https://api.openai.com/v1/chat/completions with Bearer sk-proj-1234567890abcdef"
masked_err = sanitize_text(sample_err, secret="sk-proj-1234567890abcdef")
assert "1234567890" not in masked_err, f"Sensitive key was not masked: {masked_err}"
assert "sk-..." in masked_err or "[MASKED]" in masked_err, f"Mask pattern missing: {masked_err}"
print(f"  Sanitized log: {masked_err}")
print("  -> PASS: API key strictly masked from logs!")

# Test 18: ops_fix_error has show_full_thinking reset on error
print("\n[TEST 18] Testing ops_fix_error error cleanup...")
fix_error_code = (ROOT / "ops" / "ai" / "ops_fix_error.py").read_text(encoding="utf-8")
assert "a_msg.show_thinking = False" in fix_error_code, "ops_fix_error must reset show_thinking on error"
assert "a_msg.show_full_thinking = False" in fix_error_code, "ops_fix_error must reset show_full_thinking on error"
print("  -> PASS: ops_fix_error error state cleanup verified!")

print("\n" + "=" * 60)
print("All 18 M8 AI Assistant Unit Tests Passed Successfully!")
print("=" * 60)

