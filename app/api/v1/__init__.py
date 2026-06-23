"""
API v1 module.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import tasks, evaluation, reports, benchmark

api_router = APIRouter()

api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(evaluation.router, prefix="/evaluations", tags=["evaluations"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(benchmark.router, prefix="/benchmark", tags=["benchmark"])
