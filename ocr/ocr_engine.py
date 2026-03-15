import cv2
from paddleocr import PaddleOCR


# 全局单例，避免每次初始化很慢
_OCR = PaddleOCR(
    use_angle_cls=True,
    lang="ch",
    show_log=False,
)


def _to_bgr(img):
    """允许传入 path 或 numpy；统一成 BGR"""
    if isinstance(img, str):
        x = cv2.imread(img)
        return x
    return img


def _parse_ocr_result(res):
    """
    PaddleOCR 返回结构在不同版本略有差异，这里做“兼容式提取”
    """
    texts = []

    if not res:
        return ""

    # 常见：res = [ [ [box, (text, score)], ... ] ]
    if isinstance(res, list) and len(res) == 1 and isinstance(res[0], list):
        items = res[0]
    else:
        items = res

    for it in items:
        try:
            # it 可能是 [box, (text, score)]
            if isinstance(it, list) and len(it) >= 2 and isinstance(it[1], (list, tuple)):
                t = it[1][0]
                if t:
                    texts.append(str(t))
            # 也可能是 (text, score)
            elif isinstance(it, (list, tuple)) and len(it) >= 1 and isinstance(it[0], str):
                texts.append(it[0])
        except Exception:
            continue

    # 去空行
    texts = [t.strip() for t in texts if t and str(t).strip()]
    return "\n".join(texts).strip()


def run_ocr(img):
    """
    全页 OCR（带检测）
    """
    bgr = _to_bgr(img)
    if bgr is None:
        return ""
    res = _OCR.ocr(bgr, det=True, rec=True)
    return _parse_ocr_result(res)


def run_ocr_seal(img):
    """
    印章 OCR：不做检测（det=False），直接识别整张图
    这样对“二值图 / 环展开图”更稳
    """
    bgr = _to_bgr(img)
    if bgr is None:
        return ""

    # PaddleOCR 对灰度也可，统一保证是3通道更稳
    if len(bgr.shape) == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)

    res = _OCR.ocr(bgr, det=False, rec=True)
    return _parse_ocr_result(res)