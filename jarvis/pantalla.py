"""Captura de pantalla para que JARVIS vea lo que estás haciendo (solo cuando se lo pides).

En macOS usa `screencapture` (la primera vez pide permiso en
Ajustes del Sistema > Privacidad y seguridad > Grabación de pantalla).
"""
from __future__ import annotations

import base64
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LADO_MAXIMO = 1568  # suficiente para leer texto sin gastar muchos tokens


class ErrorPantalla(Exception):
    pass


def _capturar_png() -> bytes:
    if sys.platform == "darwin" and shutil.which("screencapture"):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "pantalla.png"
            # -x: sin sonido, -C: incluye cursor, -m: solo pantalla principal
            r = subprocess.run(["screencapture", "-x", "-C", "-m", str(ruta)], capture_output=True, timeout=15)
            if r.returncode != 0 or not ruta.exists() or ruta.stat().st_size == 0:
                raise ErrorPantalla(
                    "No pude capturar la pantalla. Da permiso en Ajustes del Sistema > Privacidad y seguridad > "
                    "Grabación de pantalla (a JARVIS o a la Terminal) y vuelve a abrir JARVIS."
                )
            return ruta.read_bytes()
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except Exception as e:
        raise ErrorPantalla(f"No pude capturar la pantalla en este sistema: {e}") from e


def preparar_imagen(png: bytes, lado_maximo: int = LADO_MAXIMO) -> tuple[str, tuple[int, int]]:
    """Reduce y comprime a JPEG. Devuelve (base64, (ancho, alto))."""
    from PIL import Image

    img = Image.open(io.BytesIO(png))
    img = img.convert("RGB")
    img.thumbnail((lado_maximo, lado_maximo))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80, optimize=True)
    return base64.b64encode(buf.getvalue()).decode(), img.size


def capturar() -> tuple[str, tuple[int, int]]:
    return preparar_imagen(_capturar_png())
