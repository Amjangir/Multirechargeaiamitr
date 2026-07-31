# Deployment Guide — RechargePro (Multi-Service)

## Vercel deployment

This repo already has a root [vercel.json](./vercel.json) that wires the `frontend/`
and `backend/` services together and routes `/api/*` to the backend service.

Important: Vercel environment variables are configured in the Vercel dashboard,
not inside `vercel.json`. That is where `MONGO_URL` must be added.

### Backend service env vars

Set these in Vercel Project Settings for the `backend` service:

| Key | Value |
|---|---|
| `MONGO_URL` | `mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/<db>` |
| `DB_NAME` | `rechargepro` |
| `JWT_SECRET` | Random 64-char hex |
| `ADMIN_EMAIL` | `admin@rechargepro.com` |
| `ADMIN_PASSWORD` | Strong password |
| `CORS_ORIGINS` | `https://<your-frontend-domain>` |

If you use preview deployments, add each allowed origin as a comma-separated
value in `CORS_ORIGINS`.

### Frontend service env vars

This app already falls back to same-origin `/api` on Vercel, so `REACT_APP_BACKEND_URL`
can be left empty. If you prefer an explicit URL, set it to your backend service
domain.

### Deployment checks

After redeploying, confirm:

1. `GET /api/health` returns `mongo.ok: true`
2. `env.MONGO_URL_set` is `true`
3. Admin login succeeds with the seeded credentials

If you still see `ServerSelectionTimeoutError`, the usual causes are:

1. `MONGO_URL` missing or malformed
2. MongoDB Atlas IP allowlist not permitting Vercel
3. Username/password in the connection string not URL-encoded correctly

---

Your repo has two services: `frontend/` (React/CRA) and `backend/` (FastAPI).
Railway deploys both from the `railway.toml` at the repository root.

---

## 1. Push your repo to GitHub

```bash
git add .
git commit -m "chore: add Railway deployment config"
git push
```

---

## 2. Create a Railway project

1. Sign in at https://railway.app → **New Project → Deploy from GitHub repo**
2. Select your repository — Railway will detect `railway.toml` automatically and set up both services.

---

## 3. Add Environment Variables

Set these in Railway → each **Service → Variables tab**.

### Backend service

| Key | Value |
|---|---|
| `MONGO_URL` | `mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/` |
| `DB_NAME` | `rechargepro` |
| `JWT_SECRET` | Random 64-char hex (see command below) |
| `ADMIN_EMAIL` | `admin@rechargepro.com` |
| `ADMIN_PASSWORD` | Strong password |
| `CORS_ORIGINS` | `https://<your-frontend>.railway.app` *(set after frontend is deployed)* |

Generate a strong `JWT_SECRET`:
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### Frontend service

| Key | Value |
|---|---|
| `REACT_APP_BACKEND_URL` | `https://<your-backend>.railway.app` *(copy from backend service domain)* |

---

## 4. MongoDB Atlas (free 512 MB)

1. Sign up at https://www.mongodb.com/cloud/atlas
2. Create a free **M0** cluster.
3. **Database Access** → add a user with a strong password.
4. **Network Access** → add `0.0.0.0/0` so Railway can connect.
5. Copy the connection string → paste as `MONGO_URL` in Railway.

---

## 5. Deploy order

```
1. Deploy backend first → note the generated domain (e.g. backend-xxx.railway.app)
2. Set REACT_APP_BACKEND_URL on the frontend service to the backend domain
3. Deploy frontend → note the generated domain (e.g. frontend-xxx.railway.app)
4. Set CORS_ORIGINS on the backend service to the frontend domain
5. Redeploy backend to pick up the new CORS setting
```

---

## 6. How it works on Railway

```
Public request              →  Railway service
GET  /                      →  frontend (React SPA served by `serve`)
GET  /dashboard             →  frontend (React SPA, client-side routing)
POST /api/auth/login        →  backend (FastAPI via REACT_APP_BACKEND_URL)
GET  /api/wallet/balance    →  backend (FastAPI via REACT_APP_BACKEND_URL)
```

Unlike Vercel, Railway gives each service its own domain — the frontend calls the backend
by its absolute URL (`REACT_APP_BACKEND_URL`), not via path rewrites.

---

## 7. Verify the deployment

Hit your backend health endpoint after deploying:
```
https://<your-backend>.railway.app/api/health
```

Expected response (all `true`, `ok: true`):
```json
{
  "app": "rechargepro-api",
  "env": {
    "MONGO_URL_set": true,
    "DB_NAME_set": true,
    "JWT_SECRET_set": true,
    "ADMIN_EMAIL_set": true,
    "ADMIN_PASSWORD_set": true
  },
  "mongo": { "ok": true, "admin_seeded": true }
}
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `500` on API calls | Check backend Railway logs → look for `MONGO_URL` errors |
| `CORS` errors in browser | Set `CORS_ORIGINS` to frontend domain on backend service and redeploy |
| Frontend can't reach API | Verify `REACT_APP_BACKEND_URL` is set correctly (no trailing slash) |
| Admin login fails | Check `/api/health` → `admin_seeded` must be `true` |
| `JWT` warning in logs | Ensure `JWT_SECRET` is at least 32 characters long |
