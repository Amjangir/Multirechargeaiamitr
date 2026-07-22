# Auth Testing Playbook (RechargePro)

## JWT (email + password) — primary flow
- Admin login: `POST /api/auth/login` with `{email:"admin@rechargepro.com", password:"Admin@12345"}` → 200, `{token, user}`.
- Public retailer signup: `POST /api/auth/register` with name/email/password → creates retailer, returns token.
- Get current user: `GET /api/auth/me` with `Authorization: Bearer <token>`.
- Token stored client-side in `localStorage` under key `rp_token`.

## Password reset
1. `POST /api/auth/forgot-password` with `{email}` → returns `{reset_token}` (demo returns token in response; production would email it).
2. `POST /api/auth/reset-password` with `{token, new_password}` → updates password + marks token used.
3. Tokens are one-time-use and expire in 1 hour.

## Emergent Google OAuth
- Frontend redirects to `https://auth.emergentagent.com/?redirect=<origin>/auth/callback`.
- After Google, user is returned to `/auth/callback#session_id=…`.
- `AuthCallback.jsx` extracts `session_id`, calls `POST /api/auth/session` with `{session_id}`.
- Backend exchanges with `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data` and returns our JWT token + user (upserts on email).
- Frontend stores JWT in `localStorage` and navigates to `/dashboard`.

## RBAC
- Admin → all endpoints.
- Master-Distributor → creates distributors/retailers, transfers to downline.
- Distributor → creates retailers only, transfers to retailers.
- Retailer → cannot create users; can recharge and see own history.

## Test credentials
- Admin: `admin@rechargepro.com` / `Admin@12345`
- Retailer test accounts should be created via the signup form or admin's Add-user modal.

## Commissions
- Default 2% on success.
- Overrides via `POST /api/commissions` with `{scope via role|user_id, service?, operator?, rate}`.
- Rule resolution order: user+service+operator → user+service → user → global service+operator → global service → role → default.
