import uuid
import os
import asyncio
from pathlib import Path
from typing import List
from app.config import get_settings

settings = get_settings()


async def create_slideshow_video(image_paths: List[str], duration_per_image: float = 3.0, fps: int = 24, transition: str = "fade") -> tuple[str, str]:
    """Create a vertical (1080x1920) TikTok slideshow video from a list of images.

    Uses imageio + Pillow (no MoviePy) so it stays compatible with modern Pillow/numpy.
    """
    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image

    W, H = 1080, 1920
    frames_per_image = max(1, int(round(fps * duration_per_image)))
    fade_frames = int(fps * 0.5) if transition == "fade" else 0

    def _render() -> tuple[str, str]:
        # Pre-render each image to a 1080x1920 RGB frame (center-crop "cover" fit)
        rendered = []
        for img_path in image_paths:
            im = Image.open(img_path).convert("RGB")
            src_ratio = im.width / im.height
            dst_ratio = W / H
            if src_ratio > dst_ratio:
                new_w, new_h = int(round(H * src_ratio)), H
            else:
                new_w, new_h = W, int(round(W / src_ratio))
            im = im.resize((new_w, new_h), Image.LANCZOS)
            left, top = (new_w - W) // 2, (new_h - H) // 2
            im = im.crop((left, top, left + W, top + H))
            rendered.append(np.asarray(im, dtype=np.uint8))

        filename = f"{uuid.uuid4()}.mp4"
        upload_dir = Path(settings.UPLOAD_DIR) / "videos"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / filename

        writer = imageio.get_writer(
            str(file_path), fps=fps, codec="libx264",
            quality=8, pixelformat="yuv420p", macro_block_size=None,
        )
        try:
            for frame in rendered:
                for f in range(frames_per_image):
                    out = frame
                    if fade_frames > 0:
                        if f < fade_frames:
                            alpha = f / fade_frames
                        elif f >= frames_per_image - fade_frames:
                            alpha = (frames_per_image - 1 - f) / fade_frames
                        else:
                            alpha = 1.0
                        if alpha < 1.0:
                            out = (frame.astype(np.float32) * alpha).astype(np.uint8)
                    writer.append_data(out)
        finally:
            writer.close()

        return str(file_path), filename

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _render)


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
        if resp.status_code >= 400 or "id" not in prediction:
            detail = prediction.get("detail") or prediction.get("title") or resp.text
            raise RuntimeError(f"Replicate API error ({resp.status_code}): {detail}")
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
