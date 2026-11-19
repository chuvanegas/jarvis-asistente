#!/usr/bin/env python3
"""DelfínOS — traductor de apps del Flipper Zero (inglés -> español).

Uso:
    python3 delfin_traductor.py CARPETA_APP [--glosario glosario_es.json] [--salida CARPETA]

- Nunca toca el original: escribe una copia en CARPETA_APP_es (o --salida).
- Traduce solo textos entre comillas que coinciden EXACTO con el glosario.
- Lista los textos "pendientes" que parecen de interfaz y no están en el glosario,
  para que el administrador decida cuáles agregar (marcas y términos técnicos
  van en "no_traducir").
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

EXTENSIONES = {".c", ".h", ".cpp", ".hpp", ".fam"}
LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
GLOSARIO_DEFECTO = Path(__file__).resolve().parent.parent / "glosario_es.json"


def _decodificar(s):
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def _codificar(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def parece_interfaz(texto):
    """Heurística: texto corto con letras y espacios/mayúscula, no ruta ni formato."""
    t = texto.strip()
    if len(t) < 3 or len(t) > 60:
        return False
    if not re.search(r"[A-Za-z]{2,}", t):
        return False
    if re.search(r"[/\\_]|\.(c|h|fap|txt|sub|nfc|ir|rfid|ibtn)\b|^%|^[A-Z0-9_]+$", t):
        return False
    if re.fullmatch(r"[a-z0-9_.\-]+", t):  # identificadores, claves, tags
        return False
    return True


def traducir_texto(codigo, terminos, no_traducir, pendientes, extension):
    traducidos = 0
    lineas = codigo.split("\n")
    for i, linea in enumerate(lineas):
        if linea.lstrip().startswith("#include"):
            continue

        def reemplazar(m):
            nonlocal traducidos
            original = _decodificar(m.group(1))
            if original in terminos:
                traducidos += 1
                return '"' + _codificar(terminos[original]) + '"'
            if original not in no_traducir and parece_interfaz(original):
                pendientes.setdefault(original, 0)
                pendientes[original] += 1
            return m.group(0)

        if extension == ".fam":
            # En application.fam solo se traduce el nombre visible.
            if re.match(r"\s*name\s*=", linea):
                lineas[i] = LITERAL.sub(reemplazar, linea)
            continue
        lineas[i] = LITERAL.sub(reemplazar, linea)
    return "\n".join(lineas), traducidos


def main(argv=None):
    p = argparse.ArgumentParser(description="Traduce una app del Flipper Zero al español.")
    p.add_argument("carpeta", type=Path)
    p.add_argument("--glosario", type=Path, default=GLOSARIO_DEFECTO)
    p.add_argument("--salida", type=Path)
    a = p.parse_args(argv)

    origen = a.carpeta.resolve()
    if not origen.is_dir():
        sys.exit(f"No existe la carpeta: {origen}")
    destino = (a.salida or origen.with_name(origen.name + "_es")).resolve()
    if destino == origen:
        sys.exit("La salida no puede ser la misma carpeta que el original.")

    g = json.loads(a.glosario.read_text(encoding="utf-8"))
    terminos, no_traducir = g.get("terminos", {}), set(g.get("no_traducir", []))

    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origen, destino)

    total, pendientes, archivos = 0, {}, 0
    for f in sorted(destino.rglob("*")):
        if f.suffix not in EXTENSIONES or not f.is_file():
            continue
        codigo = f.read_text(encoding="utf-8", errors="surrogateescape")
        nuevo, n = traducir_texto(codigo, terminos, no_traducir, pendientes, f.suffix)
        if n:
            f.write_text(nuevo, encoding="utf-8", errors="surrogateescape")
            archivos += 1
            total += n

    print(f"✓ Copia traducida en: {destino}")
    print(f"✓ {total} textos traducidos en {archivos} archivos.")
    if pendientes:
        print(f"\n⚠ {len(pendientes)} textos pendientes (agrega al glosario los que sean de interfaz):")
        for t, c in sorted(pendientes.items(), key=lambda x: (-x[1], x[0])):
            print(f"  [{c}x] {t!r}")
    print("\nSiguiente paso: cd a la copia y compila con  ufbt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
