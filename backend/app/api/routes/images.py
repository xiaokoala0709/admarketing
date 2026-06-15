import base64
import io
import re
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageChops, ImageFilter

from app.core.config import settings
from app.schemas.agent import ImageGenerateOutput, ImageGenerateRequest

router = APIRouter(prefix="/images", tags=["images"])

DATA_URL_PATTERN = re.compile(r"^data:(?P<mime>[-\w.]+/[-\w.+]+);base64,(?P<data>.+)$", re.DOTALL)
POSTER_SIZE = (1024, 1536)
DRAW_TEXT_LAYER = False
DRAW_BADGE_LAYER = False
WHITE_THRESHOLD = 245
BACKGROUND_PROMPT_CONSTRAINTS = """Create a lively campaign poster background inspired by the uploaded reference image.

Strictly do not include text, letters, Chinese characters, English words, numbers, brand logos, product packages, labels, captions, badges, stickers, watermarks, UI elements, or any readable marks.
Generate only background, props, lighting, color mood, depth, motion, and atmosphere.
Use the reference image for mood, color palette, lighting, composition rhythm, commercial poster style, and campaign layout structure.
Follow this 3:4 poster structure: top 8%-28% should remain clean for a headline layer, center-lower area should remain open for the product cutout, and bottom 75%-90% should leave space for slogan or promotion text.
A lively fresh campaign style may include sky, grass, leaves, chips, ice, breeze, flying decorative elements, soft shadows, and playful cartoon energy, but never include product packaging or generated text."""


@dataclass(frozen=True)
class ImageInput:
    filename: str
    content: bytes
    media_type: str


def decode_image_data_url(value: str, fallback_name: str) -> ImageInput:
    source = value.strip()
    match = DATA_URL_PATTERN.match(source)

    if match:
        media_type = match.group("mime")
        encoded = match.group("data")
    else:
        media_type = "image/png"
        encoded = source

    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image data for {fallback_name}") from exc

    if not content:
        raise HTTPException(status_code=400, detail=f"Empty image data for {fallback_name}")

    return ImageInput(
        filename=fallback_name,
        content=content,
        media_type=media_type,
    )


def open_image_bytes(content: bytes, fallback_name: str) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image file for {fallback_name}") from exc

    return image.convert("RGBA")


def decode_base64_image(value: str, fallback_name: str) -> Image.Image:
    try:
        content = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Invalid generated image data for {fallback_name}") from exc

    return open_image_bytes(content, fallback_name)


def encode_png_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def build_background_prompt(payload: ImageGenerateRequest) -> str:
    reference_name = (payload.reference_image_name or "uploaded reference image").strip()
    headline = (payload.headline or "").strip()
    promotion_text = (payload.promotion_text or "").strip()
    platform_text = (payload.platform_text or "").strip()
    visual_style = (payload.visual_style or "参考图风格").strip()

    parts = [
        payload.prompt.strip(),
        f"Reference style image input: {reference_name if payload.reference_image else 'not provided'}.",
        f"Visual style direction: {visual_style}.",
        f"Reserve top headline layer space for: {headline or 'headline text'}.",
        f"Reserve bottom promotion layer space for: {promotion_text or 'promotion or slogan text'}.",
        f"Reserve small platform tag space for: {platform_text or 'platform tag'}.",
        BACKGROUND_PROMPT_CONSTRAINTS,
    ]
    return "\n\n".join(part for part in parts if part)


def has_meaningful_transparency(image: Image.Image) -> bool:
    alpha = image.getchannel("A")
    return alpha.getbbox() is not None and alpha.getextrema()[0] < 255


