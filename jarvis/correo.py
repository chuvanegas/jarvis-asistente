"""Leer y enviar correo por IMAP/SMTP (Gmail, Outlook, Yahoo o servidor propio)."""
from __future__ import annotations

import email
import html
import imaplib
import mimetypes
import re
import smtplib
import ssl
from dataclasses import dataclass, asdict
from datetime import date
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.utils import formataddr, parseaddr, parsedate_to_datetime
from pathlib import Path

from .config import ConfigCorreo

MESES_IMAP = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ErrorCorreo(Exception):
    pass


@dataclass
class Correo:
    uid: str
    de: str
    para: str
    asunto: str
    fecha: str
    cuerpo: str
    adjuntos: list[str]
    leido: bool = True

    def resumen(self, max_cuerpo: int = 300) -> dict:
        d = asdict(self)
        if len(self.cuerpo) > max_cuerpo:
            d["cuerpo"] = self.cuerpo[:max_cuerpo] + "…"
        return d


def _decodificar(valor: str | None) -> str:
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor)))
    except Exception:
        return valor


def _html_a_texto(contenido: str) -> str:
    contenido = re.sub(r"(?is)<(script|style).*?</\1>", " ", contenido)
    contenido = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", contenido)
    contenido = re.sub(r"<[^>]+>", " ", contenido)
    contenido = html.unescape(contenido)
    contenido = re.sub(r"[ \t]+", " ", contenido)
    return re.sub(r"\n\s*\n+", "\n\n", contenido).strip()


def extraer_cuerpo(msg: Message) -> tuple[str, list[str]]:
    """Devuelve (texto del cuerpo, nombres de adjuntos)."""
    texto, html_txt, adjuntos = "", "", []
    partes = msg.walk() if msg.is_multipart() else [msg]
    for parte in partes:
        if parte.is_multipart():
            continue
        disp = (parte.get("Content-Disposition") or "").lower()
        nombre = parte.get_filename()
        if nombre or "attachment" in disp:
            adjuntos.append(_decodificar(nombre) or "adjunto")
            continue
        tipo = parte.get_content_type()
        carga = parte.get_payload(decode=True) or b""
        charset = parte.get_content_charset() or "utf-8"
        try:
            contenido = carga.decode(charset, errors="replace")
        except LookupError:
            contenido = carga.decode("utf-8", errors="replace")
        if tipo == "text/plain" and not texto:
            texto = contenido
        elif tipo == "text/html" and not html_txt:
            html_txt = contenido
    if not texto and html_txt:
        texto = _html_a_texto(html_txt)
    return texto.strip(), adjuntos


def construir_busqueda(
    no_leidos: bool = False,
    remitente: str | None = None,
    asunto: str | None = None,
    texto: str | None = None,
    desde: str | None = None,
) -> list[str]:
    """Construye los criterios IMAP SEARCH. `desde` en formato AAAA-MM-DD."""
    criterios: list[str] = []
    if no_leidos:
        criterios.append("UNSEEN")
    for clave, valor in (("FROM", remitente), ("SUBJECT", asunto), ("TEXT", texto)):
        if valor:
            limpio = valor.replace("\\", "").replace('"', "")
            criterios += [clave, f'"{limpio}"']
    if desde:
        d = date.fromisoformat(desde)
        criterios += ["SINCE", f"{d.day:02d}-{MESES_IMAP[d.month - 1]}-{d.year}"]
    return criterios or ["ALL"]


