from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import FileResponse
from app.services.pipeline_service import run_pipeline

router = APIRouter()


@router.get("")
def health_check():
    return {"status": "ok"}


@router.get("/ui")
def web_app():
    return FileResponse("app/web/index.html")


@router.get("/ui/styles.css")
def web_styles():
    return FileResponse("app/web/styles.css")


@router.get("/ui/dev.css")
def web_dev_styles():
    return FileResponse("app/web/dev.css")


@router.get("/ui/profile_manager.js")
def web_profile_script():
    return FileResponse("app/web/profile_manager.js")


@router.get("/ui/app.js")
def web_script():
    return FileResponse("app/web/app.js")


@router.get("/ui/custom_tone.js")
def web_custom_tone_script():
    return FileResponse("app/web/custom_tone.js")


@router.get("/ui/score_diagnostics_fix.js")
def web_score_diagnostics_script():
    return FileResponse("app/web/score_diagnostics_fix.js")


@router.post("/ui/send")
async def web_send(
    user_text: str = Form(default=""),
    session_id: str = Form(default=""),
    audio_file: UploadFile | None = File(default=None),
):
    result = run_pipeline(user_text, session_id=session_id or None)
    return result
