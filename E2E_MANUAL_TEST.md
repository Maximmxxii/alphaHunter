# AlphaHunter — E2E Manual Test Plan

**Date:** 2026-04-25
**Scope:** Full multi-user flow — Google login → Alpaca keys link → place real paper order → verify in Alpaca dashboard.
**Audience:** Director / QA / Developer running smoke before release.

---

## Pre-requisites

- [ ] `.venv` activated; `pip install -r requirements.txt` clean.
- [ ] `frontend/` deps installed: `cd frontend && npm install`.
- [ ] `.env` at repo root contains:
  - `JWT_SECRET=<strong random>`
  - `GOOGLE_CLIENT_ID=<web client id>`
  - `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` (fallback only — per-user creds override)
  - `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- [ ] `frontend/.env` (or shell): `EXPO_PUBLIC_API_URL=http://<dev-host>:8000`, `EXPO_PUBLIC_GOOGLE_CLIENT_ID=<same web client id>`.
- [ ] User has Alpaca **paper** account; API key + secret in hand.
- [ ] User has Google account whitelisted in Google Cloud OAuth client (test users).

---

## Test matrix

| # | Step | Expected | Pass/Fail |
|---|------|----------|-----------|
| 1 | `uvicorn api.main:app --port 8000` | Server up, no warnings | |
| 2 | `curl http://localhost:8000/health` (or `/api/strategies`) | 200 OK | |
| 3 | `cd frontend && npx expo start` → press `w` (web) | App loads at `localhost:8081` | |
| 4 | App: tap **Iniciar sesión con Google** | Google OAuth popup opens | |
| 5 | Complete Google flow | App lands on home tab, JWT stored | |
| 6 | Tap avatar → Settings | `Mi cuenta` screen shows name + email | |
| 7 | Inspect "CUENTA ALPACA" section (first time) | Badge says **No conectada** | |
| 8 | Enter Alpaca API key + Secret + leave **Paper** ON | Form valid | |
| 9 | Tap **CONECTAR CUENTA** | Spinner → success toast → badge **Conectada** | |
| 10 | Pull-to-refresh / re-open settings | Badge persists **Conectada** | |
| 11 | Backend: `sqlite3 data/alphahunter.db "select email, alpaca_api_key is not null from users;"` | Row shows 1 (key encrypted/stored) | |
| 12 | App home: open screener → pick strategy → pick candidate | Entry screen loads with logo + price | |
| 13 | Set `amount_usd = 50` → submit | 200 OK; toast "Orden creada"; appears in positions | |
| 14 | Open Alpaca dashboard (paper) → Orders | Bracket order with same symbol + qty visible | |
| 15 | App: positions tab → tap **Cerrar posición** | 200 OK; Alpaca dashboard shows close order | |
| 16 | Settings → **Actualizar claves** → enter different paper keys | Success; `users.alpaca_api_key` updated | |
| 17 | Settings → **CERRAR SESIÓN** | Returns to login; AsyncStorage cleared | |
| 18 | Re-login same Google account | `has_alpaca = true` returned by `/api/auth/me`; settings shows **Conectada** | |

## Demo mode (parallel flow)

| # | Step | Expected | Pass/Fail |
|---|------|----------|-----------|
| D1 | Fresh user (no Alpaca keys) — open app | Demo banner / onboarding visible | |
| D2 | Activate demo mode (`DemoContext`) | Account/positions hit `/api/demo/*` | |
| D3 | Place demo entry | No real Alpaca call; mock position appears | |
| D4 | `POST /api/demo/reset` (or button) | Demo state cleared | |

---

## Negative cases

- [ ] Wrong Alpaca keys → save → expect 400 with friendly message (not 500).
- [ ] Live mode toggle ON without confirmation → shows warning text in red.
- [ ] No `Authorization` header on `/api/auth/alpaca-keys` → 401.
- [ ] Place entry with no keys saved AND no `.env` fallback → 400, not 500.

## Sign-off

- Tester: ____________________
- Date: 2026-04-__
- Result: ☐ PASS  ☐ PASS WITH ISSUES  ☐ FAIL
- Notes:
