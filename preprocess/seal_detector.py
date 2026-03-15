import os
import cv2
import numpy as np


def save_image(img, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, img)


def crop_by_bbox(img, bbox):
    x1, y1, x2, y2 = bbox
    h, w = img.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w - 1, int(x2)), min(h - 1, int(y2))
    return img[y1:y2, x1:x2].copy()


def draw_bboxes(img, bboxes, color=(0, 255, 0), thickness=2):
    out = img.copy()
    for (x1, y1, x2, y2) in bboxes:
        cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
    return out


def _red_mask_hsv(img_bgr):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # 红色两个区间
    lower1 = np.array([0, 50, 50])
    upper1 = np.array([10, 255, 255])
    lower2 = np.array([160, 50, 50])
    upper2 = np.array([180, 255, 255])
    m1 = cv2.inRange(hsv, lower1, upper1)
    m2 = cv2.inRange(hsv, lower2, upper2)
    mask = cv2.bitwise_or(m1, m2)
    # 去噪 + 填洞
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    return mask


def detect_red_seals(img_bgr):
    """
    返回候选印章 bbox 列表：
    [{"bbox":[x1,y1,x2,y2], "score":0.xx}, ...] 按 score 降序
    """
    if img_bgr is None:
        return []

    mask = _red_mask_hsv(img_bgr)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = img_bgr.shape[:2]
    results = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 500:  # 太小的噪声
            continue

        x, y, bw, bh = cv2.boundingRect(c)
        if bw < 30 or bh < 30:
            continue

        # 形状约束：印章一般接近正方形区域（圆章外接矩形）
        ratio = bw / (bh + 1e-6)
        if ratio < 0.6 or ratio > 1.6:
            continue

        # 圆形度（越接近1越圆）
        peri = cv2.arcLength(c, True)
        circularity = (4 * np.pi * area) / (peri * peri + 1e-6)

        # 面积占比（过滤过大的红块）
        box_area = bw * bh
        area_ratio = area / (box_area + 1e-6)

        # 打分：圆形度 + 红色占比 + 尺寸
        size_score = min(1.0, box_area / (0.12 * w * h + 1e-6))
        score = 0.45 * np.clip(circularity, 0, 1) + 0.35 * np.clip(area_ratio, 0, 1) + 0.20 * size_score

        results.append({"bbox": [x, y, x + bw, y + bh], "score": float(score)})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _enhance_for_ocr(gray):
    """通用增强：放大 + 对比度 + 锐化"""
    if gray is None:
        return None
    # 放大（印章字很细，放大明显有效）
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)

    # CLAHE 提升局部对比度
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 轻微锐化
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]], dtype=np.float32)
    gray = cv2.filter2D(gray, -1, kernel)
    return gray


def _seal_binary_from_red(img_bgr):
    """
    用红色信息生成“黑字白底”的二值图（比直接灰度更适合红章）
    """
    b, g, r = cv2.split(img_bgr)
    # 红度：r - max(g,b)
    red = cv2.subtract(r, cv2.max(g, b))
    red = cv2.normalize(red, None, 0, 255, cv2.NORM_MINMAX)
    red = cv2.GaussianBlur(red, (3, 3), 0)
    _, th = cv2.threshold(red, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 让文字变黑：反相（OCR更稳）
    th = 255 - th

    # 去小噪点
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k, iterations=1)
    return th


def unwrap_seal_ring(img_bgr):
    """
    圆环展开：把印章外圈文字拉直成一条长条图
    返回展开后的灰度/二值图（黑字白底）
    """
    if img_bgr is None:
        return None

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # 先用红色mask找一个近似圆心
    mask = _red_mask_hsv(img_bgr)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    center = None
    radius = None
    if cnts:
        c = max(cnts, key=cv2.contourArea)
        (cx, cy), r = cv2.minEnclosingCircle(c)
        center = (float(cx), float(cy))
        radius = float(r)

    # HoughCircles 再尝试更稳的圆参数
    try:
        circles = cv2.HoughCircles(
            gray_blur, cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=gray.shape[0] / 4,
            param1=120, param2=30,
            minRadius=20,
            maxRadius=int(min(gray.shape[:2]) * 0.6)
        )
        if circles is not None:
            circles = np.squeeze(circles, axis=0)
            # 取半径最大那个
            circles = sorted(circles, key=lambda x: x[2], reverse=True)
            x, y, r = circles[0]
            center = (float(x), float(y))
            radius = float(r)
    except Exception:
        pass

    if center is None or radius is None or radius < 25:
        return None

    # 极坐标展开：x=角度(0..360) y=半径(0..R)
    # width 取 720（2像素/度），height 取 radius
    width = 720
    height = int(radius)
    polar = cv2.warpPolar(
        gray, (width, height), center, radius,
        flags=cv2.WARP_POLAR_LINEAR + cv2.WARP_FILL_OUTLIERS
    )

    # 外圈文字通常在靠外侧半径区域，截取一个环带
    y1 = int(height * 0.65)
    y2 = int(height * 0.98)
    band = polar[y1:y2, :]

    # 增强 + 二值化
    band = _enhance_for_ocr(band)
    _, th = cv2.threshold(band, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = 255 - th  # 黑字白底

    return th


def generate_seal_ocr_variants(seal_crop_bgr):
    """
    返回多个“更适合印章OCR”的候选图像：
    - variant_name, img (BGR或灰度/二值都可以，ocr_engine会处理)
    """
    if seal_crop_bgr is None or seal_crop_bgr.size == 0:
        return []

    variants = []

    # A) 原图灰度增强
    gray = cv2.cvtColor(seal_crop_bgr, cv2.COLOR_BGR2GRAY)
    gray_enh = _enhance_for_ocr(gray)
    variants.append(("gray_enh", gray_enh))

    # B) 红色分离二值
    th = _seal_binary_from_red(seal_crop_bgr)
    th = cv2.resize(th, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    variants.append(("red_binary", th))

    # C) 圆环展开（外圈更准）
    ring = unwrap_seal_ring(seal_crop_bgr)
    if ring is not None:
        # 让图像高度适合 OCR
        ring = cv2.resize(ring, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        variants.append(("ring_unwrap", ring))

    return variants


def choose_best_seal_text(text_map):
    """
    text_map: [{"name":..., "text":...}, ...]
    用启发式选一个最靠谱的印章文本
    """
    def score_text(t: str):
        if not t:
            return 0
        t2 = t.replace(" ", "").replace("\n", "")
        # 中文字符越多越好，出现“办”“章”“公司”“委员会”等更好
        zh = sum(1 for ch in t2 if "\u4e00" <= ch <= "\u9fff")
        bonus = 0
        for kw in ["办公室", "人民政府", "委员会", "有限公司", "公司", "专用章", "印章", "公章"]:
            if kw in t2:
                bonus += 6
        # 年月日出现加分
        if ("年" in t2 and "月" in t2) or ("20" in t2):
            bonus += 4
        # 太多奇怪字符扣分
        bad = sum(1 for ch in t2 if ch in ["|", "_", "~", "^"])
        return zh * 2 + bonus - bad * 2 + min(len(t2), 60)

    best = ""
    best_name = ""
    best_score = -1
    for item in text_map:
        t = (item.get("text") or "").strip()
        s = score_text(t)
        if s > best_score:
            best_score = s
            best = t
            best_name = item.get("name", "")

    return best, best_name, best_score