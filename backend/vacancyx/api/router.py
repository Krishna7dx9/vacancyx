"""Versioned API router."""

from fastapi import APIRouter

from vacancyx.api.routes.answers import router as answers_router
from vacancyx.api.routes.candidates import router as candidates_router
from vacancyx.api.routes.jobs import router as jobs_router
from vacancyx.api.routes.resume_parsing import router as resume_parsing_router
from vacancyx.api.routes.resumes import router as resumes_router
from vacancyx.api.routes.search_profiles import router as search_profiles_router

api_router = APIRouter()
api_router.include_router(candidates_router)
api_router.include_router(jobs_router)
api_router.include_router(search_profiles_router)
api_router.include_router(answers_router)
api_router.include_router(resumes_router)
api_router.include_router(resume_parsing_router)
