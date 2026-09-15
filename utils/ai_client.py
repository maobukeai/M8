"""OpenAI-compatible async HTTP client using Python standard library.

Provides non-blocking chat completion requests and connectivity testing
without requiring third-party libraries (requests, openai, etc.).
"""

import json
import re
import ssl
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import bpy
from .logger import get_logger

logger = get_logger()


class AIResponse(str):
    """String subclass that also holds reasoning/thinking information."""
    def __new__(cls, content: str, reasoning: str = "", raw_text: str = ""):
        obj = super().__new__(cls, content)
        obj.content = str(content)
        obj.reasoning = str(reasoning)
        obj.raw_text = str(raw_text or content)
        return obj

    @property
    def thinking(self) -> str:
        return self.reasoning


def _sanitize_text(text: str, secret: str = "") -> str:
    """Mask sensitive tokens or keys in error messages and logs."""
    if not text:
        return ""
    res = str(text)
    if secret and len(secret.strip()) >= 6:
        sec = secret.strip()
        masked = sec[:3] + "..." + sec[-3:]
        res = res.replace(sec, masked)
    res = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{8,}", r"\1[MASKED]", res)
    res = re.sub(r"(sk-[a-zA-Z0-9_\-]{6})[a-zA-Z0-9_\-]+", r"\1...", res)
    return res


def clean_markdown_code(text: str) -> str:
    """Extract clean Python code from markdown code fences or raw text."""
    if not text:
        return ""

    text = text.strip()

    # Match ```python ... ``` or ``` ... ``` (case-insensitive)
    pattern = r"```(?:python|py)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if matches:
        return "\n\n".join(m.strip() for m in matches if m.strip())

    # Fallback: if text contains unclosed ```
    if "```" in text:
        parts = text.split("```", 1)
        code_lines = parts[1].splitlines()
        if code_lines and code_lines[0].strip().lower() in ("python", "py", ""):
            return "\n".join(code_lines[1:]).strip()
        return "\n".join(code_lines).strip()

    return text


def split_markdown_response(text: str):
    """Split response into (explanation_text, python_code)."""
    if not text:
        return "", ""
    text = text.strip()
    pattern = r"```(?:python|py)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if matches:
        code = "\n\n".join(m.strip() for m in matches if m.strip())
        explanation = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        return explanation, code

    # Fallback: if text contains an unclosed ```
    if "```" in text:
        parts = text.split("```", 1)
        explanation = parts[0].strip()
        code_lines = parts[1].splitlines()
        if code_lines and code_lines[0].strip().lower() in ("python", "py", ""):
            code = "\n".join(code_lines[1:]).strip()
        else:
            code = "\n".join(code_lines).strip()
        return explanation, code

    # Check if text looks like python code
    has_code_syntax = any(k in text for k in ("import bpy", "bpy.", "bmesh.", "from mathutils", "import math", "def "))
    has_prose_hints = any(k in text for k in ("你好", "请看", "这是一段", "如下所示", "实现方法"))
    if has_code_syntax and not has_prose_hints:
        return "", text

    return text, ""


def _create_ssl_context():
    """Create SSL context with fallback for local self-signed or enterprise proxies."""
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        ctx = ssl._create_unverified_context()
        return ctx


