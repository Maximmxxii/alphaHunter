# AlphaHunter -- Deploy to VPS

Complete step-by-step guide to deploy AlphaHunter on `200.29.99.205` with domain `api.actualtrends.blog`.

---

## Step 1 -- SSH into VPS and install prerequisites

```bash
ssh root@200.29.99.205
```

If Docker is not installed yet:

```bash
curl -fsSL https://get.docker.com | sh
apt-get update && apt-get install -y docker-compose-plugin curl python3 python3-pip
pip3 install cryptography
```

Verify:

```bash
docker --version
docker compose version
```

---

## Step 2 -- Clone the repository (or pull latest)

First time:

```bash
cd /opt
git clone https://github.com/YOUR-USER/AlphaHunter.git
cd AlphaHunter
```

Subsequent deploys:

```bash
cd /opt/AlphaHunter
git pull origin main
```

---

## Step 3 -- Configure environment variables

Copy the example file and edit:

```bash
cp .env.example .env
nano .env
```

Variables you **must** fill:

| Variable | Description | How to get it |
|---|---|---|
| `JWT_SECRET` | Random hex string for token signing | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | Fernet key for encrypting stored API keys | Leave empty -- `deploy.sh` auto-generates it |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Google Cloud Console > Credentials |
| `ALPACA_API_KEY` | Alpaca paper trading key | https://app.alpaca.markets > Paper Account > API Keys |
| `ALPACA_SECRET_KEY` | Alpaca paper trading secret | Same as above |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Already set in .env.example |
| `ALLOWED_ORIGINS` | Comma-separated allowed CORS origins | `https://api.actualtrends.blog` |

> **IMPORTANT**: `ENCRYPTION_KEY` can be left empty. `deploy.sh` will generate one automatically on first run. Once generated, do NOT change it or existing encrypted data becomes unreadable.

---

## Step 4 -- Run deploy.sh

```bash
bash deploy.sh
```

This script will:
- Verify Docker and Compose are installed
- Check `.env` exists and has required values
- Auto-generate `ENCRYPTION_KEY` if missing
- Build and start containers (`api` + `nginx`)
- Wait up to 10 retries (3s each) for `http://localhost:8000/health`
- Print final container status

If the health check passes, proceed to Step 5.

---

## Step 5 -- Enable HTTPS with Certbot

The nginx container is already configured with the Certbot webroot path. Run:

```bash
docker compose exec nginx sh -c "apk add --no-cache certbot && certbot certonly --webroot -w /var/www/certbot -d api.actualtrends.blog --email YOUR-EMAIL --agree-tos --non-interactive"
```

This places certificates at `/etc/letsencrypt/live/api.actualtrends.blog/` inside the container.

If you prefer the `certbot --nginx` approach (requires certbot with nginx plugin):

```bash
docker compose exec nginx certbot --nginx -d api.actualtrends.blog
```

> **Note**: The `certbot --nginx` command requires the nginx-certbot Docker image or manual installation of the python-certbot-nginx plugin inside the container. The `certonly --webroot` method above is more reliable with the plain `nginx:alpine` image currently in use.

After obtaining certificates, restart nginx to load SSL:

```bash
docker compose restart nginx
```

---

## Step 6 -- Google Cloud Console -- Authorized URIs

1. Go to [Google Cloud Console > Credentials](https://console.cloud.google.com/apis/credentials)
2. Select your OAuth 2.0 Client ID (Web application type)
3. Under **Authorized JavaScript origins**, add:

```
https://api.actualtrends.blog
```

4. Under **Authorized redirect URIs**, add:

```
https://auth.expo.io/@YOUR-EXPO-USERNAME/alphahunter
```

Replace `YOUR-EXPO-USERNAME` with your actual Expo account username.

5. Click **Save**.

---

## Step 7 -- Build mobile app (EAS)

From your **local machine** (with the Expo project):

```bash
cd /path/to/alphahunter-frontend
eas build --profile preview-apk --platform android
```

This builds a preview APK you can install directly on a device for testing.

> Make sure `EXPO_PUBLIC_GOOGLE_CLIENT_ID` in `frontend/.env` matches the `GOOGLE_CLIENT_ID` in the server `.env`.

---

## Step 8 -- Verify deployment

From the VPS or any machine with internet access:

```bash
curl -sf https://api.actualtrends.blog/health
```

Expected response: HTTP 200 with a JSON body indicating healthy status.

Also verify in a browser or with curl:

```bash
curl -I https://api.actualtrends.blog/health
```

Should return `HTTP/2 200`.

---

## Step 9 -- Run E2E manual tests

Follow the test plan document:

```bash
cat /opt/AlphaHunter/E2E_MANUAL_TEST.md
```

Execute each test case in the document to verify all endpoints and flows work correctly over HTTPS.

---

## Rollback procedure

If something goes wrong after a deploy:

```bash
cd /opt/AlphaHunter

# Option A: Roll back to previous git commit
git log --oneline -5          # find the last working commit
git checkout <commit-hash>    # switch to it
bash deploy.sh                # redeploy

# Option B: Just restart with previous image (if you haven't rebuilt)
docker compose down
docker compose up -d

# Option C: Nuclear -- remove everything and start fresh
docker compose down -v        # WARNING: removes volumes (database data)
git checkout main
git pull origin main
bash deploy.sh
```

---

## Useful commands

```bash
# View logs
docker compose logs -f api
docker compose logs -f nginx

# Restart a single service
docker compose restart api

# Check container health
docker compose ps

# Renew SSL certificate (set up a cron job)
# 0 3 * * * cd /opt/AlphaHunter && docker compose exec nginx certbot renew && docker compose exec nginx nginx -s reload
```
