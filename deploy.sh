#!/usr/bin/env bash
set -euo pipefail

# ── AlphaHunter deploy.sh ──────────────────────────────────────────────────────
# Run on VPS: bash deploy.sh
# Builds images, starts containers, waits for health check.
# ────────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*" >&2; exit 1; }

# ── 1. Pre-flight checks ──────────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
    fail "Docker is not installed. Install it first:\n  curl -fsSL https://get.docker.com | sh"
fi

if ! docker compose version &>/dev/null; then
    fail "Docker Compose v2 plugin not found. Install it:\n  apt-get update && apt-get install -y docker-compose-plugin"
fi

log "Docker $(docker --format '{{.Server.Version}}' 2>/dev/null || docker version --format '{{.Server.Version}}')"
log "Compose $(docker compose version --short)"

# ── 2. Ensure .env exists ─────────────────────────────────────────────────────

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        warn ".env created from .env.example — review and fill real values before re-running."
        fail "Edit .env with production values, then run deploy.sh again."
    else
        fail ".env file not found. Create it from .env.example first."
    fi
fi

# ── 3. Generate ENCRYPTION_KEY if empty ───────────────────────────────────────

ENCRYPTION_KEY_PRESENT=$(grep -c "^ENCRYPTION_KEY=.\+" .env 2>/dev/null || true)
if [ "$ENCRYPTION_KEY_PRESENT" -eq 0 ]; then
    # Key is missing or empty — generate one
    GENERATED_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
        || python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
    # Update or append
    if grep -q "^ENCRYPTION_KEY=" .env; then
        sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${GENERATED_KEY}|" .env
    else
        echo "ENCRYPTION_KEY=${GENERATED_KEY}" >> .env
    fi
    log "ENCRYPTION_KEY generated and saved to .env"
else
    log "ENCRYPTION_KEY already set in .env"
fi

# ── 4. Build and start containers ─────────────────────────────────────────────

log "Building Docker images..."
docker compose build

log "Starting containers in background..."
docker compose up -d

# ── 5. Health check loop ──────────────────────────────────────────────────────

HEALTH_URL="http://localhost:8000/health"
MAX_RETRIES=10
SLEEP_SECONDS=3
RETRY=0
HEALTHY=false

log "Waiting for API health check (${HEALTH_URL})..."
while [ $RETRY -lt $MAX_RETRIES ]; do
    RETRY=$((RETRY + 1))
    if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    log "Retry ${RETRY}/${MAX_RETRIES} — API not ready, waiting ${SLEEP_SECONDS}s..."
    sleep "$SLEEP_SECONDS"
done

# ── 6. Final status ───────────────────────────────────────────────────────────

echo ""
echo "=========================================="
if $HEALTHY; then
    log "API is HEALTHY (attempt ${RETRY}/${MAX_RETRIES})"
else
    fail "API did NOT respond healthy after ${MAX_RETRIES} retries"
fi

log "Container status:"
docker compose ps

echo ""
log "Next steps:"
echo "  1. Run SSL:  docker compose exec nginx sh -c \"apk add --no-cache certbot && certbot certonly --webroot -w /var/www/certbot -d api.actualtrends.blog --email YOUR-EMAIL --agree-tos --non-interactive\""
echo "  2. Verify:   curl -sf https://api.actualtrends.blog/health"
echo "  3. Run E2E:  cat E2E_MANUAL_TEST.md"
echo "=========================================="
