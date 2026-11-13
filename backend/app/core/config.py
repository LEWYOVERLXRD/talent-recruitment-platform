"""应用配置：通过 .env 读取环境变量，集中管理参数"""
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # 基础信息
    PROJECT_NAME: str = "毕设后端"
    API_V1_STR: str = "/api/v1"

    # 数据库（拆分字段，便于处理密码中的特殊字符）
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "graduation_project"
    DB_ECHO: bool = False  # 是否打印 SQL 日志

    # 安全
    SECRET_KEY: str = Field(repr=False)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    # 初始管理员（服务启动时幂等创建，不开放注册）
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_REAL_NAME: str = "平台管理员"

    # 忘记密码（密保）安全策略
    RESET_MAX_FAILED: int = 5          # 连续答错多少次触发锁定
    RESET_LOCK_MINUTES: int = 15       # 锁定时长（分钟）

    # 跨域
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # LLM 接入（后续阶段填充）
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "gpt-3.5-turbo"
    LLM_TIMEOUT_SECONDS: float = 60.0
    # 备用模型：主模型不可用时自动降级；留空则只使用主模型
    LLM_FALLBACK_MODEL: str = ""
    LLM_FALLBACK_BASE_URL: str = ""  # 留空则复用 LLM_BASE_URL

    # 私有简历目录，不挂载到静态资源
    RESUME_STORAGE_DIR: Path = BASE_DIR / "private_uploads" / "resumes"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        hide_input_in_errors=True,
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_signing_key(cls, value: str) -> str:
        if (len(value) < 32 or value != value.strip() or
                value.lower().startswith(("your_", "change-me", "replace-me"))):
            raise ValueError("SECRET_KEY 必须为至少 32 字符的独立随机密钥，不能使用默认值或占位符")
        return value

    def get_database_url(self) -> str:
        """构造 MySQL 连接字符串。

        使用 quote_plus 对密码做 URL 编码，避免密码里出现 + / @ : 等
        特殊字符导致 SQLAlchemy 解析 URL 时出错。
        """
        pwd = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{self.DB_USER}:{pwd}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


settings = Settings()
