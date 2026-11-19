#!/usr/bin/env python3
"""Traduce al español, por lotes y con Claude, los textos de pantalla de muchas apps del Flipper.

Uso (en la Mac, con ANTHROPIC_API_KEY o `ant auth login`):
    pip install anthropic
    python3 traducir_con_claude.py CARPETA_DE_APPS [CARPETA_DE_APPS ...]
    python3 traducir_con_claude.py ~/Documents/DelfinOS/applications/external ~/Documents/DelfinOS/applications_user

- Solo pide a Claude los textos que todavía no están en glosario_es.json.
- Guarda cada lote en glosario/apps.json en cuanto llega: si se corta, se vuelve a correr y sigue.
- Valida cada traducción (mismos %d/%s, mismos saltos de línea, mismos espacios al borde,
  que quepa en la pantalla). Si falla, la vuelve a pedir una vez con el motivo; si falla otra
  vez, la deja en inglés y la anota en glosario/apps_revisar.json.
- Al final mezcla todo en glosario_es.json, que es el que usan el traductor de la Mac y la web.
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textos_pantalla import textos_de_pantalla  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
GLOSARIO = RAIZ / "glosario_es.json"
APPS = RAIZ / "glosario" / "apps.json"
REVISAR = RAIZ / "glosario" / "apps_revisar.json"
MODELO = "claude-opus-5-5"
LOTE = 120
ANCHO = 21  # caracteres por línea que caben en la pantalla de 128 px con la fuente normal

FORMATO = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|z|j|t|L)?[diouxXfFeEgGcspn%]")

SISTEMA = """Traduces la interfaz de apps del Flipper Zero del inglés al español para DelfínOS, un firmware \
usado por hispanohablantes de todo el mundo.