class ClienteCorreo:
    def __init__(self, config: ConfigCorreo):
        self.config = config

    def _verificar(self) -> None:
        if not self.config.configurado:
            raise ErrorCorreo(
                "El correo no está configurado. Define CORREO_USUARIO, CORREO_CLAVE y "
                "CORREO_PROVEEDOR en el archivo .env"
            )

    def _imap(self) -> imaplib.IMAP4_SSL:
        self._verificar()
        conn = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_puerto,
                                 ssl_context=ssl.create_default_context())
        try:
            conn.login(self.config.usuario, self.config.clave)
        except imaplib.IMAP4.error as e:
            raise ErrorCorreo(f"No pude iniciar sesión en el correo: {e}") from e
        return conn

    # ------------------------------------------------------------------ lectura
    def buscar(
        self,
        carpeta: str = "INBOX",
        limite: int = 10,
        no_leidos: bool = False,
        remitente: str | None = None,
        asunto: str | None = None,
        texto: str | None = None,
        desde: str | None = None,
    ) -> list[Correo]:
        criterios = construir_busqueda(no_leidos, remitente, asunto, texto, desde)
        conn = self._imap()
        try:
            conn.select(f'"{carpeta}"', readonly=True)
            estado, datos = conn.uid("SEARCH", None, *criterios)
            if estado != "OK":
                raise ErrorCorreo(f"Búsqueda fallida: {datos}")
            uids = (datos[0] or b"").split()
            uids = list(reversed(uids))[: max(1, min(limite, 50))]
            return [c for c in (self._descargar(conn, u.decode()) for u in uids) if c]
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def leer(self, uid: str, carpeta: str = "INBOX", marcar_leido: bool = False) -> Correo:
        conn = self._imap()
        try:
            conn.select(f'"{carpeta}"', readonly=not marcar_leido)
            correo = self._descargar(conn, uid, marcar_leido)
            if not correo:
                raise ErrorCorreo(f"No encontré el correo con id {uid}")
            return correo
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def _descargar(self, conn, uid: str, marcar_leido: bool = False) -> Correo | None:
        consulta = "(RFC822 FLAGS)" if marcar_leido else "(BODY.PEEK[] FLAGS)"
        estado, datos = conn.uid("FETCH", uid, consulta)
        if estado != "OK" or not datos or datos[0] is None:
            return None
        crudo, banderas = b"", b""
        for item in datos:
            if isinstance(item, tuple):
                banderas += item[0]
                crudo = item[1]
            elif isinstance(item, bytes):
                banderas += item
        return parsear_correo(uid, crudo, leido=b"\\Seen" in banderas)

    # ------------------------------------------------------------------ envío
    def construir_mensaje(
        self,
        para: list[str] | str,
        asunto: str,
        cuerpo: str,
        cc: list[str] | None = None,
        adjuntos: list[str] | None = None,
        html_cuerpo: str | None = None,
        responder_a_id: str | None = None,
    ) -> EmailMessage:
        destinatarios = [para] if isinstance(para, str) else list(para)
        for d in destinatarios + (cc or []):
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", parseaddr(d)[1] or ""):
                raise ErrorCorreo(f"Dirección de correo inválida: {d}")
        msg = EmailMessage()
        msg["From"] = formataddr((self.config.nombre, self.config.usuario)) if self.config.nombre else self.config.usuario
        msg["To"] = ", ".join(destinatarios)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = asunto
        if responder_a_id:
            msg["In-Reply-To"] = responder_a_id
            msg["References"] = responder_a_id
        msg.set_content(cuerpo)
        if html_cuerpo:
            msg.add_alternative(html_cuerpo, subtype="html")
        for ruta in adjuntos or []:
            p = Path(ruta)
            if not p.is_file():
                raise ErrorCorreo(f"No existe el adjunto: {ruta}")
            tipo, _ = mimetypes.guess_type(p.name)
            principal, sub = (tipo or "application/octet-stream").split("/", 1)
            msg.add_attachment(p.read_bytes(), maintype=principal, subtype=sub, filename=p.name)
        return msg

    def enviar(self, msg: EmailMessage) -> str:
        self._verificar()
        contexto = ssl.create_default_context()
        try:
            if self.config.smtp_puerto == 465:
                with smtplib.SMTP_SSL(self.config.smtp_host, 465, context=contexto) as s:
                    s.login(self.config.usuario, self.config.clave)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_puerto) as s:
                    s.starttls(context=contexto)
                    s.login(self.config.usuario, self.config.clave)
                    s.send_message(msg)
        except smtplib.SMTPException as e:
            raise ErrorCorreo(f"No pude enviar el correo: {e}") from e
        return f"Correo enviado a {msg['To']}"


def parsear_correo(uid: str, crudo: bytes, leido: bool = True) -> Correo:
    msg = email.message_from_bytes(crudo)
    cuerpo, adjuntos = extraer_cuerpo(msg)
    fecha = msg.get("Date", "")
    try:
        fecha = parsedate_to_datetime(fecha).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return Correo(
        uid=uid,
        de=_decodificar(msg.get("From")),
        para=_decodificar(msg.get("To")),
        asunto=_decodificar(msg.get("Subject")) or "(sin asunto)",
        fecha=fecha,
        cuerpo=cuerpo,
        adjuntos=adjuntos,
        leido=leido,
    )
