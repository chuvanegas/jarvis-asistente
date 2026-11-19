# DelfínOS

Firmware del Flipper Zero en español, basado en Momentum-Firmware, con herramientas curadas y probadas. Para todo el mundo.

| Archivo | Qué es |
|---|---|
| `index.html` | Web del proyecto: instalador web, emulador, catálogo, pipeline, panel de admin (demo). Publicada: https://claude.ai/artifact/2U94sQVLWLjwNuKUw1WSpm |
| `PLAN_TECNICO.md` | Arquitectura, fuentes, reglas y hoja de ruta |
| `HISTORIAL.md` | Resumen de decisiones del chat original y estado en la Mac |
| `glosario_es.json` | Glosario inglés → español (`terminos`) y lista de marcas/términos que no se traducen (`no_traducir`) |
| `herramientas/delfin_traductor.py` | Traduce una app a una copia `_es` y lista los textos pendientes |

## Traducir una app
```bash
python3 herramientas/delfin_traductor.py ruta/a/la_app
```
```bash
cd ruta/a/la_app_es && ufbt
```

## Pruebas
```bash
python3 -m pytest -q tests/
```
