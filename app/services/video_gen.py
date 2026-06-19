import uuid
import os
import asyncio
from pathlib import Path
from typing import List
from app.config import get_settings

settings = get_settings()


async def create_slideshow_video(image_paths: List[str], duration_per_image: float = 3.0, fps: int = 24, transition: str = "fade") -> tuple[str, str]:
    """Create a video slideshow from a list of images using MoviePy."""
    from moviepy.editor import ImageClip, concatenate_videoclips, VideoFileClip
    from moviepy.video.fx.all import fadein, fadeout

    clips = []
    for img_path in image_paths:
        clip = ImageClip(img_path, duration=duration_per_image)
        clip = clip.resize(height=1920).crop(x_center=clip.w / 2, y_center=clip.h / 2, width=1080, height=1920)
        if transition == "fade":
            clip = clip.fadein(0.5).fadeout(0.5)
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")

    filename = f"{uuid.uuid4()}.mp4"
    upload_dir = Path(settings.UPLOAD_DIR) / "videos"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename

    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: final.write_videofile(str(file_path), fps=fps, codec="libx264", audio=False, verbose=False, logger=None),
    )

    return str(file_path), filename


async def generate_ai_video_replicate(prompt: str, duration: int = 5) -> tuple[str, str]:
    """Generate AI video via Replicate (Stable Video Diffusion / RunwayML)."""
    import httpx

    if not settings.REPLICATE_API_TOKEN:
        raise ValueError("REPLICATE_API_TOKEN not configured")

    headers = {
        "Authorization": f"Token {settings.REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    # Using Wan-Video model on Replicate for text-to-video
    payload = {
        "version": "2b017d9b67edd2ee1401238df49d75da53c523f36e363881e057f5dc3ed3c5b2",
        "input": {
            "prompt": prompt,
            "num_frames": duration * 8,
            "fps": 8,
        },
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post("https://api.replicate.com/v1/predictions", headers=headers, json=payload)
        prediction = resp.json()
        prediction_id = prediction["id"]

        for _ in range(100):
            await asyncio.sleep(5)
            poll = await client.get(f"https://api.replicate.com/v1/predictions/{prediction_id}", headers=headers)
            data = poll.json()
            if data["status"] == "succeeded":
                video_url = data["output"]
                if isinstance(video_url, list):
                    video_url = video_url[0]
                vid_resp = await client.get(video_url)
                filename = f"{uuid.uuid4()}.mp4"
                upload_dir = Path(settings.UPLOAD_DIR) / "videos"
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / filename
                with open(file_path, "wb") as f:
                    f.write(vid_resp.content)
                return str(file_path), filename
            elif data["status"] == "failed":
                raise RuntimeError(f"Video generation failed: {data.get('error')}")

    raise RuntimeError("Video generation timed out")
