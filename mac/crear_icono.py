"""Dibuja el icono de JARVIS (1024x1024 PNG). Uso: python crear_icono.py salida.png"""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter

T = 1024


def crear(ruta: str) -> None:
    base = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    m = 90
    d.rounded_rectangle((m, m, T - m, T - m), radius=200, fill=(9, 14, 30, 255))

    brillo = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    db = ImageDraw.Draw(brillo)
    c = T // 2
    for r, a in ((300, 40), (240, 70), (180, 120)):
        db.ellipse((c - r, c - r, c + r, c + r), fill=(63, 208, 255, a))
    brillo = brillo.filter(ImageFilter.GaussianBlur(40))
    base.alpha_composite(brillo)

    d = ImageDraw.Draw(base)
    for r, color, ancho, ini, fin in ((330, (63, 208, 255), 22, 200, 520), (380, (124, 107, 255), 14, 20, 300)):
        d.arc((c - r, c - r, c + r, c + r), ini, fin, fill=color, width=ancho)
    for r in range(150, 0, -2):
        t = r / 150
        col = (int(201 * (1 - t) + 27 * t), int(244 * (1 - t) + 95 * t), int(255 * (1 - t) + 176 * t), 255)
        d.ellipse((c - r, c - r, c + r, c + r), fill=col)
    for ang in range(0, 360, 45):
        x1 = c + 205 * math.cos(math.radians(ang)); y1 = c + 205 * math.sin(math.radians(ang))
        x2 = c + 245 * math.cos(math.radians(ang)); y2 = c + 245 * math.sin(math.radians(ang))
        d.line((x1, y1, x2, y2), fill=(63, 208, 255, 220), width=10)
    base.save(ruta)


if __name__ == "__main__":
    crear(sys.argv[1] if len(sys.argv) > 1 else "icono.png")
