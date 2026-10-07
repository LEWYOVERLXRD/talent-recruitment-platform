"""v1 路由聚合：在此处汇总所有 endpoints"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, companies, jobs

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(companies.router)
api_router.include_router(jobs.router)


# 示例：健康检查接口
@api_router.get("/ping", summary="健康检查")
def ping() -> dict:
    return {"pong": True}
