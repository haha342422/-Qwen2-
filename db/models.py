# db/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    summary = db.Column(db.Text)

    # 用 JSON 字符串存 categories
    categories = db.Column(db.Text)  # '["教育","科技"]'
    level = db.Column(db.String(50))
    issue_date = db.Column(db.String(50))

    # ====== 印章相关（新增）======
    seal_count = db.Column(db.Integer, default=0)
    seals = db.Column(db.Text)  # JSON 字符串，存候选框等信息
    seal_preview_path = db.Column(db.String(500))
    seal_crop_path = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        try:
            categories = json.loads(self.categories) if self.categories else []
        except Exception:
            categories = []

        try:
            seals = json.loads(self.seals) if self.seals else []
        except Exception:
            seals = []

        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "categories": categories,
            "level": self.level,
            "issue_date": self.issue_date,
            "seal_count": self.seal_count,
            "seals": seals,
            "seal_preview_path": self.seal_preview_path,
            "seal_crop_path": self.seal_crop_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db():
    db.create_all()