from email.message import EmailMessage

import pytest

from jarvis.config import ConfigCorreo
from jarvis.correo import ClienteCorreo, ErrorCorreo, construir_busqueda, parsear_correo

CFG = ConfigCorreo("yo@x.com", "clave", "Yo", "imap.x.com", 993, "smtp.x.com", 587)


def test_busqueda():
    assert construir_busqueda() == ["ALL"]
    c = construir_busqueda(no_leidos=True, remitente='jefe"', desde="2026-03-07")
    assert c == ["UNSEEN", "FROM", '"jefe"', "SINCE", "07-Mar-2026"]


def test_parsear_multipart_html():
    m = EmailMessage()
    m["From"] = "=?utf-8?q?Jos=C3=A9?= <jose@x.com>"
    m["Subject"] = "Reunión"
    m["Date"] = "Mon, 09 Nov 2026 10:00:00 -0500"
    m.set_content("<p>Hola<br>mundo</p>", subtype="html")
    m.add_attachment(b"abc", maintype="application", subtype="pdf", filename="f.pdf")
    c = parsear_correo("7", m.as_bytes(), leido=False)
    assert c.de.startswith("José") and c.asunto == "Reunión"
    assert "Hola" in c.cuerpo and "<p>" not in c.cuerpo
    assert c.adjuntos == ["f.pdf"] and c.fecha == "2026-11-09 10:00"


def test_construir_mensaje(tmp_path):
    adj = tmp_path / "r.xlsx"
    adj.write_bytes(b"PK")
    msg = ClienteCorreo(CFG).construir_mensaje(["a@b.com"], "Hola", "Texto", cc=["c@d.com"], adjuntos=[str(adj)])
    assert msg["To"] == "a@b.com" and msg["Cc"] == "c@d.com"
    assert [p.get_filename() for p in msg.iter_attachments()] == ["r.xlsx"]
    with pytest.raises(ErrorCorreo):
        ClienteCorreo(CFG).construir_mensaje(["no-es-correo"], "a", "b")
    with pytest.raises(ErrorCorreo):
        ClienteCorreo(CFG).construir_mensaje(["a@b.com"], "a", "b", adjuntos=["/no/existe"])


def test_enviar_usa_starttls(monkeypatch):
    llamadas = []

    class FakeSMTP:
        def __init__(self, host, port):
            llamadas.append(("init", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self, context=None): llamadas.append("tls")
        def login(self, u, p): llamadas.append(("login", u))
        def send_message(self, m): llamadas.append("send")

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    cli = ClienteCorreo(CFG)
    r = cli.enviar(cli.construir_mensaje("a@b.com", "x", "y"))
    assert "a@b.com" in r and llamadas == [("init", "smtp.x.com", 587), "tls", ("login", "yo@x.com"), "send"]


def test_sin_configurar():
    with pytest.raises(ErrorCorreo):
        ClienteCorreo(ConfigCorreo()).buscar()
