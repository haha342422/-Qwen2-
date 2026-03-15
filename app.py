from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import uuid
import traceback

from config import Config

from input.file_loader import load_file
from preprocess.image_process import detect_lines

from preprocess.seal_detector import (
    detect_red_seals,
    crop_by_bbox,
    draw_bboxes,
    save_image,
    generate_seal_ocr_variants,
    choose_best_seal_text,
)

from ocr.ocr_engine import run_ocr, run_ocr_seal
from doc_layout.layout_split import split_layout
from extract.key_info_extractor import extract_key_info

from llm.classifier import classify_document
from llm.summarizer import generate_summary
from llm.seal_refiner import refine_seal_with_qwen

from utils.redactor import redact_text

from db.models import db, init_db
from db.crud import (
    save_document,
    get_document,
    delete_document,
    search_documents,
    list_documents,
    update_document,
)

app = Flask(__name__)
app.config.from_object(Config)

# JSON 中文不转义
app.config["JSON_AS_ASCII"] = False
try:
    app.json.ensure_ascii = False
except Exception:
    pass

db.init_app(app)
with app.app_context():
    init_db()

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

SEAL_DIR = os.path.join(app.config["UPLOAD_FOLDER"], "_seals")
os.makedirs(SEAL_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    name = (name or "file").replace("\\", "_").replace("/", "_")
    return name


def _to_url_path(abs_path: str) -> str:
    """把 uploads 下的绝对路径转成可访问 URL：/uploads/xxx"""
    if not abs_path:
        return ""
    rel = os.path.relpath(abs_path, app.config["UPLOAD_FOLDER"]).replace("\\", "/")
    return f"/uploads/{rel}"


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/uploads/<path:filename>", methods=["GET"])
def serve_uploads(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "ok": True,
        "qwen_api_url": bool(app.config.get("QWEN_API_URL")),
        "upload_folder": app.config["UPLOAD_FOLDER"],
    })


