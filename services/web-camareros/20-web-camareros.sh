#!/bin/sh
set -e

cat > /usr/share/nginx/html/config.js <<EOF
window.CAMAREROS_API_URL = "$CAMAREROS_API_URL";
window.NEGOCIO_API_URL = "$NEGOCIO_API_URL";
EOF