Reglas:
- Español neutro, claro y corto. Tutea al usuario ("Pulsa", "Elige"). Nada de regionalismos.
- La pantalla mide 128x64 píxeles: cada línea cabe en unos 21 caracteres. Nunca alargues una línea \
por encima de 21 caracteres si el original cabía; abrevia con sentido ("Frec.", "Config.").
- Conserva EXACTAMENTE los especificadores de formato (%d, %s, %02X, %lu, %.2f...), en el mismo orden, \
los saltos de línea (\\n), y los espacios al inicio y al final.
- No traduzcas nombres propios, marcas, protocolos, siglas ni términos técnicos que se usan en inglés \
(NFC, RFID, Sub-GHz, GPIO, UART, BLE, WiFi, ESP32, Marauder, MIFARE, DuckyScript, PIN, UID, hex, RAW...).
- Si el texto no es para una persona (un identificador, una clave, un comando, código, una URL, solo \
números o una marca), devuélvelo igual y marca traducir=false.
- Los juegos pueden tener humor: tradúcelo con gracia, sin cambiar el sentido.
Devuelve un elemento por cada id recibido."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "es": {"type": "string"},
                    "traducir": {"type": "boolean"},
                },
                "required": ["id", "es", "traducir"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def problema(en, es):
    """Devuelve por qué la traducción no sirve, o None si está bien."""
    if FORMATO.findall(en) != FORMATO.findall(es):
        return "los especificadores de formato deben ser exactamente " + (" ".join(FORMATO.findall(en)) or "ninguno")
    if en.count("\n") != es.count("\n"):
        return f"debe tener {en.count(chr(10))} saltos de línea"
    if en[:1] == " " and es[:1] != " " or en[-1:] == " " and es[-1:] != " ":
        return "conserva los espacios al inicio y al final"
    for le, ls in zip(en.split("\n"), es.split("\n")):
        if len(ls) > max(ANCHO, len(le)) and len(ls) > len(le):
            return f"la línea '{ls}' tiene {len(ls)} caracteres; máximo {max(ANCHO, len(le))}"
    return None


def pedir(cliente, textos, contexto):
    entrada = "\n".join(json.dumps({"id": i, "en": t, "apps": contexto.get(t, [])[:2]}, ensure_ascii=False)
                        for i, t in enumerate(textos))
    r = cliente.beta.messages.create(
        model=MODELO,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SISTEMA,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": "Traduce estos textos (uno por línea, JSON):\n" + entrada}],
    )
    if r.stop_reason == "refusal":
        raise RuntimeError("Claude rechazó este lote")
    if r.stop_reason == "max_tokens":
        raise RuntimeError("respuesta cortada (max_tokens)")
    texto = next(b.text for b in r.content if b.type == "text")
    return {it["id"]: it for it in json.loads(texto)["items"]}


def traducir_lote(cliente, textos, contexto):
    """Traduce un lote; reintenta una vez los que no pasan la validación."""
    hechos, no_traducir, revisar = {}, [], {}
    res = pedir(cliente, textos, contexto)
    malos = []
    for i, en in enumerate(textos):
        it = res.get(i)
        if not it:
            malos.append((en, "faltó en la respuesta"))
        elif not it["traducir"]:
            no_traducir.append(en)
        elif (p := problema(en, it["es"])):
            malos.append((en, p))
        else:
            hechos[en] = it["es"]
    if malos:
        notas = {en: p for en, p in malos}
        contexto2 = {en: [f"CORRIGE: {p}"] + contexto.get(en, [])[:1] for en, p in notas.items()}
        res2 = pedir(cliente, list(notas), contexto2)
        for i, en in enumerate(notas):
            it = res2.get(i)
            if it and not it["traducir"]:
                no_traducir.append(en)
            elif it and not problema(en, it["es"]):
                hechos[en] = it["es"]
            else:
                revisar[en] = {"motivo": notas[en], "propuesta": it["es"] if it else None}
    return hechos, no_traducir, revisar


def cargar(ruta, defecto):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto


def guardar(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Traduce con Claude los textos de pantalla de apps del Flipper.")
    ap.add_argument("carpetas", nargs="+", type=Path)
    ap.add_argument("--hilos", type=int, default=4)
    ap.add_argument("--limite", type=int, help="traducir solo los N textos más repetidos (para probar)")
    a = ap.parse_args()

    glosario = cargar(GLOSARIO, {"terminos": {}, "no_traducir": []})
    apps = cargar(APPS, {"terminos": {}, "no_traducir": []})
    revisar = cargar(REVISAR, {})
    conocidos = set(glosario["terminos"]) | set(glosario["no_traducir"]) | set(apps["terminos"]) | set(apps["no_traducir"])

    contexto = {}
    for c in a.carpetas:
        for app in sorted(p for p in c.expanduser().iterdir() if p.is_dir()):
            for t in textos_de_pantalla(app):
                contexto.setdefault(t, []).append(app.name)
    pendientes = sorted((t for t in contexto if t not in conocidos), key=lambda t: (-len(contexto[t]), t))
    if a.limite:
        pendientes = pendientes[:a.limite]
    print(f"{len(contexto)} textos de pantalla, {len(pendientes)} por traducir en {-(-len(pendientes) // LOTE)} lotes")
    if not pendientes:
        return

    cliente = anthropic.Anthropic()
    lotes = [pendientes[i:i + LOTE] for i in range(0, len(pendientes), LOTE)]
    with ThreadPoolExecutor(a.hilos) as ex:
        futuros = {ex.submit(traducir_lote, cliente, l, contexto): n for n, l in enumerate(lotes)}
        for k, f in enumerate(as_completed(futuros), 1):
            try:
                hechos, nt, rev = f.result()
            except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as e:
                print(f"  ✗ lote {futuros[f]}: {e} (vuelve a correr el script para reintentarlo)")
                continue
            apps["terminos"].update(hechos)
            apps["no_traducir"] = sorted(set(apps["no_traducir"]) | set(nt))
            revisar.update(rev)
            guardar(APPS, apps)
            guardar(REVISAR, revisar)
            print(f"  ✓ lote {k}/{len(lotes)}: {len(hechos)} traducidos, {len(nt)} sin traducir, {len(rev)} a revisar")

    glosario["terminos"].update({k: v for k, v in apps["terminos"].items() if k not in glosario["terminos"]})
    glosario["no_traducir"] = sorted(set(glosario["no_traducir"]) | set(apps["no_traducir"]))
    guardar(GLOSARIO, glosario)
    print(f"\n✓ glosario_es.json: {len(glosario['terminos'])} términos. A revisar a mano: {len(revisar)} "
          f"(glosario/apps_revisar.json)")


if __name__ == "__main__":
    main()
