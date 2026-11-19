#!/usr/bin/env python3
"""Genera las fuentes de DelfínOS: las del Flipper + letras del español (á é í ó ú ü ñ ¿ ¡ y mayúsculas).

Uso: python3 generar_fuentes.py RUTA/u8g2_fonts.c_de_Momentum RUTA/u8g2_fonts.c_oficial salida.c
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import u8g2_fuente as u

ESPANOL = "¡¿ÁÉÍÑÓÚÜáéíñóúü"


def g(filas, x=0, y=0, dx=None):
    f = [[1 if c == "#" else 0 for c in r] for r in filas]
    w = len(f[0])
    return {"w": w, "h": len(f), "x": x, "y": y, "dx": dx if dx is not None else w + 1, "filas": f}


def con_acento(base, acento, sobre_tope=True, desplaz=0):
    """Pone filas de acento encima del glifo base (alineadas a la derecha + desplaz)."""
    w = max(base["w"], max(len(a) for a in acento) + desplaz)
    filas = []
    for a in acento:
        r = [0] * w
        for i, c in enumerate(a):
            if c == "#":
                r[i + desplaz] = 1
        filas.append(r)
    cuerpo = [r + [0] * (w - len(r)) for r in base["filas"]]
    return {**base, "w": w, "h": base["h"] + len(filas), "filas": filas + cuerpo, "dx": max(base["dx"], w + 1)}


def invertir(base, y):
    f = [list(reversed(r)) for r in reversed(base["filas"])]
    return {**base, "filas": f, "y": y}


def haxrcorp(glifos):
    """Dibuja las letras con tilde para haxrcorp4089 (FontSecondary), que no las trae."""
    G = dict(glifos)
    agudo4, agudo5 = ["..#.", ".#.."], ["...#.", "..#.."]
    for c in "aeou":
        G[ord({"a": "á", "e": "é", "o": "ó", "u": "ú"}[c])] = con_acento(glifos[ord(c)], agudo4)
    G[ord("ü")] = con_acento(glifos[ord("u")], ["#..#", "...."])
    G[ord("ñ")] = con_acento(glifos[ord("n")], [".#.#", "#.#."])
    G[ord("í")] = g([".#", "#.", "#.", "#.", "#.", "#.", "#."], dx=3)
    for c, d in zip("AEOU", "ÁÉÓÚ"):
        G[ord(d)] = con_acento(glifos[ord(c)], agudo5 if glifos[ord(c)]["w"] == 5 else agudo4)
    G[ord("Í")] = con_acento(glifos[ord("I")], [".#", "#."]); G[ord("Í")]["dx"] = 3
    G[ord("Ü")] = con_acento(glifos[ord("U")], ["#...#", "....."])
    G[ord("Ñ")] = con_acento(glifos[ord("N")], [".#.#.", "#.#.."])
    G[ord("¿")] = invertir(glifos[ord("?")], -2)
    G[ord("¡")] = invertir(glifos[ord("!")], -2)
    return G


def construir(base_c, oficial_c, nombre_tr, nombre_tf):
    data = u.extraer_arreglo(base_c, nombre_tr)
    h, glifos = u.decodificar(data)
    if nombre_tf:
        _, completos = u.decodificar(u.extraer_arreglo(oficial_c, nombre_tf))
        for c in ESPANOL:
            glifos[ord(c)] = completos[ord(c)]
    else:
        glifos = haxrcorp(glifos)
    assert all(ord(c) in glifos for c in ESPANOL), nombre_tr
    return u.codificar(h, glifos), len(data)


FUENTES = [  # (fuente del Flipper, versión completa oficial o None = dibujada aquí)
    ("u8g2_font_haxrcorp4089_tr", None),
    ("u8g2_font_helvB08_tr", "u8g2_font_helvB08_tf"),
    ("u8g2_font_profont11_mr", "u8g2_font_profont11_mf"),
    ("u8g2_font_5x7_tr", "u8g2_font_5x7_tf"),
]


def main():
    base_c = Path(sys.argv[1]).read_text(encoding="latin-1")
    oficial_c = Path(sys.argv[2]).read_text(encoding="latin-1")
    salida = ["/* Fuentes DelfínOS: fuentes del Flipper + letras del español. Generado por generar_fuentes.py */",
              '#include "u8g2.h"', ""]
    for tr, tf in FUENTES:
        datos, antes = construir(base_c, oficial_c, tr, tf)
        nuevo = tr.replace("_tr", "_es").replace("_mr", "_es")
        salida.append(u.a_c(nuevo, datos))
        print(f"{nuevo}: {antes} -> {len(datos)} bytes (+{len(datos) - antes})")
    Path(sys.argv[3]).write_text("\n".join(salida))


if __name__ == "__main__":
    main()
