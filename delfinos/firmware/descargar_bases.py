#!/usr/bin/env python3
"""Descarga las mejores bases de datos para potenciar DelfínOS (infrarrojo, Sub-GHz, NFC).

Uso (en la Mac):
    python3 descargar_bases.py --infrarrojo [--salida ~/DelfinOS_SD]
    python3 descargar_bases.py --todo

Qué baja (todas de uso legítimo, mantenidas por la comunidad):
  --infrarrojo : Flipper-IRDB (UberGuidoZ) — miles de controles de TV, aires, etc.
  --subghz     : base de .sub por marca y dispositivo (UberGuidoZ/Flipper)
  --nfc        : diccionarios y tarjetas soportadas (UberGuidoZ/Flipper)

Las bases son GRANDES y van en la SD del Flipper, NO dentro del firmware. El script
las deja en carpetas listas para copiar a la raíz de tu SD:
  <salida>/infrared/   -> copia a  /infrared  de la SD
  <salida>/subghz/     -> copia a  /subghz    de la SD
  <salida>/nfc/        -> copia a  /nfc        de la SD

Así el Mando Universal y los lectores NFC/Sub-GHz reconocen muchísimos más equipos.
Uso educativo y responsable; revisa las leyes de tu país.
"""
import argparse
import subprocess
import sys
from pathlib import Path

# repo, subcarpeta dentro del repo (o ""), carpeta destino en la SD
BASES = {
    "infrarrojo": ("https://github.com/UberGuidoZ/Flipper-IRDB.git", "", "infrared"),
    "subghz": ("https://github.com/UberGuidoZ/Flipper.git", "Sub-GHz", "subghz"),
    "nfc": ("https://github.com/UberGuidoZ/Flipper.git", "NFC", "nfc"),
}


def clonar(url, subcarpeta, destino):
    tmp = destino.parent / (destino.name + "_tmp")
    if tmp.exists():
        subprocess.run(["rm", "-rf", str(tmp)], check=True)
    print(f"→ Descargando {url} … (es grande, puede tardar varios minutos)")
    args = ["git", "clone", "-q", "--depth", "1"]
    if subcarpeta:
        args += ["--filter=blob:none", "--sparse"]
    args += [url, str(tmp)]
    if subprocess.run(args).returncode:
        sys.exit(f"✗ No se pudo descargar {url} (¿internet? ¿git instalado?).")
    if subcarpeta:
        subprocess.run(["git", "-C", str(tmp), "sparse-checkout", "set", subcarpeta], check=True)
        origen = tmp / subcarpeta
    else:
        origen = tmp
    if destino.exists():
        subprocess.run(["rm", "-rf", str(destino)], check=True)
    origen.rename(destino)
    subprocess.run(["rm", "-rf", str(tmp)], check=True)
    n = sum(1 for _ in destino.rglob("*") if _.is_file())
    print(f"✓ {destino.name}: {n} archivos en {destino}")


def main():
    ap = argparse.ArgumentParser(description="Descarga bases de datos para DelfínOS.")
    ap.add_argument("--infrarrojo", action="store_true")
    ap.add_argument("--subghz", action="store_true")
    ap.add_argument("--nfc", action="store_true")
    ap.add_argument("--todo", action="store_true", help="descargar las tres")
    ap.add_argument("--salida", type=Path, default=Path("~/DelfinOS_SD"))
    a = ap.parse_args()

    quiere = {k for k in BASES if getattr(a, k) or a.todo}
    if not quiere:
        ap.error("Elige al menos una: --infrarrojo, --subghz, --nfc o --todo")
    salida = a.salida.expanduser().resolve()
    salida.mkdir(parents=True, exist_ok=True)
    for k in ("infrarrojo", "subghz", "nfc"):
        if k not in quiere:
            continue
        url, sub, dest = BASES[k]
        clonar(url, sub, salida / dest)
    print(f"\n✓ Listo. Copia el contenido de {salida} a la raíz de tu tarjeta SD.")
    print("  En el Flipper, el Mando Universal y los lectores ya reconocerán muchos más equipos.")


if __name__ == "__main__":
    main()
