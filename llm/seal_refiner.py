import json
import re
import requests
from config import Config


def _extract_json(text: str):
    """从模型输出里尽量提取 JSON"""
    if not text:
        return None
    text = text.strip()
    # 如果直接就是 JSON
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except Exception:
            pass
    # 尝试截取第一个 {...}
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def refine_seal_with_qwen(seal_text: str, key_info: dict, doc_title: str = "", doc_footer_hint: str = ""):
    """
    输入：印章 OCR 原文本 + 关键信息（印发机关/日期/标题等）
    输出：更干净的 seal_org / seal_date / seal_text_refined
    """
    seal_text = (seal_text or "").strip()
    if not seal_text:
        return {
            "seal_text_refined": "",
            "seal_org": None,
            "seal_date": None,
            "explain": "无印章文本"
        }

    # 没配置Qwen就返回原样
    if not Config.QWEN_API_URL:
        return {
            "seal_text_refined": seal_text,
            "seal_org": key_info.get("印发机关") or None,
            "seal_date": key_info.get("印发日期") or None,
            "explain": "QWEN_API_URL 未配置，未执行纠错"
        }

    prompt = f"""
你是中文公文“印章纠错”助手。印章OCR经常有错字、漏字、拆行、把X识别成N等问题。
请结合“公文关键信息”与“印章OCR文本”，输出一个严格JSON（不要输出任何额外文字）。

【公文标题】{doc_title}
【公文印发机关】{key_info.get("印发机关")}
【公文印发日期】{key_info.get("印发日期")}
【公文发文机关标识】{key_info.get("发文机关标识")}
【页脚线索】{doc_footer_hint}

【印章OCR文本】：
{seal_text}

要求：
1）尽量纠正明显错字（例如 NDOC→XDOC 这种），去掉无意义单字。
2）输出 seal_org（印章机构名）与 seal_date（若能推断年月日）。
3）seal_text_refined 给一段合并后的“合理印章内容”。

严格输出：
{{
  "seal_text_refined": "...",
  "seal_org": "... 或 null",
  "seal_date": "... 或 null",
  "explain": "简短说明你怎么纠错的"
}}
""".strip()

    payload = {
        "model": "qwen2.5-3b-instruct",
        "messages": [
            {"role": "system", "content": "You must output valid JSON only. No extra words."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.QWEN_API_KEY or 'EMPTY'}",
    }

    r = requests.post(
        Config.QWEN_API_URL,
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=Config.QWEN_TIMEOUT,
    )

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    obj = _extract_json(content)
    if not obj:
        return {
            "seal_text_refined": seal_text,
            "seal_org": key_info.get("印发机关") or None,
            "seal_date": key_info.get("印发日期") or None,
            "explain": "模型输出非JSON，已兜底返回原文"
        }

    # 兜底键
    obj.setdefault("seal_text_refined", seal_text)
    obj.setdefault("seal_org", None)
    obj.setdefault("seal_date", None)
    obj.setdefault("explain", "OK")
    return obj