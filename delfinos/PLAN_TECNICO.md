# DelfínOS — Plan técnico

> Momentum en español, curado y probado. Lo mejor de todas las fuentes, sin basura, sin jammers, 100 % estable.

## Visión
- Firmware del Flipper Zero **en español**, para todo el mundo hispanohablante (no solo Colombia).
- Lo mejor del firmware oficial, Momentum y la comunidad, **curado y sin repetir**.
- Menú moderno, iconos propios, pantalla de arranque con el delfín y juegos incluidos.
- Instalador web y catálogo propio en **nuestro servidor**.
- **Nada entra al catálogo sin pasar pruebas.**

## Arquitectura (3 bloques)

### 1. Firmware
- Fork de `Next-Flip/Momentum-Firmware` en `~/Documents/DelfinOS` (con `upstream` apuntando a Momentum para traer actualizaciones).
- Traducción de menús con el glosario (`glosario_es.json`) y el traductor (`herramientas/delfin_traductor.py`).
- Identidad: nombre DelfínOS, logo, animación de arranque, pack de iconos.
- Ajustes por región: bandas Sub-GHz legales de cada país (315 / 433 / 868 MHz), teclados BadUSB por idioma, bases IR regionales.
- Compilar: `./fbt` · Grabar: `./fbt flash_usb` · Paquete de actualización: `./fbt updater_package`.

### 2. Servidor
- Web (`index.html`) con instalador por WebSerial (Chrome/Edge), emulador del menú, catálogo y panel de administrador.
- Hospeda los builds de DelfínOS (`.tgz` de actualización) que consume el instalador.
- API del catálogo: lista de apps aprobadas, versión, compatibilidad con la API del firmware, hash.
- Backend del panel de administrador: autenticación real en el servidor (nunca contraseñas en la página), subida de `.fap`, estados staging → aprobado → publicado.

### 3. Pipeline de pruebas ("emular antes de incluir")
No existe un emulador completo y maduro del Flipper que ejecute cualquier app, así que el filtro real es:
1. **Fuente**: se vigilan los repos buenos.
2. **Compila**: build automático de cada app contra el SDK de DelfínOS (`ufbt`). Si no compila, se rechaza sola (filtra ~80 % de los problemas).
3. **Pruebas**: staging, prueba en un Flipper dedicado solo a testing.
4. **Catálogo**: lo que funciona pasa al catálogo oficial de DelfínOS.

## Fuentes curadas
| Repo | Uso |
|---|---|
| Next-Flip/Momentum-Firmware | Base de DelfínOS |
| flipperdevices/flipper-application-catalog | Catálogo oficial, se auto-actualiza |
| flipperdevices/flipperzero-good-faps | Apps oficiales extra |
| xMasterX/all-the-plugins | Colección comunitaria |
| UberGuidoZ/Flipper | Bases de IR y Sub-GHz, documentación |
| djsime1/awesome-flipperzero | Índice del ecosistema |

## Reglas fijas
- **Sin jammers** ni herramientas de ataque indiscriminado (ilegales casi en todo el mundo, no solo en Colombia).
- No redistribuir código sin revisar: todo pasa por el pipeline.
- Uso responsable: solo equipos propios o con autorización; cada usuario cumple las leyes de su país.

## Hoja de ruta
1. **Etapa 1 — Mac y primer build**: Command Line Tools ✅, git ✅, clon de Momentum ✅ (renombrado a `DelfinOS`), VS Code, primer `./fbt` sin cambios.
2. **Etapa 2 — Identidad y español**: ✅ sistema traducido (1.261 textos), fuentes con tildes y ñ, menú en español, animaciones del delfín, base estable `mntm-012` (`firmware/aplicar_delfinos.py`). Falta: compilar y probar en el Flipper.
3. **Etapa 3 — Herramienta de administrador** (✅ traductor web y de Mac, con reglas de seguridad): traductor + `ufbt` para apps de terceros; luego ventana gráfica en la Mac.
4. **Etapa 4 — Servidor**: ✅ instalador web vía Flipper Lab (`lab.flipper.net/?url=`). Falta: subir el `.tgz` al servidor con CORS para lab.flipper.net; API del catálogo.
5. **Etapa 5 — Pipeline**: compilación automática (CI), staging, Flipper de pruebas, publicación.

## Apps externas (siguiente)
Momentum trae 245 apps externas con unos 5.500 textos de pantalla. El plan: elegir las mejores de cada categoría (Momentum + catálogo oficial + comunidad), traducirlas por tandas con el traductor y publicarlas en el catálogo de DelfínOS después de probarlas.
