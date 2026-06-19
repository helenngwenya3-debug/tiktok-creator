import httpx
import base64
import uuid
import os
from pathlib import Path
from app.config import get_settings

settings = get_settings()


async def generate_image_hf(prompt: str, negative_prompt: str = "", width: int = 1024, height: int = 1024) -> str:
    """Generate image via Hugging Face Inference API (Stable Diffusion XL)."""
    if not settings.HUGGINGFACE_API_KEY:
        raise ValueError("HUGGINGFACE_API_KEY not configured")

    api_url = f"https://api-inference.huggingface.co/models/{settings.HF_IMAGE_MODEL}"
    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(api_url, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(f"HuggingFace API error: {response.text}")

    # Response is raw image bytes
    filename = f"{uuid.uuid4()}.png"
    upload_dir = Path(settings.UPLOAD_DIR) / "images"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename

    with open(file_path, "wb") as f:
        f.write(response.content)

    return str(file_path), filename


async def generate_image_replicate(prompt: str, negative_prompt: str = "") -> tuple[str, str]:
    """Generate image via Replicate API as fallback."""
    if not settings.REPLICATE_API_TOKEN:
        raise ValueError("REPLICATE_API_TOKEN not configured")

    headers = {
        "Authorization": f"Token {settings.REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "version": "ac732df83cea7fff18b8472768c88ad041fa750ed7461b5e09fcc26ab72d70b",
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": 1024,
            "height": 1024,
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post("https://api.replicate.com/v1/predictions", headers=headers, json=payload)
        prediction = resp.json()
        prediction_id = prediction["id"]

        # Poll for result
        for _ in range(60):
            import asyncio
            await asyncio.sleep(3)
            poll = await client.get(f"https://api.replicate.com/v1/predictions/{prediction_id}", headers=headers)
            data = poll.json()
            if data["status"] == "succeeded":
                image_url = data["output"][0]
                img_resp = await client.get(image_url)
                filename = f"{uuid.uuid4()}.png"
                upload_dir = Path(settings.UPLOAD_DIR) / "images"
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / filename
                with open(file_path, "wb") as f:
                    f.write(img_resp.content)
                return str(file_path), filename
            elif data["status"] == "failed":
                raise RuntimeError(f"Replicate prediction failed: {data.get('error')}")

    raise RuntimeError("Image generation timed out")
