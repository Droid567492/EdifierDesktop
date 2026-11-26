#!/usr/bin/env bash
# Build a native .rpm (Fedora, RHEL/Alma/Rocky, openSUSE) for Edifier M60 / M90 Studio Control.
# Requires: python3 (+ backend/requirements.txt & pyinstaller), node/npm, rpm-build.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
APP_VERSION="$("${PYTHON_BIN}" -c "from backend.version import APP_VERSION; print(APP_VERSION)")"
echo "==> Building Edifier M60 / M90 Studio Control v${APP_VERSION} RPM (x86_64)"

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

echo "[3/4] Staging RPM payload..."
STAGE_DIR="${ROOT_DIR}/build/rpm-stage"
RPM_TOPDIR="${ROOT_DIR}/build/rpmbuild"
rm -rf "$STAGE_DIR" "$RPM_TOPDIR"
mkdir -p "${STAGE_DIR}/opt/edifier-m60-control" "${RPM_TOPDIR}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}
cp -a dist/edifier-m60-control/. "${STAGE_DIR}/opt/edifier-m60-control/"
printf 'linux_rpm\n' > "${STAGE_DIR}/opt/edifier-m60-control/.install-method"
cp installer/linux/edifier-m60-control.desktop "${STAGE_DIR}/edifier-m60-control.desktop"
cp build/edifier-m60-control.png "${STAGE_DIR}/edifier-m60-control.png"
cp LICENSE "${STAGE_DIR}/LICENSE"

echo "[4/4] Running rpmbuild..."
rpmbuild -bb \
  --target x86_64 \
  --define "_topdir ${RPM_TOPDIR}" \
  --define "app_version ${APP_VERSION}" \
  --define "stagedir ${STAGE_DIR}" \
  installer/linux/rpm/edifier-m60-control.spec

RPM_NAME="edifier-m60-control-${APP_VERSION}-1.x86_64.rpm"
BUILT_RPM="$(find "${RPM_TOPDIR}/RPMS" -name 'edifier-m60-control-*.rpm' | head -n 1)"
if [ -z "$BUILT_RPM" ]; then
  echo "ERROR: rpmbuild did not produce an RPM" >&2
  exit 1
fi
cp "$BUILT_RPM" "dist/${RPM_NAME}"
rpm -qip "dist/${RPM_NAME}"
ls -lh "dist/${RPM_NAME}"
