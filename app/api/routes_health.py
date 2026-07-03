from fastapi import APIRouter
from fastapi.responses import FileResponse

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
