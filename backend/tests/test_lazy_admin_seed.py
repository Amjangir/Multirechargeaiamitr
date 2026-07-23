"""
Lazy admin seeding regression tests — iteration 9.

Fixes the 'cannot login after Vercel deploy' bug. The login handler now calls
_ensure_admin_seeded() when the incoming email matches ADMIN_EMAIL, so the
admin is created (or password resynced) on demand even when the startup event
did not fire (Vercel Python Services cold start).

We use mongosh to mutate the users collection directly so we exercise ONLY
the lazy-seed code path — the same behaviour that will apply on Vercel where
startup events are unreliable.
"""
import os
import shlex
import subprocess

import pytest
import requests

# Do NOT split across xdist workers — tests mutate the shared admin row
# and must run serially in declared order.
pytestmark = pytest.mark.xdist_group(name="lazy_admin_seed_serial")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://recharge-hub-184.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@rechargepro.com"
ADMIN_PW = "Admin@12345"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _mongosh(js: str) -> str:
    """Run a JS snippet against the test database via mongosh."""
    cmd = [
        "mongosh",
        f"{MONGO_URL}/{DB_NAME}",
        "--quiet",
        "--eval",
        js,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert out.returncode == 0, f"mongosh failed: {out.stderr}\n{out.stdout}"
    return out.stdout.strip()


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --------------------------------------------------------------------------
# Scenario 1: Admin missing -> lazy seed on login
# --------------------------------------------------------------------------
class TestLazyAdminSeeding:
    def test_delete_admin_then_login_seeds_and_returns_token(self, http):
        # Delete admin user directly in mongo
        _mongosh(f'db.users.deleteOne({{email: "{ADMIN_EMAIL}"}})')
        # Confirm gone
        remaining = _mongosh(f'db.users.countDocuments({{email: "{ADMIN_EMAIL}"}})')
        assert remaining.endswith("0"), f"admin not deleted: {remaining!r}"

        # Login should trigger lazy seed and succeed
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200, f"lazy seed login failed: {r.status_code} {r.text}"
        body = r.json()
        assert "token" in body and isinstance(body["token"], str) and len(body["token"]) > 20
        assert body["user"]["email"] == ADMIN_EMAIL
        assert body["user"]["role"] == "admin"

    def test_second_login_is_idempotent(self, http):
        # Second login: the seed function should not create duplicate rows
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"

        # Only ONE admin row must exist
        count = _mongosh(f'db.users.countDocuments({{email: "{ADMIN_EMAIL}"}})')
        assert count.endswith("1"), f"duplicate admin created: {count!r}"

    def test_wrong_password_still_401_after_seed(self, http):
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401


# --------------------------------------------------------------------------
# Scenario 2: env-driven password resync
# --------------------------------------------------------------------------
class TestPasswordResync:
    def test_stale_hash_resyncs_from_env_on_login(self, http):
        # Corrupt the admin password_hash so it will not verify anything sensible
        _mongosh(
            f'db.users.updateOne({{email: "{ADMIN_EMAIL}"}}, '
            f'{{$set: {{password_hash: "invalid-not-a-bcrypt-hash"}}}})'
        )
        # Login with the env-declared password must succeed because
        # _ensure_admin_seeded resyncs the hash when it does not match.
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200, f"resync login failed: {r.status_code} {r.text}"
        assert r.json()["user"]["role"] == "admin"

    def test_login_after_resync_still_rejects_wrong_pw(self, http):
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": "definitely-wrong"})
        assert r.status_code == 401


# --------------------------------------------------------------------------
# Scenario 3: full authenticated regression flow
# --------------------------------------------------------------------------
class TestPostLoginRegression:
    @pytest.fixture(scope="class")
    def admin_hdrs(self, http):
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['token']}"}

    def test_auth_me(self, http, admin_hdrs):
        r = http.get(f"{API}/auth/me", headers=admin_hdrs)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body["role"] == "admin"

    def test_wallet_balance(self, http, admin_hdrs):
        r = http.get(f"{API}/wallet/balance", headers=admin_hdrs)
        assert r.status_code == 200
        assert "balance" in r.json()
        assert isinstance(r.json()["balance"], (int, float))

    def test_operators(self, http, admin_hdrs):
        r = http.get(f"{API}/operators", headers=admin_hdrs)
        assert r.status_code == 200
        data = r.json()
        for k in ("mobile_prepaid", "dth", "electricity", "data_card"):
            assert k in data and isinstance(data[k], list) and len(data[k]) > 0


# --------------------------------------------------------------------------
# Scenario 4: frontend fallback string sanity
# --------------------------------------------------------------------------
class TestFrontendFallback:
    def test_api_js_has_empty_fallback(self):
        with open("/app/frontend/src/lib/api.js") as f:
            src = f.read()
        assert 'process.env.REACT_APP_BACKEND_URL || ""' in src, (
            "api.js must fall back to empty string so relative /api/* URLs work on Vercel"
        )
        assert 'export const API = `${BACKEND_URL}/api`' in src


# --------------------------------------------------------------------------
# Scenario 5: server.py wiring (lifespan + startup + login lazy seed)
# --------------------------------------------------------------------------
class TestServerWiring:
    def test_server_has_lifespan_and_startup(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        assert "from contextlib import asynccontextmanager" in src
        assert "@asynccontextmanager" in src
        assert "async def lifespan(_app" in src
        assert "await _ensure_admin_seeded()" in src
        assert "lifespan=lifespan" in src
        # legacy startup path still wired so local supervisor works
        assert '@app.on_event("startup")' in src
