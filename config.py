# config.py
import os


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # Upload
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(50 * 1024 * 1024)))  # 50MB

    # DB
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///document.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # =========================
    # Qwen2（默认使用 LM Studio 本地 OpenAI-compatible 接口）
    # 只要 LM Studio 的 Local Server 是 Running，这里就能直接用，
    # 不需要每次在终端里手动设置环境变量。
    # =========================
    # 1) LM Studio（你现在用的）：http://127.0.0.1:1234/v1/chat/completions
    # 2) Ollama（可选）：         http://127.0.0.1:11434/v1/chat/completions
    # 3) vLLM（可选）：           http://127.0.0.1:8000/v1/chat/completions
    QWEN_API_URL = os.getenv(
        "QWEN_API_URL",
        "http://127.0.0.1:1234/v1/chat/completions"
    ).strip()

    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "EMPTY").strip()

    # 你在 LM Studio 右侧看到的 API Model Identifier，默认就是这个
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5-3b-instruct").strip()

    # 超时
    QWEN_TIMEOUT = int(os.getenv("QWEN_TIMEOUT", "60"))
     # 平台化：分页/批量
    PAGE_SIZE = int(os.getenv("PAGE_SIZE", "10"))
    BATCH_MAX_FILES = int(os.getenv("BATCH_MAX_FILES", "20"))

    # 安全：脱敏开关（1=开启）
    ENABLE_REDACTION = os.getenv("ENABLE_REDACTION", "0").strip() == "1"