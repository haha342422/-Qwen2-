# preprocess/seal_preprocess.py
import cv2
import numpy as np


def seal_enhance_for_ocr(bgr_img, scale: int = 3):
    """
    输入：BGR(OpenCV)图
    输出：增强后的BGR图（可直接喂给 PaddleOCR）
    适配多图片，不依赖某一张图的阈值。
    """
    if bgr_img is None:
        return None

    img = bgr_img.copy()

    # 1) 放大（章通常很小，放大提升巨大）
    h, w = img.shape[:2]
    if min(h, w) < 300:
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    # 2) 转 HSV，提取红色（兼容浅红/深红）
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower1 = np.array([0, 50, 50])
    upper1 = np.array([10, 255, 255])
    lower2 = np.array([160, 50, 50])
    upper2 = np.array([179, 255, 255])
    mask1 = cv2.inRange(hsv, lower1, upper1)
    mask2 = cv2.inRange(hsv, lower2, upper2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    # 3) 形态学：补断裂字
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # 4) 用mask把红字“抠出来”，再转灰度
    red_only = cv2.bitwise_and(img, img, mask=red_mask)
    gray = cv2.cvtColor(red_only, cv2.COLOR_BGR2GRAY)

    # 5) 自适应阈值/OTSU（二选一：这里用 OTSU 更稳）
    gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 6) 反色（让字更像“黑字白底”）
    bw = 255 - bw

    # 7) 再做一次轻微膨胀，让细字更粗一点
    bw = cv2.dilate(bw, kernel, iterations=1)

    # PaddleOCR 更喜欢 3通道
    out = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    return out