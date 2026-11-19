#!/bin/bash
# Compila DelfínOS y deja el paquete listo para instalar (USB o web).
# Uso: ./compilar_delfinos.sh ~/Documents/DelfinOS [version]
set -euo pipefail

FW="${1:?Indica la carpeta del firmware, p. ej. ~/Documents/DelfinOS}"
VERSION="${2:-0.1}"
SALIDA="$(cd "$(dirname "$0")" && pwd)/dist"

cd "$FW"
export DIST_SUFFIX="delfinos-$VERSION"

echo "[1] Compilando firmware (la primera vez descarga el compilador, 10-20 min)…"
./fbt COMPACT=1 DEBUG=0 updater_package

PAQUETE=$(ls -t dist/f7-C/flipper-z-f7-update-"$DIST_SUFFIX".tgz 2>/dev/null | head -1)
if [ -z "$PAQUETE" ]; then
  echo "✗ No encontré el paquete en dist/f7-C/. Revisa los errores de arriba." >&2
  exit 1
fi

mkdir -p "$SALIDA"
cp "$PAQUETE" "$SALIDA/"
echo
echo "✓ Paquete: $SALIDA/$(basename "$PAQUETE")"
echo
echo "Para instalar en tu Flipper por USB (cierra qFlipper antes):"
echo "  cd \"$FW\" && ./fbt COMPACT=1 DEBUG=0 flash_usb_full"
echo
echo "Para instalar desde la web: sube el .tgz a tu servidor y abre"
echo "  https://lab.flipper.net/?url=https://TU-SERVIDOR/$(basename "$PAQUETE")&channel=delfinos&version=$VERSION"
