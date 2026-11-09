"""JARVIS — asistente de trabajo: correo + Excel + validación.

Uso:
  python -m jarvis                 # chat por texto
  python -m jarvis --voz           # di "Jarvis, ..." para darle órdenes
  python -m jarvis -c "revisa mis correos no leídos y resúmelos"
  python -m jarvis --validar archivo.xlsx --reglas reglas.json
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import excel
from .comandos import ejecutar_comando
from .config import Config
from .herramientas import Herramientas

SALIR = {"salir", "adiós", "adios", "exit", "quit", "apágate", "apagate"}


def confirmar_consola(texto: str) -> bool:
    print("\n" + texto)
    return input("Escribe 'si' para confirmar: ").strip().lower() in ("si", "sí", "s", "yes", "y")


def construir(config: Config, confirmar=confirmar_consola):
    h = Herramientas(config, confirmar)
    if not config.api_key:
        return h, None
    from .cerebro import Cerebro

    def aviso(nombre, datos):
        print(f"  ⚙ {nombre}…", file=sys.stderr)

    return h, Cerebro(config, h, al_usar_herramienta=aviso)


def responder(texto: str, h: Herramientas, cerebro) -> str:
    if cerebro is None:
        return ejecutar_comando(texto, h)
    if texto.strip().lower() in ("reiniciar", "nueva conversación", "nueva conversacion"):
        cerebro.reiniciar()
        return "Conversación reiniciada."
    return cerebro.preguntar(texto)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jarvis", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--comando", help="Ejecuta una orden y termina")
    ap.add_argument("--voz", action="store_true", help="Modo voz")
    ap.add_argument("--validar", metavar="XLSX", help="Valida un Excel sin IA y termina")
    ap.add_argument("--reglas", metavar="JSON", help="Reglas para --validar")
    args = ap.parse_args(argv)

    config = Config.desde_entorno()

    if args.validar:
        res = excel.validar_hoja(args.validar, args.reglas)
        destino = config.carpeta_salida / (Path(args.validar).stem + "_validado.xlsx")
        print(excel.resumen_texto(res))
        print(f"Reporte: {excel.generar_reporte(args.validar, res, destino)}")
        return 0 if res["valido"] else 1

    h, cerebro = construir(config)
    if cerebro is None:
        print("⚠ Sin ANTHROPIC_API_KEY: modo comandos básico (escribe 'ayuda').", file=sys.stderr)
    if not config.correo.configurado:
        print("⚠ Correo sin configurar: copia .env.example a .env y complétalo.", file=sys.stderr)

    if args.comando:
        print(responder(args.comando, h, cerebro))
        return 0

    if args.voz:
        from .voz import Voz, quitar_palabra_clave

        voz = Voz()
        voz.hablar("JARVIS en línea. ¿En qué le ayudo?")
        while True:
            oido = voz.escuchar()
            if not oido:
                continue
            orden = quitar_palabra_clave(oido)
            if orden is None:
                continue
            print(f"🎙 {oido}")
            if orden.lower() in SALIR:
                voz.hablar("Hasta luego.")
                return 0
            if not orden:
                voz.hablar("Dígame.")
                continue
            r = responder(orden, h, cerebro)
            print(f"JARVIS: {r}\n")
            voz.hablar(r)

    print("JARVIS en línea. Escribe tu orden ('salir' para terminar).")
    while True:
        try:
            texto = input("\nTú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not texto:
            continue
        if texto.lower() in SALIR:
            print("JARVIS: Hasta luego.")
            return 0
        print(f"\nJARVIS: {responder(texto, h, cerebro)}")


if __name__ == "__main__":
    raise SystemExit(main())