def request_chat_completion_async(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    temperature: float = 0.3,
    timeout: int = 60,
    stream: bool = True,
    on_chunk=None,
    on_success=None,
    on_error=None,
):
    """Send async Chat Completion request in a background thread with SSE streaming support."""

    def _worker():
        try:
            url = base_url.strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            url = url.rstrip("/")
            if not url.endswith("/chat/completions"):
                if url.endswith("/v1"):
                    url = f"{url}/chat/completions"
                else:
                    url = f"{url}/chat/completions"

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Blender-M8-AI-Assistant/1.0",
            }
            if api_key and api_key.strip():
                headers["Authorization"] = f"Bearer {api_key.strip()}"

            ctx = _create_ssl_context()

            # Attempt streaming first if on_chunk is provided
            if stream and on_chunk:
                try:
                    payload = {
                        "model": model.strip(),
                        "messages": messages,
                        "temperature": max(0.0, min(2.0, float(temperature))),
                        "stream": True,
                    }
                    req_data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

                    full_content_parts = []
                    full_reasoning_parts = []
                    in_tag_think = False

                    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
                        while True:
                            line_bytes = response.readline()
                            if not line_bytes:
                                break
                            line = line_bytes.decode("utf-8").strip()
                            if not line:
                                continue
                            if line == "data: [DONE]":
                                break
                            if line.startswith("data: "):
                                chunk_str = line[6:].strip()
                                try:
                                    chunk_json = json.loads(chunk_str)
                                    choices = chunk_json.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        c = delta.get("content") or ""
                                        r = delta.get("reasoning_content") or delta.get("reasoning") or ""

                                        # Handle <think> tags in content
                                        if "<think>" in c:
                                            in_tag_think = True
                                            parts = c.split("<think>", 1)
                                            c = parts[0]
                                            r = (r + parts[1]) if len(parts) > 1 else r
                                        elif "</think>" in c:
                                            in_tag_think = False
                                            parts = c.split("</think>", 1)
                                            r = (r + parts[0])
                                            c = parts[1] if len(parts) > 1 else ""
                                        elif in_tag_think:
                                            r = (r + c) if r else c
                                            c = ""

                                        if c:
                                            full_content_parts.append(c)
                                        if r:
                                            full_reasoning_parts.append(r)

                                        if (c or r) and on_chunk:
                                            def _dispatch_chunk(curr_c=c, curr_r=r):
                                                try:
                                                    on_chunk(curr_c, curr_r)
                                                except Exception:
                                                    pass
                                                return None
                                            bpy.app.timers.register(_dispatch_chunk, first_interval=0.0)
                                except Exception:
                                    pass

                    full_content = "".join(full_content_parts)
                    full_reasoning = "".join(full_reasoning_parts)
                    if full_content or full_reasoning:
                        response_obj = AIResponse(full_content, reasoning=full_reasoning, raw_text=full_content)
                        if on_success:
                            def _main_thread_success():
                                try:
                                    on_success(response_obj)
                                except Exception as cb_err:
                                    logger.error(f"Error in on_success callback: {cb_err}", exc_info=True)
                                return None
                            bpy.app.timers.register(_main_thread_success, first_interval=0.0)
                        return
                except Exception as stream_err:
                    logger.warning(f"Streaming failed, falling back to non-streaming: {stream_err}")

            # Non-streaming request (or fallback)
            payload = {
                "model": model.strip(),
                "messages": messages,
                "temperature": max(0.0, min(2.0, float(temperature))),
                "stream": False,
            }

            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            raw_body = None
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
                raw_body = response.read().decode("utf-8")

            res_json = json.loads(raw_body)
            choices = res_json.get("choices", [])
            if not choices:
                error_msg = res_json.get("error", {}).get("message", "API 返回内容为空")
                raise RuntimeError(error_msg)

            msg_data = choices[0].get("message", {})
            raw_content = msg_data.get("content", "") or ""
            reasoning = msg_data.get("reasoning_content", "") or msg_data.get("reasoning", "") or ""

            # Check if content has <think>...</think> tags
            if "<think>" in raw_content:
                if "</think>" in raw_content:
                    think_match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL)
                    if think_match:
                        extracted_think = think_match.group(1).strip()
                        if not reasoning:
                            reasoning = extracted_think
                        raw_content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
                else:
                    parts = raw_content.split("<think>", 1)
                    if not reasoning:
                        reasoning = parts[1].strip()
                    raw_content = parts[0].strip()

            response_obj = AIResponse(raw_content, reasoning=reasoning, raw_text=raw_content)

            if on_success:
                def _main_thread_success():
                    try:
                        on_success(response_obj)
                    except Exception as cb_err:
                        logger.error(f"Error in on_success callback: {cb_err}", exc_info=True)
                    return None

                bpy.app.timers.register(_main_thread_success, first_interval=0.0)

        except urllib.error.HTTPError as http_err:
            try:
                err_body = http_err.read().decode("utf-8")
                err_data = json.loads(err_body)
                msg = err_data.get("error", {}).get("message", str(http_err))
            except Exception:
                msg = f"HTTP {http_err.code}: {http_err.reason}"
            msg = _sanitize_text(msg, api_key)
            logger.error(f"HTTP error during chat completion: {msg}")

            if on_error:
                def _main_thread_error():
                    try:
                        on_error(msg)
                    except Exception:
                        pass
                    return None

                bpy.app.timers.register(_main_thread_error, first_interval=0.0)

        except Exception as e:
            err_msg = _sanitize_text(str(e), api_key)
            logger.error(f"Failed chat completion request: {err_msg}", exc_info=True)

            if on_error:
                def _main_thread_error():
                    try:
                        on_error(err_msg)
                    except Exception:
                        pass
                    return None

                bpy.app.timers.register(_main_thread_error, first_interval=0.0)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread


def test_api_connection(
    base_url: str,
    api_key: str,
    model: str,
    callback,
):
    """Test connection with a simple ping message."""
    import time
    start_time = time.time()
    messages = [
        {"role": "user", "content": "Hello, respond with 'OK'."}
    ]

    def _on_success(content):
        latency = time.time() - start_time
        reply_preview = str(content).strip().replace("\r", " ").replace("\n", " ")
        if len(reply_preview) > 40:
            reply_preview = reply_preview[:40] + "..."
        callback(True, f"响应正常 (耗时 {latency:.2f}s) | 响应: {reply_preview}")

    def _on_error(err):
        latency = time.time() - start_time
        clean_err = str(err).strip().replace("\r", " ").replace("\n", " ")
        if len(clean_err) > 80:
            clean_err = clean_err[:80] + "..."
        callback(False, f"连接异常 (耗时 {latency:.2f}s) | 原因: {clean_err}")

    request_chat_completion_async(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        timeout=15,
        on_success=_on_success,
        on_error=_on_error,
    )


