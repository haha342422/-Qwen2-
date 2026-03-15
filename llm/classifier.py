# llm/classifier.py
import json
import re
from llm.qwen_client import call_qwen, QwenClientError


TOPIC_LABELS = ["农业", "工业", "教育", "科技", "经济", "政务", "医疗", "交通", "文旅", "其他"]
LEVEL_LABELS = ["公开", "内部", "秘密", "机密"]


def _rule_fallback(text: str):
    t = text or ""
    cats = set()

    kw_map = {
        "农业": ["农业", "乡村", "农田", "粮食", "种植", "畜牧", "养殖"],
        "工业": ["工业", "制造", "工厂", "产业", "生产", "装备", "企业"],
        "教育": ["教育", "学校", "教师", "学生", "招生", "课程", "学科"],
        "科技": ["科技", "信息化", "数字", "互联网", "人工智能", "平台", "系统", "数据"],
        "经济": ["经济", "财政", "金融", "税", "投资", "贸易", "营商", "市场"],
        "政务": ["政府", "办公厅", "党委", "机关", "公文", "通知", "意见", "决定", "方案"],
        "医疗": ["医疗", "医院", "卫生", "诊疗", "药品", "疾控"],
        "交通": ["交通", "道路", "铁路", "航运", "公交", "运输"],
        "文旅": ["文旅", "旅游", "景区", "文化", "展会", "会展"],
    }

    for c, kws in kw_map.items():
        if any(k in t for k in kws):
            cats.add(c)

    if not cats:
        cats.add("其他")

    # 涉密规则：优先看原文是否出现密级字样
    level = "公开"
    if "机密" in t:
        level = "机密"
    elif "秘密" in t:
        level = "秘密"
    elif "内部" in t or "内部资料" in t:
        level = "内部"

    return {
        "categories": sorted(list(cats)),
        "level": level,
        "explain": "规则关键词兜底（Qwen不可用或返回异常）",
    }


def _extract_json_from_text(s: str):
    """
    从大模型返回中提取 JSON（哪怕它外面包了说明文字）
    """
    if not s:
        return None
    s = s.strip()

    # 直接就是 JSON
    if s.startswith("{") and s.endswith("}"):
        try:
            return json.loads(s)
        except Exception:
            pass

    # 找到第一段 {...}
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def classify_document(text: str):
    """
    返回：
    {
      "categories": [...],
      "level": "公开/内部/秘密/机密",
      "explain": "...可解释..."
    }
    """
    prompt = f"""
你是公文分类与涉密等级判定助手。
请根据给定公文内容，输出严格 JSON（不要代码块、不要额外文字）：
{{
  "categories": ["农业/工业/教育/科技/经济/政务/医疗/交通/文旅/其他"... 可多标签],
  "level": "公开/内部/秘密/机密",
  "explain": "用一句话说明依据（关键词/句子线索）"
}}
要求：
- categories 只允许来自这组：{TOPIC_LABELS}
- level 只允许来自：{LEVEL_LABELS}
公文内容如下：
{text}
""".strip()

    try:
        out = call_qwen([{"role": "user", "content": prompt}], model="qwen2", temperature=0.1)
        data = _extract_json_from_text(out)
        if not isinstance(data, dict):
            raise QwenClientError("Qwen返回非JSON或无法解析")

        cats = data.get("categories", [])
        level = data.get("level", "公开")
        explain = data.get("explain", "Qwen判定")

        # 规范化
        cats = [c for c in cats if c in TOPIC_LABELS]
        if not cats:
            cats = ["其他"]
        if level not in LEVEL_LABELS:
            level = "公开"

        return {"categories": cats, "level": level, "explain": explain}

    except Exception as e:
        fb = _rule_fallback(text)
        fb["explain"] = f"Qwen不可用或返回异常，已兜底（原因：{e})"
        return fb