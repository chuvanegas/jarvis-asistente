# Servidor de compilación de DelfínOS — para que todo sea 100% web

Con este servidor, agregar, **validar y compilar apps** se hace desde la web, sin Terminal.

## Por qué hace falta un servidor
Compilar una app del Flipper a `.fap` necesita el toolchain ARM (`ufbt`). Eso **no existe dentro de una página web**: ningún navegador puede compilar código ARM. La forma "web" de hacerlo es que la página le pida a un servidor que compile y le devuelva el resultado. Este es ese servidor.

## Montarlo (en tu servidor)
Con Docker:
```bash
docker build -t delfinos-build .
docker run -d -p 8000:8000 --name delfinos delfinos-build
```
Sin Docker:
```bash
pip install -r requirements.txt ufbt
uvicorn app:app --host 0.0.0.0 --port 8000
```
Prueba: `curl http://TU-SERVIDOR:8000/salud` → debe decir `"ok": true`.

## Endpoints
| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/salud` | Comprueba que ufbt está listo |
| POST | `/validar` | `{github_url}`: compila para ver si sirve y devuelve los errores (no guarda) |
| POST | `/compilar-app` | `{github_url, commit?}`: compila y devuelve el `.fap` (base64) + errores |
| GET | `/descargar/{id}` | Baja un `.fap` ya compilado |

## Hacerlo 100% web (incluido el botón de compilar)
Los artefactos de claude.ai **bloquean** las llamadas a otros servidores (política CSP), así que el catálogo publicado ahí no puede hablar con este backend. Para que sea 100% web de punta a punta:

1. Copia los HTML de DelfínOS (`delfinos/index.html`, `delfinos/catalogo/`, `delfinos/traductor/`) a una carpeta `web/` junto a `app.py` (o descomenta `COPY web ./web` en el Dockerfile).
2. Este servidor ya los sirve en `/` (las últimas líneas de `app.py`).
3. En el catálogo, el botón **Compilar** (en cada app de "En pruebas") llama a `POST /compilar-app` de ESTE servidor —misma URL, sin CSP— y muestra los errores en la misma página.

Así, desde tu dominio: agregas una app (pegando el link de GitHub), la **validas/compilas** y ves los errores, todo en la web.

## Lo que NO compila
Jammers (bloqueadores de señal): su única función es inhibir a terceros, es ilegal casi en todo el mundo. El servidor los rechaza (código 403).
