# 🤖 JARVIS — Asistente personal de trabajo

Asistente en Python que **revisa tu correo, envía correos, crea hojas de Excel y valida los archivos de tu trabajo**.
Funciona por texto o por voz ("Jarvis, ...") y usa Claude como cerebro para entender órdenes en lenguaje natural.

Inspirado en las ideas de los proyectos JARVIS de GitHub (voz con palabra clave, arquitectura de herramientas, asistente
por comandos) pero escrito desde cero y enfocado en el trabajo de oficina.

## ¿Qué puede hacer?

| Área | Ejemplos de órdenes |
|---|---|
| 📥 Revisar correo | "revisa mis correos no leídos y dime cuáles son urgentes", "busca los correos de facturación de esta semana", "lee el correo 1532" |
| 📤 Enviar correo | "responde a Laura que el informe sale el viernes", "envía ventas.xlsx a jefe@empresa.com con un resumen" (**siempre pide confirmación antes de enviar**) |
| 📊 Crear Excel | "crea un Excel con los pedidos que me llegaron hoy por correo", "haz una hoja de gastos con estas filas… y suma el total" |
| ✅ Validar Excel | "valida nomina.xlsx", "revisa que en ventas.xlsx el Total sea Cantidad × Precio y que no haya facturas repetidas" |
| 🖥️ Ver tu pantalla | "mira mi pantalla y dime qué está mal en esta fórmula", "¿qué dice este error?" |
| 🧠 Aprender | "recuerda que mi jefe es Carlos (carlos@empresa.com)", "esta hoja está correcta, aprende sus reglas", "aprende de mis archivos", "¿en qué he estado trabajando?" |
| 🎙 Voz | Pulsa 🎙 (o ⌘K), o activa *manos libres* y di **"Jarvis, …"**. Te responde en voz alta |

La validación detecta: columnas faltantes, celdas vacías, tipos incorrectos (número, entero, fecha, texto, email),
valores fuera de rango, valores no permitidos, duplicados en columnas únicas, formatos (regex), totales mal calculados,
**errores de fórmula** (`#DIV/0!`, `#REF!`, `#N/A`…) y filas repetidas. Genera una copia `*_validado.xlsx` con las celdas
marcadas en rojo/amarillo, un comentario en cada una y una hoja **Validación** con el informe.

## 🍏 Instalación en Mac (con app y launcher)

```bash
git clone https://github.com/chuvanegas/jarvis-asistente.git
cd jarvis-asistente
bash mac/instalar_mac.sh
```

El instalador crea un entorno en `~/.jarvis/venv`, instala todo y crea **JARVIS.app** en `~/Applications`, con su icono.
Ábrela con Spotlight (⌘ + espacio → "JARVIS") o arrástrala al Dock. Después edita `.env` con tu clave y tu correo.

Permisos que macOS te pedirá:
- **Micrófono**: acepta el aviso la primera vez que pulses 🎙.
- **Grabación de pantalla**: Ajustes del Sistema → Privacidad y seguridad → Grabación de pantalla → activa JARVIS.
  Luego cierra y vuelve a abrir JARVIS.

## Instalación manual (cualquier sistema)

```bash
git clone https://github.com/chuvanegas/jarvis-asistente.git
cd jarvis-asistente
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # Windows: copy .env.example .env
```

Edita `.env`:

1. **`ANTHROPIC_API_KEY`** — clave de <https://console.anthropic.com>. Sin ella JARVIS funciona en *modo comandos básico*.
2. **Correo** — `CORREO_PROVEEDOR` (`gmail`, `outlook`, `yahoo` o `personalizado`), `CORREO_USUARIO` y `CORREO_CLAVE`.
   - **Gmail:** activa la verificación en 2 pasos y crea una *contraseña de aplicación* (Cuenta de Google → Seguridad →
     Contraseñas de aplicación). Usa esa clave de 16 letras, no tu contraseña normal. IMAP debe estar activado.
   - **Outlook/Office 365:** algunas empresas bloquean IMAP/SMTP con contraseña; si falla, pide a TI que lo habilite.

## Uso

```bash
python -m jarvis --gui               # interfaz gráfica (ventana; --navegador para abrirla en el navegador)
python -m jarvis                     # chat por texto
python -m jarvis -c "resume mis correos no leídos"
python -m jarvis --voz               # modo voz: di "Jarvis, revisa mi correo"
python -m jarvis --validar ejemplos/ventas_ejemplo.xlsx --reglas ejemplos/reglas_ventas.json
```

Para voz, ventana y pantalla instala `pip install -r requirements-mac.txt` (el instalador de Mac ya lo hace).

## 🎙 Cómo funciona la voz

1. **Escuchar**: graba el micrófono y deja de grabar sola cuando terminas de hablar. Antes mide el ruido de fondo.
2. **Entender**: transcribe con **Whisper en tu Mac** (`faster-whisper`), sin mandar el audio a internet. La primera vez
   descarga el modelo (`JARVIS_WHISPER_MODELO=small`, unos 460 MB; usa `base` si tu Mac es lento). Si Whisper no está
   instalado, usa el reconocedor de Google.
