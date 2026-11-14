"""Versioned API router."""

from fastapi import APIRouter

from vacancyx.api.routes.candidates import router as candidates_router
from vacancyx.api.routes.resumes import router as resumes_router
from vacancyx.api.routes.resume_parsing import router as resume_parsing_router

api_router = APIRouter()
api_router.include_router(candidates_router)
api_router.include_router(resumes_router)
api_router.include_router(resume_parsing_router)
