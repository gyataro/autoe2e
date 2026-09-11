import base64
import io
from pathlib import Path

from PIL import Image


def encode_image(path: str | Path) -> str:
    with Image.open(path) as image:
        resized_image = image.resize((512, 512))
        buffer = io.BytesIO()
        resized_image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
