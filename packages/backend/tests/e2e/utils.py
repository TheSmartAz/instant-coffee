import base64
from pathlib import Path


def encode_image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    ext = image_path.suffix.lstrip(".")
    return f"data:image/{ext};base64,{data}"
