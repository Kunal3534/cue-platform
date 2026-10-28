import logging
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import projects, edits, views, callsheets, exports, chat, events
from .routes import auth, scenarios, resources, share, editorial

_log = logging.getLogger(__name__)

# Warn loudly if production + dev bypass is set
if settings.env == "production" and settings.dev_auto_login_email:
    warnings.warn(
        "DEV_AUTO_LOGIN_EMAIL is set in a production environment — "
        "all requests will be authenticated as that user without a session cookie. "
        "Unset DEV_AUTO_LOGIN_EMAIL before deploying.",
        stacklevel=1,
    )
    _log.critical(
        "SECURITY WARNING: DEV_AUTO_LOGIN_EMAIL is set in production (%s). "
        "Remove it immediately.",
        settings.dev_auto_login_email,
    )

app = FastAPI(title="Cue API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(edits.router)
app.include_router(views.router)
app.include_router(callsheets.router)
app.include_router(exports.router)
app.include_router(chat.router)
app.include_router(events.router)
app.include_router(scenarios.router)
app.include_router(resources.router)
app.include_router(share.router)
app.include_router(editorial.router)


@app.get("/")
def root():
    return {"ok": True, "service": "cue-api", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"ok": True}
