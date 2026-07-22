# RechargePro — Product Requirements Document

## Original problem statement
> "i want a multirecharge software with multiple role (Admin, Master-distributor, distributor, retailer), and with all settings in dot net 8 and with best front end design template"

User accepted implementation in React + FastAPI + MongoDB (dot net not supported on this platform).

## Chosen options
- Services: Mobile Prepaid + DTH + Electricity + Data Card
- Recharge API: Mock/simulated (~90% success rate, 2% flat commission)
- Payments: Wallet-based only (no gateway)
- Auth: JWT (email + password). Google login deferred to a future iteration.
- Theme: Modern fintech dark theme (Outfit + Manrope fonts, cyan accent)

## Architecture
- Backend: FastAPI + Motor (async MongoDB), JWT (PyJWT), bcrypt hashing
- Frontend: React 19, Tailwind, Shadcn tokens, Recharts, sonner (toasts), lucide-react
- Data: `users`, `transactions`, `wallet_ledger` collections in MongoDB
- Role hierarchy: admin > master_distributor > distributor > retailer
- Downline scoping enforced server-side on `/users`, `/transactions`, `/stats/summary`

## User personas
- **Admin** — platform owner. Adds MDs, credits/debits any wallet, sees all activity.
- **Master Distributor** — regional lead. Adds distributors, funds them, sees region-wide reports.
- **Distributor** — territory lead. Adds retailers, tops up their wallets.
- **Retailer** — shop owner. Runs the recharges, earns commissions.

## What's been implemented (2026-02)
- JWT auth: register (public retailer), login, /auth/me, logout
- Admin seeding from env on startup
- Role-based user creation and downline scoping
- Wallet: balance, ledger, admin credit/debit, distributor→downline transfer
- Recharge engine (mock) with commission credit on success
- Operator catalogue for 4 services
- Transactions list with status + service filters
- Dashboard with role-aware metrics + 7-day volume chart + user counts
- Landing, login, signup pages (dark fintech theme)
- Sidebar shell + protected routes

## P0 backlog (next iteration)
- Google OAuth (Emergent) login as alternative to JWT
- Per-operator commission rules (currently flat 2%)
- Password reset flow

## P1 backlog
- CSV export of transactions
- Bulk user import
- Real recharge gateway integration slot

## P2
- Notifications
- Audit log for admin actions
