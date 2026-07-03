from fastapi import FastAPI
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_audio import router as audio_router
from app.core.lifecycle import clear_data_files

app = FastAPI(
    title="Healing Score Agent",
    version="0.1.0",
    description="Supportive dialogue and risk scoring prototype"
)

app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(audio_router, prefix="/audio", tags=["audio"])


@app.on_event("shutdown")
def _on_shutdown():
    """服务关闭时清理 data/ 中的持久化文件（仅 dev 模式）"""
    clear_data_files()


@app.get("/")
def root():
    return {"message": "Healing Score Agent is running"}
