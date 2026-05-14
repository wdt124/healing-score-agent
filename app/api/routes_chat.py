from fastapi import APIRouter
from app.models.schemas import ChatRequest, ChatResponse
from app.services.pipeline_service import run_pipeline

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
def chat_message(request: ChatRequest):
    result = run_pipeline(request.user_text, audio_path=request.audio_path)
    return ChatResponse(**result)