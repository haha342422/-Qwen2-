# extract/key_info_extractor.py
import re
from typing import Dict, Optional

from utils.text_cleaner import clean_ocr_text, normalize_whitespace


# 常见字段正则
RE_LEVEL = re.compile(r"(绝密|机密|秘密|内部|公开)")
RE_URGENCY = re.compile(r"(特急|加急|平急)")
RE_SERIAL = re.compile(r"(?<!\d)(\d{5,8})(?!\d)")  # 份号常见 000001
RE_DOCNO = re.compile(
    r"([^\s]{1,10}[〔\[\(]?\d{4}[〕\]\)]?\d{1,4}号|[^\s]{1,10}\[\d{4}\]\d{1,4}号|[^\s]{1,10}\[\d{4}\]\d{1,4}|[^\s]{1,10}\[\d{4}\]\d{1,4}号|[^\s]{1,10}\[\d{4}\]\d{1,4})"
)
RE_DATE = re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日)")
RE_CC = re.compile(r"抄送[:：]\s*(.+)")
RE_ATTACH = re.compile(r"(附件|附：)\s*(.+)?")

# 发文机关标识关键词（只从版头取）
ORG_HINT = re.compile(r"(人民政府|人民政府办公厅|委员会|办公室|厅|局|处|中心|学院|大学|集团|公司|文件)")


def _simple_split_layout(text: str) -> Dict[str, str]:
    """
    当 app.py 没传 layout 时，用文本规则做一个“能用”的版头/主体/版记划分：
    - 版记通常包含“抄送/印发/主办/督办”等
    - 版头取前若干行（直到出现标题后的一段正文开始）
    """
    t = normalize_whitespace(text)
    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]

    if not lines:
        return {"版头": "", "主体": "", "版记": ""}

    # 找版记起点
    footer_start = None
    for i, ln in enumerate(lines):
        if ("抄送" in ln) or ("印发" in ln) or ln.startswith("主办") or ln.startswith("督办"):
            footer_start = i
            break

    if footer_start is None:
        footer_start = len(lines)

    head_and_body = lines[:footer_start]
    footer = lines[footer_start:]

    # 标题一般包含“关于”或以通知/决定/通报等结尾
    title_idx = None
    for i, ln in enumerate(head_and_body[:30]):
        if "关于" in ln or ln.endswith(("通知", "决定", "通报", "请示", "报告", "公告", "通告", "函", "意见", "方案", "办法", "规定")):
            # 避免把“抄送”当标题
            if "抄送" not in ln and len(ln) >= 8:
                title_idx = i
                break

    if title_idx is None:
        # 兜底：前 10 行做版头
        head = head_and_body[:10]
        body = head_and_body[10:]
    else:
        # 标题之前 + 标题行 作为版头
        head = head_and_body[:title_idx + 1]
        body = head_and_body[title_idx + 1:]

    return {
        "版头": "\n".join(head).strip(),
        "主体": "\n".join(body).strip(),
        "版记": "\n".join(footer).strip(),
    }


def _pick_title(head: str) -> Optional[str]:
    lines = [ln.strip() for ln in head.split("\n") if ln.strip()]
    # 优先：包含“关于”的长句
    candidates = []
    for ln in lines:
        if "关于" in ln and len(ln) >= 8 and "http" not in ln:
            candidates.append(ln)
    if candidates:
        return max(candidates, key=len)

    # 次优：以通知/决定等结尾
    for ln in lines:
        if ln.endswith(("通知", "决定", "通报", "请示", "报告", "公告", "通告", "函", "意见", "方案", "办法", "规定")) and len(ln) >= 8:
            return ln

    return None


def _pick_docno(head: str) -> Optional[str]:
    # 发文字号通常在版头，形如 农[2015]1号 / 豫政〔2021〕51号
    for ln in head.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        m = re.search(r"[^\s]{1,10}[〔\[]?\d{4}[〕\]]?\d{1,4}号", ln)
        if m:
            return m.group(0)
        m2 = re.search(r"[^\s]{1,10}\[\d{4}\]\d{1,4}号", ln)
        if m2:
            return m2.group(0)
    return None


def _pick_org_mark(head: str, title: Optional[str], docno: Optional[str]) -> Optional[str]:
    """
    发文机关标识：只允许从版头抽，且不能是标题/正文句子
    """
    lines = [ln.strip() for ln in head.split("\n") if ln.strip()]
    best = None
    for ln in lines:
        # 排除标题/文号/日期/URL
        if title and ln == title:
            continue
        if docno and docno in ln:
            continue
        if "http" in ln:
            continue
        if RE_DATE.search(ln):
            continue

        # 需要命中机关关键词
        if ORG_HINT.search(ln):
            # “文件”类通常是机关标识
            if "文件" in ln or "人民政府" in ln or "办公厅" in ln or ln.endswith(("办公室", "委员会", "人民政府")):
                best = ln
                break
            # 否则先记着最长的
            if best is None or len(ln) > len(best):
                best = ln

    return best


def _pick_level(head: str) -> Optional[str]:
    m = RE_LEVEL.search(head)
    return m.group(1) if m else None


def _pick_urgency(head: str) -> Optional[str]:
    m = RE_URGENCY.search(head)
    return m.group(1) if m else None


def _pick_serial(head: str) -> Optional[str]:
    # 份号一般在最顶部
    lines = [ln.strip() for ln in head.split("\n") if ln.strip()]
    for ln in lines[:5]:
        m = RE_SERIAL.fullmatch(ln)
        if m:
            return m.group(1)
    # 兜底：前 3 行找 5-8 位数字
    for ln in lines[:3]:
        m = RE_SERIAL.search(ln)
        if m:
            return m.group(1)
    return None


def _pick_cc(footer: str) -> Optional[str]:
    m = RE_CC.search(footer)
    if m:
        return m.group(1).strip()
    return None


def _pick_issue_print_info(footer: str) -> Dict[str, Optional[str]]:
    """
    从版记抽：印发机关、印发日期
    支持：
      - XDOC办公室 2015年1月1日印发
      - 河南省人民政府办公厅
        2021年12月31日印发
    """
    lines = [ln.strip() for ln in footer.split("\n") if ln.strip()]

    issue_org = None
    issue_date = None

    # 1) 同行形式
    for ln in lines:
        if "印发" in ln and RE_DATE.search(ln):
            issue_date = RE_DATE.search(ln).group(1)
            # 印发机关取日期前的内容
            pre = ln.split(issue_date)[0].strip()
            pre = pre.replace("印发", "").strip()
            if pre:
                issue_org = pre
            break

    # 2) 分行形式：找一个“办公室/办公厅/局/厅...”作为机关，再找日期+印发
    if issue_org is None:
        for ln in lines:
            if ORG_HINT.search(ln) and ("抄送" not in ln) and ("主办" not in ln) and ("督办" not in ln):
                # 机关行一般不会太长
                if 2 <= len(ln) <= 30:
                    issue_org = ln
                    break

    if issue_date is None:
        for ln in lines:
            if "印发" in ln and RE_DATE.search(ln):
                issue_date = RE_DATE.search(ln).group(1)
                break

    return {"印发机关": issue_org, "印发日期": issue_date}


def _pick_signed_date(body: str, footer: str) -> Optional[str]:
    """
    成文日期：优先正文落款日期（不含“印发”）
    """
    # 在正文末尾 15 行找日期
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    tail = lines[-20:] if len(lines) > 20 else lines
    for ln in reversed(tail):
        if RE_DATE.search(ln) and "印发" not in ln:
            return RE_DATE.search(ln).group(1)

    # 次优：版记里找不含“印发”的日期（少见）
    for ln in footer.split("\n"):
        ln = ln.strip()
        if RE_DATE.search(ln) and "印发" not in ln:
            return RE_DATE.search(ln).group(1)

    return None


def _pick_main_receiver(head_and_body: str) -> Optional[str]:
    """
    主送机关常见形式：
      - 各省辖市人民政府...：
      - XX单位：
    """
    lines = [ln.strip() for ln in head_and_body.split("\n") if ln.strip()]
    for ln in lines[:30]:
        if ln.endswith(("：", ":")) and len(ln) >= 4:
            # 排除“抄送：”
            if "抄送" in ln:
                continue
            return ln.rstrip("：:").strip()
        # 另一种：行内出现“主送：”
        if "主送" in ln and ("：" in ln or ":" in ln):
            parts = re.split(r"[:：]", ln, maxsplit=1)
            if len(parts) == 2:
                return parts[1].strip() or None
    return None


def _pick_attach(text: str) -> Optional[str]:
    m = RE_ATTACH.search(text)
    if m:
        # 附件可能在同一行后面
        if m.group(2):
            return m.group(2).strip()
        return "有附件"
    return None


def extract_key_info(text: str, layout: Optional[Dict[str, str]] = None) -> Dict[str, Optional[str]]:
    """
    关键信息抽取（最终验收版）：
    - 清洗 OCR 噪声
    - 版头/主体/版记分区（layout 可传入，否则内部简易切）
    - 发文机关标识只从版头提取（修复你现在的误抽）
    - 补齐印发机关/印发日期
    - 成文日期不再误用“印发日期”
    """
    cleaned = clean_ocr_text(text)

    if layout is None:
        layout = _simple_split_layout(cleaned)
    else:
        # layout 里也清洗一下，避免残留噪声
        layout = {k: clean_ocr_text(v) for k, v in layout.items()}

    head = layout.get("版头", "") or ""
    body = layout.get("主体", "") or ""
    footer = layout.get("版记", "") or ""

    title = _pick_title(head)
    docno = _pick_docno(head)
    serial = _pick_serial(head)
    level = _pick_level(head)
    urgency = _pick_urgency(head)

    org_mark = _pick_org_mark(head, title=title, docno=docno)

    cc = _pick_cc(footer)
    issue_info = _pick_issue_print_info(footer)
    issue_org = issue_info.get("印发机关")
    issue_date = issue_info.get("印发日期")

    signed_date = _pick_signed_date(body, footer)

    main_receiver = _pick_main_receiver(head + "\n" + body)
    attach = _pick_attach(cleaned)

    # 保密期限：常见“秘密一年/秘密 1年/秘密（1年）”
    secrecy_term = None
    if level and ("一年" in head or "两年" in head or "三年" in head):
        m = re.search(r"(一年|两年|三年|四年|五年|长期|\d+年|\d+个月)", head)
        if m:
            secrecy_term = m.group(1)

    # 正文：优先主体；如果主体为空就用全文去掉版头版记
    main_text = body.strip() if body.strip() else cleaned

    return {
        "份号": serial,
        "密级": level,
        "保密期限": secrecy_term,
        "紧急程度": urgency,

        "发文机关标识": org_mark,
        "发文字号": docno,
        "签发人": None,  # 你可以后续扩展：在正文中找“签发人：XXX”
        "标题": title,

        "主送机关": main_receiver,
        "正文": main_text,

        "抄送机关": cc,
        "印发机关": issue_org,
        "印发日期": issue_date,

        # 成文日期：优先落款日期，其次为空；不要直接用印发日期误判
        "成文日期": signed_date,

        "附件": attach,
    }