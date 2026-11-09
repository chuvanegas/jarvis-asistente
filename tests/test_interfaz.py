import json
import time
import urllib.request
from types import SimpleNamespace as NS

from jarvis.config import Config
from jarvis.interfaz import Asistente, iniciar_servidor


class CerebroFalso:
    def __init__(self, asistente):
        self.asistente = asistente
    def preguntar(self, texto):
        if "envía" in texto:
            ok = self.asistente.herramientas.confirmar("¿Envío?")
            return "enviado" if ok else "cancelado"
        return f"eco: {texto}"
    def reiniciar(self):
        pass


def _req(url, ruta, token, datos=None):
    r = urllib.request.Request(url.split("/?")[0] + ruta, headers={"X-Jarvis-Token": token})
    if datos is not None:
        r.data = json.dumps(datos).encode()
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=5) as resp:
        return json.loads(resp.read())


def _esperar(cond, t=5):
    fin = time.time() + t
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_servidor_chat_y_confirmacion(tmp_path):
    a = Asistente(Config(carpeta_datos=tmp_path, carpeta_salida=tmp_path), cerebro_factory=CerebroFalso,
                  hablante=NS(hablar=lambda t: None, callar=lambda: None, hablando=False))
    srv, url = iniciar_servidor(a)
    token = url.split("t=")[1]
    try:
        html = urllib.request.urlopen(url, timeout=5).read().decode()
        assert token in html and "__TOKEN__" not in html
        try:
            urllib.request.urlopen(url.split("/?")[0] + "/api/estado", timeout=5)
            assert False, "debió rechazar sin token"
        except urllib.error.HTTPError as e:
            assert e.code == 403
        _req(url, "/api/chat", token, {"texto": "hola"})
        assert _esperar(lambda: any(m["texto"] == "eco: hola" for m in a.mensajes))
        _req(url, "/api/chat", token, {"texto": "envía el reporte"})
        assert _esperar(lambda: _req(url, "/api/estado", token)["confirmacion"])
        conf = _req(url, "/api/estado", token)["confirmacion"]
        assert _req(url, "/api/confirmar", token, {"id": conf["id"], "si": True})["ok"]
        assert _esperar(lambda: any(m["texto"] == "enviado" for m in a.mensajes))
        msgs = _req(url, "/api/mensajes?desde=1", token)["mensajes"]
        assert [m["rol"] for m in msgs][:2] == ["usuario", "jarvis"]
    finally:
        srv.shutdown()
