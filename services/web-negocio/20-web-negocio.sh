#!/bin/sh
set -e

cat > /usr/share/nginx/html/config.js <<EOF
window.NEGOCIO_API_URL = "$NEGOCIO_API_URL";
EOF