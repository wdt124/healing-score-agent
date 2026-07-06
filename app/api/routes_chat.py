from fastapi import APIRouter
from app.models.schemas import ChatRequest, ChatResponse
from app.services.pipeline_service import run_pipeline

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
def chat_message(request: ChatRequest):
    agent_profile = request.agent_profile.model_dump() if request.agent_profile else None
    result = run_pipeline(
        request.user_text,
        audio_path=request.audio_path,
        session_id=request.session_id,
        agent_profile=agent_profile,
    )
    return ChatResponse(**result)
