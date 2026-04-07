"""
Preprocessing delle immagini di targhe identificative.
Pipeline: resize → auto-levels → contrasto → nitidezza → unsharp mask
Ottimizzato per targhe metalliche ossidate, sporche, con illuminazione scarsa.
"""
import base64
import io

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np


MAX_DIMENSION = 1568  # Ottimale per Claude Vision e Gemini Vision


def preprocess_plate_image(image_base64: str) -> str:
    """
    Processa l'immagine della targa e restituisce la versione migliorata in base64.
    """
    raw = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(raw)).convert("RGB")

    img = _resize_for_api(img, MAX_DIMENSION)
    img = _auto_levels(img)

    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.0)

    # Unsharp mask: evidenzia testo in rilievo/inciso
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def check_image_brightness(image_base64: str) -> dict:
    """
    Valuta la luminosità dell'immagine.
    Restituisce {'brightness': 0-255, 'is_too_dark': bool, 'is_too_bright': bool}
    """
    raw = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(raw)).convert("L")  # Grayscale
    arr = np.array(img)
    mean_brightness = float(arr.mean())
    return {
        "brightness": round(mean_brightness, 1),
        "is_too_dark": mean_brightness < 40,
        "is_too_bright": mean_brightness > 220,
    }


def preprocess_plate_image_variant(image_base64: str, variant: int) -> str:
    """
    Preprocessing alternativo per multi-shot OCR.
    variant=1: alto contrasto B&W — per targhe ossidate o con testo inciso/in rilievo
    variant=2: denoised morbido — per riflessioni, sovraesposizione, granularità
    """
    raw = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img = _resize_for_api(img, MAX_DIMENSION)

    if variant == 1:
        img = img.convert("L").convert("RGB")  # Grayscale
        img = _auto_levels(img)
        img = ImageEnhance.Contrast(img).enhance(3.0)
        img = ImageEnhance.Sharpness(img).enhance(3.0)
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=200, threshold=1))
    elif variant == 2:
        img = img.filter(ImageFilter.GaussianBlur(radius=1))  # Riduce rumore/riflessi
        img = _auto_levels(img)
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = ImageEnhance.Sharpness(img).enhance(1.5)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def _resize_for_api(img: Image.Image, max_dimension: int) -> Image.Image:
    w, h = img.size
    if max(w, h) > max_dimension:
        ratio = max_dimension / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    return img


def _auto_levels(img: Image.Image) -> Image.Image:
    """Stretching dell'istogramma per ogni canale RGB (percentile 2-98)."""
    arr = np.array(img, dtype=np.float32)
    for c in range(3):
        channel = arr[:, :, c]
        lo = np.percentile(channel, 2)
        hi = np.percentile(channel, 98)
        if hi > lo:
            arr[:, :, c] = np.clip((channel - lo) / (hi - lo) * 255, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))
