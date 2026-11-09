from openpyxl import Workbook, load_workbook

from jarvis import excel


def _libro(tmp_path, filas, enc=("Factura", "Cantidad", "Precio", "Total", "Correo")):
    wb = Workbook()
    ws = wb.active
    ws.title = "Hoja"
    ws.append(list(enc))
    for f in filas:
        ws.append(f)
    ruta = tmp_path / "datos.xlsx"
    wb.save(ruta)
    return ruta


def test_crear_y_leer(tmp_path):
    ruta = excel.crear_hoja(tmp_path / "x", ["A", "B"], [["1", "2026-01-05"], [2.5, "hola"]], totales=["A"])
    assert ruta.suffix == ".xlsx"
    d = excel.leer_hoja(ruta)
    assert d["encabezados"] == ["A", "B"]
    assert d["filas"][0][0] == 1  # texto convertido a número
    assert d["filas"][0][1].startswith("2026-01-05")
    ws = load_workbook(ruta).active
    assert ws["A4"].value == "=SUM(A2:A3)"


def test_validacion_completa(tmp_path):
    ruta = _libro(tmp_path, [
        ["F1", 2, 10, 20, "a@b.com"],
        ["F1", 1, 5, 99, "malo"],
        ["F3", "x", 5, None, None],
        ["F4", 1, 1, "#DIV/0!", "c@d.co"],
    ])
    reglas = {
        "columnas_requeridas": ["Factura", "Fecha"],
        "no_vacios": ["Total"],
        "tipos": {"Cantidad": "entero", "Correo": "email"},
        "unicos": ["Factura"],
        "formula_total": {"columna": "Total", "igual_a": "Cantidad * Precio"},
    }
    res = excel.validar_hoja(ruta, reglas)
    reglas_vistas = {p["regla"] for p in res["problemas"]}
    assert not res["valido"]
    assert {"columna_requerida", "no_vacio", "tipo", "unico", "formula_total", "error_formula"} <= reglas_vistas
    filas_formula = [p["fila"] for p in res["problemas"] if p["regla"] == "formula_total"]
    assert 2 not in filas_formula and 3 in filas_formula


def test_valido_y_reporte(tmp_path):
    ruta = _libro(tmp_path, [["F1", 2, 10, 20, "a@b.com"], ["TOTAL", None, None, 20, None]])
    res = excel.validar_hoja(ruta, {"formula_total": {"columna": "Total", "igual_a": "Cantidad * Precio"}})
    assert res["valido"] and res["filas_revisadas"] == 1
    salida = excel.generar_reporte(ruta, res, tmp_path / "rep.xlsx")
    assert "Validación" in load_workbook(salida).sheetnames


def test_reporte_marca_celdas(tmp_path):
    ruta = _libro(tmp_path, [["F1", -1, 10, -10, "a@b.com"]])
    res = excel.validar_hoja(ruta, {"rangos": {"Cantidad": {"min": 0}}})
    ws = load_workbook(excel.generar_reporte(ruta, res, tmp_path / "r.xlsx"))["Hoja"]
    assert ws["B2"].fill.start_color.rgb.endswith("FFC7CE")
    assert "menor" in ws["B2"].comment.text


def test_duplicados_y_valores_permitidos(tmp_path):
    ruta = _libro(tmp_path, [["F1", 1, 1, 1, "x"], ["F1", 1, 1, 1, "x"]], enc=("A", "B", "C", "D", "Estado"))
    res = excel.validar_hoja(ruta, {"valores_permitidos": {"Estado": ["ok"]}})
    reglas = [p["regla"] for p in res["problemas"]]
    assert "fila_duplicada" in reglas and reglas.count("valor_permitido") == 2


def test_expresion_segura():
    assert excel._evaluar_expresion("Cantidad * Precio", {"Cantidad": 2, "Precio": 3.5}) == 7
    import pytest
    with pytest.raises(ValueError):
        excel._evaluar_expresion("__import__('os')", {"A": 1})
