#!/usr/bin/env python3
"""Dibuja las animaciones de DelfínOS para el escritorio del Flipper (128x64, 1 bit).

Uso: python3 generar_animaciones.py CARPETA_SALIDA
Crea L1_DelfinOS_Salto_128x64/ y L1_DelfinOS_Logo_128x64/ con frame_N.png y meta.txt.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fuentes"))
import u8g2_fuente as u  # noqa: E402

W, H = 128, 64
# Silueta de delfín mirando a la derecha (lienzo de 60x26), suavizada con Chaikin.
CONTORNO = [(59, 14), (52, 10), (46, 7), (38, 5.5), (33, 5.5), (29, 0), (27, 1), (26, 6.5), (18, 8.5),
            (10, 11.5), (5, 8), (1, 5), (3, 12.5), (0, 20), (5, 17), (10, 15), (19, 17.5), (27, 19),
            (25, 25.5), (29, 24), (33, 19.5), (44, 18), (51, 16.5), (59, 15.5)]
OJO = (49, 11.5)


def chaikin(pts, vueltas=2):
    for _ in range(vueltas):
        nuevos = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            nuevos += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]),
                       (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        pts = nuevos
    return pts


SIL = chaikin(CONTORNO)
CX = sum(p[0] for p in SIL) / len(SIL)
CY = sum(p[1] for p in SIL) / len(SIL)


def transformar(p, cx, cy, escala, angulo, espejo=False):
    x, y = (p[0] - CX) * escala, (p[1] - CY) * escala
    if espejo:
        x = -x
    ca, sa = math.cos(angulo), math.sin(angulo)
    return (cx + x * ca - y * sa, cy + x * sa + y * ca)


def delfin(dib, cx, cy, escala=0.72, angulo=0.0, espejo=False):
    poli = [transformar(p, cx, cy, escala, angulo, espejo) for p in SIL]
    dib.polygon(poli, fill=0, outline=0)
    ox, oy = transformar(OJO, cx, cy, escala, angulo, espejo)
    dib.point((round(ox), round(oy)), fill=1)


def olas(dib, fase, base=54):
    for x in range(W):
        y = base + round(1.6 * math.sin((x + fase) / 6.0))
        dib.point((x, y), fill=0)
        for yy in range(y + 2, H):
            if (x + yy) % 2 == 0 and yy > y + 3 or (x % 4 == 0 and yy == y + 2):
                dib.point((x, yy), fill=0)


FUENTES = None


def texto(dib, x, y, s, nombre="u8g2_font_helvB08_es"):
    global FUENTES
    if FUENTES is None:
        c = (Path(__file__).resolve().parent.parent / "fuentes" / "u8g2_fuentes_es.c").read_text(encoding="latin-1")
        FUENTES = {n: u.decodificar(u.extraer_arreglo(c, n)) for n in ("u8g2_font_helvB08_es", "u8g2_font_haxrcorp4089_es")}
    h, g = FUENTES[nombre]
    for ch in s:
        gl = g.get(ord(ch))
        if not gl:
            x += 3
            continue
        top = y - gl["y"] - gl["h"]
        for fy, fila in enumerate(gl["filas"]):
            for fx, p in enumerate(fila):
                if p:
                    dib.point((x + gl["x"] + fx, top + fy + 1), fill=0)
        x += gl["dx"]
    return x


def ancho(s, nombre="u8g2_font_helvB08_es"):
    texto(ImageDraw.Draw(Image.new("1", (1, 1))), 0, 0, "")
    h, g = FUENTES[nombre]
    return sum(g[ord(c)]["dx"] if ord(c) in g else 3 for c in s)


def lienzo():
    im = Image.new("1", (W, H), 1)
    return im, ImageDraw.Draw(im)


def anim_salto(salida):
    frames = []
    # Pasivos: el delfín asoma y nada en la superficie
    for i in range(4):
        im, d = lienzo()
        olas(d, i * 3)
        delfin(d, 30 + i * 2, 50 + (i % 2), angulo=-0.15)
        olas(d, i * 3)  # redibuja la ola encima para que "nade"
        frames.append(im)
    # Activos: salto en arco de izquierda a derecha
    n = 8
    for i in range(n):
        im, d = lienzo()
        t = i / (n - 1)
        x = 22 + t * 84
        y = 50 - math.sin(t * math.pi) * 34
        ang = (t - 0.5) * 2.2
        olas(d, 12 + i * 3)
        delfin(d, x, y, angulo=ang)
        if i in (0, n - 1):  # salpicadura
            for k in (-6, -3, 3, 6):
                d.point((round(x + k), 48 - abs(k) // 2), fill=0)
                d.point((round(x + k), 47 - abs(k) // 2), fill=0)
        frames.append(im)
    meta = f"""Filetype: Flipper Animation
Version: 1

Width: 128
Height: 64
Passive frames: 4
Active frames: {n}
Frames order: {' '.join(str(k) for k in range(4 + n))}
Active cycles: 2
Frame rate: 4
Duration: 3600
Active cooldown: 5

Bubble slots: 1

Slot: 0
X: 2
Y: 4
Text: ¡Hola! Soy\\nDelfínOS
AlignH: Right
AlignV: Bottom
StartFrame: 4
EndFrame: 7
"""
    return frames, meta


def anim_logo(salida):
    frames = []
    for i in range(8):
        im, d = lienzo()
        dy = round(math.sin(i / 8 * 2 * math.pi) * 1.5)
        # ícono: cuadro redondeado con el delfín en blanco
        d.rounded_rectangle((8, 8 + dy, 46, 46 + dy), radius=9, fill=0)
        poli = [transformar(p, 27, 27 + dy, 0.55, -0.35, False) for p in SIL]
        d.polygon(poli, fill=1)
        ox, oy = transformar(OJO, 27, 27 + dy, 0.55, -0.35, False)
        d.point((round(ox), round(oy)), fill=0)
        texto(d, 54, 22, "DelfínOS")
        texto(d, 54, 34, "Flipper Zero", "u8g2_font_haxrcorp4089_es")
        texto(d, 54, 43, "en español", "u8g2_font_haxrcorp4089_es")
        olas(d, i * 4, base=56)
        frames.append(im)
    meta = """Filetype: Flipper Animation
Version: 1

Width: 128
Height: 64
Passive frames: 8
Active frames: 0
Frames order: 0 1 2 3 4 5 6 7
Active cycles: 0
Frame rate: 3
Duration: 3600
Active cooldown: 0

Bubble slots: 0
"""
    return frames, meta


def guardar(carpeta, nombre, frames, meta):
    c = Path(carpeta) / nombre
    c.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(frames):
        f.save(c / f"frame_{i}.png")
    (c / "meta.txt").write_text(meta, encoding="utf-8")
    return c


def main():
    salida = Path(sys.argv[1])
    for nombre, fn in (("L1_DelfinOS_Salto_128x64", anim_salto), ("L1_DelfinOS_Logo_128x64", anim_logo)):
        frames, meta = fn(salida)
        print(guardar(salida, nombre, frames, meta), len(frames), "cuadros")


if __name__ == "__main__":
    main()
