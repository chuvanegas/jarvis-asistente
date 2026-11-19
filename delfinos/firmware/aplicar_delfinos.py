#!/usr/bin/env python3
"""Convierte una copia de Momentum en DelfínOS.

Uso (en la Mac):
    python3 aplicar_delfinos.py ~/Documents/DelfinOS
    python3 aplicar_delfinos.py ~/Documents/DelfinOS --version mntm-012

Pasos, en orden:
  1. (opcional) cambia a la versión estable de Momentum indicada con --version
  2. aplica los parches de código de parches/*.patch (nombres del menú en español)
  3. traduce el sistema con el glosario (sin tocar claves de archivos, comparaciones
     ni nombres internos de apps)
  4. instala las fuentes con tildes y ñ
  5. agrega las animaciones de DelfínOS y traduce las burbujas del delfín

Se puede deshacer todo con:  git checkout -- . && git clean -fd assets applications
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_DELFINOS = AQUI.parent
sys.path.insert(0, str(RAIZ_DELFINOS / "herramientas"))
sys.path.insert(0, str(RAIZ_DELFINOS / "fuentes"))
import delfin_traductor as dt  # noqa: E402
import u8g2_fuente as u  # noqa: E402

CARPETAS_SISTEMA = ["applications/main", "applications/services", "applications/settings", "applications/system"]
FUENTES = {  # nombre en el firmware -> nombre en u8g2_fuentes_es.c
    "u8g2_font_haxrcorp4089_tr": "u8g2_font_haxrcorp4089_es",
    "u8g2_font_helvB08_tr": "u8g2_font_helvB08_es",
    "u8g2_font_profont11_mr": "u8g2_font_profont11_es",
    "u8g2_font_5x7_tr": "u8g2_font_5x7_es",
}
ANIMACIONES = {"L1_DelfinOS_Salto_128x64": 10, "L1_DelfinOS_Logo_128x64": 8}  # nombre -> peso


def git(fw, *args, check=True):
    return subprocess.run(["git", "-C", str(fw), *args], check=check, capture_output=True, text=True)


def paso(n, texto):
    print(f"\n[{n}] {texto}")


def cambiar_version(fw, version):
    paso(1, f"Cambiando a Momentum {version}")
    git(fw, "fetch", "--tags", "origin")
    git(fw, "checkout", version)
    subprocess.run(["git", "-C", str(fw), "submodule", "update", "--init", "--recursive"], check=True)
    print("   ✓", git(fw, "log", "--oneline", "-1").stdout.strip())


def aplicar_parches(fw):
    paso(2, "Aplicando parches de código")
    for p in sorted((AQUI / "parches").glob("*.patch")):
        if git(fw, "apply", "--reverse", "--check", str(p), check=False).returncode == 0:
            print(f"   = {p.name} (ya estaba aplicado)")
            continue
        r = git(fw, "apply", str(p), check=False)
        if r.returncode:
            sys.exit(f"   ✗ No se pudo aplicar {p.name}:\n{r.stderr}\n"
                     "   ¿Es otra versión de Momentum? Prueba con --version mntm-012")
        print(f"   ✓ {p.name}")


def traducir(fw, apps=False):
    paso(3, "Traduciendo el sistema al español")
    terminos, no_traducir = dt.cargar_glosario(RAIZ_DELFINOS / "glosario_es.json")
    protegidos = dt.nombres_de_apps(fw / "applications")
    no_traducir |= protegidos
    terminos = {k: v for k, v in terminos.items() if k not in protegidos}
    total = 0
    for c in CARPETAS_SISTEMA:
        n, archivos, _ = dt.traducir_carpeta(fw / c, terminos, no_traducir, fam_nombre=False,
                                             raiz_comparaciones=fw / "applications")
        total += n
        print(f"   ✓ {c}: {n} textos en {archivos} archivos")
    print(f"   Sistema: {total} textos")
    if apps:
        # Las apps externas (bundled de Momentum + las que descargaste) se traducen con lo que
        # haya en el glosario. Los textos aún no traducidos quedan en inglés, sin romper nada.
        for c in ("applications/external", "applications_user"):
            if not (fw / c).is_dir():
                continue
            n_app, n, archivos = 0, 0, 0
            for app in sorted(p for p in (fw / c).iterdir() if p.is_dir()):
                nn, na, _ = dt.traducir_carpeta(app, terminos, no_traducir, fam_nombre=True,
                                                raiz_comparaciones=app)
                if nn:
                    n_app += 1; n += nn; archivos += na
            print(f"   ✓ {c}: {n} textos en {archivos} archivos de {n_app} apps")


def preparar_fuentes(fw):
    """Revisa y prepara las fuentes ANTES de tocar nada, para no dejar la copia a medias."""
    ruta = fw / "lib/u8g2/u8g2_fonts.c"
    texto = ruta.read_text(encoding="latin-1")
    nuevas = (RAIZ_DELFINOS / "fuentes/u8g2_fuentes_es.c").read_text(encoding="latin-1")
    resumen = []
    for nombre_fw, nombre_es in FUENTES.items():
        datos = u.extraer_arreglo(nuevas, nombre_es)
        _, g_nuevo = u.decodificar(datos)
        _, g_fw = u.decodificar(u.extraer_arreglo(texto, nombre_fw))
        distintos = [chr(k) for k in g_fw if u._recortar(g_fw[k]) != g_nuevo.get(k)]
        if distintos:
            sys.exit(f"✗ {nombre_fw} de esta versión no coincide con la de DelfínOS ({''.join(distintos)[:20]}).\n"
                     "  Regenera las fuentes con fuentes/generar_fuentes.py o usa --version mntm-012")
        # El arreglo termina en el último literal "..." seguido de ; (los datos pueden tener ; dentro)
        patron = re.compile(r"const uint8_t " + re.escape(nombre_fw) +
                            r"\[\d+\][^=]*=\s*(?:\s*\"(?:[^\"\\]|\\.)*\")+\s*;")
        reemplazo = u.a_c(nombre_fw, datos).rstrip()
        texto, n = patron.subn(lambda _: reemplazo, texto, count=1)
        if n != 1:
            sys.exit(f"✗ No encontré {nombre_fw} en {ruta}")
        resumen.append(f"{nombre_fw}: {len(g_nuevo)} letras")
    return ruta, texto, resumen


def instalar_fuentes(fuentes):
    paso(4, "Instalando fuentes con tildes y ñ")
    ruta, texto, resumen = fuentes
    ruta.write_text(texto, encoding="latin-1")
    for r in resumen:
        print("   ✓", r)


SALUDO = {"es": "¡Hola! Soy\\nDelfínOS", "en": "Hi! I'm\\nDelfinOS"}


def animaciones(fw, idioma="es"):
    paso(5, "Animaciones y burbujas del delfín")
    destino = fw / "assets/dolphin/external"
    origen = RAIZ_DELFINOS / "animaciones/dolphin"
    for nombre in ANIMACIONES:
        if (destino / nombre).exists():
            shutil.rmtree(destino / nombre)
        shutil.copytree(origen / nombre, destino / nombre)
    # El saludo del salto va según el idioma (el meta trae el marcador DELFINOS_SALUDO).
    meta_salto = destino / "L1_DelfinOS_Salto_128x64" / "meta.txt"
    meta_salto.write_text(meta_salto.read_text(encoding="utf-8").replace("DELFINOS_SALUDO", SALUDO[idioma]),
                          encoding="utf-8")
    manifiesto = destino / "manifest.txt"
    m = manifiesto.read_text(encoding="utf-8")
    for nombre, peso in ANIMACIONES.items():
        if f"Name: {nombre}\n" not in m:
            m = m.rstrip("\n") + (f"\n\nName: {nombre}\nMin butthurt: 0\nMax butthurt: 14\n"
                                  f"Min level: 1\nMax level: 30\nWeight: {peso}\n")
    manifiesto.write_text(m, encoding="utf-8")
    print(f"   ✓ {len(ANIMACIONES)} animaciones de DelfínOS en el escritorio")

    if idioma != "es":
        return
    burbujas = json.loads((RAIZ_DELFINOS / "animaciones/burbujas_es.json").read_text(encoding="utf-8"))
    n = 0
    for meta in sorted((fw / "assets/dolphin").glob("*/*/meta.txt")):
        textos = burbujas.get(meta.parent.name)
        if not textos:
            continue
        lineas = meta.read_text(encoding="utf-8").split("\n")
        idx = [i for i, l in enumerate(lineas) if l.startswith("Text: ")]
        if len(idx) != len(textos):
            print(f"   ! {meta.parent.name}: cambió el número de burbujas, se deja igual")
            continue
        for i, t in zip(idx, textos):
            lineas[i] = "Text: " + t.replace("\n", "\\n")
        meta.write_text("\n".join(lineas), encoding="utf-8")
        n += 1
    print(f"   ✓ burbujas traducidas en {n} animaciones")


def main():
    ap = argparse.ArgumentParser(description="Convierte Momentum en DelfínOS.")
    ap.add_argument("firmware", type=Path, help="carpeta del clon de Momentum (p. ej. ~/Documents/DelfinOS)")
    ap.add_argument("--version", help="etiqueta de Momentum a usar, p. ej. mntm-012")
    ap.add_argument("--con-apps", action="store_true",
                    help="traducir también las apps externas (usa el glosario; lo que falte queda en inglés)")
    ap.add_argument("--idioma", choices=["es", "en"], default="es",
                    help="es: DelfínOS en español (por defecto). en: DelfínOS en inglés "
                         "(logo, animaciones y nombres de DelfínOS, pero sin traducir los textos)")
    a = ap.parse_args()
    fw = a.firmware.expanduser().resolve()
    if not (fw / "fbt").exists() or not (fw / "applications").is_dir():
        sys.exit(f"{fw} no parece una copia de Momentum (no encuentro fbt ni applications/).")
    if git(fw, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        sys.exit("La copia tiene cambios sin guardar. Para empezar limpio:\n"
                 f"  cd {fw} && git checkout -- . && git clean -fd assets applications")
    if a.version:
        cambiar_version(fw, a.version)
    fuentes = preparar_fuentes(fw)
    if a.idioma == "es":
        aplicar_parches(fw)
        traducir(fw, apps=a.con_apps)
    else:
        paso(2, "Idioma inglés: se omite la traducción (se mantiene el texto original)")
        paso(3, "DelfínOS en inglés: solo marca, fuentes y animaciones")
    instalar_fuentes(fuentes)
    animaciones(fw, a.idioma)
    marca = "es" if a.idioma == "es" else "en"
    print(f"\n✓ Listo (idioma: {a.idioma}). Ahora compila con:  ./compilar_delfinos.sh {fw} 0.1-{marca}")


if __name__ == "__main__":
    main()
