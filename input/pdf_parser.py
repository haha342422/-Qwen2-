# input/pdf_parser.py
import fitz  # PyMuPDF
import numpy as np
import cv2


def pdf_to_images(pdf_path: str, dpi: int = 200):
    """
    将 PDF 每页渲染成 OpenCV BGR 图片（np.ndarray）
    不依赖 poppler，Windows 最稳。
    """
    doc = fitz.open(pdf_path)
    images = []

    # DPI -> zoom
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=mat, alpha=False)  # alpha=False 更稳
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        # pix.n 通常是 3（RGB）
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        images.append(img)

    doc.close()
    return images