import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 确保能找到 .env 文件
# 尝试从多个位置加载
env_paths = [
    os.path.join(os.path.dirname(__file__), "..", ".env"),  # backend/.env
    os.path.join(os.path.dirname(__file__), "..", "..", ".env"),  # .env
    ".env"  # 当前目录
]

for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break
else:
    # 如果都没找到，尝试加载默认配置
    load_dotenv()


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))


def _resolve_project_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    cleaned = path[2:] if path.startswith("./") else path
    return os.path.abspath(os.path.join(PROJECT_ROOT, cleaned))


class Settings(BaseSettings):
    app_name: str = os.getenv("APP_NAME", "AI Tutor")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"

    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "root")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "ai_tutor")

    @property
    def database_url(self) -> str:
        # Check if DATABASE_URL is set in environment, otherwise use MySQL
        env_url = os.getenv("DATABASE_URL", "")
        if env_url:
            return env_url
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    secret_key: str = os.getenv("SECRET_KEY", "1f2f5999e2c3f1bd4d7a05c0261a44df2ac407484056b9703fadbba03091de0f")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))


    # 硅基流动配置
    vision_model: str = os.getenv("VISION_MODEL", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    siliconflow_api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
    siliconflow_api_base: str = os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")

    # 超算互联网配置（比赛限定模型 - Qwen3-Embedding-8B）
    chaosuan_api_key: str = os.getenv("CHAOSUAN_API_KEY", "")
    chaosuan_api_base: str = os.getenv("CHAOSUAN_API_BASE", "https://api.scnet.cn/v1")
    chaosuan_embedding_model: str = os.getenv("CHAOSUAN_EMBEDDING_MODEL", "Qwen3-Embedding-8B")

    # DashScope（通义千问官方）配置
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_api_base: str = os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/api/v1")
    dashscope_embedding_model: str = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3")

    # 豆包/火山引擎配置（备用）
    volc_access_key: str = os.getenv("VOLC_ACCESS_KEY", "")
    volc_secret_key: str = os.getenv("VOLC_SECRET_KEY", "")
    volc_region: str = os.getenv("VOLC_REGION", "cn-beijing")
    volc_endpoint: str = os.getenv("VOLC_ENDPOINT", "ark.cn-beijing.volces.com")
    volc_model: str = os.getenv("VOLC_MODEL", "")
    volc_vision_model: str = os.getenv("VOLC_VISION_MODEL", "")
    volc_embedding_model: str = os.getenv("VOLC_EMBEDDING_MODEL", "")

    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./storage/chroma")
    chroma_collection_name: str = os.getenv("CHROMA_COLLECTION_NAME", "sequence_questions")

    kg_persist_dir: str = os.getenv("KG_PERSIST_DIR", "./storage/kg")
    kg_file_name: str = os.getenv("KG_FILE_NAME", "sequence_kg.json")

    upload_dir: str = os.getenv("UPLOAD_DIR", "./storage/uploads")
    max_upload_size: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))

    cors_origins: List[str] = os.getenv("CORS_ORIGINS", '["http://localhost:3000", "http://localhost:5173"]').strip("[]").replace('"', '').split(",")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_dir: str = os.getenv("LOG_DIR", "./logs")

    verbose: bool = Field(default=False, env="VERBOSE")


settings = Settings()

settings.chroma_persist_dir = _resolve_project_path(settings.chroma_persist_dir)
settings.kg_persist_dir = _resolve_project_path(settings.kg_persist_dir)
settings.upload_dir = _resolve_project_path(settings.upload_dir)
settings.log_dir = _resolve_project_path(settings.log_dir)
