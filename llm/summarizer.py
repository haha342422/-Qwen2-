# llm/summarizer.py
from llm.qwen_client import call_qwen


def generate_summary(text: str, max_chars: int = 200):
    prompt = f"""
请用中文把下面公文内容总结为 5 条要点（每条不超过 25 字），只输出要点列表（用 - 开头）。
内容：
{text}
""".strip()

    try:
        out = call_qwen([{"role": "user", "content": prompt}], model="qwen2", temperature=0.2)
        out = (out or "").strip()
        if out:
            return out
    except Exception:
        pass

    t = (text or "").strip()
    if len(t) > max_chars:
        return t[:max_chars] + "…"
    return t