import httpx
import os
from pathlib import Path
from typing import List
from app.config import get_settings

settings = get_settings()

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


async def post_video_to_tiktok(access_token: str, video_path: str, caption: str, title: str = "") -> dict:
    """Upload and publish a video to TikTok."""
    file_size = os.path.getsize(video_path)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Step 1: Initialize upload
    init_payload = {
        "post_info": {
            "title": title or caption[:150],
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        init_resp = await client.post(
            f"{TIKTOK_API_BASE}/post/publish/video/init/",
            headers=headers,
            json=init_payload,
        )
        init_data = init_resp.json()

        if init_data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"TikTok init error: {init_data}")

        publish_id = init_data["data"]["publish_id"]
        upload_url = init_data["data"]["upload_url"]

        # Step 2: Upload video
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_headers = {
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Content-Length": str(file_size),
            "Content-Type": "video/mp4",
        }
        upload_resp = await client.put(upload_url, headers=upload_headers, content=video_bytes)

        if upload_resp.status_code not in (200, 201, 206):
            raise RuntimeError(f"TikTok upload error: {upload_resp.text}")

    return {"publish_id": publish_id, "status": "published"}


async def post_photos_to_tiktok(access_token: str, image_paths: List[str], caption: str, title: str = "") -> dict:
    """Upload images as a photo post (single image or slider/carousel) to TikTok."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Step 1: Initialize content post
    init_payload = {
        "post_info": {
            "title": title or caption[:150],
            "description": caption,
            "privacy_level": "SELF_ONLY",
            "disable_comment": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "photo_count": len(image_paths),
        },
        "post_mode": "DIRECT_POST",
        "media_type": "PHOTO",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        init_resp = await client.post(
            f"{TIKTOK_API_BASE}/post/publish/content/init/",
            headers=headers,
            json=init_payload,
        )
        init_data = init_resp.json()

        if init_data.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"TikTok photo init error: {init_data}")

        publish_id = init_data["data"]["publish_id"]
        upload_urls = init_data["data"]["upload_urls"]

        # Step 2: Upload each image
        for img_path, upload_url in zip(image_paths, upload_urls):
            file_size = os.path.getsize(img_path)
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            upload_headers = {
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                "Content-Length": str(file_size),
                "Content-Type": "image/jpeg",
            }
            up_resp = await client.put(upload_url, headers=upload_headers, content=img_bytes)
            if up_resp.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok image upload error: {up_resp.text}")

    return {"publish_id": publish_id, "status": "published"}


async def check_post_status(access_token: str, publish_id: str) -> dict:
    """Check the status of a TikTok post."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
            headers=headers,
            json={"publish_id": publish_id},
        )
    return resp.json()
