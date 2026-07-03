from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
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


@router.get("/ui/app.js")
def web_script():
    return FileResponse("app/web/app.js")
