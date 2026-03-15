import re

# 手机号（中国大陆简单版）
RE_PHONE = re.compile(r'(?<!\d)(1[3-9]\d{9})(?!\d)')
# 身份证（18位含X）
RE_ID18 = re.compile(r'(?<!\d)(\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx])(?!\d)')
# 邮箱
RE_EMAIL = re.compile(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')

def _mask(s: str, keep_left=3, keep_right=2):
    if not s:
        return s
    if len(s) <= keep_left + keep_right:
        return "*" * len(s)
    return s[:keep_left] + "*" * (len(s) - keep_left - keep_right) + s[-keep_right:]

def redact_text(text: str) -> str:
    if not text:
        return text
    t = text
    t = RE_PHONE.sub(lambda m: _mask(m.group(1), 3, 2), t)
    t = RE_ID18.sub(lambda m: _mask(m.group(1), 4, 2), t)
    t = RE_EMAIL.sub(lambda m: _mask(m.group(1), 2, 2), t)
    return t