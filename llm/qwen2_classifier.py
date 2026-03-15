def classify_document(text):
    if not text.strip():
        return "无法分类（文本为空）"

    # 示例规则 + 占位（你后面可接 Qwen2）
    if "通知" in text:
        return "通知类公文"
    if "请示" in text:
        return "请示类公文"
    if "报告" in text:
        return "报告类公文"

    return "其他公文"