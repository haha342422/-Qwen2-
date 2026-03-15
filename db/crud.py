import json
from sqlalchemy import or_
from db.models import db, Document


def _to_list_categories(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        # 可能是 JSON
        try:
            x = json.loads(s)
            if isinstance(x, list):
                return x
        except Exception:
            pass
        # 逗号分隔
        return [i.strip() for i in s.split(",") if i.strip()]
    return []


def _dump_categories(val):
    # DB中尽量存 JSON 字符串，兼容旧字段类型 Text
    return json.dumps(_to_list_categories(val), ensure_ascii=False)


def _doc_to_dict(d: Document):
    if d is None:
        return None

    out = {}
    # 常见字段（存在就输出）
    for k in [
        "id", "title", "content", "summary", "categories", "level", "issue_date",
        "file_name", "file_type", "upload_url",
        "seal_preview_url", "seal_best_url", "seal_text", "seal_text_refined",
        "created_at", "updated_at",
    ]:
        if hasattr(d, k):
            out[k] = getattr(d, k)

    # categories 统一转 list
    if "categories" in out:
        out["categories"] = _to_list_categories(out["categories"])

    # 如果你后续在 DB 里存了 key_info/layout/seals（JSON字符串），也兼容解析
    for k in ["key_info", "layout", "seals", "classification"]:
        if hasattr(d, k):
            v = getattr(d, k)
            if isinstance(v, str):
                try:
                    out[k] = json.loads(v)
                except Exception:
                    out[k] = v
            else:
                out[k] = v

    return out


def save_document(data: dict) -> int:
    """
    只写入 Document 已存在的列，避免 invalid keyword argument
    """
    fields = {}
    for k, v in (data or {}).items():
        if not hasattr(Document, k):
            continue
        if k == "categories":
            v = _dump_categories(v)
        fields[k] = v

    # 兼容：若 Document 没有 title，但你给了 title，就依然能保存 content
    doc = Document(**fields)
    db.session.add(doc)
    db.session.commit()
    return doc.id


def get_document(doc_id: int):
    doc = db.session.get(Document, doc_id)
    return _doc_to_dict(doc)


def delete_document(doc_id: int):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return
    db.session.delete(doc)
    db.session.commit()


def update_document(doc_id: int, data: dict):
    """
    PUT /api/document/<id>
    可更新：title / level / categories / summary / issue_date 等（存在才写）
    """
    doc = db.session.get(Document, doc_id)
    if not doc:
        return False, None

    for k, v in (data or {}).items():
        if not hasattr(Document, k):
            continue
        if k == "categories":
            v = _dump_categories(v)
        setattr(doc, k, v)

    db.session.commit()
    return True, _doc_to_dict(doc)


def list_documents(page: int = 1, page_size: int = 10):
    q = db.session.query(Document).order_by(Document.id.desc())
    total = q.count()
    pages = (total + page_size - 1) // page_size

    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
        "items": [_doc_to_dict(x) for x in items]
    }


def search_documents(keyword=None, category=None, level=None, page: int = 1, page_size: int = 10):
    q = db.session.query(Document)

    if keyword:
        like = f"%{keyword}%"
        conds = []
        if hasattr(Document, "title"):
            conds.append(Document.title.like(like))
        if hasattr(Document, "content"):
            conds.append(Document.content.like(like))
        if hasattr(Document, "summary"):
            conds.append(Document.summary.like(like))
        if conds:
            q = q.filter(or_(*conds))

    if level and hasattr(Document, "level"):
        q = q.filter(Document.level == level)

    if category and hasattr(Document, "categories"):
        # categories 是 JSON字符串时，直接 LIKE 搜
        q = q.filter(Document.categories.like(f"%{category}%"))

    q = q.order_by(Document.id.desc())

    total = q.count()
    pages = (total + page_size - 1) // page_size

    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
        "items": [_doc_to_dict(x) for x in items]
    }