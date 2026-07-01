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

    api_url = f"https://router.huggingface.co/hf-inference/models/{settings.HF_IMAGE_MODEL}"
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


async def generate_image_img2img_replicate(prompt: str, image_bytes: bytes, strength: float = 0.8) -> tuple[str, str]:
    """Image-to-image generation via Replicate FLUX-dev (reference image + prompt).

    strength (prompt_strength): 0 = stay close to the reference, 1 = follow the prompt freely.
    """
    if not settings.REPLICATE_API_TOKEN:
        raise ValueError("REPLICATE_API_TOKEN not configured")

    import asyncio

    data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
    headers = {
        "Authorization": f"Bearer {settings.REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": {
            "prompt": prompt,
            "image": data_uri,
            "prompt_strength": strength,
            "aspect_ratio": "match_input_image",
            "output_format": "png",
            "num_outputs": 1,
        }
    }
    url = "https://api.replicate.com/v1/models/black-forest-labs/flux-dev/predictions"

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        prediction = resp.json()
        if resp.status_code >= 400 or "id" not in prediction:
            detail = prediction.get("detail") or prediction.get("title") or resp.text
            raise RuntimeError(f"Replicate API error ({resp.status_code}): {detail}")

        get_url = prediction["urls"]["get"]
        for _ in range(90):
            await asyncio.sleep(2)
            poll = await client.get(get_url, headers=headers)
            data = poll.json()
            status = data.get("status")
            if status == "succeeded":
                out = data["output"]
                image_url = out[0] if isinstance(out, list) else out
                img_resp = await client.get(image_url)
                filename = f"{uuid.uuid4()}.png"
                upload_dir = Path(settings.UPLOAD_DIR) / "images"
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / filename
                with open(file_path, "wb") as f:
                    f.write(img_resp.content)
                return str(file_path), filename
            elif status in ("failed", "canceled"):
                raise RuntimeError(f"Replicate img2img failed: {data.get('error')}")

    raise RuntimeError("Image generation timed out")


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
