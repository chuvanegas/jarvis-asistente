"""Encuentra los textos que una app del Flipper muestra en pantalla (y no los que usa como datos)."""
import re
from pathlib import Path

import delfin_traductor as dt

# Llamadas que dibujan o muestran texto en el Flipper.
LLAMADAS_PANTALLA = re.compile(
    r"(?<![\w])(submenu_\w+|widget_add_\w+|dialog_ex_set_\w+|dialog_message_set_\w+|popup_set_\w+|canvas_draw_str\w*|"
    r"elements_\w+|variable_item_\w+|text_input_set_header_text|byte_input_set_header_text|"
    r"number_input_set_header_text|button_menu_add_item|button_panel_add_\w+|menu_add_item|text_box_set_text|"
    r"loading_\w+|file_browser_\w+|dialog_file_browser_\w+|"
    r"furi_string_(?:set|cat|printf|cat_printf|set_str|cat_str|alloc_set|alloc_printf)\w*|snprintf|"
    r"empty_screen_\w+|view_\w+_set_\w+|\w+_set_(?:header|text|title|label|message)\w*)\b")
CARPETAS_IGNORADAS = {"lib", "libs", "debug", "examples", "example", "test", "tests", "plugins", "supported_cards",
                      "protocols", "helpers_parsers", "docs", ".git", "build", "dist", "third_party", "vendor"}


def _es_lista(ctx):
    """El texto está dentro de una lista inicializada (`{"Uno", "Dos"}`), típica de opciones de menú."""
    return bool(re.search(r"=\s*\{[^;]*$", ctx[-300:]))


def textos_de_pantalla(raiz):
    """Devuelve {texto: [archivos donde aparece]} para los textos de pantalla bajo raiz."""
    res = {}
    raiz = Path(raiz)
    for f in sorted(raiz.rglob("*")):
        if f.suffix not in (".c", ".h", ".cpp") or not f.is_file():
            continue
        rel = f.relative_to(raiz)
        if dt.ARCHIVOS_PROHIBIDOS.search(str(rel)) or CARPETAS_IGNORADAS & set(rel.parts[:-1]):
            continue
        codigo = f.read_text(encoding="utf-8", errors="replace")
        for m in dt.LITERAL.finditer(codigo):
            texto = dt._decodificar(m.group(1))
            if not dt.parece_interfaz(texto) or re.search(r'\\[^n"]', m.group(1)):
                continue
            linea = codigo[codigo.rfind("\n", 0, m.start()) + 1:m.start()]
            if linea.lstrip().startswith("#"):
                continue
            ctx = codigo[dt._inicio_sentencia(codigo, m.start()):m.start()]
            if dt.LLAMADAS_PROHIBIDAS.search(ctx):
                continue
            if LLAMADAS_PANTALLA.search(ctx) or _es_lista(ctx):
                res.setdefault(texto, []).append(str(rel))
    return res
