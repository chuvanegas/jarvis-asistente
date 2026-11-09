import json
from pathlib import Path
from types import SimpleNamespace as NS

from jarvis.cerebro import Cerebro
from jarvis.comandos import ejecutar_comando
from jarvis.config import Config
from jarvis.correo import Correo
from jarvis.herramientas import DEFINICIONES, Herramientas


class FakeCorreo:
    def __init__(self):
        self.enviados = []
    def buscar(self, **kw):
        return [Correo("1", "jefe@x.com", "yo@x.com", "Informe", "2026-11-09 08:00", "Envíame el informe", [], False)]
    def leer(self, uid, carpeta="INBOX"):
        return self.buscar()[0]
    def construir_mensaje(self, para, asunto, cuerpo, cc=None, adjuntos=None):
        return {"To": ", ".join(para), "Cc": None, "asunto": asunto}
    def enviar(self, msg):
        self.enviados.append(msg)
        return f"Correo enviado a {msg['To']}"


def _h(tmp_path, confirmar=True):
    cfg = Config(carpeta_salida=tmp_path, carpeta_datos=tmp_path / "datos")
    return Herramientas(cfg, lambda _t: confirmar, FakeCorreo())


def test_definiciones_validas():
    nombres = {d["name"] for d in DEFINICIONES}
    assert {"buscar_correos", "enviar_correo", "crear_excel", "validar_excel"} <= nombres
    h = Herramientas(Config(carpeta_datos=Path("/nonexistent-jarvis")), lambda t: True, FakeCorreo())
    for n in nombres:
        assert hasattr(h, f"h_{n}")


def test_enviar_requiere_confirmacion(tmp_path):
    h = _h(tmp_path, confirmar=False)
    r, err = h.ejecutar("enviar_correo", {"para": ["a@b.com"], "asunto": "x", "cuerpo": "y"})
    assert "canceló" in r and not err and h.correo.enviados == []
    h = _h(tmp_path, confirmar=True)
    r, _ = h.ejecutar("enviar_correo", {"para": ["a@b.com"], "asunto": "x", "cuerpo": "y"})
    assert "enviado" in r and len(h.correo.enviados) == 1


def test_crear_y_validar_excel(tmp_path):
    h = _h(tmp_path)
    r, err = h.ejecutar("crear_excel", {"archivo": "a.xlsx", "encabezados": ["N", "V"], "filas": [["x", 1], ["", -2]]})
    assert not err and (tmp_path / "a.xlsx").exists()
    r, err = h.ejecutar("validar_excel", {"archivo": "a.xlsx", "reglas": {"no_vacios": ["N"], "rangos": {"V": {"min": 0}}}})
    d = json.loads(r)
    assert not err and d["errores"] == 2 and Path(d["reporte"]).exists()


def test_error_controlado(tmp_path):
    r, err = _h(tmp_path).ejecutar("leer_excel", {"archivo": "noexiste.xlsx"})
    assert err and "No existe" in r


def test_comandos_sin_ia(tmp_path):
    h = _h(tmp_path)
    assert "Informe" in ejecutar_comando("no leidos", h)
    assert "Envíame" in ejecutar_comando("leer 1", h)
    assert "ayuda" in ejecutar_comando("xyz", h)


class FakeMessages:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []
    def create(self, **kw):
        self.llamadas.append(kw)
        return self.respuestas.pop(0)


def test_cerebro_bucle_herramientas(tmp_path):
    uso = NS(type="tool_use", id="t1", name="buscar_correos", input={"no_leidos": True})
    r1 = NS(stop_reason="tool_use", content=[uso])
    r2 = NS(stop_reason="end_turn", content=[NS(type="text", text="Tienes 1 correo urgente del jefe.")])
    msgs = FakeMessages([r1, r2])
    cliente = NS(beta=NS(messages=msgs))
    cer = Cerebro(Config(carpeta_salida=tmp_path), _h(tmp_path), cliente=cliente)
    assert "urgente" in cer.preguntar("revisa mi correo")
    resultado = cer.historial[2]["content"][0]
    assert resultado["tool_use_id"] == "t1" and "Informe" in resultado["content"]
    assert msgs.llamadas[0]["model"] == "claude-opus-5-5"
    assert len(cer.historial) == 4


def test_cerebro_rechazo(tmp_path):
    cliente = NS(beta=NS(messages=FakeMessages([NS(stop_reason="refusal", content=[])])))
    cer = Cerebro(Config(carpeta_datos=tmp_path), _h(tmp_path), cliente=cliente)
    assert "no puedo" in cer.preguntar("algo")
