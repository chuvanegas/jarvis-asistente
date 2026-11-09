"""Memoria local de JARVIS: notas, perfiles aprendidos de tus hojas e índice de tus archivos.

Todo se guarda en ~/.jarvis/memoria.json (nunca sale de tu Mac, salvo lo que JARVIS
incluya en una respuesta a Claude cuando lo necesita).
"""
from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from . import excel

EXTENSIONES = {".xlsx", ".xlsm"}
IGNORAR = {"node_modules", ".git", "Library", ".Trash", "__pycache__", ".venv", "venv"}


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _tokens(t: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", _normalizar(t)) if len(w) > 2}


class Memoria:
    def __init__(self, carpeta: Path):
        self.carpeta = Path(carpeta).expanduser()
        self.ruta = self.carpeta / "memoria.json"
        self._lock = threading.RLock()
        self.datos: dict[str, Any] = {"notas": [], "perfiles": {}, "archivos": {}}
        if self.ruta.is_file():
            try:
                self.datos.update(json.loads(self.ruta.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                respaldo = self.ruta.with_suffix(f".corrupto-{int(time.time())}.json")
                self.ruta.rename(respaldo)

    def guardar(self) -> None:
        with self._lock:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            tmp = self.ruta.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.datos, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            tmp.replace(self.ruta)

    # ------------------------------------------------------------- notas
    def recordar(self, texto: str, etiquetas: list[str] | None = None) -> dict:
        nota = {"id": max([n["id"] for n in self.datos["notas"]] or [0]) + 1, "texto": texto.strip(),
                "etiquetas": etiquetas or [], "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")}
        with self._lock:
            self.datos["notas"].append(nota)
            self.guardar()
        return nota

    def olvidar(self, nota_id: int) -> bool:
        with self._lock:
            antes = len(self.datos["notas"])
            self.datos["notas"] = [n for n in self.datos["notas"] if n["id"] != nota_id]
            self.guardar()
            return len(self.datos["notas"]) < antes

    def buscar_notas(self, consulta: str = "", limite: int = 20) -> list[dict]:
        notas = self.datos["notas"]
        if not consulta:
            return notas[-limite:]
        q = _tokens(consulta)
        puntuadas = [(len(q & _tokens(n["texto"] + " " + " ".join(n["etiquetas"]))), n) for n in notas]
        return [n for p, n in sorted(puntuadas, key=lambda x: -x[0]) if p > 0][:limite]

    # ------------------------------------------------------------- perfiles aprendidos
    def aprender_reglas(self, archivo: str | Path, nombre: str | None = None, hoja: str | None = None) -> dict:
        perfil = excel.perfilar_hoja(archivo, hoja=hoja)
        reglas = excel.inferir_reglas(perfil)
        nombre = nombre or Path(archivo).stem
        with self._lock:
            self.datos["perfiles"][nombre] = {
                "encabezados": perfil["encabezados"], "reglas": reglas, "origen": str(archivo),
                "filas_ejemplo": perfil["filas"], "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            self.guardar()
        return {"perfil": nombre, "reglas": reglas}

    def perfil_para(self, encabezados: list[str], umbral: float = 0.7) -> tuple[str, dict] | None:
        mejor, puntaje = None, 0.0
        for nombre, p in self.datos["perfiles"].items():
            s = excel.similitud_encabezados(encabezados, p["encabezados"])
            if s > puntaje:
                mejor, puntaje = nombre, s
        if mejor and puntaje >= umbral:
            return mejor, self.datos["perfiles"][mejor]["reglas"]
        return None

    def ajustar_perfil(self, nombre: str, cambios: dict) -> dict:
        with self._lock:
            if nombre not in self.datos["perfiles"]:
                raise ValueError(f"No existe el perfil '{nombre}'")
            reglas = self.datos["perfiles"][nombre]["reglas"]
            for clave, valor in cambios.items():
                if valor is None:
                    reglas.pop(clave, None)
                else:
                    reglas[clave] = valor
            self.guardar()
            return reglas

    # ------------------------------------------------------------- índice de archivos
    def indexar(self, carpetas: list[Path], max_archivos: int = 500, profundidad: int = 4) -> dict:
        nuevos, actualizados, errores, vistos = 0, 0, 0, 0
        indice = self.datos["archivos"]
        for base in carpetas:
            base = Path(base).expanduser()
            if not base.is_dir():
                continue
            for ruta in self._recorrer(base, profundidad):
                if vistos >= max_archivos:
                    break
                vistos += 1
                clave = str(ruta)
                try:
                    mtime = ruta.stat().st_mtime
                except OSError:
                    continue
                if clave in indice and indice[clave].get("mtime") == mtime:
                    continue
                try:
                    p = excel.perfilar_hoja(ruta, max_filas=2000)
                    entrada = {
                        "nombre": ruta.name, "mtime": mtime, "hojas": p["hojas"], "hoja": p["hoja"],
                        "filas": p["filas"], "encabezados": p["encabezados"],
                        "columnas": {k: {"tipo": v["tipo"], "ejemplos": v["ejemplos"][:3]}
                                     for k, v in p["columnas"].items()},
                    }
                except Exception as e:  # archivos protegidos, dañados, etc.
                    entrada = {"nombre": ruta.name, "mtime": mtime, "error": str(e)[:200]}
                    errores += 1
                if clave in indice:
                    actualizados += 1
                else:
                    nuevos += 1
                indice[clave] = entrada
        # quitar archivos que ya no existen
        for clave in [k for k in indice if not Path(k).exists()]:
            del indice[clave]
        self.guardar()
        return {"revisados": vistos, "nuevos": nuevos, "actualizados": actualizados, "errores": errores,
                "total_indexados": len(indice)}

    @staticmethod
    def _recorrer(base: Path, profundidad: int):
        pila = [(base, 0)]
        while pila:
            carpeta, nivel = pila.pop()
            try:
                hijos = list(carpeta.iterdir())
            except OSError:
                continue
            for h in hijos:
                if h.name.startswith((".", "~$")) or h.name in IGNORAR:
                    continue
                if h.is_dir() and nivel < profundidad:
                    pila.append((h, nivel + 1))
                elif h.is_file() and h.suffix.lower() in EXTENSIONES:
                    yield h

    def buscar_archivos(self, consulta: str, limite: int = 10) -> list[dict]:
        q = _tokens(consulta)
        resultados = []
        for ruta, e in self.datos["archivos"].items():
            texto = " ".join([e.get("nombre", ""), " ".join(e.get("hojas", [])), " ".join(e.get("encabezados", []))]
                             + [" ".join(c.get("ejemplos", [])) for c in e.get("columnas", {}).values()])
            t = _tokens(texto)
            puntaje = len(q & t) + 2 * len(q & _tokens(e.get("nombre", "")))
            if puntaje:
                resultados.append((puntaje, e.get("mtime", 0), ruta, e))
        resultados.sort(key=lambda x: (-x[0], -x[1]))
        return [{"ruta": r, "nombre": e["nombre"], "hoja": e.get("hoja"), "filas": e.get("filas"),
                 "encabezados": e.get("encabezados", [])[:20],
                 "modificado": datetime.fromtimestamp(m).strftime("%Y-%m-%d %H:%M")}
                for _, m, r, e in resultados[:limite]]

    def recientes(self, limite: int = 10) -> list[dict]:
        orden = sorted(self.datos["archivos"].items(), key=lambda kv: -kv[1].get("mtime", 0))
        return [{"ruta": r, "nombre": e["nombre"], "encabezados": e.get("encabezados", [])[:15],
                 "modificado": datetime.fromtimestamp(e.get("mtime", 0)).strftime("%Y-%m-%d %H:%M")}
                for r, e in orden[:limite]]

    # ------------------------------------------------------------- contexto para el prompt
    def contexto(self, max_notas: int = 30) -> str:
        partes = []
        notas = self.datos["notas"][-max_notas:]
        if notas:
            partes.append("Lo que sé del usuario y su trabajo (notas guardadas):\n" +
                          "\n".join(f"- [{n['id']}] {n['texto']}" for n in notas))
        if self.datos["perfiles"]:
            partes.append("Perfiles de validación aprendidos: " + ", ".join(
                f"{k} ({len(v['encabezados'])} columnas)" for k, v in self.datos["perfiles"].items()))
        if self.datos["archivos"]:
            rec = self.recientes(5)
            partes.append(f"Archivos de trabajo indexados: {len(self.datos['archivos'])}. Recientes: " +
                          "; ".join(f"{r['nombre']} ({r['modificado']})" for r in rec))
        return "\n\n".join(partes)

    def estadisticas(self) -> dict:
        return {"notas": len(self.datos["notas"]), "perfiles": len(self.datos["perfiles"]),
                "archivos": len(self.datos["archivos"])}
