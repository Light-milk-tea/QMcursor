#!/usr/bin/env bash
# Cloud Agent install: create a usable Python venv and install QMcursor[dev].
# Debian/Ubuntu images often ship python3 without ensurepip unless python3-venv is installed.
set -euo pipefail

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  python3-venv \
  python3.12-venv \
  libegl1 \
  libxcb-cursor0 \
  libxcb-icccm4 \
  libxcb-image0 \
  libxcb-keysyms1 \
  libxcb-render-util0 \
  libxcb-xinerama0 \
  libxcb-xkb1 \
  libxkbcommon-x11-0

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  rm -rf .venv
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev]"
