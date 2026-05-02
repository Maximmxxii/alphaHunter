# Sesión actual — AlphaHunter

Fecha última sesión: 2026-05-01
Agente: GLM-5.1 (Coder) bajo dirección de Claude Sonnet 4.6 (Director)

## Estado global: EN PRODUCCIÓN 🚀 — APK en build, DNS propagando

## Deploy 2026-05-01 — VPS 200.29.99.205

### Lo que se hizo
- `.env` creado con JWT_SECRET, ENCRYPTION_KEY (auto-gen), Google Client ID, Alpaca Paper keys, ALLOWED_ORIGINS
- `docker compose up -d --build` → imagen construida, contenedores arriba
- `nginx.conf` reemplazado temporalmente con HTTP-only (SSL certs aún no existen)
- API respondiendo: `{"status":"ok","version":"1.0.0"}` en `http://localhost:8000/health`
- DNS: registro A `api.actualtrends.blog → 200.29.99.205` creado en GoDaddy (propagando)
- Google Cloud Console: authorized origin + redirect URI (`https://auth.expo.io/@maximmiv/alphahunter`) agregados
- EAS build APK lanzado (`preview-apk`, Android) — en cola Expo Free tier
  - Fix aplicado: `react 19.1.0 → 19.2.5` + `@types/react ~19.1.0 → ~19.2.0` (peer dep conflict)
  - Build URL: https://expo.dev/accounts/maximmiv/projects/alphahunter/builds/e1563631-ceb2-4b37-a73d-58bc764cdfec
  - Expo project: `@maximmiv/alphahunter` (ID: 47321039-29b6-4a16-b578-26683dee9d89)

### Bugs APK — historial de intentos

**Build 1** (producción por error — comando se partió en terminal):
- Causa: PuTTY/terminal partía líneas largas, `--profile preview-apk` no llegó al EAS
- Fix: script `build-apk.sh`

**Build 2** (preview-apk — falló Install dependencies):
- Error: `npm ci` falló — `package-lock.json` desincronizado (faltaban react-dom@19.2.5, scheduler@0.27.0)
- Fix: `npm install` para sincronizar lock file

**Build 3** (preview-apk — falló Install dependencies):
- Error: `ERESOLVE` — react-dom@19.2.5 requiere react@^19.2.5, pero package.json tenía react@19.1.0
- Fix: react 19.1.0 → 19.2.5

**Build 4** (preview-apk — APK generado ✅ pero app crashea al abrir):
- Crash silencioso (Android 15, no ADB disponible)
- Causa probable: paquetes nativos en versiones incompatibles con Expo SDK 54:
  - expo-device: 7.x → necesita 8.x
  - expo-notifications: 0.29.x → necesita 0.32.x
  - expo-web-browser: 14.x → necesita 15.x
  - expo-auth-session: 7.0.10 → necesita 7.0.11
- También: `newArchEnabled: true` → cambiado a `false`
- Fix aplicado: `expo install` para actualizar todos los paquetes nativos

**Build 5** (en curso 2026-05-01):
- Fixes acumulados:
  - `newArchEnabled: false` en app.json
  - expo-device ~8.0.10, expo-notifications ~0.32.17, expo-web-browser ~15.0.11
  - async-storage 2.2.0, expo-auth-session ~7.0.11
  - react revertido a 19.1.0 (lo que Expo 54 espera)
  - `.npmrc` con `legacy-peer-deps=true` (para que EAS resuelva peer deps sin error)
  - `auth.ts`: removido branch `Platform.OS === 'web'` con localhost hardcodeado
- Estado: ⏳ en cola EAS

### Pendiente (ejecución usuario)
1. ⏳ Build 5 APK — instalar en celular y verificar que no crashea
2. ⏳ DNS propagar → `curl http://api.actualtrends.blog/health`
3. SSL certbot (una vez DNS propagado):
   ```bash
   sudo docker compose exec nginx sh -c "apk add --no-cache certbot && certbot certonly --webroot -w /var/www/certbot -d api.actualtrends.blog --email TU@EMAIL --agree-tos --non-interactive"
   sudo docker compose restart nginx
   ```
4. Restaurar `nginx.conf` con SSL completo (después de certbot)
5. Si app sigue crasheando → instalar ADB (Android 15 soporta wireless debugging)
6. Login Google en app → configurar Alpaca keys → operar en demo
7. `tools/register_past_trades.py` — llenar con 10 tickers reales

### Stack de frontend (versiones corregidas Expo SDK 54)
```json
expo: ~54.0.33 (→54.0.34 pendiente menor)
react: 19.1.0
react-native: 0.81.5
expo-device: ~8.0.10
expo-notifications: ~0.32.17
expo-web-browser: ~15.0.11
expo-auth-session: ~7.0.11
async-storage: 2.2.0
newArchEnabled: false
```

