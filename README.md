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

La validación detecta: columnas faltantes, celdas vacías, tipos incorrectos (número, entero, fecha, texto, email),
valores fuera de rango, valores no permitidos, duplicados en columnas únicas, formatos (regex), totales mal calculados,
**errores de fórmula** (`#DIV/0!`, `#REF!`, `#N/A`…) y filas repetidas. Genera una copia `*_validado.xlsx` con las celdas
marcadas en rojo/amarillo, un comentario en cada una y una hoja **Validación** con el informe.

## Instalación

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
python -m jarvis                     # chat por texto
python -m jarvis -c "resume mis correos no leídos"
python -m jarvis --voz               # modo voz: di "Jarvis, revisa mi correo"
python -m jarvis --validar ejemplos/ventas_ejemplo.xlsx --reglas ejemplos/reglas_ventas.json
```

Para el modo voz instala además: `pip install SpeechRecognition pyaudio pyttsx3`.

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
  excel.py        Crear, leer, validar y generar reporte de Excel
  comandos.py     Modo sin IA (comandos básicos)
  voz.py          Reconocimiento y síntesis de voz (opcional)
ejemplos/         Excel y reglas de ejemplo
tests/            Pruebas (pytest)
```

## Seguridad

- Tus claves viven solo en `.env` (está en `.gitignore`; **nunca lo subas**).
- Los correos se leen en modo solo lectura (no se marcan como leídos).
- Cada envío muestra destinatarios, asunto, adjuntos y cuerpo y espera tu confirmación.
- JARVIS trata el contenido de correos y archivos como información, no como órdenes: si un correo le "pide" algo, te avisa.

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
