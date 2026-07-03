from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/app")
def web_app():
    return FileResponse("app/web/index.html")


@router.get("/app/styles.css")
def web_styles():
    return FileResponse("app/web/styles.css")


@router.get("/app/app.js")
def web_script():
    return FileResponse("app/web/app.js")
