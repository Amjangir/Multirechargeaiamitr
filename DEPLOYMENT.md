# Vercel Deployment Guide — RechargePro

Your app is 2 services. Vercel hosts the **frontend only**. The backend must run separately on a Python host (Render / Railway / Fly.io).

## 1. Deploy Backend first (Render free tier — recommended)

1. Sign in at https://render.com and connect your GitHub repo.
2. **New → Web Service**.
3. Root directory: `backend`
4. Runtime: Python 3
5. Build command:
   ```
   pip install -r requirements.txt
   ```
6. Start command:
   ```
   uvicorn server:app --host 0.0.0.0 --port $PORT
   ```
7. Environment variables:
   | Key | Value |
   |---|---|
   | `MONGO_URL` | your MongoDB Atlas connection string |
   | `DB_NAME` | `rechargepro` (or any name) |
   | `JWT_SECRET` | a random 64-char hex |
   | `ADMIN_EMAIL` | `admin@rechargepro.com` |
   | `ADMIN_PASSWORD` | `Admin@12345` |
   | `CORS_ORIGINS` | your Vercel frontend URL, e.g. `https://rechargepro.vercel.app` |
8. Deploy. Copy the public URL (e.g. `https://rechargepro-api.onrender.com`).

## 2. Deploy Frontend on Vercel

1. Sign in at https://vercel.com and import your GitHub repo.
2. **Root directory**: set to `frontend`  ← IMPORTANT
3. Vercel auto-detects Create React App via the `vercel.json` here.
4. Environment variables (Project → Settings → Environment Variables):
   | Key | Value |
   |---|---|
   | `REACT_APP_BACKEND_URL` | your Render backend URL (from step 1) |
5. Click **Deploy**. Done.

## 3. MongoDB Atlas (free)

1. Sign up at https://www.mongodb.com/cloud/atlas
2. Create a free M0 cluster.
3. Database Access → add a user with a strong password.
4. Network Access → add `0.0.0.0/0` (allow Render to connect).
5. Copy the connection string → paste as `MONGO_URL` on Render.

## What this `vercel.json` does

- **SPA rewrites** — every route (`/dashboard`, `/login`, etc.) is served `index.html` so React Router works after page refresh.
- **Immutable cache** for `/static/*` — faster loads.
- **Build config** — Vercel uses `yarn` (matches your local setup, not npm).

## Full-stack on Vercel (advanced, not recommended)

Vercel supports Python serverless functions but your FastAPI backend uses Motor (async MongoDB) which needs persistent connections. Serverless is a poor fit. Stick with Render/Railway for the backend.
