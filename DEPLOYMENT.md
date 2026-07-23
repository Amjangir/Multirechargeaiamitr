# Vercel Deployment Guide — RechargePro (Multi-Service)

Your repo has two services: `frontend/` (React) and `backend/` (FastAPI). Vercel's newer **`services`** schema deploys both from **one** `vercel.json` at the repository root.

## 1. Push your repo to GitHub

Click "Save to GitHub" in the Emergent chat to push everything.

## 2. Import the repo on Vercel

- Sign in at https://vercel.com → **Add New → Project** → Import your GitHub repo.
- **Root Directory**: leave as `./` (the root).
- Vercel will read `/vercel.json` and detect both services automatically:
  - `frontend` (create-react-app in `frontend/`, built with yarn)
  - `backend` (FastAPI in `backend/`, entrypoint `server:app`)

## 3. Add environment variables

Add these in Vercel → **Project → Settings → Environment Variables**. Attach each variable to the correct service (Vercel lets you pick).

### Backend service (`backend`)
| Key | Value |
|---|---|
| `MONGO_URL` | connection string from MongoDB Atlas |
| `DB_NAME` | `rechargepro` |
| `JWT_SECRET` | random 64-char hex |
| `ADMIN_EMAIL` | `admin@rechargepro.com` |
| `ADMIN_PASSWORD` | `Admin@12345` |
| `CORS_ORIGINS` | `*` (same-origin via rewrites so this is safe) |

### Frontend service (`frontend`)
| Key | Value |
|---|---|
| `REACT_APP_BACKEND_URL` | leave empty OR set to your Vercel project URL — see note below |

**Note on `REACT_APP_BACKEND_URL`**: Because our `vercel.json` rewrites `/api/*` from the same origin to the backend service, your frontend can just call `/api/...`. But this code currently uses `${REACT_APP_BACKEND_URL}/api/...`, so set `REACT_APP_BACKEND_URL` to your Vercel project URL (e.g. `https://rechargepro.vercel.app`).

## 4. MongoDB Atlas (free 512 MB)

1. Sign up at https://www.mongodb.com/cloud/atlas
2. Create a free M0 cluster.
3. Database Access → add a user with a password.
4. Network Access → allow `0.0.0.0/0` so Vercel can connect.
5. Copy the connection string → set as `MONGO_URL` on the backend service.

## 5. Deploy

Click **Deploy**. Vercel builds both services from the single root `vercel.json`.

## How the routing works

```
Public request           →  Vercel rewrites  →  Service
GET  /                   →  /                →  frontend (React)
GET  /dashboard          →  /dashboard       →  frontend (React SPA)
POST /api/auth/login     →  /api/auth/login  →  backend (FastAPI)
GET  /api/wallet/balance →  /api/wallet/…    →  backend (FastAPI)
```

The backend is **internal**; it's only reachable through the `/api/*` rewrite — this gives you same-origin API calls (no CORS pain).

## Troubleshooting

- **"vercel.json required" error in the Vercel UI**: this is fixed — `vercel.json` is now at the repo root.
- **Backend cold start on first request**: expected on Vercel Services free tier. Second request onward is fast.
- **500 on API calls**: check the backend service logs in Vercel → Deployments → Functions.
- **`ModuleNotFoundError` on backend**: make sure `backend/requirements.txt` is up to date. It already is.
