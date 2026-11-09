"""Interfaz gráfica de JARVIS: servidor local + ventana nativa (pywebview) o navegador.

El servidor solo escucha en 127.0.0.1 y exige un token aleatorio por sesión en cada llamada,
así ninguna página web externa puede darle órdenes a JARVIS.
"""
from __future__ import annotations

import json
import queue
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .comandos import ejecutar_comando
from .config import Config
from .herramientas import Herramientas

WEB = Path(__file__).with_name("web")

NOMBRES_HERRAMIENTAS = {
    "buscar_correos": "Revisando tu correo",
    "leer_correo": "Leyendo el correo",
    "enviar_correo": "Preparando el envío",
    "crear_excel": "Creando el Excel",
    "leer_excel": "Leyendo el Excel",
    "validar_excel": "Validando la hoja",
    "ver_pantalla": "Mirando tu pantalla",
    "recordar": "Guardando en memoria",
    "consultar_memoria": "Consultando mi memoria",
    "aprender_de_mis_archivos": "Aprendiendo de tus archivos",
    "buscar_en_mis_archivos": "Buscando en tus archivos",
    "archivos_recientes": "Revisando en qué trabajas",
    "aprender_reglas": "Aprendiendo reglas de tu hoja",
}


class Asistente:
    """Estado compartido entre la interfaz, la voz y el cerebro."""

    def __init__(self, config: Config, cerebro_factory=None, hablante=None, oido=None):
        self.config = config
        self.lock = threading.RLock()
        self.mensajes: list[dict] = []
        self.actividad = ""
        self.ocupado = False
        self.escuchando = False
        self.voz_activa = True
        self.manos_libres = False
        self.confirmacion: dict | None = None
        self._respuesta_confirmacion: bool | None = None
        self._evento_confirmacion = threading.Event()
        self.cola: queue.Queue[tuple[str, bool]] = queue.Queue()
        self.herramientas = Herramientas(config, self._confirmar)
        if cerebro_factory:
            self.cerebro = cerebro_factory(self)
        elif config.api_key:
            from .cerebro import Cerebro

            self.cerebro = Cerebro(config, self.herramientas, al_usar_herramienta=self._al_usar)
        else:
            self.cerebro = None
        self._hablante = hablante
        self._oido = oido
        threading.Thread(target=self._trabajador, daemon=True).start()
        self.agregar("jarvis", self._saludo())

    # ------------------------------------------------------------ voz (perezosa)
    @property
    def hablante(self):
        if self._hablante is None:
            from .voz import Hablante

            self._hablante = Hablante(self.config.voz_mac)
        return self._hablante

    @property
    def oido(self):
        if self._oido is None:
            from .voz import Oido

            self._oido = Oido(self.config.whisper_modelo)
        return self._oido

    def _saludo(self) -> str:
        hora = datetime.now().hour
        saludo = "Buenos días" if hora < 12 else "Buenas tardes" if hora < 19 else "Buenas noches"
        avisos = []
        if not self.cerebro:
            avisos.append("falta **ANTHROPIC_API_KEY** en `.env` (modo comandos básico)")
        if not self.config.correo.configurado:
            avisos.append("el **correo** no está configurado en `.env`")
        texto = f"{saludo}. JARVIS en línea. ¿En qué le ayudo hoy?"
        if avisos:
            texto += "\n\nAntes de empezar: " + "; ".join(avisos) + "."
        return texto

    # ------------------------------------------------------------ mensajes
    def agregar(self, rol: str, texto: str) -> dict:
        with self.lock:
            m = {"id": len(self.mensajes) + 1, "rol": rol, "texto": texto, "hora": datetime.now().strftime("%H:%M")}
            self.mensajes.append(m)
            return m

    def ordenar(self, texto: str, por_voz: bool = False) -> None:
        texto = texto.strip()
        if not texto:
            return
        self.agregar("usuario", texto)
        self.cola.put((texto, por_voz))

    def _al_usar(self, nombre: str, _datos: dict) -> None:
        self.actividad = NOMBRES_HERRAMIENTAS.get(nombre, f"Usando {nombre}")

    def _trabajador(self) -> None:
        while True:
            texto, por_voz = self.cola.get()
            self.ocupado, self.actividad = True, "Pensando"
            try:
                if texto.lower() in ("reiniciar", "nueva conversación", "nueva conversacion"):
                    if self.cerebro:
                        self.cerebro.reiniciar()
                    respuesta = "Listo, empecemos de nuevo."
                elif self.cerebro:
                    respuesta = self.cerebro.preguntar(texto)
                else:
                    respuesta = ejecutar_comando(texto, self.herramientas, preguntar=lambda _p: "")
            except Exception as e:  # nunca tumbar la interfaz
                traceback.print_exc()
                respuesta = f"Tuve un problema: {e}"
            self.agregar("jarvis", respuesta)
            self.ocupado, self.actividad = False, ""
            if self.voz_activa:
                self.hablar(respuesta)

    # ------------------------------------------------------------ confirmaciones
    def _confirmar(self, texto: str) -> bool:
        with self.lock:
            self.confirmacion = {"id": secrets.token_hex(4), "texto": texto}
            self._evento_confirmacion.clear()
            self._respuesta_confirmacion = None
        self.actividad = "Esperando tu confirmación"
        if self.voz_activa:
            self.hablar("Necesito su confirmación en pantalla.")
        self._evento_confirmacion.wait(timeout=300)
        with self.lock:
            ok = bool(self._respuesta_confirmacion)
            self.confirmacion = None
        return ok

    def responder_confirmacion(self, conf_id: str, si: bool) -> bool:
        with self.lock:
            if not self.confirmacion or self.confirmacion["id"] != conf_id:
                return False
            self._respuesta_confirmacion = si
            self._evento_confirmacion.set()
            return True

    # ------------------------------------------------------------ voz
    def hablar(self, texto: str) -> None:
        def _run():
            try:
                self.hablante.hablar(texto)
            except Exception as e:
                print(f"[voz] {e}", file=sys.stderr)

        threading.Thread(target=_run, daemon=True).start()

    def escuchar_una_vez(self) -> str | None:
        if self.escuchando:
            return None
        try:
            if self._hablante is not None:
                self._hablante.callar()
            self.escuchando = True
            return self.oido.escuchar()
        finally:
            self.escuchando = False

    def detener(self) -> None:
        if self._oido is not None:
            self._oido.detener()
        if self._hablante is not None:
            self._hablante.callar()

    def activar_manos_libres(self, activo: bool) -> None:
        if activo and not self.manos_libres:
            self.manos_libres = True
            threading.Thread(target=self._bucle_manos_libres, daemon=True).start()
        elif not activo:
            self.manos_libres = False
            self.detener()

    def _bucle_manos_libres(self) -> None:
        from .voz import quitar_palabra_clave

        while self.manos_libres:
            if self.ocupado or (self._hablante is not None and self._hablante.hablando) or self.confirmacion:
                time.sleep(0.3)
                continue
            try:
                self.escuchando = True
                texto = self.oido.escuchar(espera_voz_seg=30)
            except Exception as e:
                self.agregar("sistema", f"No pude usar el micrófono: {e}")
                self.manos_libres = False
                break
            finally:
                self.escuchando = False
            if not texto or not self.manos_libres:
                continue
            orden = quitar_palabra_clave(texto)
            if orden is None:
                continue
            if not orden:
                self.hablar("Dígame.")
                continue
            self.ordenar(orden, por_voz=True)

    # ------------------------------------------------------------ estado
    def estado(self) -> dict:
        h = self._hablante
        return {
            "ocupado": self.ocupado, "actividad": self.actividad, "escuchando": self.escuchando,
            "hablando": bool(h and h.hablando), "voz_activa": self.voz_activa, "manos_libres": self.manos_libres,
            "confirmacion": self.confirmacion, "ia": self.cerebro is not None,
            "correo": self.config.correo.configurado, "cuenta": self.config.correo.usuario,
            "memoria": self.herramientas.memoria.estadisticas(), "total_mensajes": len(self.mensajes),
        }


def elegir_archivo() -> str | None:
    if sys.platform == "darwin" and shutil.which("osascript"):
        script = 'POSIX path of (choose file with prompt "Elige un archivo para JARVIS")'
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
        return r.stdout.strip() or None
    return None


def crear_manejador(asistente: Asistente, token: str):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _autorizado(self) -> bool:
            if secrets.compare_digest(self.headers.get("X-Jarvis-Token", ""), token):
                return True
            self._json({"error": "no autorizado"}, 403)
            return False

        def _leer(self) -> dict:
            largo = int(self.headers.get("Content-Length") or 0)
            if not largo:
                return {}
            try:
                return json.loads(self.rfile.read(min(largo, 1_000_000)))
            except json.JSONDecodeError:
                return {}

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                q = parse_qs(url.query)
                if not secrets.compare_digest(q.get("t", [""])[0], token):
                    self.send_error(403)
                    return
                html = (WEB / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                cuerpo = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:")
                self.end_headers()
                self.wfile.write(cuerpo)
                return
            if not self._autorizado():
                return
            if url.path == "/api/estado":
                self._json(asistente.estado())
            elif url.path == "/api/mensajes":
                desde = int(parse_qs(url.query).get("desde", ["0"])[0])
                with asistente.lock:
                    self._json({"mensajes": [m for m in asistente.mensajes if m["id"] > desde]})
            else:
                self.send_error(404)

        def do_POST(self):
            if not self._autorizado():
                return
            ruta, d = urlparse(self.path).path, self._leer()
            if ruta == "/api/chat":
                asistente.ordenar(str(d.get("texto", ""))[:20000])
                self._json({"ok": True})
            elif ruta == "/api/confirmar":
                self._json({"ok": asistente.responder_confirmacion(str(d.get("id")), bool(d.get("si")))})
            elif ruta == "/api/escuchar":
                try:
                    texto = asistente.escuchar_una_vez()
                except Exception as e:
                    self._json({"error": str(e)}, 500)
                    return
                if texto and d.get("enviar", True):
                    asistente.ordenar(texto, por_voz=True)
                self._json({"texto": texto or ""})
            elif ruta == "/api/detener":
                asistente.detener()
                self._json({"ok": True})
            elif ruta == "/api/ajustes":
                if "voz_activa" in d:
                    asistente.voz_activa = bool(d["voz_activa"])
                    if not asistente.voz_activa:
                        asistente.detener()
                if "manos_libres" in d:
                    asistente.activar_manos_libres(bool(d["manos_libres"]))
                self._json(asistente.estado())
            elif ruta == "/api/elegir_archivo":
                self._json({"ruta": elegir_archivo()})
            else:
                self.send_error(404)

    return Manejador


def iniciar_servidor(asistente: Asistente, puerto: int = 0) -> tuple[ThreadingHTTPServer, str]:
    token = secrets.token_urlsafe(24)
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), crear_manejador(asistente, token))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{servidor.server_address[1]}/?t={token}"
    return servidor, url


def abrir(config: Config, navegador: bool = False) -> int:
    asistente = Asistente(config)
    servidor, url = iniciar_servidor(asistente)
    try:
        if navegador:
            raise ImportError
        import webview  # pywebview

        webview.create_window("JARVIS", url, width=1180, height=800, min_size=(760, 560),
                              background_color="#0A0F1C")
        webview.start()
    except ImportError:
        import webbrowser

        print(f"JARVIS abierto en el navegador: {url}\n(Ctrl+C para cerrar)")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    finally:
        asistente.detener()
        servidor.shutdown()
    return 0
