"""Herramientas que JARVIS (Claude) puede usar: correo, Excel y utilidades."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import excel
from .config import Config
from .correo import ClienteCorreo, ErrorCorreo

# callback(resumen_texto) -> bool : pide confirmación al usuario antes de acciones sensibles
Confirmador = Callable[[str], bool]


def _obj(props: dict, requeridos: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": requeridos, "additionalProperties": False}


DEFINICIONES: list[dict] = [
    {
        "name": "buscar_correos",
        "description": "Busca correos en el buzón del usuario y devuelve un resumen (id, remitente, asunto, "
        "fecha, inicio del cuerpo, adjuntos). Úsala para 'revisa mi correo', 'qué correos no he leído', etc.",
        "input_schema": _obj({
            "no_leidos": {"type": "boolean", "description": "Solo correos no leídos"},
            "remitente": {"type": "string", "description": "Filtra por remitente"},
            "asunto": {"type": "string", "description": "Filtra por texto en el asunto"},
            "texto": {"type": "string", "description": "Filtra por texto en cualquier parte"},
            "desde": {"type": "string", "description": "Fecha mínima AAAA-MM-DD"},
            "limite": {"type": "integer", "description": "Máximo de correos (1-50, por defecto 10)"},
            "carpeta": {"type": "string", "description": "Carpeta IMAP, por defecto INBOX"},
        }, []),
    },
    {
        "name": "leer_correo",
        "description": "Lee el contenido completo de un correo por su id (obtenido con buscar_correos).",
        "input_schema": _obj({
            "id": {"type": "string"},
            "carpeta": {"type": "string"},
        }, ["id"]),
    },
    {
        "name": "enviar_correo",
        "description": "Envía un correo desde la cuenta del usuario. El usuario SIEMPRE confirma antes del envío. "
        "Puede adjuntar archivos (por ejemplo un Excel que acabas de crear).",
        "input_schema": _obj({
            "para": {"type": "array", "items": {"type": "string"}, "description": "Destinatarios"},
            "asunto": {"type": "string"},
            "cuerpo": {"type": "string", "description": "Texto del correo"},
            "cc": {"type": "array", "items": {"type": "string"}},
            "adjuntos": {"type": "array", "items": {"type": "string"}, "description": "Rutas de archivos"},
        }, ["para", "asunto", "cuerpo"]),
    },
    {
        "name": "crear_excel",
        "description": "Crea un archivo .xlsx con encabezados, filas y (opcional) fila de totales con fórmulas. "
        "Las rutas relativas se guardan en la carpeta de salida de JARVIS. Fechas en formato AAAA-MM-DD.",
        "input_schema": _obj({
            "archivo": {"type": "string", "description": "Nombre o ruta del archivo .xlsx"},
            "encabezados": {"type": "array", "items": {"type": "string"}},
            "filas": {"type": "array", "items": {"type": "array", "items": {}}},
            "nombre_hoja": {"type": "string"},
            "totales": {"type": "array", "items": {"type": "string"}, "description": "Columnas a sumar"},
        }, ["archivo", "encabezados", "filas"]),
    },
    {
        "name": "leer_excel",
        "description": "Lee un archivo Excel y devuelve hojas, encabezados y filas (hasta max_filas).",
        "input_schema": _obj({
            "archivo": {"type": "string"},
            "hoja": {"type": "string"},
            "max_filas": {"type": "integer"},
        }, ["archivo"]),
    },
    {
        "name": "validar_excel",
        "description": "Valida un Excel: columnas requeridas, vacíos, tipos (numero, entero, fecha, texto, email), "
        "rangos min/max, valores permitidos, únicos, patrones regex y fórmula de total (p.ej. Total = Cantidad * "
        "Precio). Siempre detecta errores de fórmula (#DIV/0!, #REF!...) y filas duplicadas. Puede generar una copia "
        "con las celdas marcadas y una hoja 'Validación'. Si el usuario no da reglas, infiérelas leyendo primero el "
        "archivo con leer_excel y explícale qué reglas usaste.",
        "input_schema": _obj({
            "archivo": {"type": "string"},
            "reglas": {
                "type": "object",
                "description": "Reglas: hoja, fila_encabezado, columnas_requeridas, no_vacios, tipos, rangos, "
                "valores_permitidos, unicos, patrones, formula_total{columna, igual_a, tolerancia}",
            },
            "archivo_reglas": {"type": "string", "description": "Ruta de un JSON con reglas (alternativa)"},
            "generar_reporte": {"type": "boolean", "description": "Crear copia marcada *_validado.xlsx"},
        }, ["archivo"]),
    },
    {
        "name": "listar_archivos",
        "description": "Lista archivos de una carpeta (por defecto la carpeta actual), opcionalmente por extensión.",
        "input_schema": _obj({
            "carpeta": {"type": "string"},
            "extension": {"type": "string", "description": "Ej: .xlsx"},
        }, []),
    },
    {
        "name": "fecha_hora",
        "description": "Devuelve la fecha y hora actual del equipo.",
        "input_schema": _obj({}, []),
    },
]


class Herramientas:
    def __init__(self, config: Config, confirmar: Confirmador, cliente_correo: ClienteCorreo | None = None):
        self.config = config
        self.confirmar = confirmar
        self.correo = cliente_correo or ClienteCorreo(config.correo)

    def _ruta_salida(self, archivo: str) -> Path:
        p = Path(archivo).expanduser()
        return p if p.is_absolute() or p.parent != Path(".") else self.config.carpeta_salida / p

    def _ruta_entrada(self, archivo: str) -> Path:
        p = Path(archivo).expanduser()
        if not p.exists() and not p.is_absolute() and (self.config.carpeta_salida / p).exists():
            return self.config.carpeta_salida / p
        return p

    def ejecutar(self, nombre: str, datos: dict[str, Any]) -> tuple[str, bool]:
        """Devuelve (resultado_texto, es_error)."""
        metodo = getattr(self, f"h_{nombre}", None)
        if metodo is None:
            return f"Herramienta desconocida: {nombre}", True
        try:
            res = metodo(**datos)
            return (res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, default=str)), False
        except (ErrorCorreo, excel.ErrorExcel, ValueError, TypeError, OSError) as e:
            return f"Error: {e}", True

    # ----------------------------------------------------------- correo
    def h_buscar_correos(self, limite: int = 10, carpeta: str = "INBOX", **filtros) -> dict:
        correos = self.correo.buscar(carpeta=carpeta, limite=limite, **filtros)
        return {"cantidad": len(correos), "correos": [c.resumen() for c in correos]}

    def h_leer_correo(self, id: str, carpeta: str = "INBOX") -> dict:
        c = self.correo.leer(id, carpeta=carpeta)
        d = c.resumen(max_cuerpo=20000)
        return d

    def h_enviar_correo(self, para: list[str], asunto: str, cuerpo: str,
                        cc: list[str] | None = None, adjuntos: list[str] | None = None) -> str:
        adjuntos = [str(self._ruta_entrada(a)) for a in (adjuntos or [])]
        msg = self.correo.construir_mensaje(para, asunto, cuerpo, cc=cc, adjuntos=adjuntos)
        vista = (
            f"Para: {msg['To']}\n" + (f"CC: {msg['Cc']}\n" if cc else "") +
            f"Asunto: {asunto}\n" + (f"Adjuntos: {', '.join(Path(a).name for a in adjuntos)}\n" if adjuntos else "") +
            f"---\n{cuerpo}\n---"
        )
        if not self.confirmar(f"¿Envío este correo?\n{vista}"):
            return "El usuario canceló el envío. No se envió nada."
        return self.correo.enviar(msg)

    # ----------------------------------------------------------- excel
    def h_crear_excel(self, archivo: str, encabezados: list[str], filas: list[list[Any]],
                      nombre_hoja: str = "Datos", totales: list[str] | None = None) -> str:
        ruta = excel.crear_hoja(self._ruta_salida(archivo), encabezados, filas, nombre_hoja, totales)
        return f"Excel creado: {ruta.resolve()} ({len(filas)} filas)"

    def h_leer_excel(self, archivo: str, hoja: str | None = None, max_filas: int = 100) -> dict:
        return excel.leer_hoja(self._ruta_entrada(archivo), hoja=hoja, max_filas=min(max_filas, 500))

    def h_validar_excel(self, archivo: str, reglas: dict | None = None, archivo_reglas: str | None = None,
                        generar_reporte: bool = True) -> dict:
        ruta = self._ruta_entrada(archivo)
        res = excel.validar_hoja(ruta, reglas if reglas else archivo_reglas)
        salida = {k: v for k, v in res.items() if not k.startswith("_")}
        salida["problemas"] = res["problemas"][:100]
        if len(res["problemas"]) > 100:
            salida["nota"] = f"Se muestran 100 de {len(res['problemas'])} problemas"
        if generar_reporte:
            destino = self.config.carpeta_salida / f"{ruta.stem}_validado.xlsx"
            salida["reporte"] = str(excel.generar_reporte(ruta, res, destino).resolve())
        return salida

    # ----------------------------------------------------------- utilidades
    def h_listar_archivos(self, carpeta: str = ".", extension: str | None = None) -> dict:
        p = Path(carpeta).expanduser()
        if not p.is_dir():
            raise ValueError(f"No existe la carpeta {carpeta}")
        archivos = sorted(
            f.name for f in p.iterdir()
            if f.is_file() and (not extension or f.suffix.lower() == extension.lower())
        )
        return {"carpeta": str(p.resolve()), "archivos": archivos[:200]}

    def h_fecha_hora(self) -> str:
        return datetime.now().strftime("%A %d de %B de %Y, %H:%M")
