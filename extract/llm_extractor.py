import re

def rule_extract(text):

    date = re.search(r"\d{4}年\d{1,2}月\d{1,2}日", text)
    doc_number = re.search(r"〔\d{4}〕\d+号", text)

    return {
        "成文日期": date.group() if date else None,
        "发文字号": doc_number.group() if doc_number else None
    }