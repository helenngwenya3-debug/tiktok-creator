import uuid
import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Media, MediaType
from app.auth import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/media", tags=["media"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/avi"}


@router.get("/library", response_class=HTMLResponse)
def library_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    media_items = db.query(Media).filter(Media.user_id == user.id).order_by(Media.created_at.desc()).all()
    return templates.TemplateResponse("media/library.html", {
        "request": request, "user": user, "media_items": media_items
    })


@router.post("/upload")
async def upload_media(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    uploaded = []
    for file in files:
        if file.content_type in ALLOWED_IMAGE_TYPES:
            media_type = MediaType.image
            subfolder = "images"
        elif file.content_type in ALLOWED_VIDEO_TYPES:
            media_type = MediaType.video
            subfolder = "videos"
        else:
            raise HTTPException(400, f"Unsupported file type: {file.content_type}")

        ext = Path(file.filename).suffix or ".bin"
        filename = f"{uuid.uuid4()}{ext}"
        save_dir = Path(settings.UPLOAD_DIR) / subfolder
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / filename

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size = os.path.getsize(file_path)
        media = Media(
            user_id=user.id,
            filename=filename,
            original_name=file.filename,
            file_path=str(file_path),
            media_type=media_type,
            file_size=file_size,
            source="upload",
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        uploaded.append({"id": media.id, "filename": media.filename, "type": media_type.value})

    return JSONResponse({"uploaded": uploaded})


@router.delete("/{media_id}")
def delete_media(media_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    media = db.query(Media).filter(Media.id == media_id, Media.user_id == user.id).first()
    if not media:
        raise HTTPException(404, "Media not found")
    try:
        os.remove(media.file_path)
    except FileNotFoundError:
        pass
    db.delete(media)
    db.commit()
    return JSONResponse({"deleted": True})


@router.get("/api/list")
def list_media_api(
    media_type: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Media).filter(Media.user_id == user.id)
    if media_type:
        query = query.filter(Media.media_type == media_type)
    items = query.order_by(Media.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "filename": m.filename,
            "original_name": m.original_name,
            "type": m.media_type.value,
            "source": m.source,
            "url": f"/static/uploads/{'images' if m.media_type == MediaType.image else 'videos'}/{m.filename}",
            "created_at": m.created_at.isoformat(),
        }
        for m in items
    ]
