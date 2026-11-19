#!/usr/bin/env python3
"""DelfínOS — traductor de apps y firmware del Flipper Zero (inglés -> español).

Uso:
    python3 delfin_traductor.py CARPETA [--glosario glosario_es.json] [--salida CARPETA]
    python3 delfin_traductor.py CARPETA --en-sitio [--sin-nombre-fam]

- Por defecto nunca toca el original: escribe una copia en CARPETA_es (o --salida).
- --en-sitio traduce dentro de la carpeta (úsalo solo en un repo git, para poder deshacer).
- --sin-nombre-fam deja en inglés el `name=` de application.fam (apps del sistema: el
  celular y qFlipper las abren por ese nombre).
- Traduce solo textos entre comillas que coinciden EXACTO con el glosario y que no
  están dentro de llamadas que usan el texto como dato (claves de archivos, rutas,
  comparaciones, logs, CLI).
- Lista los textos "pendientes" que parecen de pantalla y no están en el glosario.
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

# Textos dentro de estas llamadas NO son de pantalla: claves de archivos guardados
# (.sub, .nfc, .ir...), comparaciones, rutas, logs, CLI o nombres con los que la app
# del celular y qFlipper abren apps. Traducirlos rompe compatibilidad.
LLAMADAS_PROHIBIDAS = re.compile(
    r"(?<![\w])(flipper_format_\w+|FURI_LOG_\w+|furi_log_\w+|strn?cmp|strn?casecmp|strstr|strchr|sscanf|"
    r"furi_string_(?:cmp|equal|search|start_with|end_with)\w*|storage_\w+|furi_record_\w+|furi_thread_\w+|"
    r"furi_hal_\w+|furi_check|furi_assert|furi_crash|furi_pubsub_\w+|path_\w+|args_\w+|cli_\w+|rpc_\w+|"
    r"loader_\w+|infrared_brute_force_\w+|subghz_environment_\w+|printf|fopen|archive_favorites_\w+|"
    r"\.?app_name|\w*button_names|\w*keybind\w*|"
    r"(?:EXT|INT|ANY|APP_DATA|APP_ASSETS)_PATH)\b")
DEFINE_CLAVE = re.compile(
    r"^\s*#\s*define\s+\w*(KEY|PATH|FOLDER|DIR|EXT|FILE|TAG|APPID|APP_ID|HEADER|FILETYPE|FORMAT|PREFIX|MAGIC|PROTOCOL)\w*\s",
    re.I)
# Comparaciones: un texto comparado en un sitio y asignado en otro debe quedar igual en
# ambos, así que todo texto que aparece en una comparación no se traduce en ningún lado.
COMPARACIONES = re.compile(
    r"(?<![\w])(strn?cmp|strn?casecmp|strstr|furi_string_(?:cmp|equal|search|start_with|end_with)\w*)\b")
ARCHIVOS_PROHIBIDOS = re.compile(r"(^|[_/])(cli|rpc)([_./]|$)|unit_test|(^|/)tests?/", re.I)


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


def _inicio_sentencia(codigo, pos):
    """Inicio de la sentencia que contiene pos. Si el texto está dentro de una lista
    inicializada (`x[] = {...}`, `.campo = {...}` o `{...}, {...}`), incluye la declaración
    completa para ver el nombre de la variable."""
    ini = max(codigo.rfind(c, 0, pos) for c in ";{}")
    if ini >= 0 and codigo[ini] == "{" and codigo[:ini].rstrip().endswith(("=", ",", "{")):
        return codigo.rfind(";", 0, ini) + 1
    return ini + 1


def traducir_texto(codigo, terminos, no_traducir, pendientes, extension, fam_nombre=True, cambios=None):
    """Devuelve (codigo_traducido, n_traducidos). Llena `pendientes` {texto: n}."""
    n = 0
    salida, desplaz = [], 0
    for linea in codigo.split("\n"):
        base = desplaz
        desplaz += len(linea) + 1
        if linea.lstrip().startswith("#include") or DEFINE_CLAVE.match(linea):
            salida.append(linea)
            continue
        if extension == ".fam" and not (fam_nombre and re.match(r"\s*name\s*=", linea)):
            salida.append(linea)
            continue

        def reemplazo(m):
            nonlocal n
            if extension != ".fam":
                ini = _inicio_sentencia(codigo, base + m.start())
                if LLAMADAS_PROHIBIDAS.search(codigo[ini:base + m.start()]):
                    return m.group(0)
            original = _decodificar(m.group(1))
            if original in terminos:
                n += 1
                if cambios is not None:
                    cambios.append((original, terminos[original]))
                return '"' + _codificar(terminos[original]) + '"'
            if original not in no_traducir and parece_interfaz(original):
                pendientes[original] = pendientes.get(original, 0) + 1
            return m.group(0)

        salida.append(LITERAL.sub(reemplazo, linea))
    return "\n".join(salida), n


def nombres_de_apps(raiz):
    """Nombres internos de las apps (name= en application.fam). Se usan para abrirlas,
    fijarlas en Favoritos o en atajos, así que nunca se traducen en el código."""
    nombres = set()
    for fam in Path(raiz).rglob("application.fam"):
        nombres |= set(re.findall(r'\bname\s*=\s*"([^"]+)"', fam.read_text(errors="replace")))
    return nombres


def cargar_glosario(ruta):
    g = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return g.get("terminos", {}), set(g.get("no_traducir", []))


def textos_comparados(raiz):
    """Todos los textos que aparecen dentro de una comparación en algún archivo de raiz."""
    vistos = set()
    for f in Path(raiz).rglob("*"):
        if f.suffix not in EXTENSIONES or not f.is_file() or f.suffix == ".fam":
            continue
        codigo = f.read_text(encoding="utf-8", errors="replace")
        if not COMPARACIONES.search(codigo):
            continue
        for m in LITERAL.finditer(codigo):
            ini = _inicio_sentencia(codigo, m.start())
            if COMPARACIONES.search(codigo[ini:m.start()]):
                vistos.add(_decodificar(m.group(1)))
    return vistos


def traducir_carpeta(destino, terminos, no_traducir, fam_nombre=True, raiz_comparaciones=None):
    comparados = textos_comparados(raiz_comparaciones or destino)
    no_traducir = no_traducir | comparados
    terminos = {k: v for k, v in terminos.items() if k not in comparados}
    total, archivos, pendientes = 0, 0, {}
    for f in sorted(destino.rglob("*")):
        if f.suffix not in EXTENSIONES or not f.is_file():
            continue
        if ARCHIVOS_PROHIBIDOS.search(str(f.relative_to(destino))):
            continue
        with open(f, encoding="utf-8", errors="surrogateescape", newline="") as fh:
            codigo = fh.read()  # newline="" conserva los finales de línea (CRLF o LF)
        nuevo, n = traducir_texto(codigo, terminos, no_traducir, pendientes, f.suffix, fam_nombre)
        if n:
            with open(f, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                fh.write(nuevo)
            archivos += 1
            total += n
    return total, archivos, pendientes


def main(argv=None):
    p = argparse.ArgumentParser(description="Traduce una app o el firmware del Flipper Zero al español.")
    p.add_argument("carpeta", type=Path)
    p.add_argument("--glosario", type=Path, default=GLOSARIO_DEFECTO)
    p.add_argument("--salida", type=Path)
    p.add_argument("--en-sitio", action="store_true", help="traducir dentro de la carpeta (solo en un repo git)")
    p.add_argument("--sin-nombre-fam", action="store_true", help="no traducir name= de application.fam")
    p.add_argument("--proteger-apps", type=Path, metavar="RAIZ",
                   help="no traducir nombres de apps ni textos comparados en cualquier parte de RAIZ")
    p.add_argument("--max-pendientes", type=int, default=60)
    a = p.parse_args(argv)

    origen = a.carpeta.resolve()
    if not origen.is_dir():
        sys.exit(f"No existe la carpeta: {origen}")
    terminos, no_traducir = cargar_glosario(a.glosario)
    if a.proteger_apps:
        protegidos = nombres_de_apps(a.proteger_apps)
        no_traducir |= protegidos
        terminos = {k: v for k, v in terminos.items() if k not in protegidos}

    if a.en_sitio:
        destino = origen
    else:
        destino = (a.salida or origen.with_name(origen.name + "_es")).resolve()
        if destino == origen:
            sys.exit("La salida no puede ser la misma carpeta que el original (usa --en-sitio).")
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(origen, destino)

    total, archivos, pendientes = traducir_carpeta(destino, terminos, no_traducir, not a.sin_nombre_fam,
                                                   a.proteger_apps)

    print(f"✓ {'Traducido en' if a.en_sitio else 'Copia traducida en'}: {destino}")
    print(f"✓ {total} textos traducidos en {archivos} archivos.")
    if pendientes:
        print(f"\n⚠ {len(pendientes)} textos pendientes (agrega al glosario los que sean de pantalla):")
        orden = sorted(pendientes.items(), key=lambda x: (-x[1], x[0]))
        for t, c in orden[:a.max_pendientes]:
            print(f"  [{c}x] {t!r}")
        if len(orden) > a.max_pendientes:
            print(f"  … y {len(orden) - a.max_pendientes} más")
    if not a.en_sitio:
        print("\nSiguiente paso: cd a la copia y compila con  ufbt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
