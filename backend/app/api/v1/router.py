"""v1 路由聚合：在此处汇总所有 endpoints"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, companies, jobs, candidates, matches, agencies, assignments
from app.api.v1.endpoints import resumes, delivery, applications, jobseeker

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(companies.router)
api_router.include_router(jobs.router)
api_router.include_router(candidates.router)
api_router.include_router(matches.router)
api_router.include_router(agencies.router)
api_router.include_router(assignments.router)
api_router.include_router(assignments.provider_router)
api_router.include_router(resumes.router)
api_router.include_router(delivery.router)
api_router.include_router(applications.router)
api_router.include_router(jobseeker.router)


# 示例：健康检查接口
@api_router.get("/ping", summary="健康检查")
def ping() -> dict:
    return {"pong": True}
