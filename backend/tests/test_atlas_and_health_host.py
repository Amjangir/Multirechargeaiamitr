"""
Iteration 11 regression tests.

Focus:
  (a) /api/health.mongo.host present, points at Atlas hostname, and does NOT
      leak credentials (no '@', no password substring, no 'localhost').
  (b) /api/health.env.MONGO_URL_set == True locally.
  (c) Full Atlas-backed flow: admin login -> create retailer -> credit wallet ->
      retailer login -> mobile_prepaid Airtel recharge -> verify commission and
      transaction persistence.
  (d) Regression on /api/wallet/ledger, /api/operators, /api/reports/summary,
      /api/commissions with admin token.
  (e) Static code-path checks:
        - server.py must contain _MONGO_URL_MISSING import-time flag logic.
        - login 500 handler must contain the 'MONGO_URL env var is not set'
          hint string plus a 'localhost:27017' guard clause.

All created test data is prefixed with 'itest_' so the user can clean it up.
Runs sequentially by nature (Atlas is the shared store).
"""
import os
import re
import time
import uuid
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://recharge-hub-184.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@rechargepro.com"
ADMIN_PW = "Admin@12345"

SERVER_PY = Path("/app/backend/server.py")


# ---------- Shared session + admin token ----------
@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(http):
    r = http.post(f"{API}/auth/login",
                  json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_hdrs(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- (a) /api/health.mongo.host ----------
class TestHealthHostField:
    def test_health_200(self, http):
        r = http.get(f"{API}/health")
        assert r.status_code == 200, r.text

    def test_mongo_host_present_and_atlas(self, http):
        body = http.get(f"{API}/health").json()
        mongo = body["mongo"]
        assert "host" in mongo, "mongo.host field is missing"
        host = mongo["host"]
        assert isinstance(host, str) and host, "mongo.host must be non-empty string"
        # Must be Atlas hostname
        assert "mongodb.net" in host, f"expected Atlas host, got {host!r}"
        # Redaction: no user/pass leaked
        assert "@" not in host, f"mongo.host leaks credentials: contains '@' -> {host!r}"
        assert "localhost" not in host.lower(), f"unexpected localhost: {host!r}"
        # No connection-string scheme leaked either
        assert not host.startswith("mongodb"), f"host must be bare hostname, got {host!r}"

    def test_mongo_host_matches_expected_atlas_cluster(self, http):
        host = http.get(f"{API}/health").json()["mongo"]["host"]
        # Expected sub-domain (from PRD note): atlas-purple-ball.wvr7dp7.mongodb.net
        assert "atlas-purple-ball" in host or "wvr7dp7" in host, (
            f"host does not look like the configured cluster: {host!r}"
        )

    def test_env_MONGO_URL_set_true(self, http):
        env = http.get(f"{API}/health").json()["env"]
        assert env["MONGO_URL_set"] is True

    def test_mongo_ok_and_admin_seeded_on_atlas(self, http):
        mongo = http.get(f"{API}/health").json()["mongo"]
        assert mongo["ok"] is True
        assert mongo["error"] is None
        assert mongo["admin_seeded"] is True
        assert mongo["user_count"] >= 1


# ---------- (b) Login on Atlas ----------
class TestAdminLoginOnAtlas:
    def test_admin_login_success(self, http):
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("token"), str) and len(body["token"]) > 20
        assert body["user"]["email"] == ADMIN_EMAIL
        assert body["user"]["role"] == "admin"

    def test_admin_login_wrong_password_401(self, http):
        r = http.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": "definitely-wrong"})
        assert r.status_code == 401
        assert "Invalid email or password" in r.json().get("detail", "")


# ---------- (c) End-to-end Atlas flow: create retailer, credit, recharge ----------
# Module-level constants + shared state so the class fixture works without
# instance-method surprises (pytest 10 deprecation).
RUN_ID = uuid.uuid4().hex[:8]
RETAILER_EMAIL = f"itest_retailer_{RUN_ID}@example.com"
RETAILER_PW = "Retailer@12345"
RETAILER_NAME = f"itest Retailer {RUN_ID}"


@pytest.fixture(scope="module")
def created_retailer(http, admin_hdrs):
    payload = {
        "name": RETAILER_NAME,
        "email": RETAILER_EMAIL,
        "password": RETAILER_PW,
        "role": "retailer",
        "phone": "9999900000",
    }
    r = http.post(f"{API}/users", json=payload, headers=admin_hdrs)
    assert r.status_code == 200, f"create retailer failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["email"] == RETAILER_EMAIL
    assert body["role"] == "retailer"
    assert body["name"] == RETAILER_NAME
    assert body["wallet_balance"] == 0.0
    assert isinstance(body["user_id"], str) and body["user_id"].startswith("ret_")
    return body


@pytest.fixture(scope="module")
def retailer_token(http, created_retailer):
    r = http.post(f"{API}/auth/login",
                  json={"email": RETAILER_EMAIL, "password": RETAILER_PW})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == RETAILER_EMAIL
    assert body["user"]["role"] == "retailer"
    return body["token"]


@pytest.fixture(scope="module")
def retailer_hdrs(retailer_token):
    return {"Authorization": f"Bearer {retailer_token}"}


class TestFullAtlasFlow:

    def test_1_retailer_visible_in_list(self, http, admin_hdrs, created_retailer):
        r = http.get(f"{API}/users", headers=admin_hdrs)
        assert r.status_code == 200
        emails = {u["email"] for u in r.json()}
        assert RETAILER_EMAIL in emails, "created retailer not in /api/users"

    def test_2_credit_retailer_wallet(self, http, admin_hdrs, created_retailer):
        r = http.post(
            f"{API}/wallet/transfer",
            json={
                "user_id": created_retailer["user_id"],
                "amount": 500.0,
                "kind": "credit",
                "note": "itest seed credit",
            },
            headers=admin_hdrs,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_3_retailer_login(self, http, retailer_token):
        # fixture already validated login; assert token shape here
        assert isinstance(retailer_token, str) and len(retailer_token) > 20

    def test_4_retailer_wallet_balance_500(self, http, retailer_hdrs):
        r = http.get(f"{API}/wallet/balance", headers=retailer_hdrs)
        assert r.status_code == 200
        bal = r.json()["balance"]
        assert bal == 500.0, f"expected wallet 500.0 after admin credit, got {bal}"

    def test_5_recharge_airtel_100(self, http, retailer_hdrs):
        # Recharge success is ~90% mocked. Retry a few times to isolate the
        # commission-rate assertion from mock flakiness.
        tx = None
        for attempt in range(8):
            r = http.post(
                f"{API}/recharge",
                json={
                    "service": "mobile_prepaid",
                    "operator": "airtel",
                    "number": "9999911111",
                    "amount": 100.0,
                    "circle": "DL",
                },
                headers=retailer_hdrs,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["service"] == "mobile_prepaid"
            assert body["operator"] == "airtel"
            assert body["amount"] == 100.0
            assert body["status"] in ("success", "failed")
            if body["status"] == "success":
                tx = body
                break
        assert tx is not None, "Recharge never succeeded after 8 attempts (mock ~90%)"
        # Default commission = 0.02 -> 2.00 on amount 100
        assert tx["commission_rate"] == pytest.approx(0.02), (
            f"expected default 2% commission, got {tx['commission_rate']}"
        )
        assert tx["commission"] == pytest.approx(2.00), (
            f"expected commission 2.00, got {tx['commission']}"
        )
        assert isinstance(tx.get("operator_ref"), str) and tx["operator_ref"].startswith("TXN")
        TestFullAtlasFlow._tx_id = tx["id"]
        TestFullAtlasFlow._tx_ref = tx["operator_ref"]

    def test_6_transaction_persisted(self, http, retailer_hdrs):
        r = http.get(f"{API}/transactions", headers=retailer_hdrs)
        assert r.status_code == 200
        txs = r.json()
        assert isinstance(txs, list) and len(txs) >= 1
        our = next((t for t in txs if t.get("id") == TestFullAtlasFlow._tx_id), None)
        assert our is not None, (
            f"tx {TestFullAtlasFlow._tx_id} not found in retailer /transactions"
        )
        assert our["operator"] == "airtel"
        assert our["service"] == "mobile_prepaid"
        assert our["status"] == "success"
        assert our["operator_ref"] == TestFullAtlasFlow._tx_ref

    def test_7_retailer_ledger_has_recharge_and_commission(self, http, retailer_hdrs):
        r = http.get(f"{API}/wallet/ledger", headers=retailer_hdrs)
        assert r.status_code == 200
        rows = r.json()
        types = [row["type"] for row in rows]
        assert "recharge" in types, f"missing 'recharge' ledger entry; got {types}"
        assert "commission" in types, f"missing 'commission' ledger entry; got {types}"
        assert "transfer_in" in types or "credit" in types, (
            f"missing incoming credit ledger entry; got {types}"
        )


# ---------- (d) Regression on admin-scoped endpoints ----------
class TestAdminRegression:
    def test_wallet_ledger(self, http, admin_hdrs):
        r = http.get(f"{API}/wallet/ledger", headers=admin_hdrs)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_operators(self, http, admin_hdrs):
        r = http.get(f"{API}/operators", headers=admin_hdrs)
        assert r.status_code == 200
        data = r.json()
        for k in ("mobile_prepaid", "dth", "electricity", "data_card"):
            assert k in data and isinstance(data[k], list) and len(data[k]) > 0
        # airtel present under mobile_prepaid
        airtel = next((o for o in data["mobile_prepaid"] if o["code"] == "airtel"), None)
        assert airtel is not None, "airtel operator missing"

    def test_reports_summary(self, http, admin_hdrs):
        r = http.get(f"{API}/reports/summary", headers=admin_hdrs)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("by_role", "by_service", "by_operator", "by_user", "by_slab", "daily"):
            assert k in body, f"missing key {k} in /reports/summary"
            assert isinstance(body[k], list)

    def test_commissions_list(self, http, admin_hdrs):
        r = http.get(f"{API}/commissions", headers=admin_hdrs)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- (e) Static source-code checks (module-level & login handler) ----------
class TestServerSourceGuards:
    """The reset-scenario cannot be run (would require unsetting env + restart).
    Instead assert the code paths exist statically per the review request."""

    @pytest.fixture(scope="class")
    def src(self):
        return SERVER_PY.read_text(encoding="utf-8")

    def test_module_has_MONGO_URL_MISSING_flag(self, src):
        assert "_MONGO_URL_MISSING" in src, "_MONGO_URL_MISSING flag not found"
        # Must be derived from `'MONGO_URL' not in os.environ`
        assert re.search(r"_MONGO_URL_MISSING\s*=\s*['\"]MONGO_URL['\"]\s+not\s+in\s+os\.environ",
                         src), "flag should be `'MONGO_URL' not in os.environ`"

    def test_startup_log_line_prints_mongo_host(self, src):
        # Logger call includes the redacted host
        assert "Mongo config" in src, "startup log line missing"
        assert "host=" in src, "log should include host="
        # And a WARNING branch when missing
        assert "MONGO_URL env var is NOT SET" in src, "missing-env warning not found"

    def test_login_500_hint_string(self, src):
        # exact hint substring from the review request
        assert "MONGO_URL env var is not set on this deployment" in src, (
            "login 500 handler must include the MONGO_URL diagnostic hint"
        )

    def test_login_500_hint_guarded_by_localhost_check(self, src):
        # The hint is appended when the exception message mentions localhost:27017
        assert 'localhost:27017' in src, (
            "login handler must guard the hint with a 'localhost:27017' substring check"
        )

    def test_health_endpoint_redacts_password(self, src):
        # host field derived from split('@')[-1] which strips creds
        assert 'split("@")' in src or "split('@')" in src, (
            "health endpoint must redact user/password via split('@')"
        )
