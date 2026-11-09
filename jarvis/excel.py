"""Crear, leer y VALIDAR hojas de Excel (.xlsx).

Reglas de validación (dict o archivo JSON):
{
  "hoja": "Ventas",                       # opcional, por defecto la activa
  "fila_encabezado": 1,                   # opcional
  "columnas_requeridas": ["Fecha", "Cliente", "Total"],
  "no_vacios": ["Cliente", "Total"],
  "tipos": {"Fecha": "fecha", "Total": "numero", "Correo": "email", "Cantidad": "entero"},
  "rangos": {"Total": {"min": 0, "max": 1000000}},
  "valores_permitidos": {"Estado": ["Pagado", "Pendiente"]},
  "unicos": ["Factura"],
  "patrones": {"NIT": "^[0-9]{9}-[0-9]$"},
  "formula_total": {"columna": "Total", "igual_a": "Cantidad * Precio", "tolerancia": 0.01}
}
Además, SIEMPRE se detectan celdas con errores de fórmula (#DIV/0!, #REF!, #N/A, …)
y filas completamente duplicadas.
"""
from __future__ import annotations

import ast
import json
import operator
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ERRORES_FORMULA = {"#DIV/0!", "#REF!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#VALUE!", "#SPILL!", "#CALC!"}
RELLENO_ERROR = PatternFill("solid", start_color="FFC7CE", end_color="FFC7CE")
RELLENO_AVISO = PatternFill("solid", start_color="FFEB9C", end_color="FFEB9C")
RELLENO_ENCABEZADO = PatternFill("solid", start_color="1F4E78", end_color="1F4E78")
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorExcel(Exception):
    pass


@dataclass
class Problema:
    fila: int
    columna: str
    regla: str
    mensaje: str
    valor: Any = None
    severidad: str = "error"  # error | aviso

    def a_dict(self) -> dict:
        d = asdict(self)
        if isinstance(d["valor"], (datetime, date)):
            d["valor"] = d["valor"].isoformat()
        return d


# --------------------------------------------------------------------- crear
def crear_hoja(
    ruta: str | Path,
    encabezados: list[str],
    filas: list[list[Any]],
    nombre_hoja: str = "Datos",
    totales: list[str] | None = None,
) -> Path:
    """Crea un .xlsx con formato profesional. `totales` = columnas a sumar con fórmula =SUMA."""
    if not encabezados:
        raise ErrorExcel("Se necesitan encabezados")
    ruta = Path(ruta)
    if ruta.suffix.lower() != ".xlsx":
        ruta = ruta.with_suffix(".xlsx")
    ruta.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = nombre_hoja[:31]
    ws.append(list(encabezados))
    for fila in filas:
        ws.append([_convertir_valor(v) for v in fila])

    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = RELLENO_ENCABEZADO
        c.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"
    ultima = len(filas) + 1
    if filas:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(encabezados))}{ultima}"

    if totales and filas:
        fila_total = ultima + 1
        ws.cell(row=fila_total, column=1, value="TOTAL").font = Font(bold=True)
        for nombre in totales:
            if nombre not in encabezados:
                raise ErrorExcel(f"La columna de total '{nombre}' no existe")
            col = encabezados.index(nombre) + 1
            letra = get_column_letter(col)
            celda = ws.cell(row=fila_total, column=col, value=f"=SUM({letra}2:{letra}{ultima})")
            celda.font = Font(bold=True)

    for i, enc in enumerate(encabezados, start=1):
        largo = max([len(str(enc))] + [len(str(f[i - 1])) for f in filas if len(f) >= i] or [10])
        ws.column_dimensions[get_column_letter(i)].width = min(max(largo + 2, 10), 60)
        for fila in ws.iter_rows(min_row=2, min_col=i, max_col=i):
            for c in fila:
                if isinstance(c.value, (datetime, date)):
                    c.number_format = "yyyy-mm-dd"
                elif isinstance(c.value, float):
                    c.number_format = "#,##0.00"
    wb.save(ruta)
    return ruta


def _convertir_valor(v: Any) -> Any:
    """Convierte textos tipo número/fecha en valores reales de Excel."""
    if not isinstance(v, str):
        return v
    s = v.strip()
    if re.fullmatch(r"-?\d+", s) and not (len(s) > 1 and s.startswith("0")):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return v
    return v


# --------------------------------------------------------------------- leer
def leer_hoja(ruta: str | Path, hoja: str | None = None, max_filas: int = 200,
              fila_encabezado: int = 1) -> dict:
    wb = _abrir(ruta)
    ws = _seleccionar(wb, hoja)
    encabezados = [_texto(c.value) for c in ws[fila_encabezado]]
    filas = []
    for fila in ws.iter_rows(min_row=fila_encabezado + 1, values_only=True):
        if all(v is None for v in fila):
            continue
        filas.append([_serializable(v) for v in fila])
        if len(filas) >= max_filas:
            break
    return {
        "archivo": str(ruta),
        "hojas": wb.sheetnames,
        "hoja": ws.title,
        "encabezados": encabezados,
        "total_filas": max(ws.max_row - fila_encabezado, 0),
        "filas": filas,
    }


def _abrir(ruta: str | Path, valores: bool = True):
    p = Path(ruta)
    if not p.is_file():
        raise ErrorExcel(f"No existe el archivo: {ruta}")
    try:
        return load_workbook(p, data_only=valores)
    except Exception as e:
        raise ErrorExcel(f"No pude abrir {ruta}: {e}") from e


def _seleccionar(wb, hoja: str | None):
    if hoja:
        if hoja not in wb.sheetnames:
            raise ErrorExcel(f"La hoja '{hoja}' no existe. Hojas: {wb.sheetnames}")
        return wb[hoja]
    return wb.active


def _texto(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _serializable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


# --------------------------------------------------------------------- validar
def cargar_reglas(reglas: dict | str | Path | None) -> dict:
    if reglas is None:
        return {}
    if isinstance(reglas, dict):
        return reglas
    p = Path(reglas)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(str(reglas))


def _es_numero(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v.replace(",", ""))
            return True
        except ValueError:
            return False
    return False


def _a_numero(v: Any) -> float:
    return float(v.replace(",", "")) if isinstance(v, str) else float(v)


def _es_fecha(v: Any) -> bool:
    if isinstance(v, (datetime, date)):
        return True
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                datetime.strptime(v.strip(), fmt)
                return True
            except ValueError:
                pass
    return False


VALIDADORES_TIPO = {
    "numero": _es_numero,
    "entero": lambda v: (isinstance(v, int) and not isinstance(v, bool))
    or (isinstance(v, float) and v.is_integer())
    or (isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip()) is not None),
    "fecha": _es_fecha,
    "texto": lambda v: isinstance(v, str),
    "email": lambda v: isinstance(v, str) and RE_EMAIL.match(v.strip()) is not None,
}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _evaluar_expresion(expr: str, fila: dict[str, Any]) -> float:
    """Evalúa de forma segura expresiones como 'Cantidad * Precio' (solo + - * / y columnas)."""
    nombres = sorted(fila.keys(), key=len, reverse=True)
    variables: dict[str, Any] = {}
    texto = expr
    for i, n in enumerate(nombres):
        if n and n in texto:
            var = f"_c{i}"
            texto = texto.replace(n, var)
            variables[var] = fila[n]

    def ev(nodo):
        if isinstance(nodo, ast.Expression):
            return ev(nodo.body)
        if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPS:
            return _OPS[type(nodo.op)](ev(nodo.left), ev(nodo.right))
        if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, ast.USub):
            return -ev(nodo.operand)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
            return nodo.value
        if isinstance(nodo, ast.Name) and nodo.id in variables:
            return _a_numero(variables[nodo.id])
        raise ValueError(f"Expresión no permitida: {expr}")

    return ev(ast.parse(texto, mode="eval"))


