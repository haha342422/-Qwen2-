# input/file_loader.py
import os
import cv2

from .pdf_parser import pdf_to_images
from .docx_parser import docx_to_text


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
PDF_EXTS = {".pdf"}
WORD_EXTS = {".docx", ".doc"}


def load_file(file_path: str):
    """
    返回 (content, file_type)
    - image: content = np.ndarray(BGR)
    - pdf:   content = list[np.ndarray(BGR)]  # 每页一张
    - text:  content = str  # Word/docx 解析后的纯文本
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在：{file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    # 1) 图片
    if ext in IMAGE_EXTS:
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError(f"图片读取失败（可能路径含中文或文件损坏）：{file_path}")
        return img, "image"

    # 2) PDF -> 每页渲染成图片（后续走 OCR）
    if ext in PDF_EXTS:
        images = pdf_to_images(file_path, dpi=200)
        if not images:
            raise ValueError("PDF 渲染失败：未得到任何页面图像")
        return images, "pdf"

    # 3) Word
    if ext == ".docx":
        text = docx_to_text(file_path)
        if not text:
            text = ""
        return text, "text"

    if ext == ".doc":
        # .doc 旧格式很麻烦（需要 LibreOffice/antiword/textract 等），这里给清晰提示
        raise ValueError("暂不直接支持 .doc（旧Word格式），请用 Word 另存为 .docx 再上传。")

    raise ValueError(f"不支持的文件类型：{ext}")