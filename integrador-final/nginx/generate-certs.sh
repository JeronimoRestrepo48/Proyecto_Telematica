#!/usr/bin/env bash
# Genera certificado autofirmado para pruebas locales o hasta configurar Let's Encrypt en AWS.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$DIR/certs"
CN="${1:-localhost}"
openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout "$DIR/certs/server.key" \
  -out "$DIR/certs/server.crt" \
  -subj "/CN=$CN/O=EAFIT/C=CO"
