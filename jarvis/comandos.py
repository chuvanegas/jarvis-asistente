"""Modo sin IA: comandos directos cuando no hay ANTHROPIC_API_KEY.

Ejemplos:
  correos                      -> últimos 10 correos
  no leidos                    -> correos no leídos
  leer 1234                    -> lee el correo con id 1234
  buscar factura               -> busca texto en correos
  enviar                       -> asistente paso a paso para enviar un correo
  validar ventas.xlsx [reglas.json]
  leer excel ventas.xlsx
  ayuda
"""
from __future__ import annotations

import json
import shlex
from typing import Callable

from . import excel
from .herramientas import Herramientas

AYUDA = __doc__.split("Ejemplos:")[1]


def _lista_correos(res: dict) -> str:
    if not res["correos"]:
        return "No hay correos que coincidan."
    lineas = [f"{res['cantidad']} correos:"]
    for c in res["correos"]:
        marca = "  " if c["leido"] else "● "
        lineas.append(f"{marca}[{c['uid']}] {c['fecha']} — {c['de']}\n      {c['asunto']}")
    return "\n".join(lineas)


def ejecutar_comando(texto: str, h: Herramientas, preguntar: Callable[[str], str] = input) -> str:
    t = texto.strip()
    bajo = t.lower()
    try:
        partes = shlex.split(t)
    except ValueError:
        partes = t.split()

    def correr(nombre, **datos):
        salida, error = h.ejecutar(nombre, datos)
        if error:
            raise RuntimeError(salida)
        return json.loads(salida) if salida.startswith(("{", "[")) else salida

    try:
        if bajo in ("ayuda", "help", "?"):
            return AYUDA
        if bajo in ("correos", "revisa mi correo", "revisar correo", "bandeja"):
            return _lista_correos(correr("buscar_correos", limite=10))
        if bajo.startswith(("no leidos", "no leídos", "pendientes")):
            return _lista_correos(correr("buscar_correos", no_leidos=True, limite=20))
        if bajo.startswith("buscar ") and len(partes) > 1:
            return _lista_correos(correr("buscar_correos", texto=" ".join(partes[1:]), limite=15))
        if bajo.startswith("leer excel ") and len(partes) > 2:
            d = correr("leer_excel", archivo=partes[2], max_filas=20)
            filas = "\n".join(" | ".join(map(str, f)) for f in d["filas"])
            return f"Hoja {d['hoja']} ({d['total_filas']} filas)\n{' | '.join(d['encabezados'])}\n{filas}"
        if bajo.startswith("leer ") and len(partes) == 2:
            c = correr("leer_correo", id=partes[1])
            return f"De: {c['de']}\nAsunto: {c['asunto']}\nFecha: {c['fecha']}\n\n{c['cuerpo']}"
        if bajo.startswith("validar ") and len(partes) > 1:
            reglas = partes[2] if len(partes) > 2 else None
            ruta = h._ruta_entrada(partes[1])
            res = excel.validar_hoja(ruta, reglas)
            destino = h.config.carpeta_salida / f"{ruta.stem}_validado.xlsx"
            reporte = excel.generar_reporte(ruta, res, destino)
            return excel.resumen_texto(res) + f"\nReporte: {reporte}"
        if bajo == "enviar":
            para = [x.strip() for x in preguntar("Para (separa con comas): ").split(",") if x.strip()]
            asunto = preguntar("Asunto: ")
            cuerpo = preguntar("Mensaje: ")
            adj = [x.strip() for x in preguntar("Adjuntos (rutas, opcional): ").split(",") if x.strip()]
            return correr("enviar_correo", para=para, asunto=asunto, cuerpo=cuerpo, adjuntos=adj)
        if bajo in ("hora", "fecha", "qué hora es", "que hora es"):
            return correr("fecha_hora")
    except (RuntimeError, excel.ErrorExcel, ValueError) as e:
        return str(e)
    return ("No entendí el comando (sin ANTHROPIC_API_KEY solo funcionan comandos básicos). "
            "Escribe 'ayuda'.")
