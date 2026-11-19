# DelfínOS · armar el firmware en tu Mac

DelfínOS = **Momentum `mntm-012` (la última versión estable)** + sistema en español + fuentes con tildes y ñ + animaciones del delfín.

## 1. Convertir tu copia de Momentum en DelfínOS

Tu copia está en `~/Documents/DelfinOS`. Desde esta carpeta (`delfinos/firmware`):

```bash
python3 aplicar_delfinos.py ~/Documents/DelfinOS --version mntm-012
```

Qué hace, en orden:

| Paso | Qué cambia |
|---|---|
| Versión | Pasa tu copia a `mntm-012`, la estable (la que tienes ahora es `dev`, menos probada) |
| Parches | Nombres del menú principal y de Ajustes en español (solo lo que se ve) |
| Traducción | 1.261 textos del sistema en 328 archivos, con el glosario de 841 términos |
| Fuentes | Las 4 fuentes de pantalla con á é í ó ú ü ñ ¿ ¡ (+734 bytes) |
| Animaciones | 2 animaciones de DelfínOS en el escritorio y las burbujas del delfín en español |

Para deshacer todo y volver a Momentum limpio:

```bash
cd ~/Documents/DelfinOS && git checkout -- . && git clean -fd assets applications
```

## 2. Compilar

```bash
./compilar_delfinos.sh ~/Documents/DelfinOS 0.1
```

Deja el paquete en `firmware/dist/flipper-z-f7-update-delfinos-0.1.tgz`.

## 3. Instalar

- **Por USB (tu Flipper):** cierra qFlipper y corre `./fbt COMPACT=1 DEBUG=0 flash_usb_full` dentro de `~/Documents/DelfinOS`.
- **Por qFlipper:** *Install from file* → el `.tgz`.
- **Desde la web (para todos):** sube el `.tgz` a tu servidor y pon su URL en `PAQUETE` dentro de `delfinos/index.html`. El botón abre Flipper Lab (`lab.flipper.net/?url=…`), que instala por USB desde Chrome o Edge. El servidor debe responder con `Access-Control-Allow-Origin: https://lab.flipper.net`.

## Qué NO se traduce, a propósito

Traducir estas cosas rompería el Flipper o la compatibilidad con la comunidad:

- **Claves de archivos guardados** (`Frequency`, `Protocol`… en `.sub`, `.nfc`, `.ir`): tus señales y las de internet dejarían de abrir.
- **Nombres internos de apps** (`Infrared`, `Storage`…): con ellos abren las apps el celular, qFlipper, los atajos y los Favoritos. En pantalla salen en español gracias a `delfinos_nombres.h`.
- **Textos que se comparan en el código** (por ejemplo `"Clock"` en los atajos del escritorio): si se traducen en un lado y no en el otro, dejan de coincidir.
- **Nombres de botones IR** (`Power`, `Vol_up`…): son el estándar de las bases de controles universales.
- **Comandos de consola (CLI) y RPC.**

Por eso 18 palabras de pantalla (como `Yes`, `None` o `Default`) quedan en inglés.

## Qué falta probar en tu Mac

Aquí no se puede compilar (el servidor del compilador del Flipper está bloqueado en este entorno). Ya está verificado:

- Las fuentes nuevas, dibujadas con la librería real u8g2 (ver `fuentes/prueba_pantalla.png`).
- Que `u8g2_fonts.c` y `delfinos_nombres.h` compilan.
- Que todos los textos traducidos siguen siendo C válido.

Falta: el `./fbt` completo, que el firmware quepa en la memoria y una vuelta por los menús en el Flipper.

## Regenerar piezas

- Fuentes: `python3 ../fuentes/generar_fuentes.py <Momentum>/lib/u8g2/u8g2_fonts.c <u8g2>/csrc/u8g2_fonts.c ../fuentes/u8g2_fuentes_es.c`
- Animaciones: `python3 ../animaciones/generar_animaciones.py ../animaciones/dolphin` (requiere Pillow)
