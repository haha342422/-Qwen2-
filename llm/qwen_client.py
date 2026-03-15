# llm/qwen_client.py
import json
import requests
from config import Config


class QwenClientError(Exception):
    pass


def call_qwen(messages, model="qwen2", temperature=0.1):
    """
    messages: [{"role":"user","content":"..."}]
    返回: str（大模型输出文本）
    """
    url = Config.QWEN_API_URL
    if not url:
        raise QwenClientError("QWEN_API_URL 未配置（环境变量为空）")

    headers = {"Content-Type": "application/json"}
    if Config.QWEN_API_KEY:
        headers["Authorization"] = f"Bearer {Config.QWEN_API_KEY}"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        # 关键：禁用代理，避免 requests 走 SOCKS 导致 Missing dependencies for SOCKS support
        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=Config.QWEN_TIMEOUT,
            proxies={"http": None, "https": None},
        )
    except Exception as e:
        raise QwenClientError(f"请求异常: {e}")

    if r.status_code != 200:
        # 有些服务会返回 HTML 错误页
        text_preview = (r.text or "")[:200]
        raise QwenClientError(f"HTTP {r.status_code}: {text_preview}")

    try:
        data = r.json()
    except Exception:
        raise QwenClientError(f"返回不是JSON: {(r.text or '')[:200]}")

    # OpenAI兼容：choices[0].message.content
    if isinstance(data, dict) and "choices" in data:
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            raise QwenClientError(f"JSON结构异常: {json.dumps(data)[:200]}")

    # 少数实现可能是 output/text
    if isinstance(data, dict) and "output" in data:
        out = data.get("output")
        if isinstance(out, dict) and "text" in out:
            return out["text"]

    raise QwenClientError(f"无法解析返回JSON结构: {json.dumps(data)[:200]}")