def remove_near_white_background(image: Image.Image) -> Image.Image:
    processed = image.copy().convert("RGBA")
    pixels = processed.load()
    for y in range(processed.height):
        for x in range(processed.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha and red > WHITE_THRESHOLD and green > WHITE_THRESHOLD and blue > WHITE_THRESHOLD:
                pixels[x, y] = (red, green, blue, 0)
    return processed


def trim_transparent_edges(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return image
    return image.crop(bbox)


def preprocess_product_image(product: Image.Image) -> Image.Image:
    processed = product.copy().convert("RGBA")
    if not has_meaningful_transparency(processed):
        processed = remove_near_white_background(processed)
    processed = trim_transparent_edges(processed)
    return processed


def fit_product_image(product: Image.Image, canvas_size: tuple[int, int]) -> Image.Image:
    min_height = int(canvas_size[1] * 0.42)
    max_height = int(canvas_size[1] * 0.55)
    target_height = min(max(product.height, min_height), max_height)
    scale = target_height / product.height

    max_width = int(canvas_size[0] * 0.72)
    scaled_width = int(product.width * scale)
    if scaled_width > max_width:
        scale = max_width / product.width

    new_size = (
        max(1, int(product.width * scale)),
        max(1, int(product.height * scale)),
    )
    return product.resize(new_size, Image.LANCZOS)


def create_product_shadow(product: Image.Image) -> Image.Image:
    alpha = product.getchannel("A")
    shadow_mask = alpha.point(lambda value: int(value * 0.28))
    shadow = Image.new("RGBA", product.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    return shadow


def paste_product(background: Image.Image, product: Image.Image) -> Image.Image:
    poster = background.copy().convert("RGBA")
    processed_product = preprocess_product_image(product)
    fitted_product = fit_product_image(processed_product, poster.size)
    shadow = create_product_shadow(fitted_product)

    x = (poster.width - fitted_product.width) // 2
    y = poster.height - fitted_product.height - int(poster.height * 0.1)
    y = max(int(poster.height * 0.36), y)

    shadow_x = x
    shadow_y = y + 22
    poster.alpha_composite(shadow, (shadow_x, shadow_y))
    poster.alpha_composite(fitted_product, (x, y))
    return poster


def compose_poster(background: Image.Image, product: Image.Image) -> Image.Image:
    poster = paste_product(background, product)
    if DRAW_TEXT_LAYER or DRAW_BADGE_LAYER:
        return poster
    return poster


def request_background_image(payload: ImageGenerateRequest, reference_image: ImageInput | None) -> tuple[str, str]:
    files = []
    if reference_image:
        files.append(("image[]", (reference_image.filename, reference_image.content, reference_image.media_type)))

    data = {
        "model": settings.openai_image_model,
        "prompt": build_background_prompt(payload),
        "size": "1024x1536",
        "n": "1",
    }

    try:
        response = httpx.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {settings.image_api_key}"},
            data=data,
            files=files or None,
            timeout=180.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        error_data = exc.response.json() if exc.response.headers.get("content-type", "").startswith("application/json") else {}
        detail = error_data.get("error", {}).get("message", "OpenAI image generation failed")
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="OpenAI image generation request failed") from exc

    response_data = response.json().get("data") or []
    first_image = response_data[0] if response_data else {}
    return str(first_image.get("url") or ""), str(first_image.get("b64_json") or "")


@router.post("/generate")
def generate_image(payload: ImageGenerateRequest) -> ImageGenerateOutput:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Image prompt is required")

    if settings.image_provider != "openai":
        raise HTTPException(
            status_code=503,
            detail="图片生成 API 尚未配置，请先配置 IMAGE_API_KEY。",
        )

    if not settings.has_image_api_key:
        raise HTTPException(
            status_code=503,
            detail="图片生成 API 尚未配置，请先配置 IMAGE_API_KEY。",
        )

    if not payload.product_image:
        raise HTTPException(status_code=400, detail="Product image is required")

    product_input = decode_image_data_url(
        payload.product_image,
        payload.product_image_name or "product_image.png",
    )
    reference_input = None
    if payload.reference_image:
        reference_input = decode_image_data_url(
            payload.reference_image,
            payload.reference_image_name or "reference_image.png",
        )

    image_url, image_base64 = request_background_image(payload, reference_input)
    if not image_url and not image_base64:
        raise HTTPException(status_code=502, detail="OpenAI did not return an image")

    if image_base64:
        background = decode_base64_image(image_base64, "generated_background.png")
    else:
        try:
            response = httpx.get(image_url, timeout=180.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Failed to download generated background") from exc
        background = open_image_bytes(response.content, "generated_background.png")

    background = background.resize(POSTER_SIZE, Image.LANCZOS)
    product = open_image_bytes(product_input.content, product_input.filename)
    final_image = compose_poster(background, product)

    return ImageGenerateOutput(
        image_url="",
        image_base64=encode_png_base64(final_image),
        status="completed",
        message="图片已生成。",
    )
