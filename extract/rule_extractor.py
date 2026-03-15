import re
from typing import Dict, Optional


SECRET_LEVELS = ["绝密", "机密", "秘密", "内部", "公开"]
URGENCY_LEVELS = ["特急", "加急", "急件", "平急"]


def split_lines(text):
    return [x.strip() for x in text.split("\n") if x.strip()]


def extract_key_info(text: str, layout: Optional[Dict] = None):

    full = text or ""

    head = layout.get("版头", "") if layout else full
    body = layout.get("主体", "") if layout else full
    tail = layout.get("版记", "") if layout else full

    head_lines = split_lines(head)
    tail_lines = split_lines(tail)

    info = {
        "份号": None,
        "密级": None,
        "保密期限": None,
        "紧急程度": None,
        "发文机关标识": None,
        "发文字号": None,
        "签发人": None,
        "标题": None,
        "主送机关": None,
        "正文": body,
        "抄送机关": None,
        "附件": None,
        "印发机关": None,
        "印发日期": None,
        "成文日期": None
    }

    # ==========================
    # 份号
    # ==========================
    for line in head_lines:
        if re.fullmatch(r"\d{6}", line):
            info["份号"] = line
            break

    # ==========================
    # 密级 + 保密期限（修复）
    # ==========================
    for line in head_lines:
        for level in SECRET_LEVELS:
            if level in line:

                info["密级"] = level

                m = re.search(r"(一年|二年|三年|四年|五年|\d+年|长期)", line)

                if m:
                    info["保密期限"] = m.group(1)

                break

    # ==========================
    # 紧急程度
    # ==========================
    for line in head_lines:
        for u in URGENCY_LEVELS:
            if u in line:
                info["紧急程度"] = u

    # ==========================
    # 发文机关标识（严格限制只在版头）
    # ==========================
    for line in head_lines:

        if "文件" in line:

            info["发文机关标识"] = line
            break

    # ==========================
    # 发文字号
    # ==========================
    m = re.search(r"[^\s]{1,10}\[\d{4}\]\d+号", full)

    if m:
        info["发文字号"] = m.group(0)

    # ==========================
    # 标题
    # ==========================
    for line in head_lines:

        if "通知" in line or "决定" in line:

            info["标题"] = line
            break

    # ==========================
    # 抄送机关
    # ==========================
    m = re.search(r"抄送[:：]\s*(.*)", tail)

    if m:
        info["抄送机关"] = m.group(1)

    # ==========================
    # 印发机关 + 印发日期（修复核心）
    # ==========================
    for i, line in enumerate(tail_lines):

        if "印发" in line:

            # 印发日期
            m = re.search(r"\d{4}年\d{1,2}月\d{1,2}日", line)

            if m:
                info["印发日期"] = m.group(0)
                info["成文日期"] = m.group(0)

            # 印发机关 = 上一行
            if i > 0:
                info["印发机关"] = tail_lines[i - 1]

            break

    return info