def validar_hoja(ruta: str | Path, reglas: dict | str | Path | None = None) -> dict:
    reglas = cargar_reglas(reglas)
    wb = _abrir(ruta)
    ws = _seleccionar(wb, reglas.get("hoja"))
    fila_enc = int(reglas.get("fila_encabezado", 1))
    encabezados = [_texto(c.value) for c in ws[fila_enc]]
    idx = {n: i for i, n in enumerate(encabezados) if n}
    problemas: list[Problema] = []

    def letra(nombre: str) -> str:
        return get_column_letter(idx[nombre] + 1) if nombre in idx else nombre

    for col in reglas.get("columnas_requeridas", []):
        if col not in idx:
            problemas.append(Problema(fila_enc, col, "columna_requerida", f"Falta la columna '{col}'"))

    # columnas referenciadas en reglas que no existen -> aviso (una vez)
    referenciadas = set(reglas.get("no_vacios", [])) | set(reglas.get("unicos", []))
    for clave in ("tipos", "rangos", "valores_permitidos", "patrones"):
        referenciadas |= set(reglas.get(clave, {}).keys())
    for col in sorted(referenciadas - set(idx) - set(reglas.get("columnas_requeridas", []))):
        problemas.append(Problema(fila_enc, col, "columna_inexistente",
                                  f"La regla usa la columna '{col}' que no existe", severidad="aviso"))

    vistos_unicos: dict[str, dict[Any, int]] = defaultdict(dict)
    filas_vistas: dict[tuple, int] = {}
    total_filas = 0
    patrones = {c: re.compile(p) for c, p in reglas.get("patrones", {}).items()}
    formula = reglas.get("formula_total")

    for n_fila, fila in enumerate(ws.iter_rows(min_row=fila_enc + 1, values_only=True), start=fila_enc + 1):
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in fila):
            continue
        primera = _texto(fila[0]).upper() if fila else ""
        if primera in ("TOTAL", "TOTALES", "SUBTOTAL"):
            continue
        total_filas += 1
        valores = {n: (fila[i] if i < len(fila) else None) for n, i in idx.items()}

        for i, v in enumerate(fila):
            if isinstance(v, str) and v.strip() in ERRORES_FORMULA:
                nombre = encabezados[i] if i < len(encabezados) and encabezados[i] else get_column_letter(i + 1)
                problemas.append(Problema(n_fila, nombre, "error_formula", f"Error de fórmula {v}", v))

        clave_fila = tuple(fila)
        if clave_fila in filas_vistas:
            problemas.append(Problema(n_fila, "*", "fila_duplicada",
                                      f"Fila idéntica a la fila {filas_vistas[clave_fila]}", severidad="aviso"))
        else:
            filas_vistas[clave_fila] = n_fila

        for col in reglas.get("no_vacios", []):
            if col in valores and (valores[col] is None or _texto(valores[col]) == ""):
                problemas.append(Problema(n_fila, col, "no_vacio", f"'{col}' está vacío"))

        for col, tipo in reglas.get("tipos", {}).items():
            v = valores.get(col)
            if v is None or _texto(v) == "" or col not in idx:
                continue
            fn = VALIDADORES_TIPO.get(tipo)
            if fn is None:
                raise ErrorExcel(f"Tipo desconocido '{tipo}'. Usa: {list(VALIDADORES_TIPO)}")
            if not fn(v):
                problemas.append(Problema(n_fila, col, "tipo", f"'{col}' debería ser {tipo}", v))

        for col, rango in reglas.get("rangos", {}).items():
            v = valores.get(col)
            if v is None or not _es_numero(v):
                continue
            num = _a_numero(v)
            if "min" in rango and num < rango["min"]:
                problemas.append(Problema(n_fila, col, "rango", f"'{col}'={num} es menor que {rango['min']}", v))
            if "max" in rango and num > rango["max"]:
                problemas.append(Problema(n_fila, col, "rango", f"'{col}'={num} es mayor que {rango['max']}", v))

        for col, permitidos in reglas.get("valores_permitidos", {}).items():
            v = valores.get(col)
            if v is not None and _texto(v) and v not in permitidos and _texto(v) not in map(str, permitidos):
                problemas.append(Problema(n_fila, col, "valor_permitido",
                                          f"'{v}' no está permitido en '{col}' (permitidos: {permitidos})", v))

        for col, patron in patrones.items():
            v = valores.get(col)
            if v is not None and _texto(v) and not patron.search(_texto(v)):
                problemas.append(Problema(n_fila, col, "patron", f"'{v}' no cumple el formato de '{col}'", v))

        for col in reglas.get("unicos", []):
            v = valores.get(col)
            if v is None or _texto(v) == "":
                continue
            if v in vistos_unicos[col]:
                problemas.append(Problema(n_fila, col, "unico",
                                          f"'{v}' repetido (ya está en la fila {vistos_unicos[col][v]})", v))
            else:
                vistos_unicos[col][v] = n_fila

        if formula and formula.get("columna") in valores:
            col = formula["columna"]
            esperado_v = valores.get(col)
            try:
                calculado = _evaluar_expresion(formula["igual_a"], valores)
                if esperado_v is None or not _es_numero(esperado_v) or abs(
                    _a_numero(esperado_v) - calculado
                ) > float(formula.get("tolerancia", 0.01)):
                    problemas.append(Problema(n_fila, col, "formula_total",
                                              f"'{col}'={esperado_v} pero {formula['igual_a']} = {round(calculado, 4)}",
                                              esperado_v))
            except (ValueError, TypeError, ZeroDivisionError):
                pass  # datos incompletos: ya los reportan otras reglas

    errores = sum(1 for p in problemas if p.severidad == "error")
    avisos = len(problemas) - errores
    por_regla = Counter(p.regla for p in problemas)
    return {
        "archivo": str(ruta),
        "hoja": ws.title,
        "filas_revisadas": total_filas,
        "valido": errores == 0,
        "errores": errores,
        "avisos": avisos,
        "por_regla": dict(por_regla),
        "problemas": [p.a_dict() for p in problemas],
        "_letras": {n: letra(n) for n in idx},
    }


