import base64
import io
import json

from openpyxl import Workbook
from PIL import Image

from jarvis import excel, pantalla
from jarvis.config import Config
from jarvis.herramientas import Herramientas
from jarvis.memoria import Memoria
from jarvis.voz import Hablante, limpiar_para_voz, quitar_palabra_clave, recortar_por_silencio


def _nomina(ruta, filas):
    wb = Workbook()
    ws = wb.active
    ws.title = "Nomina"
    ws.append(["Cedula", "Empleado", "Cargo", "Salario", "Correo"])
    for f in filas:
        ws.append(f)
    wb.save(ruta)
    return ruta


BUENAS = [[1000 + i, f"Persona {i}", ["Analista", "Auxiliar"][i % 2], 2_000_000.0 + i, f"p{i}@empresa.com"]
          for i in range(8)]


def test_inferir_reglas(tmp_path):
    ruta = _nomina(tmp_path / "buena.xlsx", BUENAS)
    reglas = excel.inferir_reglas(excel.perfilar_hoja(ruta))
    assert reglas["tipos"]["Salario"] == "numero" and reglas["tipos"]["Correo"] == "email"
    assert "Cedula" in reglas["unicos"]
    assert reglas["valores_permitidos"]["Cargo"] == ["Analista", "Auxiliar"]
    assert reglas["rangos"]["Salario"] == {"min": 0}
    assert set(reglas["no_vacios"]) == {"Cedula", "Empleado", "Cargo", "Salario", "Correo"}


def test_perfil_aprendido_se_usa_al_validar(tmp_path):
    cfg = Config(carpeta_salida=tmp_path / "out", carpeta_datos=tmp_path / "datos")
    h = Herramientas(cfg, lambda t: True)
    buena = _nomina(tmp_path / "buena.xlsx", BUENAS)
    r, err = h.ejecutar("aprender_reglas", {"archivo": str(buena), "nombre_perfil": "nomina"})
    assert not err and json.loads(r)["perfil"] == "nomina"
    mala = _nomina(tmp_path / "mala.xlsx", BUENAS[:3] + [[1000, "", "Gerente", -5, "x"]])
    r, err = h.ejecutar("validar_excel", {"archivo": str(mala)})
    d = json.loads(r)
    assert d["perfil_aprendido_usado"] == "nomina"
    assert {"unico", "no_vacio", "valor_permitido", "rango", "tipo"} <= set(d["por_regla"])
    # persiste en disco
    assert "nomina" in Memoria(tmp_path / "datos").datos["perfiles"]


def test_notas_e_indice(tmp_path):
    m = Memoria(tmp_path / "datos")
    m.recordar("Mi jefe es Carlos Ruiz, carlos@empresa.com", ["jefe"])
    m.recordar("La nómina se cierra el 25 de cada mes")
    assert m.buscar_notas("nomina")[0]["texto"].startswith("La nómina")
    assert "Carlos" in m.contexto()
    trabajo = tmp_path / "trabajo" / "sub"
    trabajo.mkdir(parents=True)
    _nomina(trabajo / "Nomina Octubre.xlsx", BUENAS)
    (trabajo / "~$temporal.xlsx").write_bytes(b"x")
    (trabajo / "dañado.xlsx").write_bytes(b"no es excel")
    res = m.indexar([tmp_path / "trabajo"])
    assert res["nuevos"] == 2 and res["errores"] == 1
    assert m.indexar([tmp_path / "trabajo"])["nuevos"] == 0  # no reprocesa sin cambios
    encontrados = m.buscar_archivos("nomina salario")
    assert encontrados and encontrados[0]["nombre"] == "Nomina Octubre.xlsx"
    assert m.olvidar(1) and len(m.datos["notas"]) == 1


def test_pantalla_prepara_imagen():
    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), "white").save(buf, "PNG")
    datos, (w, h) = pantalla.preparar_imagen(buf.getvalue())
    assert max(w, h) <= pantalla.LADO_MAXIMO
    assert base64.b64decode(datos)[:2] == b"\xff\xd8"  # JPEG


def test_ver_pantalla_devuelve_bloque_imagen(tmp_path, monkeypatch):
    monkeypatch.setattr(pantalla, "capturar", lambda: ("QUJD", (100, 50)))
    h = Herramientas(Config(carpeta_datos=tmp_path), lambda t: True)
    r, err = h.ejecutar("ver_pantalla", {})
    assert not err and r[1]["type"] == "image" and r[1]["source"]["data"] == "QUJD"


def test_voz_utilidades():
    assert quitar_palabra_clave("Jarvis, revisa mi correo") == "revisa mi correo"
    assert quitar_palabra_clave("oye jarvis abre la nómina") == "abre la nómina"
    assert quitar_palabra_clave("Jarvis") == ""
    assert quitar_palabra_clave("revisa mi correo") is None
    assert recortar_por_silencio([0, 0, 900, 900, 10, 10, 10], 400, 3) == 7
    assert recortar_por_silencio([0, 0, 0, 0], 400, 2) is None
    t = limpiar_para_voz("**Hola**\n\n- uno\n- dos\n```\ncodigo\n```")
    assert "*" not in t and "codigo" not in t and "uno" in t
    h = Hablante.__new__(Hablante)
    h.voz_mac, h.velocidad = "Paulina", 190
    assert h.comando("hola") == ["say", "-r", "190", "-v", "Paulina", "hola"]
