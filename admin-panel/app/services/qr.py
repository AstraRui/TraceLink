"""Local QR-code generation.

Produces a self-contained ``data:`` URI (base64 PNG) using the ``qrcode``
library — no calls to any external QR API, so it works fully offline.
"""

import base64
import io
from typing import Any

import qrcode


def generate_qr_data_uri(data: str) -> str:
    image: Any = qrcode.make(data)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
