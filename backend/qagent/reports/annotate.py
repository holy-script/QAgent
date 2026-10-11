import io
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw


def find_bbox(inputs: Dict[str, Any], target_bbox: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
    """The element at fault (a bound UI value) wins; otherwise the element the agent acted on."""
    for src in inputs.values():
        if isinstance(src, dict) and src.get("bbox"):
            return src["bbox"]
    return target_bbox


def annotate_screenshot(jpeg: bytes, step_seq: int, bbox: Optional[Dict[str, float]]) -> bytes:
    """Boxes the target element and stamps the step number in the corner."""
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    draw = ImageDraw.Draw(img)
    red = (179, 38, 30)
    if bbox:
        x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]
        pad = 4
        draw.rectangle([x - pad, y - pad, x + w + pad, y + h + pad], outline=red, width=3)
    draw.rectangle([0, 0, 64, 26], fill=red)
    draw.text((8, 7), f"step {step_seq}", fill=(255, 255, 255))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=80)
    return out.getvalue()
