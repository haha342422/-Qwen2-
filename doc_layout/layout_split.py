# doc_layout/layout_split.py
from __future__ import annotations
from typing import Dict

def split_layout(text: str) -> Dict[str, str]:
    """
    输入：清洗后的纯文本
    输出：版头/主体/版记
    """
    t = text.strip()
    if not t:
        return {"版头": "", "主体": "", "版记": ""}

    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    if not lines:
        return {"版头": "", "主体": "", "版记": ""}

    # 版记起点关键词（更像公文）
    footer_keywords = ["抄送：", "抄送:", "印发", "主办：", "主办:", "督办：", "督办:", "附件：", "附件:", "联系人：", "联系电话："]
    footer_idx = None
    for i, ln in enumerate(lines):
        if any(kw in ln for kw in footer_keywords):
            footer_idx = i
            break

    # 标题定位：含“关于”且以通知/决定/意见/请示/报告/函/通告/公告/批复结尾
    title_idx = None
    for i, ln in enumerate(lines[:40]):
        if ("关于" in ln and any(ln.endswith(x) for x in ["通知", "决定", "意见", "请示", "报告", "函", "通告", "公告", "批复"])) or \
           any(ln.endswith(x) for x in ["通知", "决定", "意见", "请示", "报告", "函", "通告", "公告", "批复"]):
            if len(ln) >= 8:
                title_idx = i
                break

    # 版头结束：优先到标题行（含标题在版头末尾）
    if title_idx is not None:
        header_end = min(title_idx + 1, len(lines))
    else:
        header_end = max(3, int(len(lines) * 0.15))

    # 版记开始
    if footer_idx is None:
        footer_idx = len(lines)

    header_lines = lines[:header_end]
    footer_lines = lines[footer_idx:] if footer_idx < len(lines) else []
    body_lines = lines[header_end:footer_idx] if header_end < footer_idx else []

    return {
        "版头": "\n".join(header_lines).strip(),
        "主体": "\n".join(body_lines).strip(),
        "版记": "\n".join(footer_lines).strip(),
    }