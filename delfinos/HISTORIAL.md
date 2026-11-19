# DelfínOS — Historial del chat "Comparar AliExpress vs Flipper Zero"

Resumen de las decisiones tomadas en ese chat, traído a este repo.

## Decisiones
- **Enfoque**: no "todos los repos automáticamente", sino lo mejor de todos lados (oficial + Momentum + comunidad), curado, probado y estable. Nicho: el único firmware en español, confiable y documentado.
- **Alcance global**: para todo el mundo hispanohablante; aviso legal internacional.
- **Ajustes por región** en vez de quitar límites: bandas Sub-GHz por país, teclados BadUSB por idioma, IR regional.
- **Sin jammers**: ilegales casi en todo el mundo.
- **"Emulador" de pruebas**: se reemplaza por compilación automática + staging + Flipper dedicado a pruebas.
- **Servidor propio** para web, instalador, catálogo y API.

## Lo que se hizo
- Logo propio (delfín saltando en ícono de SO, degradado naranja → morado).
- Web completa (`index.html`, publicada en https://claude.ai/artifact/2U94sQVLWLjwNuKUw1WSpm): instalador web, "Por qué DelfínOS", catálogo, pipeline, fuentes, ajustes por región, uso responsable.
- Mini emulador del menú en español: primero con JavaScript (no funcionaba en el celular), rehecho solo con CSS.
- Panel de administrador (solo interfaz): login, carga de `.fap`, staging con Probar/Aprobar/Publicar. La seguridad real va en el servidor.
- Glosario base (`glosario_es.json`) y traductor de apps (`herramientas/delfin_traductor.py`), probado en el chat con la app Sub-GHz de Momentum (43 textos traducidos).
- Plan técnico (`PLAN_TECNICO.md`).

## Estado en la Mac (último punto del chat)
- git 2.54 instalado ✅; qFlipper no instalado (se instala después para grabar).
- Momentum clonado en `~/Documents` (2,9 GB) y renombrado a `~/Documents/DelfinOS` ✅.
- Pendiente: abrir en VS Code (`code ~/Documents/DelfinOS`) y correr el primer `./fbt`.

> Nota: el glosario, el traductor y el plan de este repo se **reconstruyeron** a partir del texto del chat; los archivos originales no se pudieron traer.