def parse_models_response(raw_json_str: str) -> list:
    """Parse JSON string from OpenAI-compatible /models or Ollama /api/tags endpoint into a list of model IDs."""
    try:
        data = json.loads(raw_json_str)
    except Exception:
        return []

    model_ids = []
    # Standard OpenAI format: {"object": "list", "data": [{"id": "model-id", ...}, ...]}
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            for item in data["data"]:
                if isinstance(item, dict) and "id" in item:
                    model_ids.append(str(item["id"]).strip())
                elif isinstance(item, str):
                    model_ids.append(item.strip())
        # Ollama /api/tags format: {"models": [{"name": "model:tag", ...}, ...]}
        elif "models" in data and isinstance(data["models"], list):
            for item in data["models"]:
                if isinstance(item, dict):
                    m_id = item.get("name") or item.get("model") or ""
                    if m_id:
                        model_ids.append(str(m_id).strip())
                elif isinstance(item, str):
                    model_ids.append(item.strip())
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "id" in item:
                model_ids.append(str(item["id"]).strip())
            elif isinstance(item, str):
                model_ids.append(item.strip())

    # Filter out empty and duplicates while preserving uniqueness
    unique_ids = []
    seen = set()
    for mid in model_ids:
        if mid and mid not in seen:
            seen.add(mid)
            unique_ids.append(mid)

    # Sort alphabetically for clean presentation
    unique_ids.sort()
    return unique_ids


def fetch_models_async(
    base_url: str,
    api_key: str,
    timeout: int = 15,
    on_success=None,
    on_error=None,
):
    """Fetch available models from OpenAI-compatible /models endpoint or Ollama."""
    def _worker():
        try:
            url = base_url.strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            url = url.rstrip("/")
            if url.endswith("/chat/completions"):
                url = url[:-len("/chat/completions")]

            # Try /models first
            models_url = url if url.endswith("/models") else f"{url}/models"

            headers = {
                "User-Agent": "Blender-M8-AI-Assistant/1.0",
            }
            if api_key and api_key.strip():
                headers["Authorization"] = f"Bearer {api_key.strip()}"

            req = urllib.request.Request(models_url, headers=headers, method="GET")
            ctx = _create_ssl_context()

            raw_body = None
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                    raw_body = resp.read().decode("utf-8")
            except urllib.error.HTTPError as http_err:
                # If 404 and might be Ollama, try /api/tags
                if http_err.code == 404 and ("11434" in url or "ollama" in url.lower()):
                    root_url = url[:-3] if url.endswith("/v1") else url
                    tags_url = f"{root_url}/api/tags"
                    try:
                        req_tags = urllib.request.Request(tags_url, headers=headers, method="GET")
                        with urllib.request.urlopen(req_tags, context=ctx, timeout=timeout) as resp:
                            raw_body = resp.read().decode("utf-8")
                    except Exception:
                        raise http_err
                elif http_err.code == 404:
                    raise RuntimeError("该 API 端点不支持自动查询模型列表 (HTTP 404)，请点击下方【+ 手动添加】输入模型名称")
                else:
                    raise http_err
            except urllib.error.URLError as ssl_err:
                if "CERTIFICATE_VERIFY_FAILED" in str(ssl_err):
                    ctx_unverified = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, context=ctx_unverified, timeout=timeout) as resp:
                        raw_body = resp.read().decode("utf-8")
                else:
                    raise

            if not raw_body:
                raise RuntimeError("API 返回内容为空")

            model_ids = parse_models_response(raw_body)
            if not model_ids:
                raise RuntimeError("未在 API 响应中解析出有效模型 ID")

            if on_success:
                def _main_thread_success():
                    try:
                        on_success(model_ids)
                    except Exception as cb_err:
                        logger.error(f"Error in on_success callback: {cb_err}", exc_info=True)
                    return None

                bpy.app.timers.register(_main_thread_success, first_interval=0.0)

        except urllib.error.HTTPError as http_err:
            try:
                err_body = http_err.read().decode("utf-8")
                err_data = json.loads(err_body)
                msg = err_data.get("error", {}).get("message", str(http_err))
            except Exception:
                msg = f"HTTP {http_err.code}: {http_err.reason}"
            msg = _sanitize_text(msg, api_key)
            logger.error(f"HTTP error during fetch_models: {msg}")

            if on_error:
                def _main_thread_error():
                    try:
                        on_error(msg)
                    except Exception:
                        pass
                    return None

                bpy.app.timers.register(_main_thread_error, first_interval=0.0)

        except Exception as e:
            err_msg = _sanitize_text(str(e), api_key)
            logger.error(f"Failed fetch_models request: {err_msg}", exc_info=True)

            if on_error:
                def _main_thread_error():
                    try:
                        on_error(err_msg)
                    except Exception:
                        pass
                    return None

                bpy.app.timers.register(_main_thread_error, first_interval=0.0)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread

