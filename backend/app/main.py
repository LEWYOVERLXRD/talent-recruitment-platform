"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.crud.user import ensure_admin_user

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="毕设后端服务",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
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


@app.on_event("startup")
async def startup() -> None:
    """应用启动时执行：建表 + 初始化管理员账号"""
    init_db()
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