3. **Responder**: habla con las voces de macOS (`say`). Elige la voz con `JARVIS_VOZ`; para ver las disponibles:
   `say -v '?' | grep es_`. Puedes descargar voces mejores (Mejorada/Premium) en Ajustes → Accesibilidad → Contenido
   leído. Las listas y el código no se leen en voz alta: quedan en pantalla.
4. **Manos libres**: escucha todo el tiempo y solo actúa cuando la frase empieza con "Jarvis".

## 🖥️ Cómo ve tu pantalla

Cuando le pides algo sobre tu pantalla, JARVIS usa la herramienta `ver_pantalla`. Esta toma **una** captura
(`screencapture`), la reduce a 1568 px y se la muestra a Claude. **No graba ni mira tu pantalla de forma continua.**
Solo captura cuando tú se lo pides, y la imagen no se guarda en disco.

## 🧠 Cómo aprende

Todo lo que aprende se guarda **en tu Mac**, en `~/.jarvis/memoria.json`:

- **Notas**: lo que le pides recordar (tu jefe, tus clientes, fechas de cierre, formatos). Las tiene presentes en cada
  conversación. Puedes pedirle "¿qué sabes de mí?" u "olvida la nota 3".
- **Índice de tus archivos**: recorre `JARVIS_CARPETAS_TRABAJO` (por defecto Documentos, Escritorio y Descargas) y
  guarda de cada Excel sus hojas, columnas, tipos y unos ejemplos. Así puede buscar "la hoja de nómina de octubre" o
  decirte en qué has trabajado últimamente.
- **Perfiles de validación**: le das una hoja que está **bien** y aprende sus reglas: columnas obligatorias, tipos,
  valores permitidos (por ejemplo los cargos), rangos e IDs únicos (cédula, factura…). Cuando valides otra hoja con
  columnas parecidas, usa ese perfil sin que se lo pidas. Puedes ajustarlo: "en el perfil nómina agrega que el Neto
  sea Salario - Deducciones".

Dentro del chat: `reiniciar` empieza una conversación nueva y `salir` termina.

### Reglas de validación (JSON)

```json
{
  "hoja": "Ventas",
  "columnas_requeridas": ["Factura", "Fecha", "Cliente", "Total"],
  "no_vacios": ["Factura", "Cliente"],
  "tipos": {"Fecha": "fecha", "Correo": "email", "Cantidad": "entero", "Total": "numero"},
  "rangos": {"Cantidad": {"min": 1}, "Precio": {"min": 0, "max": 10000000}},
  "valores_permitidos": {"Estado": ["Pagado", "Pendiente", "Anulado"]},
  "unicos": ["Factura"],
  "patrones": {"Factura": "^F-\\d{4}$"},
  "formula_total": {"columna": "Total", "igual_a": "Cantidad * Precio", "tolerancia": 0.01}
}
```

Si no das reglas, JARVIS (con Claude) lee el archivo, propone reglas razonables y te explica cuáles aplicó.
Las filas cuya primera celda es `TOTAL`/`SUBTOTAL` se ignoran.

## Estructura

```
jarvis/
  __main__.py     CLI: texto, voz, validación directa
  cerebro.py      Claude + bucle de herramientas
  herramientas.py Definición y ejecución de herramientas (correo, Excel, archivos)
  correo.py       IMAP (leer/buscar) y SMTP (enviar con adjuntos)
  excel.py        Crear, leer, validar, perfilar y aprender reglas de Excel
  memoria.py      Notas, índice de archivos y perfiles aprendidos (~/.jarvis)
  pantalla.py     Captura de pantalla bajo demanda
  voz.py          Micrófono + Whisper local, voz de macOS
  interfaz.py     Servidor local + ventana (pywebview)
  web/index.html  Interfaz gráfica
  comandos.py     Modo sin IA (comandos básicos)
mac/              Instalador y generador del icono de JARVIS.app
ejemplos/         Excel y reglas de ejemplo
tests/            Pruebas (pytest)
```

## Seguridad

- Tus claves viven solo en `.env` (está en `.gitignore`; **nunca lo subas**).
- Los correos se leen en modo solo lectura (no se marcan como leídos).
- Cada envío muestra destinatarios, asunto, adjuntos y cuerpo y espera tu confirmación.
- JARVIS trata el contenido de correos, archivos y capturas como información, no como órdenes: si un correo le "pide"
  algo, te avisa.
- La interfaz solo escucha en `127.0.0.1` y exige un token aleatorio en cada sesión, así ninguna web puede darle órdenes.
- Lo que JARVIS lee (correos, partes de tus Excel, capturas) se envía a Claude solo cuando lo necesita para responderte.
  La memoria y el índice se quedan en tu Mac.

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
