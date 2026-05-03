#!/bin/bash
# DDNS updater: api.actualtrends.blog -> GoDaddy
# Cron: */5 * * * * /opt/alphahunter/ddns-update.sh >> /var/log/ddns.log 2>&1

set -u

ENV_FILE="/opt/alphahunter/.env"
IP_CACHE="/opt/alphahunter/.last_ip"
COMPOSE_DIR="/opt/alphahunter"
DOMAIN="actualtrends.blog"
SUBDOMAIN="api"

if [ ! -f "$ENV_FILE" ]; then
    echo "[$(date)] ERROR: .env no encontrado en $ENV_FILE" >&2
    exit 1
fi

# Source GoDaddy credentials from .env (GODADDY_KEY, GODADDY_SECRET)
set -a
. "$ENV_FILE"
set +a

if [ -z "${GODADDY_KEY:-}" ] || [ -z "${GODADDY_SECRET:-}" ]; then
    echo "[$(date)] ERROR: GODADDY_KEY o GODADDY_SECRET no definidas en .env" >&2
    exit 1
fi

CURRENT_IP=$(curl -sf https://api.ipify.org 2>/dev/null || curl -sf https://ifconfig.me 2>/dev/null)

if [ -z "$CURRENT_IP" ]; then
    echo "[$(date)] ERROR: no se pudo obtener IP publica" >&2
    exit 1
fi

LAST_IP=""
[ -f "$IP_CACHE" ] && LAST_IP=$(cat "$IP_CACHE")

if [ "$CURRENT_IP" = "$LAST_IP" ]; then
    exit 0
fi

echo "[$(date)] IP cambio: $LAST_IP -> $CURRENT_IP"

HTTP_CODE=$(curl -s -o /tmp/gd_resp.json -w "%{http_code}" \
    -X PUT \
    -H "Authorization: sso-key ${GODADDY_KEY}:${GODADDY_SECRET}" \
    -H "Content-Type: application/json" \
    -d "[{\"data\": \"${CURRENT_IP}\", \"ttl\": 600}]" \
    "https://api.godaddy.com/v1/domains/${DOMAIN}/records/A/${SUBDOMAIN}")

if [ "$HTTP_CODE" != "200" ]; then
    echo "[$(date)] ERROR GoDaddy API: HTTP $HTTP_CODE" >&2
    cat /tmp/gd_resp.json >&2
    exit 1
fi

echo "[$(date)] DNS actualizado: ${SUBDOMAIN}.${DOMAIN} -> $CURRENT_IP"

sed -i "s|ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=https://${SUBDOMAIN}.${DOMAIN}|" "$ENV_FILE"

cd "$COMPOSE_DIR" && docker compose up -d
echo "[$(date)] Contenedores reiniciados"

echo "$CURRENT_IP" > "$IP_CACHE"
