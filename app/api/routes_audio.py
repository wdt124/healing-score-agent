from pathlib import Path
from uuid import uuid4
import re

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()

UPLOAD_ROOT = Path("data/uploads")


def _safe_session_id(session_id: str | None) -> str:
    if not session_id:
        return "anonymous"
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
    return safe[:80] or "anonymous"


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
):
    """保存前端录音文件，并返回可传给 /chat/message 的 audio_path。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少音频文件名。")

    raw_suffix = Path(file.filename).suffix.lower()
    suffix = raw_suffix if raw_suffix in {".wav", ".mp3", ".m4a", ".ogg", ".webm"} else ".wav"

    session_dir = UPLOAD_ROOT / _safe_session_id(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    target_path = session_dir / f"{uuid4().hex}{suffix}"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="音频文件为空。")

    target_path.write_bytes(content)

    return {
        "audio_path": target_path.as_posix(),
        "filename": target_path.name,
        "content_type": file.content_type,
        "size_bytes": len(content),
    }
