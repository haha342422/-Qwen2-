def classify_document(text: str) -> dict:
    if "通知" in text:
        return {"公文类别": "通知"}
    if "意见" in text:
        return {"公文类别": "意见"}
    if "决定" in text:
        return {"公文类别": "决定"}
    if "通报" in text:
        return {"公文类别": "通报"}
    return {"公文类别": "其他"}