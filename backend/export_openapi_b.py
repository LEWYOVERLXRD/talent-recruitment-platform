"""导出实际注册路由的 OpenAPI；提供无凭据配置，避免读取项目 .env。"""
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from sqlalchemy.orm import declarative_base

database = ModuleType("app.core.database")
database.Base = declarative_base()
database.get_db = lambda: None
sys.modules["app.core.database"] = database

config = ModuleType("app.core.config")
config.settings = SimpleNamespace(
    SECRET_KEY="OFFLINE_OPENAPI_ONLY", ALGORITHM="HS256",
    ACCESS_TOKEN_EXPIRE_MINUTES=60, LLM_MODEL="OFFLINE_OPENAPI_ONLY",
)
sys.modules["app.core.config"] = config

from fastapi import FastAPI
from app.api.v1.router import api_router

app = FastAPI(title="高端人才定制化智能招聘平台 API", version="B 批交付")
app.include_router(api_router, prefix="/api/v1")
output = Path(__file__).resolve().parents[1] / "接口契约_B批.openapi.json"
output.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OpenAPI exported: {output}")
print(f"Paths: {len(app.openapi()['paths'])}")