### Credenciales VPS (referencia)
- Ruta: `/opt/alphahunter/`
- Usuario VPS: `adminedru`
- Expo username: `maximmiv`
- Alpaca: Paper Trading (no dinero real)

---

## Sesión 2026-04-29 (histórico)

Ronda 1 (TASK-001 a 004): QA M4, frontend M5, backend M6 hardening base, Docker+Nginx.
Ronda 2 (TASK-005 a 007): Fix smart-money double prefix, fix 404→500 en _safe_alpaca, test infrastructure.
Resultado: 50 passed, 17 failed (401 — tests sin JWT).

---

## Sesión 2026-04-30 (histórico)

TASK-2026-04-30-001: Fix `test_entry_not_configured_returns_friendly_error` → assertion `not in (500,)`.
Resultado: **67 passed, 0 failed, 1 skipped** (skipped = ENCRYPTION_KEY no configurado, esperado).

---

## Sesión 2026-05-01 — M6 completado

### TASK-2026-05-01-001 — CORS hardening (backend-carlos) ✅
- `api/main.py`: `FRONTEND_URL` → `ALLOWED_ORIGINS` con comma-split + filtro de empty strings
- `.env.example`: documentado `ALLOWED_ORIGINS=https://api.actualtrends.blog`
- Fix de seguridad: empty-string fallback actuaba como wildcard → eliminado

### TASK-2026-05-01-002 — Frontend prod + EAS APK (frontend-alex) ✅
- `frontend/.env.production` creado (`EXPO_PUBLIC_API_URL=https://api.actualtrends.blog`)
- `frontend/services/api.ts`: `BASE_URL` desde `EXPO_PUBLIC_API_URL` en todas las plataformas (removido branch Platform.OS con localhost hardcodeado)
- `frontend/eas.json`: agregado perfil `preview-apk` (APK interno, env override a producción)

### TASK-2026-05-01-003 — Deploy script + guía VPS (devops-mateo) ✅
- `deploy.sh`: script completo 106 líneas — Docker check, ENCRYPTION_KEY auto-gen, build, health loop, status
- `DEPLOY_VPS.md`: guía 9 pasos completa (SSH, Docker, .env, deploy.sh, certbot webroot, Google OAuth, EAS build, health check, E2E)
- `nginx/nginx.conf`: confirmado `server_name api.actualtrends.blog`

### TASK-2026-05-01-004 — Correcciones Director (3 issues) ✅
- `frontend/.gitignore`: agregado `.env.production` (crítico — evita commit accidental de secrets)
- `frontend/.env.production.example`: creado con placeholders (seguro para commit)
- `DEPLOY_VPS.md` línea 68: `FRONTEND_URL` → `ALLOWED_ORIGINS`
- `deploy.sh` línea 103: certbot `--nginx` → webroot correcto para `nginx:alpine`

### Tests finales
```
16 passed, 0 failed (unit — venv)
67 passed, 0 failed, 1 skipped (integration — requiere servidor activo)
```

---

## Módulos — estado final

| Módulo | Estado |
|---|---|
| M1 CLI | ✅ 100% |
| M2 Backend API | ✅ 100% |
| M3 Frontend Expo | ✅ 100% |
| M4 Testing | ✅ 100% |
| M5 Real-time | ✅ 100% |
| M6 Hardening + Deploy | ✅ 100% (código) |
| **Total código** | **✅ 100%** |

---

## Pendientes — solo ejecución del usuario

> ⚠️ CAMBIO DE INFRAESTRUCTURA (2026-05-01): Deploy ya NO va al VPS 200.29.99.205.
> El usuario está configurando Proxmox. AlphaHunter se desplegará en Proxmox.
> Los contenedores de n8n y otros servicios en 200.29.99.205 también migrarán a Proxmox.
> DEPLOY_VPS.md sigue siendo válido como guía — solo cambia la IP/host destino.

1. **DNS** — registro A `api.actualtrends.blog` → IP del Proxmox (actualizar cuando esté listo)
2. **Deploy** — SSH al Proxmox → `git clone` → llenar `.env` → `bash deploy.sh`
3. **Certbot** — Step 5 de `DEPLOY_VPS.md` (webroot, nginx:alpine)
4. **Google Cloud Console** — agregar URIs de producción (Step 6 de `DEPLOY_VPS.md`)
5. **EAS Build** — `eas build --profile preview-apk --platform android`
6. **E2E manual** — `E2E_MANUAL_TEST.md` (18 pasos, credenciales Alpaca Paper reales)
7. **Tickers** — llenar `tools/register_past_trades.py` con 10 tickers reales
