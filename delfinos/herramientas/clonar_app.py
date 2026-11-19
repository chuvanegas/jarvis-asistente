#!/usr/bin/env python3
"""Clona una app del Flipper desde GitHub y la deja lista para probar en DelfínOS.

Uso (en la Mac):
    python3 clonar_app.py URL_DE_GITHUB [--firmware ~/Documents/DelfinOS] [--traducir] [--commit SHA]

Ejemplo:
    python3 clonar_app.py https://github.com/usuario/mi-app-flipper --traducir

Qué hace:
  1. Clona el repo (solo lo necesario) en  <firmware>/applications_user/<repo>/
  2. Busca application.fam y te dice el appid, el nombre y la categoría.
  3. Con --traducir, traduce sus textos de pantalla con el glosario (sin tocar claves,
     comparaciones ni nombres internos).
  4. Te dice cómo compilarla y probarla en tu Flipper.

Las apps clonadas van a applications_user/ (tu zona de PRUEBAS). No tocan las de Momentum.
Cuando una funcione bien, la agregas a "Estable" en el catálogo web.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import delfin_traductor as dt  # noqa: E402

RE_GITHUB = re.compile(r"github\.com[/:]([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:/tree/[^/]+/(.+))?/?$", re.I)
CATALOGO = Path(__file__).resolve().parent.parent / "catalogo" / "apps.json"


def _simplificar(s):
    s = re.sub(r"\[[^\]]*\]", "", (s or "").lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(flipper|zero|app|fap|the|for|de|la|el)\b", " ", s)
    return set(w for w in s.split() if w)


def buscar_duplicado(appid, name, github):
    """¿Esta app ya está en el catálogo? Devuelve (app, motivo) o None."""
    if not CATALOGO.exists():
        return None
    import json
    repo = (re.search(r"github\.com[/:]([^/\s]+/[^/\s#?]+?)(?:\.git)?/?$", (github or "").lower()) or [None, None])[1]
    cat = json.loads(CATALOGO.read_text(encoding="utf-8"))
    A = _simplificar(name)
    mejor = None
    for a in cat:
        if a["appid"] == appid:
            return a, f"el mismo id de app ({appid})"
        ar = (re.search(r"github\.com[/:]([^/\s]+/[^/\s#?]+?)(?:\.git)?/?$", (a.get("github") or "").lower()) or [None, None])[1]
        if repo and ar == repo:
            return a, "el mismo repositorio de GitHub"
        B = _simplificar(a["name"])
        if A and B:
            inter = len(A & B)
            jac = inter / max(len(A), len(B))
            if inter and inter == min(len(A), len(B)):
                jac = max(jac, 0.7)
            if jac >= 0.6 and (not mejor or jac > mejor[1]):
                mejor = (a, jac)
    if mejor:
        return mejor[0], f"un nombre muy parecido ({mejor[0]['name']})"
    return None


def parsear(url):
    m = RE_GITHUB.search(url.strip())
    if not m:
        sys.exit(f"No reconozco ese enlace de GitHub: {url}\n"
                 "Debe ser como https://github.com/usuario/repo")
    owner, repo, subdir = m.group(1), m.group(2), m.group(3)
    return owner, repo, (subdir or "").strip("/")


def clonar(owner, repo, destino, commit=None):
    url = f"https://github.com/{owner}/{repo}.git"
    if destino.exists():
        sys.exit(f"Ya existe {destino}. Bórrala o elige otra si quieres volver a clonar.")
    destino.mkdir(parents=True)
    cmds = [["git", "init", "-q"], ["git", "remote", "add", "origin", url]]
    for c in cmds:
        subprocess.run(c, cwd=destino, check=True)
    fetch = ["git", "fetch", "-q", "--depth", "1", "--filter=blob:limit=5m", "origin"]
    fetch.append(commit or "HEAD")
    if subprocess.run(fetch, cwd=destino).returncode:
        sys.exit("No se pudo descargar el repo (¿URL o commit correctos? ¿hay internet?).")
    subprocess.run(["git", "checkout", "-q", "FETCH_HEAD" if not commit else commit], cwd=destino, check=True)


def info_fam(carpeta):
    fams = sorted(carpeta.rglob("application.fam"))
    if not fams:
        return None
    t = fams[0].read_text(errors="replace")
    g = lambda k: (re.search(r'\b' + k + r'\s*=\s*"((?:[^"\\]|\\.)*)"', t) or [None, None])[1]
    return {"fam": fams[0], "appid": g("appid"), "name": g("name"),
            "cat": g("fap_category"), "desc": g("fap_description")}


def main():
    ap = argparse.ArgumentParser(description="Clona una app del Flipper desde GitHub para DelfínOS.")
    ap.add_argument("url", help="enlace de GitHub de la app")
    ap.add_argument("--firmware", type=Path, default=Path("~/Documents/DelfinOS"),
                    help="carpeta del firmware (por defecto ~/Documents/DelfinOS)")
    ap.add_argument("--commit", help="commit exacto a clonar (recomendado para que no cambie)")
    ap.add_argument("--traducir", action="store_true", help="traducir los textos de pantalla al español")
    ap.add_argument("--forzar", action="store_true", help="quedarse con la app aunque ya exista una parecida")
    a = ap.parse_args()

    fw = a.firmware.expanduser().resolve()
    if not (fw / "fbt").exists():
        sys.exit(f"{fw} no parece el firmware (no encuentro fbt). Usa --firmware para indicar la carpeta.")
    owner, repo, subdir = parsear(a.url)
    destino = fw / "applications_user" / repo

    print(f"→ Clonando {owner}/{repo} en applications_user/{repo} …")
    clonar(owner, repo, destino, a.commit)
    carpeta = destino / subdir if subdir else destino
    info = info_fam(carpeta)
    if not info:
        sys.exit("Clonado, pero no encontré application.fam. ¿Es una app del Flipper? "
                 f"Revisa {carpeta}")
    print(f"✓ App: {info['name']}  ·  id: {info['appid']}  ·  categoría: {info['cat'] or '—'}")

    # ¿Ya existe en el catálogo? (no repetir)
    dup = buscar_duplicado(info["appid"], info["name"], a.url)
    if dup and not a.forzar:
        otra, motivo = dup
        print("\n" + "=" * 56)
        print("⚠️  ALERTA: YA EXISTE UNA APP ASÍ EN TU CATÁLOGO")
        print(f"    «{otra['name']}» ({otra.get('fuente', '')}) — coincide por {motivo}.")
        print("    No la agrego para no repetir. Si de verdad es distinta,")
        print("    vuelve a correr con  --forzar.")
        print("=" * 56)
        shutil.rmtree(destino)
        return 1
    if dup and a.forzar:
        print(f"   (ya había una parecida: {dup[0]['name']}; la agregas igual por --forzar)")

    if a.traducir:
        terminos, no_traducir = dt.cargar_glosario(dt.GLOSARIO_DEFECTO)
        protegidos = dt.nombres_de_apps(carpeta)
        no_traducir |= protegidos
        terminos = {k: v for k, v in terminos.items() if k not in protegidos}
        n, archivos, pend = dt.traducir_carpeta(carpeta, terminos, no_traducir, fam_nombre=True,
                                                raiz_comparaciones=carpeta)
        print(f"✓ Traducidos {n} textos en {archivos} archivos; {len(pend)} pendientes "
              "(usa traducir_con_claude.py para completarlos).")

    print("\nPara probarla en tu Flipper (conéctalo por USB):")
    print(f"  cd {fw}")
    print(f"  ./fbt launch APPSRC=applications_user/{repo}{('/' + subdir) if subdir else ''}")
    print("\nSi funciona bien, agrégala a «Estable» en el catálogo web:")
    print(f"  id {info['appid']}  ·  enlace {a.url}")


if __name__ == "__main__":
    main()
