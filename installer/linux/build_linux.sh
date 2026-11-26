#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
APP_VERSION="$("${PYTHON_BIN}" -c "from backend.version import APP_VERSION; print(APP_VERSION)")"
echo "==> Building Edifier M60 / M90 Studio Control v${APP_VERSION} for Linux (x86_64)"

echo "[1/5] Building frontend bundle..."
pushd frontend >/dev/null
npm ci
npm run build
popd >/dev/null

echo "[2/5] Generating PNG icon..."
mkdir -p build dist
"${PYTHON_BIN}" -c "from pathlib import Path; from backend.icon import get_icon_png_bytes; Path('build/edifier-m60-control.png').write_bytes(get_icon_png_bytes(256))"

echo "[3/5] Running PyInstaller (--onedir)..."
"${PYTHON_BIN}" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name edifier-m60-control \
  --add-data "frontend/dist:frontend/dist" \
  --collect-submodules bleak \
  --collect-submodules uvicorn \
  --collect-submodules pystray \
  --hidden-import pystray._appindicator \
  --hidden-import pystray._gtk \
  --hidden-import pystray._xorg \
  launcher.py

chmod +x dist/edifier-m60-control/edifier-m60-control

echo "[4/5] Creating Debian/Ubuntu .deb package..."
DEB_PKG="edifier-m60-control_${APP_VERSION}_amd64"
DEB_ROOT="build/${DEB_PKG}"
rm -rf "$DEB_ROOT"
mkdir -p \
  "${DEB_ROOT}/DEBIAN" \
  "${DEB_ROOT}/opt/edifier-m60-control" \
  "${DEB_ROOT}/usr/bin" \
  "${DEB_ROOT}/usr/share/applications" \
  "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps"

cp -a dist/edifier-m60-control/. "${DEB_ROOT}/opt/edifier-m60-control/"
printf 'linux_deb\n' > "${DEB_ROOT}/opt/edifier-m60-control/.install-method"
ln -sf /opt/edifier-m60-control/edifier-m60-control "${DEB_ROOT}/usr/bin/edifier-m60-control"
cp installer/linux/edifier-m60-control.desktop "${DEB_ROOT}/usr/share/applications/edifier-m60-control.desktop"
cp build/edifier-m60-control.png "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/edifier-m60-control.png"

cat > "${DEB_ROOT}/DEBIAN/control" <<EOF
Package: edifier-m60-control
Version: ${APP_VERSION}
Section: sound
Priority: optional
Architecture: amd64
Maintainer: Droid567492 <Droid567492@users.noreply.github.com>
Depends: libc6, libglib2.0-0, libgtk-3-0 | gir1.2-gtk-3.0, bluez
Recommends: pulseaudio-utils | pipewire-pulse, chromium | google-chrome
Description: Desktop controller for Edifier M60 / M90 speakers over BLE and USB-C
 Unofficial desktop control app for Edifier M60 & M90 speakers (volume, input
 source, 6/9-band custom EQ, Sub Out, multipoint, power-save, smart light,
 LDAC, AVRCP, and USB-C audio control). Built using AI assistance.
EOF

cat > "${DEB_ROOT}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
EOF
chmod 0755 "${DEB_ROOT}/DEBIAN/postinst"

cat > "${DEB_ROOT}/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
EOF
chmod 0755 "${DEB_ROOT}/DEBIAN/postrm"

dpkg-deb --build --root-owner-group "$DEB_ROOT" "dist/${DEB_PKG}.deb"

echo "[5/5] Creating portable Linux .tar.gz archive with install.sh..."
PORT_NAME="edifier-m60-control-v${APP_VERSION}-linux-x86_64"
PORT_ROOT="build/${PORT_NAME}"
rm -rf "$PORT_ROOT"
mkdir -p "${PORT_ROOT}"
cp -a dist/edifier-m60-control/. "${PORT_ROOT}/"
cp build/edifier-m60-control.png "${PORT_ROOT}/edifier-m60-control.png"
cp LICENSE "${PORT_ROOT}/LICENSE"

cat > "${PORT_ROOT}/install.sh" <<'EOF'
#!/usr/bin/env sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="${HOME}/.local/share/edifier-m60-control"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"

mkdir -p "$APP_DIR" "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"
cp -a "${HERE}/." "$APP_DIR/"
chmod +x "${APP_DIR}/edifier-m60-control"
ln -sf "${APP_DIR}/edifier-m60-control" "${BIN_DIR}/edifier-m60-control"
cp "${HERE}/edifier-m60-control.png" "${ICON_DIR}/edifier-m60-control.png"

cat > "${APPS_DIR}/edifier-m60-control.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Edifier M60 / M90 Studio Control
Comment=Control Edifier M60 / M90 desktop speakers over Bluetooth LE and USB-C
Exec=${APP_DIR}/edifier-m60-control
Icon=edifier-m60-control
Terminal=false
Categories=AudioVideo;Audio;Settings;
StartupWMClass=edifier-m60-control
DESKTOP

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q "$APPS_DIR" || true
fi
echo "Installed to ${APP_DIR} and linked ${BIN_DIR}/edifier-m60-control"
EOF
chmod +x "${PORT_ROOT}/install.sh"

cat > "${PORT_ROOT}/uninstall.sh" <<'EOF'
#!/usr/bin/env sh
set -eu
rm -rf "${HOME}/.local/share/edifier-m60-control"
rm -f "${HOME}/.local/bin/edifier-m60-control"
rm -f "${HOME}/.local/share/applications/edifier-m60-control.desktop"
rm -f "${HOME}/.local/share/icons/hicolor/256x256/apps/edifier-m60-control.png"
echo "Uninstalled Edifier M60 / M90 Studio Control."
EOF
chmod +x "${PORT_ROOT}/uninstall.sh"

tar -C build -czf "dist/${PORT_NAME}.tar.gz" "${PORT_NAME}"

ls -lh "dist/${DEB_PKG}.deb" "dist/${PORT_NAME}.tar.gz"
