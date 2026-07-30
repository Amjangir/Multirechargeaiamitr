# Project Analysis and Bug Report

## What this project is

`Multirechargeaiamitr` is a full-stack multi-role recharge platform.

- Frontend: React CRA app in `frontend/`
- Backend: FastAPI app in `backend/server.py`
- Database: MongoDB via Motor
- Core modules:
  - authentication and Google session exchange
  - role hierarchy: admin, master distributor, distributor, retailer
  - wallet credit/transfer ledger
  - recharge workflow with commission rules
  - reporting and user management

The product appears to be an admin/upline dashboard for managing recharge agents, balances, commissions, transactions, and reports.

## Verification status

I reviewed the codebase and existing tests, but I could not run the backend test suite fully in this machine.

- Local Python is `3.9.13`
- Backend `pyproject.toml` requires `>=3.11`
- `pytest` is not installed in the current shell

Because of that, the findings below are a mix of:

- confirmed code-level bugs/security issues
- deployment/setup issues
- execution risks inferred directly from implementation

## High severity bugs

### 1. Password reset token is returned directly to the caller

- File: `backend/server.py:604-619`
- Risk: account takeover

`POST /api/auth/forgot-password` generates a valid reset token and returns it in the API response:

- token is created at `backend/server.py:607`
- token is persisted at `backend/server.py:610`
- token is returned at `backend/server.py:619`

Any caller who knows a valid user email can request a reset token and immediately reset that account without email ownership proof. This is the most serious issue in the project.

## 2. Role escalation bug in status toggle endpoint

- File: `backend/server.py:357-361`
- Risk: distributors/master distributors can block arbitrary users

`PATCH /api/users/{user_id}/status` only checks the caller role. It does not verify that the target user belongs to the caller’s downline and does not protect privileged targets. A distributor or master distributor can potentially block users outside their scope, including higher-value accounts if the `user_id` is known.

## 3. CORS is configured with credentials enabled and wildcard origins

- File: `backend/server.py:900-901`
- Risk: browser auth failures and unsafe cross-origin policy

The app sets:

- `allow_credentials=True`
- `allow_origins=os.environ.get("CORS_ORIGINS", "*").split(",")`

This is an invalid combination for normal credentialed browser CORS. It can produce broken browser behavior, and the deployment guide currently recommends `CORS_ORIGINS=*`, which reinforces the issue.

## Medium severity bugs

### 4. Distributor wallet API ignores `kind` and does not honor debit semantics

- File: `backend/server.py:376-425`
- Risk: broken API contract, unexpected money movement

`WalletTxInput` supports `kind: "credit" | "debit"`, but in the distributor/master-distributor branch the code always:

- debits the sender
- credits the target

The `kind` field is ignored there. If a client sends `kind="debit"`, the transfer still behaves like a credit to the target. That is a real functional bug.

### 5. Wallet transfer and recharge updates are not atomic

- Files:
  - `backend/server.py:388-401`
  - `backend/server.py:418-425`
  - `backend/server.py:492-512`
- Risk: inconsistent balances and ledgers under failure/concurrency

Balance updates and ledger writes are split across multiple independent Mongo operations with no transaction/session handling. If one write succeeds and the next fails, the wallet balance and ledger can diverge. Concurrent requests can also overspend balances because the code does read-then-write logic without atomic guard conditions.

### 6. Recharge success is random in the main business flow

- File: `backend/server.py:474`
- Risk: nondeterministic production behavior and unreliable testing

Recharge outcome is decided by `random.random() < 0.9`. That is acceptable for a demo stub, but it is currently wired into the real endpoint instead of a sandbox/mock layer. Users can submit the same recharge and get arbitrary success/failure behavior.

### 7. Blocking synchronous HTTP call inside async FastAPI route

- File: `backend/server.py:645-654`
- Risk: event-loop blocking under load

`POST /api/auth/session` is an async route, but it uses synchronous `requests.get(...)`. Under traffic, this can block worker execution and reduce throughput. This should use an async HTTP client or be moved behind a threadpool explicitly.

### 8. Demo admin credentials are exposed in the login page

- File: `frontend/src/pages/Login.jsx:92-93`
- Risk: unauthorized access if the seeded admin exists in deployment

The login screen displays:

- `admin@rechargepro.com / Admin@12345`

The deployment guide also instructs using the same credentials. If the deployed environment follows those defaults, admin access is effectively public.

## Low severity bugs and quality issues

### 9. Duplicate startup logic

- File: `backend/server.py`
- Areas:
  - lifespan startup near `:58-70`
  - `@app.on_event("startup")` near `:171-180`

Indexes and admin seeding are executed in both the lifespan handler and the old startup event. This is not the highest-risk bug, but it is redundant and increases maintenance confusion.

### 10. Requirements and runtime config are inconsistent

- Files:
  - `backend/pyproject.toml:5`
  - `backend/requirements.txt`
- Problems:
  - project requires Python `>=3.11`
  - current environment here is Python `3.9.13`
  - `requirements.txt` contains many packages not reflected in `pyproject.toml`

This makes setup, deployment parity, and local testing less reliable. The failed test execution in this environment exposed that gap immediately.

### 11. Test suite is environment-coupled to external services

- Files: `backend/tests/*.py`
- Risk: brittle CI and local verification

Several tests depend on:

- a live backend URL
- seeded admin credentials
- Mongo shell access in some cases
- mutable shared database state

That makes the test suite hard to run locally and increases false negatives outside the original deployment context.

## Notes on project quality

The app is functionally broad for a small codebase, but the backend is concentrated in one large file. That increases regression risk because auth, finance, reporting, and admin behavior are all tightly coupled.

The frontend structure is cleaner than the backend, but most real business guarantees currently depend on backend correctness, and the backend has several security and consistency gaps.

## Recommended fix order

1. Remove reset token from `forgot-password` response and implement real reset delivery.
2. Lock down `/users/{user_id}/status` with target-scope validation.
3. Fix CORS configuration and stop using `*` with credentials.
4. Correct wallet transfer semantics and add atomic balance protections.
5. Replace random recharge logic with an explicit mock gateway abstraction.
6. Replace synchronous `requests` in async routes.
7. Remove exposed demo admin credentials from UI and deployment docs.
8. Split `backend/server.py` into auth, users, wallet, recharge, commissions, and reports modules.

## Final assessment

This is a recharge/distributor management platform prototype with meaningful admin, wallet, and reporting features. The biggest problems are not visual or structural; they are security and money-flow correctness issues. The most urgent bugs are the public password reset token, unsafe status-toggle authorization, invalid CORS setup, and non-atomic wallet operations.
