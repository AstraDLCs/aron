from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, candidates, cv_files, health, persons, positions, requirements, sources, state, users
from app.routers import settings as settings_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Pulso Laboral API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(users.router)
    for module in (state, positions, sources, requirements, settings_router, cv_files, persons, candidates):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
