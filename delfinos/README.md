# DelfínOS

Firmware del Flipper Zero en español, basado en Momentum-Firmware, con herramientas curadas y probadas. Para todo el mundo.

| Archivo | Qué es |
|---|---|
| `index.html` | Web del proyecto: instalador web, emulador, catálogo, pipeline, panel de admin (demo). Publicada: https://claude.ai/artifact/2U94sQVLWLjwNuKUw1WSpm |
| `PLAN_TECNICO.md` | Arquitectura, fuentes, reglas y hoja de ruta |
| `HISTORIAL.md` | Resumen de decisiones del chat original y estado en la Mac |
| `glosario_es.json` | Glosario inglés → español (`terminos`) y lista de marcas/términos que no se traducen (`no_traducir`) |
| `herramientas/delfin_traductor.py` | Traductor para la Mac: traduce una app a una copia `_es` y lista los pendientes |
| `firmware/` | **Convierte Momentum en DelfínOS y lo compila** (ver `firmware/README.md`) |
| `fuentes/` | Fuentes del Flipper con tildes y ñ, y la herramienta que las genera |
| `animaciones/` | Animaciones del delfín para el escritorio y burbujas en español |
| `glosario/sistema.json` | Los 811 textos del sistema traducidos y revisados para que quepan en pantalla |
| `catalogo/` | Navegador web de las 549 apps (https://claude.ai/artifact/U3e7yxabF5F9ZMoeqsr3so) y `apps.json` |
| `herramientas/traducir_con_claude.py` | Traduce con Claude, por lotes, los textos de las apps |
| `traductor/` | Traductor web (https://claude.ai/artifact/Pihzt6uoV3HECqW97PSJTh). `plantilla.html` + `glosario_es.json` generan `index.html` |

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
