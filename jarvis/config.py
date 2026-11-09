"""Configuración de JARVIS leída desde variables de entorno / archivo .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv es opcional
    pass

PROVEEDORES = {
    "gmail": ("imap.gmail.com", 993, "smtp.gmail.com", 587),
    "outlook": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "hotmail": ("outlook.office365.com", 993, "smtp.office365.com", 587),
    "yahoo": ("imap.mail.yahoo.com", 993, "smtp.mail.yahoo.com", 587),
}


@dataclass
class ConfigCorreo:
    usuario: str = ""
    clave: str = ""
    nombre: str = ""
    imap_host: str = ""
    imap_puerto: int = 993
    smtp_host: str = ""
    smtp_puerto: int = 587

    @property
    def configurado(self) -> bool:
        return bool(self.usuario and self.clave and self.imap_host and self.smtp_host)


@dataclass
class Config:
    api_key: str = ""
    modelo: str = "claude-opus-5-5"
    carpeta_salida: Path = Path("salidas")
    correo: ConfigCorreo = field(default_factory=ConfigCorreo)

    @classmethod
    def desde_entorno(cls) -> "Config":
        proveedor = os.getenv("CORREO_PROVEEDOR", "gmail").lower()
        imap_h, imap_p, smtp_h, smtp_p = PROVEEDORES.get(
            proveedor,
            (
                os.getenv("IMAP_HOST", ""),
                int(os.getenv("IMAP_PUERTO", "993")),
                os.getenv("SMTP_HOST", ""),
                int(os.getenv("SMTP_PUERTO", "587")),
            ),
        )
        correo = ConfigCorreo(
            usuario=os.getenv("CORREO_USUARIO", ""),
            clave=os.getenv("CORREO_CLAVE", ""),
            nombre=os.getenv("CORREO_NOMBRE", ""),
            imap_host=imap_h,
            imap_puerto=imap_p,
            smtp_host=smtp_h,
            smtp_puerto=smtp_p,
        )
        carpeta = Path(os.getenv("JARVIS_CARPETA_SALIDA", "salidas"))
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            modelo=os.getenv("JARVIS_MODELO", "claude-opus-5-5"),
            carpeta_salida=carpeta,
            correo=correo,
        )