# ========= 平台：列表/检索 =========
@app.route("/api/documents", methods=["GET"])
def api_documents():
    """
    GET /api/documents?page=1&page_size=10&keyword=...&category=...&level=...
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", app.config["PAGE_SIZE"]))
    keyword = request.args.get("keyword")
    category = request.args.get("category")
    level = request.args.get("level")

    if keyword or category or level:
        data = search_documents(keyword=keyword, category=category, level=level, page=page, page_size=page_size)
    else:
        data = list_documents(page=page, page_size=page_size)

    return jsonify(data)


# 兼容你老接口（仍然保留）
@app.route("/api/search", methods=["GET"])
def api_search():
    return api_documents()


# ========= 平台：详情 =========
@app.route("/api/document/<int:doc_id>", methods=["GET"])
def api_get_doc(doc_id: int):
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": "不存在"}), 404
    return jsonify(doc)


# ========= 平台：更新（CRUD 里的 U） =========
@app.route("/api/document/<int:doc_id>", methods=["PUT"])
def api_update_doc(doc_id: int):
    data = request.get_json(silent=True) or {}
    ok, updated = update_document(doc_id, data)
    if not ok:
        return jsonify({"error": "更新失败或不存在"}), 404
    return jsonify({"ok": True, "doc": updated})


# ========= 平台：删除 =========
@app.route("/api/document/<int:doc_id>", methods=["DELETE"])
def api_delete_doc(doc_id: int):
    delete_document(doc_id)
    return jsonify({"message": "删除成功"})


# ========= 核心：上传单文件 =========
@app.route("/api/upload", methods=["POST"])
def upload_document():
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "未上传文件"}), 400

        safe_name = _safe_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{safe_name}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        content, file_type = load_file(filepath)

        seals_payload = {
            "count": 0,
            "candidates": [],
            "preview_url": "",
            "best_crop_url": "",
            "seal_text": "",
            "seal_text_all": [],
            "seal_refine": {
                "seal_text_refined": "",
                "seal_org": None,
                "seal_date": None,
                "explain": "无印章文本"
            }
        }

        # ========= 解析 + OCR =========
        if file_type == "image":
            detect_lines(content)

            # ----- 印章检测 + 多版本OCR -----
            try:
                candidates = (detect_red_seals(content) or [])[:3]
                if candidates:
                    seals_payload["count"] = len(candidates)
                    seals_payload["candidates"] = candidates

                    preview = draw_bboxes(content, [c["bbox"] for c in candidates])
                    preview_path = os.path.join(SEAL_DIR, f"{uuid.uuid4().hex}_preview.png")
                    save_image(preview, preview_path)
                    seals_payload["preview_url"] = _to_url_path(preview_path)

                    seal_text_all = []
                    best_crop_url = ""

                    for i, c in enumerate(candidates):
                        crop = crop_by_bbox(content, c["bbox"])
                        crop_path = os.path.join(SEAL_DIR, f"{uuid.uuid4().hex}_seal_{i}.png")
                        save_image(crop, crop_path)

                        variants = generate_seal_ocr_variants(crop)
                        text_map = []
                        for name, vimg in variants:
                            t = (run_ocr_seal(vimg) or "").strip()
                            text_map.append({"name": name, "text": t})

                        chosen_text, chosen_name, chosen_score = choose_best_seal_text(text_map)

                        seal_text_all.append({
                            "bbox": c["bbox"],
                            "score": c.get("score"),
                            "crop_url": _to_url_path(crop_path),
                            "best_variant": chosen_name,
                            "best_variant_score": chosen_score,
                            "text": chosen_text,
                        })

                        if i == 0:
                            best_crop_url = _to_url_path(crop_path)

                    seals_payload["best_crop_url"] = best_crop_url
                    seals_payload["seal_text_all"] = seal_text_all
                    seals_payload["seal_text"] = "\n".join([x["text"] for x in seal_text_all if x.get("text")]).strip()
            except Exception:
                pass

            text = run_ocr(content)

        elif file_type == "pdf":
            # content 可能是 [page_img...]
            page_texts = []
            if isinstance(content, list) and content:
                for i, page_img in enumerate(content):
                    t = (run_ocr(page_img) or "").strip()
                    if t:
                        page_texts.append(f"【第{i+1}页】\n{t}")
            text = "\n\n".join(page_texts).strip()

        else:
            # docx/txt：load_file 已给文本
            text = (content or "").strip()

        text = (text or "").replace("\r", "\n").strip()

        # ========= 基础脱敏（可开关） =========
        text_for_store = text
        if app.config.get("ENABLE_REDACTION", False):
            text_for_store = redact_text(text_for_store)

        # ========= 版面 / 抽取 =========
        layout = split_layout(text_for_store)
        key_info = extract_key_info(text_for_store)

        # ========= Qwen 分类 + 摘要 =========
        classification = classify_document(text_for_store)
        summary = generate_summary(text_for_store)

        # ========= 印章纠错归一（可选：用 Qwen 结合正文） =========
        try:
            footer_hint = layout.get("版记") if isinstance(layout, dict) else ""
            seals_payload["seal_refine"] = refine_seal_with_qwen(
                seal_text=seals_payload.get("seal_text", ""),
                key_info=key_info,
                doc_title=key_info.get("标题") or "",
                doc_footer_hint=footer_hint or "",
            )
        except Exception:
            pass

        # ========= 入库 =========
        doc_id = save_document({
            "title": key_info.get("标题"),
            "content": text_for_store,
            "summary": summary,
            "categories": classification.get("categories", []),
            "level": classification.get("level"),
            "issue_date": key_info.get("成文日期") or key_info.get("印发日期"),
            # 可选：若你的 Document 有这些列才会写入（crud里会自动过滤）
            "file_name": filename,
            "file_type": file_type,
            "upload_url": f"/uploads/{filename}",
            "seal_preview_url": seals_payload.get("preview_url"),
            "seal_best_url": seals_payload.get("best_crop_url"),
            "seal_text": seals_payload.get("seal_text"),
            "seal_text_refined": (seals_payload.get("seal_refine") or {}).get("seal_text_refined"),
        })

        return jsonify({
            "ok": True,
            "doc_id": doc_id,
            "file_type": file_type,
            "filename": filename,
            "upload_url": f"/uploads/{filename}",
            "ocr_text": text_for_store,
            "layout": layout,
            "key_info": key_info,
            "seals": seals_payload,
            "classification": classification,
            "summary": summary,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "处理失败", "detail": str(e)}), 500


# ========= 批量上传（平台化/效率） =========
@app.route("/api/batch_upload", methods=["POST"])
def batch_upload():
    """
    表单字段：files (multiple)
    """
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "未上传文件"}), 400

        results = []
        for f in files[: app.config["BATCH_MAX_FILES"]]:
            # 复用 upload_document 的逻辑：这里简单做一次内部调用（不走HTTP）
            # 为了清晰，把核心逻辑直接复写一遍最稳
            safe_name = _safe_filename(f.filename)
            filename = f"{uuid.uuid4().hex}_{safe_name}"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            f.save(filepath)

            content, file_type = load_file(filepath)
            text = ""
            if file_type == "image":
                detect_lines(content)
                text = run_ocr(content)
            elif file_type == "pdf":
                page_texts = []
                if isinstance(content, list) and content:
                    for i, page_img in enumerate(content):
                        t = (run_ocr(page_img) or "").strip()
                        if t:
                            page_texts.append(f"【第{i+1}页】\n{t}")
                text = "\n\n".join(page_texts).strip()
            else:
                text = (content or "").strip()

            text = (text or "").replace("\r", "\n").strip()
            if app.config.get("ENABLE_REDACTION", False):
                text = redact_text(text)

            layout = split_layout(text)
            key_info = extract_key_info(text)
            classification = classify_document(text)
            summary = generate_summary(text)

            doc_id = save_document({
                "title": key_info.get("标题"),
                "content": text,
                "summary": summary,
                "categories": classification.get("categories", []),
                "level": classification.get("level"),
                "issue_date": key_info.get("成文日期") or key_info.get("印发日期"),
                "file_name": filename,
                "file_type": file_type,
                "upload_url": f"/uploads/{filename}",
            })

            results.append({
                "doc_id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "title": key_info.get("标题"),
                "level": classification.get("level"),
                "categories": classification.get("categories", []),
            })

        return jsonify({"ok": True, "count": len(results), "results": results})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "批量处理失败", "detail": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)