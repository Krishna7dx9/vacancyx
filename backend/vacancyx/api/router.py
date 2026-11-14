"""Versioned API router."""

from fastapi import APIRouter

from vacancyx.api.routes.candidates import router as candidates_router

api_router = APIRouter()
api_router.include_router(candidates_router)
