#python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""FastAPI 应用入口"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, verify_db_ready
from app.crud.user import ensure_admin_user

# Swagger UI 静态资源改为本地提供，避免运行时依赖 cdn.jsdelivr.net（国内访问不稳定会导致 /docs 白屏）
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="毕设后端服务",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # 禁用默认 Swagger/ReDoc（其 JS/CSS 依赖 CDN，国内易白屏），改用下方本地资源版本
    docs_url=None,
    redoc_url=None,
)

# CORS：允许前端跨域访问（仅放行配置中的白名单来源）
# CORS：它是后端设的"门禁名单"，告诉浏览器"这几个网站可以来调我接口"。没有它，前端就调不到后端。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,#允许哪些"来源"来串门（白名单，去配置里读）
    allow_credentials=True,
    allow_methods=["*"],#允许用什么方法（`*` =全部，GET/POST/PATCH 都行）
    allow_headers=["*"],#允许带什么东西
)

# 挂载本地静态资源目录（本地 Swagger UI 的 css/js/favicon）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/docs", include_in_schema=False)
async def local_swagger_ui():
    """自定义 Swagger UI：改用本地 css/js，规避 CDN 白屏"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{settings.PROJECT_NAME} - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon-32x32.png",
    )


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def local_swagger_ui_oauth2_redirect():
    """Swagger Authorize 登录时回调用的页面"""
    return get_swagger_ui_oauth2_redirect_html()


@app.on_event("startup")
async def startup() -> None:
    """应用启动时执行：只读检查数据库迁移版本 + 初始化管理员账号"""
    verify_db_ready()
    seed_admin()


def seed_admin() -> None:
    """幂等创建初始管理员（账号密码取自 .env，已存在则跳过）"""
    db = SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()


@app.on_event("shutdown")
async def shutdown() -> None:
    """应用关闭时执行：释放资源"""
    pass


# 注册 v1 路由
app.include_router(api_router, prefix=settings.API_V1_STR)
#`prefix=settings.API_V1_STR` → 意思是所有接口的网址都带一个固定头，比如`/api/v1`。
# 这样前端调用时，就不用每次写完整路径了。

@app.get("/")
def root() -> dict:
    """根路径健康检查"""
    return {"message": "Welcome to Graduation Project Backend", "docs": "/docs"}