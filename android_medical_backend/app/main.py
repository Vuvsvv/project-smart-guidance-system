from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routes.chat import router as chat_router
from app.routes.recommend import router as recommend_router
from app.routes.generate_script import router as generate_script_router
from app.services.ai_service import initialize_ai

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI 智慧醫療掛號導引系統",
    description="根據使用者症狀與偏好，提供多輪問答、推薦方案與 Android 導引腳本。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(recommend_router)
app.include_router(generate_script_router)


@app.on_event("startup")
def on_startup() -> None:
    try:
        initialize_ai()
    except Exception as exc:
        logger.warning("AI initialization failed during startup; API fallback remains available: %s", exc)
