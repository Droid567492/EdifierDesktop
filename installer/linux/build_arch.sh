#!/usr/bin/env bash
# Build a native Arch Linux package (.pkg.tar.zst) for Edifier M60 / M90 Studio Control.
# Requires: python (+ backend/requirements.txt & pyinstaller), node/npm, base-devel (makepkg).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
APP_VERSION="$("${PYTHON_BIN}" -c "from backend.version import APP_VERSION; print(APP_VERSION)")"
echo "==> Building Edifier M60 / M90 Studio Control v${APP_VERSION} Arch package (x86_64)"

echo "[1/4] Building frontend bundle..."
pushd frontend >/dev/null
npm ci
npm run build
popd >/dev/null

echo "[2/4] Generating PNG icon & running PyInstaller (--onedir)..."
mkdir -p build dist
"${PYTHON_BIN}" -c "from pathlib import Path; from backend.icon import get_icon_png_bytes; Path('build/edifier-m60-control.png').write_bytes(get_icon_png_bytes(256))"
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

echo "[3/4] Staging PKGBUILD & payload..."
STAGE_DIR="${ROOT_DIR}/build/arch-stage"
rm -rf "$STAGE_DIR"
mkdir -p "${STAGE_DIR}/payload"
cp -a dist/edifier-m60-control/. "${STAGE_DIR}/payload/"
sed "s/^pkgver=.*/pkgver=${APP_VERSION}/" installer/linux/arch/PKGBUILD > "${STAGE_DIR}/PKGBUILD"
cp installer/linux/arch/edifier-m60-control.install "${STAGE_DIR}/edifier-m60-control.install"
cp installer/linux/edifier-m60-control.desktop "${STAGE_DIR}/edifier-m60-control.desktop"
cp build/edifier-m60-control.png "${STAGE_DIR}/edifier-m60-control.png"
cp LICENSE "${STAGE_DIR}/LICENSE"

echo "[4/4] Running makepkg..."
if [ "$(id -u)" = "0" ]; then
  # makepkg refuses to run as root (e.g. inside CI/Docker containers).
  if ! id builder >/dev/null 2>&1; then
    useradd -m builder
  fi
  chown -R builder:builder "$STAGE_DIR"
  su -s /bin/bash builder -c "cd '${STAGE_DIR}' && makepkg -f --noconfirm"
else
  (cd "$STAGE_DIR" && makepkg -f --noconfirm)
fi

PKG_NAME="edifier-m60-control-${APP_VERSION}-1-x86_64.pkg.tar.zst"
if [ ! -f "${STAGE_DIR}/${PKG_NAME}" ]; then
  echo "ERROR: makepkg did not produce ${PKG_NAME}" >&2
  ls -la "$STAGE_DIR" >&2
  exit 1
fi
cp "${STAGE_DIR}/${PKG_NAME}" "dist/${PKG_NAME}"
ls -lh "dist/${PKG_NAME}"
