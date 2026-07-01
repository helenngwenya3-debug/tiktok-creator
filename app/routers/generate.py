from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Media, MediaType
from app.auth import get_current_user
from app.schemas import GenerateImageRequest, GenerateVideoRequest, SlideShowRequest
from app.services import image_gen, video_gen
from app.config import get_settings

router = APIRouter(prefix="/generate", tags=["generate"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/image", response_class=HTMLResponse)
def image_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("generate/image.html", {"request": request, "user": user})


@router.get("/video", response_class=HTMLResponse)
def video_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("generate/video.html", {"request": request, "user": user})


@router.post("/image")
async def generate_image(
    body: GenerateImageRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        if settings.HUGGINGFACE_API_KEY:
            file_path, filename = await image_gen.generate_image_hf(
                body.prompt, body.negative_prompt, body.width, body.height
            )
        elif settings.REPLICATE_API_TOKEN:
            file_path, filename = await image_gen.generate_image_replicate(body.prompt, body.negative_prompt)
        else:
            raise HTTPException(400, "No image generation API key configured. Add HUGGINGFACE_API_KEY or REPLICATE_API_TOKEN to .env")

        media = Media(
            user_id=user.id,
            filename=filename,
            original_name=filename,
            file_path=file_path,
            media_type=MediaType.image,
            prompt=body.prompt,
            source="generated",
        )
        db.add(media)
        db.commit()
        db.refresh(media)

        return JSONResponse({
            "id": media.id,
            "filename": filename,
            "url": f"/static/uploads/images/{filename}",
            "prompt": body.prompt,
        })
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/image/img2img")
async def generate_image_img2img(
    prompt: str = Form(...),
    strength: float = Form(0.8),
    reference: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not settings.REPLICATE_API_TOKEN:
        raise HTTPException(400, "REPLICATE_API_TOKEN not configured. Add it in Railway variables.")
    try:
        image_bytes = await reference.read()
        if not image_bytes:
            raise HTTPException(400, "Reference image is empty")
        file_path, filename = await image_gen.generate_image_img2img_replicate(prompt, image_bytes, strength)

        media = Media(
            user_id=user.id,
            filename=filename,
            original_name=filename,
            file_path=file_path,
            media_type=MediaType.image,
            prompt=prompt,
            source="generated",
        )
        db.add(media)
        db.commit()
        db.refresh(media)

        return JSONResponse({
            "id": media.id,
            "filename": filename,
            "url": f"/static/uploads/images/{filename}",
            "prompt": prompt,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/video/ai")
async def generate_ai_video(
    body: GenerateVideoRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not settings.REPLICATE_API_TOKEN:
        raise HTTPException(400, "REPLICATE_API_TOKEN not configured in .env")
    try:
        file_path, filename = await video_gen.generate_ai_video_replicate(body.prompt, body.duration)
        media = Media(
            user_id=user.id,
            filename=filename,
            original_name=filename,
            file_path=file_path,
            media_type=MediaType.video,
            prompt=body.prompt,
            source="generated",
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        return JSONResponse({
            "id": media.id,
            "filename": filename,
            "url": f"/static/uploads/videos/{filename}",
        })
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/video/slideshow")
async def create_slideshow(
    body: SlideShowRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    media_items = db.query(Media).filter(
        Media.id.in_(body.media_ids),
        Media.user_id == user.id,
        Media.media_type == MediaType.image,
    ).all()

    if not media_items:
        raise HTTPException(400, "No valid images found for slideshow")

    image_paths = [m.file_path for m in media_items]
    try:
        file_path, filename = await video_gen.create_slideshow_video(
            image_paths, body.duration_per_image, body.fps, body.transition
        )
        media = Media(
            user_id=user.id,
            filename=filename,
            original_name=f"slideshow_{filename}",
            file_path=file_path,
            media_type=MediaType.video,
            source="generated",
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        return JSONResponse({
            "id": media.id,
            "filename": filename,
            "url": f"/static/uploads/videos/{filename}",
        })
    except Exception as e:
        raise HTTPException(500, str(e))
