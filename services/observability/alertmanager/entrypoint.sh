#!/bin/sh
set -e

# Genera la config de Alertmanager desde variables de entorno (sin secretos en git).
cat > /etc/alertmanager/alertmanager.yml <<EOF
route:
  receiver: email
  group_by: [alertname]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: email
    email_configs:
      - to: "${ALERTMANAGER_ROUTE_TO}"
        from: "${EMAIL_FROM}"
        smarthost: "${EMAIL_HOST}:${EMAIL_PORT}"
        auth_username: "${EMAIL_USERNAME}"
        auth_password: "${EMAIL_PASSWORD}"
        require_tls: false
EOF

exec /bin/alertmanager --config.file=/etc/alertmanager/alertmanager.yml "$@"
