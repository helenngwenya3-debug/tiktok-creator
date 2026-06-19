import json
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.database import get_db
from app.models import Media, MediaType, TikTokPost, PostType, PostStatus
from app.auth import get_current_user
from app.schemas import TikTokPostCreate
from app.services import tiktok_service
from datetime import datetime

router = APIRouter(prefix="/tiktok", tags=["tiktok"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/post", response_class=HTMLResponse)
def post_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    images = db.query(Media).filter(Media.user_id == user.id, Media.media_type == MediaType.image).order_by(Media.created_at.desc()).all()
    videos = db.query(Media).filter(Media.user_id == user.id, Media.media_type == MediaType.video).order_by(Media.created_at.desc()).all()
    posts = db.query(TikTokPost).filter(TikTokPost.user_id == user.id).order_by(TikTokPost.created_at.desc()).limit(20).all()
    return templates.TemplateResponse("tiktok/post.html", {
        "request": request,
        "user": user,
        "images": images,
        "videos": videos,
        "posts": posts,
    })


@router.post("/publish")
async def publish_to_tiktok(
    body: TikTokPostCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not user.tiktok_access_token:
        raise HTTPException(400, "No TikTok access token. Go to Settings to add your TikTok token.")

    media_items = db.query(Media).filter(
        Media.id.in_(body.media_ids),
        Media.user_id == user.id,
    ).all()

    if not media_items:
        raise HTTPException(400, "No valid media found")

    post = TikTokPost(
        user_id=user.id,
        post_type=body.post_type,
        caption=body.caption,
        title=body.title,
        media_ids=json.dumps(body.media_ids),
        status=PostStatus.draft,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    try:
        if body.post_type == PostType.video:
            video = media_items[0]
            if video.media_type != MediaType.video:
                raise HTTPException(400, "Selected media is not a video")
            result = await tiktok_service.post_video_to_tiktok(
                user.tiktok_access_token, video.file_path, body.caption, body.title
            )
        else:
            # image or slider (one or many images)
            image_paths = [m.file_path for m in media_items if m.media_type == MediaType.image]
            if not image_paths:
                raise HTTPException(400, "No images found for image/slider post")
            result = await tiktok_service.post_photos_to_tiktok(
                user.tiktok_access_token, image_paths, body.caption, body.title
            )

        post.status = PostStatus.published
        post.tiktok_post_id = result.get("publish_id")
        post.published_at = datetime.utcnow()
        db.commit()

        return JSONResponse({"success": True, "publish_id": result.get("publish_id"), "post_id": post.id})

    except Exception as e:
        post.status = PostStatus.failed
        post.error_message = str(e)
        db.commit()
        raise HTTPException(500, str(e))


@router.get("/posts/api")
def list_posts(db: Session = Depends(get_db), user=Depends(get_current_user)):
    posts = db.query(TikTokPost).filter(TikTokPost.user_id == user.id).order_by(TikTokPost.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "post_type": p.post_type.value,
            "status": p.status.value,
            "caption": p.caption,
            "tiktok_post_id": p.tiktok_post_id,
            "created_at": p.created_at.isoformat(),
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "error_message": p.error_message,
        }
        for p in posts
    ]


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("tiktok/settings.html", {"request": request, "user": user})


@router.post("/settings/token")
async def save_tiktok_token(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    form = await request.form()
    token = form.get("tiktok_access_token", "").strip()
    open_id = form.get("tiktok_open_id", "").strip()
    db_user = db.query(type(user)).filter_by(id=user.id).first()
    db_user.tiktok_access_token = token
    db_user.tiktok_open_id = open_id
    db.commit()
    return JSONResponse({"saved": True})
