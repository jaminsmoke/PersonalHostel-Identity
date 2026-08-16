#!/bin/sh
set -e

cat > /usr/share/nginx/html/config.js <<EOF
window.IDENTITY_API_URL = "$IDENTITY_API_URL";
window.CAMAREROS_API_URL = "$CAMAREROS_API_URL";
window.NEGOCIO_API_URL = "$NEGOCIO_API_URL";
EOF