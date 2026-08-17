from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings_config import settings


def configure_cors(app: FastAPI) -> None:
    allowed_origins = settings.ALLOWED_ORIGINS
    app.state.allowed_origins = allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )