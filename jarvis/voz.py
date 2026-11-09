"""Voz de JARVIS: escuchar (micrófono -> texto) y hablar (texto -> voz).

Escuchar:  graba con `sounddevice` y se detiene sola cuando dejas de hablar.
           Transcribe con Whisper local (`faster-whisper`, sin internet) o, si no está
           instalado, con el reconocedor de Google (`SpeechRecognition`, necesita internet).
Hablar:    en macOS usa el comando `say` con una voz en español (Paulina, Mónica, Jorge…);
           en otros sistemas usa `pyttsx3`.
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import threading
import wave

PALABRA_CLAVE = "jarvis"
FRECUENCIA = 16000


# ======================================================================== hablar
def limpiar_para_voz(texto: str, max_caracteres: int = 1200) -> str:
    t = re.sub(r"```.*?```", " (te dejé el detalle en pantalla) ", texto, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)          # enlaces markdown
    t = re.sub(r"^\s*\|.*\|\s*$", "", t, flags=re.M)          # tablas
    t = re.sub(r"[*#`_>|]", "", t)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
    t = re.sub(r"\n{2,}", ". ", t).replace("\n", ", ")
    t = re.sub(r"\s{2,}", " ", t).strip()
    if len(t) > max_caracteres:
        corte = t.rfind(".", 0, max_caracteres)
        t = t[: corte + 1 if corte > 200 else max_caracteres] + " El resto está en pantalla."
    return t


class Hablante:
    def __init__(self, voz_mac: str = "Paulina", velocidad: int = 190):
        self.voz_mac = voz_mac
        self.velocidad = velocidad
        self._proceso: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._motor = None
        self.usa_say = sys.platform == "darwin" and shutil.which("say") is not None
        if self.usa_say and not self._voz_disponible(voz_mac):
            self.voz_mac = self._primera_voz_es() or ""

    @staticmethod
    def _listar_voces() -> str:
        try:
            return subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return ""

    def _voz_disponible(self, nombre: str) -> bool:
        return any(l.split()[0:1] == [nombre] for l in self._listar_voces().splitlines())

    def _primera_voz_es(self) -> str | None:
        for linea in self._listar_voces().splitlines():
            if re.search(r"\bes[_-]", linea):
                return linea.split()[0]
        return None

    def comando(self, texto: str) -> list[str]:
        cmd = ["say", "-r", str(self.velocidad)]
        if self.voz_mac:
            cmd += ["-v", self.voz_mac]
        return cmd + [texto]

    def hablar(self, texto: str, esperar: bool = True) -> None:
        limpio = limpiar_para_voz(texto)
        if not limpio:
            return
        self.callar()
        if self.usa_say:
            with self._lock:
                self._proceso = subprocess.Popen(self.comando(limpio))
            if esperar:
                self._proceso.wait()
            return
        if self._motor is None:
            try:
                import pyttsx3
            except ImportError as e:
                raise RuntimeError("Para hablar fuera de macOS instala: pip install pyttsx3") from e
            self._motor = pyttsx3.init()
            for v in self._motor.getProperty("voices"):
                if "es" in (str(getattr(v, "languages", "")) + v.id + v.name).lower():
                    self._motor.setProperty("voice", v.id)
                    break
        self._motor.say(limpio)
        self._motor.runAndWait()

    def callar(self) -> None:
        with self._lock:
            if self._proceso and self._proceso.poll() is None:
                self._proceso.terminate()
            self._proceso = None

    @property
    def hablando(self) -> bool:
        return bool(self._proceso and self._proceso.poll() is None)


# ======================================================================== escuchar
def recortar_por_silencio(niveles: list[float], umbral: float, bloques_silencio: int) -> int | None:
    """Dado el nivel (RMS) de cada bloque, devuelve el índice donde terminar: tras haber
    oído voz, `bloques_silencio` bloques seguidos por debajo del umbral. None si aún no termina."""
    hablo, silencio = False, 0
    for i, n in enumerate(niveles):
        if n >= umbral:
            hablo, silencio = True, 0
        elif hablo:
            silencio += 1
            if silencio >= bloques_silencio:
                return i + 1
    return None


def a_wav(muestras_int16: bytes, frecuencia: int = FRECUENCIA) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(frecuencia)
        w.writeframes(muestras_int16)
    return buf.getvalue()


class Oido:
    def __init__(self, modelo_whisper: str = "small", idioma: str = "es"):
        self.modelo_whisper = modelo_whisper
        self.idioma = idioma
        self._whisper = None
        self._detener = threading.Event()

    def grabar(self, max_segundos: float = 20, silencio_seg: float = 1.2, espera_voz_seg: float = 8,
               umbral: float | None = None) -> bytes | None:
        """Graba hasta que dejas de hablar. Devuelve PCM int16 mono 16 kHz, o None si no hablaste."""
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as e:
            raise RuntimeError("Para escuchar instala: pip install sounddevice numpy") from e
        self._detener.clear()
        bloque = int(FRECUENCIA * 0.1)
        bloques, niveles = [], []
        with sd.InputStream(samplerate=FRECUENCIA, channels=1, dtype="int16", blocksize=bloque) as s:
            # calibrar ruido de fondo 0.4 s
            ruido = []
            for _ in range(4):
                datos, _ = s.read(bloque)
                ruido.append(float(np.sqrt(np.mean(datos.astype(np.float32) ** 2))))
            u = umbral or max(400.0, (sum(ruido) / len(ruido)) * 2.5)
            for i in range(int(max_segundos * 10)):
                if self._detener.is_set():
                    break
                datos, _ = s.read(bloque)
                bloques.append(datos.copy())
                niveles.append(float(np.sqrt(np.mean(datos.astype(np.float32) ** 2))))
                if not any(n >= u for n in niveles) and i >= espera_voz_seg * 10:
                    return None
                fin = recortar_por_silencio(niveles, u, int(silencio_seg * 10))
                if fin:
                    break
        if not bloques or not any(n >= u for n in niveles):
            return None
        return np.concatenate(bloques).tobytes()

    def detener(self) -> None:
        self._detener.set()

    def transcribir(self, pcm: bytes) -> str:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return self._transcribir_google(pcm)
        import numpy as np

        if self._whisper is None:
            self._whisper = WhisperModel(self.modelo_whisper, device="auto", compute_type="int8")
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segmentos, _ = self._whisper.transcribe(audio, language=self.idioma, vad_filter=True, beam_size=1)
        return " ".join(s.text.strip() for s in segmentos).strip()

    def _transcribir_google(self, pcm: bytes) -> str:
        try:
            import speech_recognition as sr
        except ImportError as e:
            raise RuntimeError("Instala faster-whisper (recomendado) o SpeechRecognition para entender la voz") from e
        r = sr.Recognizer()
        try:
            return r.recognize_google(sr.AudioData(pcm, FRECUENCIA, 2), language=f"{self.idioma}-ES")
        except sr.UnknownValueError:
            return ""

    def escuchar(self, **kw) -> str | None:
        pcm = self.grabar(**kw)
        if not pcm:
            return None
        return self.transcribir(pcm) or None


def quitar_palabra_clave(texto: str) -> str | None:
    """Si el texto empieza con 'Jarvis' (o 'oye Jarvis'), devuelve la orden; si no, None."""
    t = texto.strip()
    m = re.match(r"^\s*(?:oye|hey|ok|hola)?[\s,]*j[ae]rv[ie]s\b[\s,.:!¡]*", t, flags=re.I)
    if m:
        return t[m.end():].strip()
    return None


class Voz:
    """Compatibilidad con el modo --voz de la terminal."""

    def __init__(self, voz_mac: str = "Paulina", modelo_whisper: str = "small"):
        self.oido = Oido(modelo_whisper)
        self.hablante = Hablante(voz_mac)

    def hablar(self, texto: str) -> None:
        self.hablante.hablar(texto)

    def escuchar(self) -> str | None:
        return self.oido.escuchar()
