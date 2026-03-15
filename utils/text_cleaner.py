# utils/text_cleaner.py
import re
from typing import List


_FLOAT_SCORE_RE = re.compile(r"(?<!\d)(?:0\.\d{2,4}|1\.0{1,4})(?!\d)")
_LINE_NO_RE = re.compile(r"^\s*\d+\s*[:：]\s*")  # 1: / 12： 这种行号
_MULTI_SPACE_RE = re.compile(r"[ \t\u00A0]+")


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    # 统一换行
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 去掉多余空白
    text = _MULTI_SPACE_RE.sub(" ", text)
    # 去掉连续空行（最多保留 1 个）
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _fix_year_typos_line(line: str) -> str:
    """
    常见 OCR 年份错误修复：
    - 015年 -> 2015年
    - 020年 -> 2020年
    - 15年1月 -> 2015年1月（当出现月/日时）
    """
    # 015年 / 020年 -> 2015年 / 2020年
    line = re.sub(r"(?<!\d)0(\d{2,3})年", lambda m: f"2{m.group(1)}年", line)

    # 15年1月 / 15年 -> 2015年（仅当后面出现月/日）
    line = re.sub(r"(?<!\d)(\d{2})年(?=\d{1,2}月)", r"20\1年", line)
    line = re.sub(r"(?<!\d)(\d{2})年(?=\d{1,2}月\d{1,2}日)", r"20\1年", line)

    # 2015年1月1日印发日 -> 去掉多余的“日”
    line = re.sub(r"(印发)\s*日$", r"\1", line)

    return line


def strip_noise_lines(lines: List[str]) -> List[str]:
    """
    删除明显噪声行：
    - 纯置信度分数
    - 纯符号/单字（且不是关键字）
    - 只有一个字母/无意义碎片
    """
    kept = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # 去掉行号前缀
        line = _LINE_NO_RE.sub("", line)

        # 如果整行几乎就是分数，丢掉
        if _FLOAT_SCORE_RE.fullmatch(line):
            continue

        # 去掉行内分数
        line = _FLOAT_SCORE_RE.sub("", line).strip()

        # 年份修复
        line = _fix_year_typos_line(line).strip()

        if not line:
            continue

        # 过滤孤立单字噪声（保留“年/月/日/章/号”等可能有意义的）
        if len(line) <= 1 and line not in {"年", "月", "日", "章", "号"}:
            continue

        # 过滤纯英文单字母
        if re.fullmatch(r"[A-Za-z]", line):
            continue

        kept.append(line)

    return kept


def clean_ocr_text(text: str) -> str:
    """
    总清洗：
    - 去行号/置信度分数
    - 去噪声行
    - 修复常见年份错误
    - 规范空白
    """
    if not text:
        return ""

    text = normalize_whitespace(text)

    # 按行处理
    lines = text.split("\n")
    lines = strip_noise_lines(lines)

    # 再次合并
    cleaned = "\n".join(lines)
    cleaned = normalize_whitespace(cleaned)
    return cleaned