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
| Traducción | 1.261 textos del sistema, con el glosario; con `--con-apps` también las apps externas |
| Fuentes | Las 4 fuentes de pantalla con á é í ó ú ü ñ ¿ ¡ (+734 bytes) |
| Animaciones | 2 animaciones de DelfínOS en el escritorio y las burbujas del delfín en español |

Opciones:
- `--idioma es` (por defecto): DelfínOS en español.
- `--idioma en`: DelfínOS en **inglés** — con el logo, las fuentes y las animaciones de DelfínOS, pero sin traducir los textos. Para ofrecer las dos versiones en la web.
- `--con-apps`: traduce también las apps externas con lo que haya en el glosario (lo que falte queda en inglés, sin romper nada).

Para deshacer todo y volver a Momentum limpio:

```bash
cd ~/Documents/DelfinOS && git checkout -- . && git clean -fd assets applications
```

## 2. Traducir las apps externas (opcional, una sola vez)

Momentum trae 237 apps y el catálogo oficial aporta otras 312 (ver `delfinos/catalogo/`). Para traducir sus textos de pantalla al español, usa Claude por lotes:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...        # o: ant auth login
python3 ../herramientas/traducir_con_claude.py ~/Documents/DelfinOS/applications/external
```

- Solo pide lo que falta; guarda cada lote al vuelo (si se corta, se vuelve a correr y sigue).
- Valida cada traducción (formato %d/%s, saltos de línea, que quepa en pantalla) y reintenta una vez; lo dudoso queda en `glosario/apps_revisar.json` para que lo mires.
- Al terminar, los términos entran en `glosario_es.json`. Luego vuelve a correr `aplicar_delfinos.py ... --con-apps` para aplicarlos.

## 3. Compilar (una versión por idioma)

```bash
# Español
python3 aplicar_delfinos.py ~/Documents/DelfinOS --version mntm-012 --con-apps
./compilar_delfinos.sh ~/Documents/DelfinOS 0.1-es

# Inglés (empieza de una copia limpia)
cd ~/Documents/DelfinOS && git checkout -- . && git clean -fd assets applications && cd -
python3 aplicar_delfinos.py ~/Documents/DelfinOS --idioma en
./compilar_delfinos.sh ~/Documents/DelfinOS 0.1-en
```

Deja los paquetes en `firmware/dist/`. Sube los dos `.tgz` al servidor y pon sus URLs en `PAQUETES` dentro de `delfinos/index.html` para que el botón de instalar ofrezca español e inglés.

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

## 4. Probar apps nuevas desde GitHub (zona de pruebas)

Hay dos zonas, igual que en el catálogo web:

- **Estable**: las apps de Momentum (y las que promuevas). Es lo que instala la gente.
- **Pruebas**: lo que vas encontrando y clonando. Viven en `applications_user/` y no tocan las de Momentum.

Encontraste una app en GitHub y la quieres probar:

```bash
python3 ../herramientas/clonar_app.py https://github.com/usuario/mi-app --traducir
```

La clona en `~/Documents/DelfinOS/applications_user/mi-app`, la traduce con el glosario y te dice cómo probarla en el Flipper:

```bash
cd ~/Documents/DelfinOS
./fbt launch APPSRC=applications_user/mi-app
```

Si funciona bien, la pasas a **Estable** en el catálogo web (botón «✓ Pasar a estable»). Consejo: usa `--commit SHA` para clonar una versión fija y que no cambie bajo tus pies.

> El build del firmware incluye lo que haya en `applications_user/`, así que un paquete hecho con apps en pruebas es tu **build de pruebas**. Para el **build estable**, parte de una copia limpia (sin `applications_user/`) y solo con lo aprobado.

### No repetir: alerta de duplicados

Antes de quedarse con una app, `clonar_app.py` compara su id, su repo de GitHub y su nombre contra las del catálogo (`catalogo/apps.json`). Si ya existe una parecida, **te avisa y no la agrega** (borra el clon). Si de verdad es distinta, repite con `--forzar`. El catálogo web hace la misma comprobación cuando pegas un enlace: te avisa en vivo y bloquea los duplicados fuertes (mismo id o mismo repo).

## 5. Potenciar IR, NFC y Sub-GHz (bases de datos top)

Para que el **Mando Universal** y los lectores reconozcan muchísimos más equipos, baja las mejores bases de la comunidad a tu SD:

```bash
python3 descargar_bases.py --todo          # infrarrojo + sub-ghz + nfc
python3 descargar_bases.py --infrarrojo    # solo la base de IR (Flipper-IRDB, miles de controles)
```

Deja todo en `~/DelfinOS_SD/`; copias esas carpetas a la raíz de la SD. Son bases grandes, por eso van en la SD y no dentro del firmware. Fuentes: Flipper-IRDB y el repositorio Flipper de UberGuidoZ.
