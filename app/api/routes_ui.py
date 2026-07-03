from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/ui", response_class=HTMLResponse)
def ui():
    return HTMLResponse("<html><body><h1>Healing Agent UI</h1></body></html>")
