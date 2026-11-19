#!/usr/bin/env python3
"""Servidor de compilación de DelfínOS — hace que todo sea 100% web.

Recibe desde la web el enlace de GitHub de una app, la clona, la compila con ufbt y
devuelve el .fap y los errores. Así se puede validar y crear apps sin tocar la Terminal.

Correr (en TU servidor, no en una página web):
    pip install -r requirements.txt
    uvicorn app:app --host 0.0.0.0 --port 8000
o con Docker:
    docker build -t delfinos-build . && docker run -p 8000:8000 delfinos-build

Endpoints:
    GET  /salud            -> comprueba que el servidor y ufbt están listos
    POST /validar          -> {github_url} : clona y compila; devuelve ok/errores (sin guardar)
    POST /compilar-app     -> {github_url, commit?} : compila y devuelve el .fap (base64) + errores
    GET  /descargar/{id}   -> baja un .fap ya compilado

La web (catálogo) llama a estos endpoints. Como los artefactos de claude.ai bloquean
las llamadas a otros servidores (CSP), para que sea 100% web debes servir también la
web desde este mismo servidor (ver README). Ahí sí la página puede hablar con el backend.
"""
import base64
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="DelfínOS Build Server")

# Permite que tu web (en tu dominio) llame a este servidor. Pon aquí tus dominios.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción pon tu dominio, p. ej. ["https://delfinos.tu-dominio.com"]
    allow_methods=["*"],
    allow_headers=["*"],
)

SALIDA = Path("/tmp/delfinos_builds")
SALIDA.mkdir(parents=True, exist_ok=True)

# No compilamos jammers: su única función es inhibir a terceros (ilegal casi en todo el mundo).
REPOS_BLOQUEADOS = re.compile(r"jammer|jamming|deauth(er)?|bluejam|rf.?jam|signal.?jam|nrf24.?jam", re.I)
RE_GITHUB = re.compile(r"^https?://github\.com/[\w.-]+/[\w.-]+/?(?:\.git)?$", re.I)


class Peticion(BaseModel):
    github_url: str
    commit: str | None = None


def _clonar(url: str, commit: str | None, destino: Path) -> None:
    subprocess.run(["git", "init", "-q", str(destino)], check=True)
    subprocess.run(["git", "-C", str(destino), "remote", "add", "origin", url], check=True)
    ref = commit or "HEAD"
    r = subprocess.run(["git", "-C", str(destino), "fetch", "-q", "--depth", "1",
                        "--filter=blob:limit=5m", "origin", ref], capture_output=True, text=True)
    if r.returncode:
        raise HTTPException(400, f"No se pudo clonar el repo: {r.stderr.strip()[:300]}")
    subprocess.run(["git", "-C", str(destino), "checkout", "-q", "FETCH_HEAD"], check=True)


def _carpeta_app(raiz: Path) -> Path:
    fams = sorted(raiz.rglob("application.fam"))
    if not fams:
        raise HTTPException(400, "No encontré application.fam: ¿es una app del Flipper?")
    return fams[0].parent


def _compilar(url: str, commit: str | None):
    if not RE_GITHUB.match(url.strip()):
        raise HTTPException(400, "Enlace de GitHub inválido (usa https://github.com/usuario/repo).")
    if REPOS_BLOQUEADOS.search(url):
        raise HTTPException(403, "Este servidor no compila jammers: solo sirven para inhibir a terceros y son ilegales.")
    tmp = Path(tempfile.mkdtemp(prefix="delfinos_"))
    try:
        _clonar(url, commit, tmp)
        carpeta = _carpeta_app(tmp)
        # ufbt compila una app contra el SDK; devuelve el .fap en dist/
        r = subprocess.run(["ufbt", "faps"], cwd=carpeta, capture_output=True, text=True, timeout=600)
        errores = (r.stdout + "\n" + r.stderr).strip()
        faps = list(carpeta.glob("dist/*.fap"))
        if r.returncode or not faps:
            return {"ok": False, "errores": errores[-4000:] or "La compilación falló sin mensaje."}
        fap = faps[0]
        bid = uuid.uuid4().hex[:12]
        guardado = SALIDA / f"{bid}.fap"
        shutil.copy2(fap, guardado)
        return {"ok": True, "errores": errores[-2000:], "nombre": fap.name, "id": bid,
                "fap_base64": base64.b64encode(fap.read_bytes()).decode()}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.get("/salud")
def salud():
    tiene_ufbt = shutil.which("ufbt") is not None
    return {"ok": tiene_ufbt, "ufbt": tiene_ufbt,
            "mensaje": "Listo para compilar" if tiene_ufbt else "Falta instalar ufbt (pip install ufbt)"}


@app.post("/validar")
def validar(p: Peticion):
    """Compila para ver si la app sirve, sin guardar el .fap. Devuelve ok + errores."""
    r = _compilar(p.github_url, p.commit)
    return {"ok": r["ok"], "errores": r["errores"], "nombre": r.get("nombre")}


@app.post("/compilar-app")
def compilar_app(p: Peticion):
    """Compila y devuelve el .fap (base64) para instalarlo, más los errores."""
    return _compilar(p.github_url, p.commit)


@app.get("/descargar/{bid}")
def descargar(bid: str):
    f = SALIDA / f"{re.sub(r'[^a-f0-9]', '', bid)}.fap"
    if not f.exists():
        raise HTTPException(404, "No encontré ese .fap (quizá ya se limpió).")
    from fastapi.responses import FileResponse
    return FileResponse(f, filename=f.name, media_type="application/octet-stream")


# Sirve la web (catálogo, traductor, sitio) desde el mismo servidor, para que pueda
# llamar a este backend sin el bloqueo CSP de los artefactos. Copia aquí los HTML.
web = Path(__file__).parent / "web"
if web.is_dir():
    app.mount("/", StaticFiles(directory=str(web), html=True), name="web")
