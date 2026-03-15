# preprocess/image_process.py
from __future__ import annotations
import os
import cv2
import numpy as np
from typing import Any, Dict, Optional, Union

def detect_lines(image_input: Union[str, Any], save_path: Optional[str] = None) -> Dict[str, object]:
    """
    分割线检测（HoughLinesP）
    image_input: 图片路径 或 numpy图像
    save_path: 可选，保存绘制了线段的图片
    return: {"line_count": int, "save_path": str|None}
    """
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_input}")
    else:
        img = image_input
        if img is None:
            raise ValueError("image_input为空")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=120,
        minLineLength=80,
        maxLineGap=10,
    )

    out = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    line_count = 0
    if lines is not None:
        line_count = len(lines)
        for l in lines:
            x1, y1, x2, y2 = l[0]
            cv2.line(out, (x1, y1), (x2, y2), (0, 255, 0), 2)

    saved = None
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, out)
        saved = save_path

    return {"line_count": line_count, "save_path": saved}