def generar_reporte(ruta: str | Path, resultado: dict, salida: str | Path | None = None) -> Path:
    """Copia el Excel marcando en rojo/amarillo las celdas con problemas y agrega una hoja 'Validación'."""
    ruta = Path(ruta)
    salida = Path(salida) if salida else ruta.with_name(ruta.stem + "_validado.xlsx")
    wb = load_workbook(ruta)  # con fórmulas
    ws = wb[resultado["hoja"]]
    letras = resultado.get("_letras", {})
    for p in resultado["problemas"]:
        if p["columna"] in letras:
            celda = ws[f"{letras[p['columna']]}{p['fila']}"]
            celda.fill = RELLENO_ERROR if p["severidad"] == "error" else RELLENO_AVISO
            previo = celda.comment.text + "\n" if celda.comment else ""
            celda.comment = Comment(previo + p["mensaje"], "JARVIS")

    if "Validación" in wb.sheetnames:
        del wb["Validación"]
    rep = wb.create_sheet("Validación")
    rep.append(["Archivo", str(ruta.name)])
    rep.append(["Filas revisadas", resultado["filas_revisadas"]])
    rep.append(["Resultado", "VÁLIDO ✅" if resultado["valido"] else "CON ERRORES ❌"])
    rep.append(["Errores", resultado["errores"]])
    rep.append(["Avisos", resultado["avisos"]])
    rep.append([])
    rep.append(["Fila", "Columna", "Regla", "Severidad", "Mensaje", "Valor"])
    for c in rep[7]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = RELLENO_ENCABEZADO
    for p in resultado["problemas"]:
        rep.append([p["fila"], p["columna"], p["regla"], p["severidad"], p["mensaje"],
                    None if p["valor"] is None else str(p["valor"])])
    for col, ancho in zip("ABCDEF", (8, 18, 18, 10, 70, 25)):
        rep.column_dimensions[col].width = ancho
    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)
    return salida


def resumen_texto(resultado: dict, max_lineas: int = 20) -> str:
    lineas = [
        f"Archivo: {resultado['archivo']} (hoja {resultado['hoja']})",
        f"Filas revisadas: {resultado['filas_revisadas']}",
        f"Resultado: {'VÁLIDO' if resultado['valido'] else 'CON ERRORES'} — "
        f"{resultado['errores']} errores, {resultado['avisos']} avisos",
    ]
    for p in resultado["problemas"][:max_lineas]:
        lineas.append(f"  [{p['severidad']}] fila {p['fila']}, {p['columna']}: {p['mensaje']}")
    resto = len(resultado["problemas"]) - max_lineas
    if resto > 0:
        lineas.append(f"  … y {resto} problemas más")
    return "\n".join(lineas)
