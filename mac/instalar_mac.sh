#!/bin/bash
# Instala JARVIS en tu Mac y crea la app "JARVIS" en Aplicaciones.
# Uso:  bash mac/instalar_mac.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DATOS="$HOME/.jarvis"
VENV="$DATOS/venv"
APP="$HOME/Applications/JARVIS.app"

echo "==> JARVIS: instalando desde $REPO"

# 1. Python 3.10+
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; exit(0 if sys.version_info >= (3,10) else 1)'; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Necesitas Python 3.10 o superior. Instálalo con:  brew install python@3.12"
  echo "(o desde https://www.python.org/downloads/macos/) y vuelve a ejecutar este script."
  exit 1
fi
echo "==> Usando $PY ($("$PY" --version))"

# 2. PortAudio (para el micrófono)
if ! "$PY" -c 'import ctypes.util,sys; sys.exit(0 if ctypes.util.find_library("portaudio") else 1)' 2>/dev/null; then
  if command -v brew >/dev/null 2>&1; then
    echo "==> Instalando portaudio (micrófono)…"; brew install portaudio
  else
    echo "!! No encontré portaudio ni Homebrew. sounddevice trae su propia copia normalmente; si el micrófono falla instala Homebrew y ejecuta: brew install portaudio"
  fi
fi

# 3. Entorno virtual y dependencias
mkdir -p "$DATOS"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
echo "==> Instalando dependencias (puede tardar unos minutos la primera vez)…"
"$VENV/bin/pip" install -r "$REPO/requirements-mac.txt"

# 4. Archivo .env
if [ ! -f "$REPO/.env" ]; then
  cp "$REPO/.env.example" "$REPO/.env"
  echo "==> Creé $REPO/.env — ábrelo y pon tu ANTHROPIC_API_KEY y los datos de tu correo."
fi

# 5. Crear JARVIS.app
echo "==> Creando $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/MacOS/JARVIS" <<EOF
#!/bin/bash
cd "$REPO"
exec "$VENV/bin/python" -m jarvis --gui >> "$DATOS/jarvis.log" 2>&1
EOF
chmod +x "$APP/Contents/MacOS/JARVIS"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>JARVIS</string>
  <key>CFBundleDisplayName</key><string>JARVIS</string>
  <key>CFBundleIdentifier</key><string>com.chuvanegas.jarvis</string>
  <key>CFBundleVersion</key><string>0.2.0</string>
  <key>CFBundleShortVersionString</key><string>0.2.0</string>
  <key>CFBundleExecutable</key><string>JARVIS</string>
  <key>CFBundleIconFile</key><string>JARVIS</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>JARVIS usa el micrófono para escuchar tus órdenes de voz.</string>
  <key>NSAppleEventsUsageDescription</key><string>JARVIS abre el selector de archivos para elegir tus hojas de Excel.</string>
</dict>
</plist>
EOF

# Icono
TMP="$(mktemp -d)"
"$VENV/bin/python" "$REPO/mac/crear_icono.py" "$TMP/icono.png"
ICONSET="$TMP/JARVIS.iconset"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$TMP/icono.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s*2)); sips -z $d $d "$TMP/icono.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/JARVIS.icns"
rm -rf "$TMP"
touch "$APP"

# Atajo de terminal
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/jarvis" <<EOF
#!/bin/bash
cd "$REPO" && exec "$VENV/bin/python" -m jarvis "\$@"
EOF
chmod +x "$HOME/.local/bin/jarvis"

cat <<EOF

✅ JARVIS instalado.

  • Ábrelo desde Launchpad / Spotlight (⌘ + espacio, escribe "JARVIS") o en ~/Applications.
  • Arrástralo al Dock para tenerlo siempre a mano.
  • En terminal:  ~/.local/bin/jarvis --gui   (o  jarvis  si ~/.local/bin está en tu PATH)

Permisos (la primera vez macOS te los pedirá):
  • Micrófono: acepta el aviso al pulsar 🎙.
  • Pantalla: Ajustes del Sistema > Privacidad y seguridad > Grabación de pantalla > activa JARVIS
    (si no aparece, pídele "mira mi pantalla" una vez y vuelve a esa pantalla).

La primera vez que hables, Whisper descarga el modelo de voz (~460 MB para "small").
Registro de errores: $DATOS/jarvis.log
EOF
