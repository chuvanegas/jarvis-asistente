"""Entrada y salida por voz (opcional). Requiere: SpeechRecognition, pyaudio, pyttsx3."""
from __future__ import annotations

import re

PALABRA_CLAVE = "jarvis"


class Voz:
    def __init__(self, idioma: str = "es-ES"):
        try:
            import pyttsx3
            import speech_recognition as sr
        except ImportError as e:
            raise RuntimeError(
                "El modo voz necesita: pip install SpeechRecognition pyaudio pyttsx3"
            ) from e
        self.sr = sr
        self.idioma = idioma
        self.reconocedor = sr.Recognizer()
        self.motor = pyttsx3.init()
        for v in self.motor.getProperty("voices"):
            if "es" in (str(getattr(v, "languages", "")) + v.id + v.name).lower():
                self.motor.setProperty("voice", v.id)
                break
        self.motor.setProperty("rate", 175)

    def hablar(self, texto: str) -> None:
        limpio = re.sub(r"[*#`_|>]", "", texto)
        self.motor.say(limpio[:1500])
        self.motor.runAndWait()

    def escuchar(self, segundos: int = 8) -> str | None:
        with self.sr.Microphone() as fuente:
            self.reconocedor.adjust_for_ambient_noise(fuente, duration=0.5)
            try:
                audio = self.reconocedor.listen(fuente, timeout=segundos, phrase_time_limit=20)
            except self.sr.WaitTimeoutError:
                return None
        try:
            return self.reconocedor.recognize_google(audio, language=self.idioma)
        except (self.sr.UnknownValueError, self.sr.RequestError):
            return None


def quitar_palabra_clave(texto: str) -> str | None:
    """Devuelve la orden si el texto empieza con 'Jarvis', si no None."""
    t = texto.strip()
    if t.lower().startswith(PALABRA_CLAVE):
        return t[len(PALABRA_CLAVE):].lstrip(" ,.:") or ""
    return None
