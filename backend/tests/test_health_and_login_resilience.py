"""
Iteration 10 regression tests.

Covers the deploy-only 500-on-login fix:
  (a) NEW GET /api/health diagnostic endpoint (env + mongo ping + admin_seeded + user_count).
  (b) Login endpoint no longer returns 500 when _ensure_admin_seeded encounters
      a bad DB state (empty/garbage password_hash). It self-heals and returns 200
      on the NEXT attempt (or 401 if user supplies wrong password).
  (c) Regression: /api/wallet/balance, /api/operators, /api/transactions still
      work with an admin token.

Tests mutate the shared admin row via mongosh -> must run serially.
"""
import os
import subprocess
import time

import pytest
import requests

pytestmark = pytest.mark.xdist_group(name="health_login_serial")

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
    out = subprocess.run(
        ["mongosh", f"{MONGO_URL}/{DB_NAME}", "--quiet", "--eval", js],
        capture_output=True, text=True, timeout=15,
    )
    assert out.returncode == 0, f"mongosh failed: {out.stderr}\n{out.stdout}"
    return out.stdout.strip()


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- /api/health ----------
class TestHealthEndpoint:
    def test_health_returns_200(self, http):
        r = http.get(f"{API}/health")
        assert r.status_code == 200, f"unexpected: {r.status_code} {r.text}"

    def test_health_shape(self, http):
        body = http.get(f"{API}/health").json()
        # app + time
        assert body.get("app") == "rechargepro-api"
        assert isinstance(body.get("time"), str) and len(body["time"]) > 10
        # env block: every key present and boolean
        env = body.get("env")
        assert isinstance(env, dict)
        for k in ("MONGO_URL_set", "DB_NAME_set", "JWT_SECRET_set",
                  "ADMIN_EMAIL_set", "ADMIN_PASSWORD_set"):
            assert k in env, f"missing env key: {k}"
            assert isinstance(env[k], bool), f"env.{k} must be bool"
        # mongo block
        mongo = body.get("mongo")
        assert isinstance(mongo, dict)
        for k in ("ok", "admin_seeded"):
            assert isinstance(mongo.get(k), bool), f"mongo.{k} must be bool"
        assert isinstance(mongo.get("user_count"), int)
        assert mongo["user_count"] >= 0
        # error should be nullable string
        assert mongo.get("error") is None or isinstance(mongo["error"], str)

    def test_health_env_all_true_locally(self, http):
        env = http.get(f"{API}/health").json()["env"]
        assert env["MONGO_URL_set"] is True
        assert env["DB_NAME_set"] is True
        assert env["JWT_SECRET_set"] is True
        assert env["ADMIN_EMAIL_set"] is True
        assert env["ADMIN_PASSWORD_set"] is True

    def test_health_mongo_ok_and_admin_seeded(self, http):
        mongo = http.get(f"{API}/health").json()["mongo"]
        assert mongo["ok"] is True
        assert mongo["error"] is None
        assert mongo["admin_seeded"] is True
        assert mongo["user_count"] >= 1

    def test_health_no_auth_required(self, http):
        # No Authorization header, should still work
        s = requests.Session()
        r = s.get(f"{API}/health")
        assert r.status_code == 200

    def test_health_stable_under_burst(self, http):
        for i in range(3):
            r = http.get(f"{API}/health")
            assert r.status_code == 200, f"burst[{i}] failed: {r.status_code}"
            body = r.json()
            assert body["mongo"]["ok"] is True


# ---------- Login regression ----------
class TestLoginRegression:
    def test_login_success(self, http):
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert isinstance(body.get("token"), str) and len(body["token"]) > 20
        assert body["user"]["email"] == ADMIN_EMAIL
        assert body["user"]["role"] == "admin"

    def test_login_wrong_password_401(self, http):
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": "definitely-wrong"})
        assert r.status_code == 401
        # error message from server
        detail = r.json().get("detail", "")
        assert "Invalid email or password" in detail


# ---------- Login resilience: garbage hash / empty hash must NOT 500 ----------
class TestLoginResilience:
    def test_garbage_hash_login_returns_200(self, http):
        # Set a garbage (non-bcrypt) hash
        _mongosh(
            f'db.users.updateOne({{email: "{ADMIN_EMAIL}"}}, '
            f'{{$set: {{password_hash: "not-a-bcrypt"}}}})'
        )
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        # Self-heal via _ensure_admin_seeded resync
        assert r.status_code == 200, f"expected 200 self-heal, got {r.status_code} {r.text}"
        assert r.json()["user"]["role"] == "admin"

    def test_garbage_hash_then_wrong_pw_returns_401_not_500(self, http):
        _mongosh(
            f'db.users.updateOne({{email: "{ADMIN_EMAIL}"}}, '
            f'{{$set: {{password_hash: "not-a-bcrypt"}}}})'
        )
        # After the seed function resyncs the hash from env, wrong password is 401
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code in (401,), f"expected 401 not 500, got {r.status_code} {r.text}"

    def test_empty_hash_no_500(self, http):
        # Simulate the RCA case: password_hash == ''
        _mongosh(
            f'db.users.updateOne({{email: "{ADMIN_EMAIL}"}}, '
            f'{{$set: {{password_hash: "", status: "active"}}}})'
        )
        # Correct env password -> _ensure_admin_seeded resyncs -> 200
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text}"

    def test_admin_row_healed_after_resilience_tests(self, http):
        # Final state must be a working admin login
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200


# ---------- Post-login regression: wallet/operators/transactions ----------
class TestAuthenticatedRegression:
    @pytest.fixture(scope="class")
    def admin_hdrs(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}

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

    def test_transactions(self, http, admin_hdrs):
        r = http.get(f"{API}/transactions", headers=admin_hdrs)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_auth_me(self, http, admin_hdrs):
        r = http.get(f"{API}/auth/me", headers=admin_hdrs)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body["role"] == "admin"


# ---------- Ensure admin left seeded ----------
def test_zzz_final_admin_state():
    """Runs last (alphabetical zzz) — confirm admin row is single & valid."""
    count = _mongosh(f'db.users.countDocuments({{email: "{ADMIN_EMAIL}"}})')
    assert count.endswith("1"), f"expected exactly 1 admin, got {count!r}"
