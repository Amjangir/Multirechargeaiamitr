"""
Backend tests for iteration 4:
- Slab-based commission tiers (min_amount/max_amount)
- Reports endpoint GET /api/reports/summary
- RBAC scope for distributor reports
- Default 2% fallback when no rule matches
"""
import os
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get('REACT_APP_BACKEND_URL')
    if not v:
        try:
            with open('/app/frontend/.env') as fp:
                for line in fp:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        v = line.split('=', 1)[1].strip()
                        break
        except Exception:
            pass
    if not v:
        raise RuntimeError('REACT_APP_BACKEND_URL not configured')
    return v.rstrip('/')

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@rechargepro.com"
ADMIN_PW = "Admin@12345"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_hdrs(http):
    r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _uniq(prefix="TEST"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@rechargepro.example.com"


def _wipe_rules(http, admin_hdrs):
    r = http.get(f"{API}/commissions", headers=admin_hdrs)
    for rule in r.json():
        http.delete(f"{API}/commissions/{rule['id']}", headers=admin_hdrs)


# ---------- Slab-based commission tiers ----------
class TestCommissionSlabs:
    _ids = []

    def test_create_three_slab_rules_for_retailer(self, http, admin_hdrs):
        _wipe_rules(http, admin_hdrs)
        slabs = [
            {"role": "retailer", "rate": 0.03, "min_amount": 0,   "max_amount": 99},
            {"role": "retailer", "rate": 0.04, "min_amount": 100, "max_amount": 499},
            {"role": "retailer", "rate": 0.05, "min_amount": 500},  # unlimited
        ]
        for s in slabs:
            r = http.post(f"{API}/commissions", headers=admin_hdrs, json=s)
            assert r.status_code == 200, r.text
            doc = r.json()
            assert doc["role"] == "retailer"
            assert doc["min_amount"] == s["min_amount"]
            if "max_amount" in s:
                assert doc["max_amount"] == s["max_amount"]
            else:
                assert doc.get("max_amount") in (None,)
            TestCommissionSlabs._ids.append(doc["id"])
        # GET verifies persistence
        rows = http.get(f"{API}/commissions", headers=admin_hdrs).json()
        found = [r for r in rows if r["role"] == "retailer"]
        assert len(found) >= 3

    def test_reject_max_less_than_min(self, http, admin_hdrs):
        r = http.post(f"{API}/commissions", headers=admin_hdrs,
                      json={"role": "retailer", "rate": 0.02, "min_amount": 500, "max_amount": 100})
        assert r.status_code == 400
        body = r.json()
        # should be a readable message (not CRA overlay)
        assert "detail" in body
        assert "min" in str(body["detail"]).lower() or "max" in str(body["detail"]).lower()

    def test_slab_applied_on_recharge_50_200_800(self, http, admin_hdrs):
        # Fresh retailer
        email = _uniq("TEST_slab_retailer")
        pw = "Test@12345"
        reg = http.post(f"{API}/auth/register", json={"name": "Slab R", "email": email, "password": pw})
        assert reg.status_code == 200
        retailer = reg.json()["user"]
        r_hdrs = {"Authorization": f"Bearer {reg.json()['token']}"}

        # Admin credits ₹5000
        cr = http.post(f"{API}/wallet/transfer", headers=admin_hdrs,
                       json={"user_id": retailer["user_id"], "amount": 5000, "kind": "credit"})
        assert cr.status_code == 200

        expected = [(50.0, 0.03, 1.50), (200.0, 0.04, 8.00), (800.0, 0.05, 40.00)]
        for amount, expected_rate, expected_commission in expected:
            tx = None
            for _ in range(4):  # 3 retries on random-fail mock
                r = http.post(f"{API}/recharge", headers=r_hdrs,
                              json={"service": "mobile_prepaid", "operator": "jio",
                                    "number": "9998887770", "amount": amount})
                assert r.status_code == 200, r.text
                tx = r.json()
                if tx["status"] == "success":
                    break
            assert tx is not None and tx["status"] == "success", f"recharge for ₹{amount} failed 4x"
            assert tx["commission_rate"] == expected_rate, \
                f"amount={amount}: expected rate {expected_rate}, got {tx['commission_rate']}"
            assert tx["commission"] == expected_commission, \
                f"amount={amount}: expected ₹{expected_commission}, got ₹{tx['commission']}"

    def test_cleanup_slab_rules(self, http, admin_hdrs):
        for rid in TestCommissionSlabs._ids:
            http.delete(f"{API}/commissions/{rid}", headers=admin_hdrs)


# ---------- Default 2% fallback ----------
class TestDefaultCommission:
    def test_default_2pct_when_no_rule_matches(self, http, admin_hdrs):
        _wipe_rules(http, admin_hdrs)
        email = _uniq("TEST_dflt_retailer")
        pw = "Test@12345"
        reg = http.post(f"{API}/auth/register", json={"name": "Dflt R", "email": email, "password": pw})
        assert reg.status_code == 200
        r_hdrs = {"Authorization": f"Bearer {reg.json()['token']}"}
        uid = reg.json()["user"]["user_id"]

        http.post(f"{API}/wallet/transfer", headers=admin_hdrs,
                  json={"user_id": uid, "amount": 500, "kind": "credit"})

        tx = None
        for _ in range(4):
            r = http.post(f"{API}/recharge", headers=r_hdrs,
                          json={"service": "mobile_prepaid", "operator": "jio",
                                "number": "9998887771", "amount": 100})
            assert r.status_code == 200
            tx = r.json()
            if tx["status"] == "success":
                break
        assert tx["status"] == "success"
        assert tx["commission_rate"] == 0.02
        assert tx["commission"] == 2.00


# ---------- Reports summary endpoint ----------
class TestReportsSummary:
    def test_admin_reports_full_shape(self, http, admin_hdrs):
        r = http.get(f"{API}/reports/summary", headers=admin_hdrs)
        assert r.status_code == 200
        data = r.json()
        for key in ("by_role", "by_service", "by_user", "by_operator", "by_slab", "daily"):
            assert key in data, f"missing key: {key}"
            assert isinstance(data[key], list)
        # by_slab must always return 5 slab rows (0-99, 100-499, 500-999, 1000-4999, 5000+)
        assert len(data["by_slab"]) == 5
        labels = [s["label"] for s in data["by_slab"]]
        assert labels[0] == "0 – 99"
        assert labels[-1] == "5000+"
        for s in data["by_slab"]:
            assert "count" in s and "amount" in s and "commission" in s

    def test_reports_with_date_range(self, http, admin_hdrs):
        r = http.get(f"{API}/reports/summary?start=2020-01-01&end=2020-01-02", headers=admin_hdrs)
        assert r.status_code == 200
        data = r.json()
        # Old date window -> no txs in by_role/by_service (unless db has old data)
        assert isinstance(data["by_role"], list)

    def test_distributor_reports_scope_downline_only(self, http, admin_hdrs):
        # Create a distributor under admin
        dist_email = _uniq("TEST_distributor")
        dist_pw = "Dist@12345"
        r = http.post(f"{API}/users", headers=admin_hdrs, json={
            "name": "Dist RBAC", "email": dist_email, "password": dist_pw, "role": "distributor"
        })
        assert r.status_code == 200
        dist = r.json()
        dist_login = http.post(f"{API}/auth/login", json={"email": dist_email, "password": dist_pw})
        dist_hdrs = {"Authorization": f"Bearer {dist_login.json()['token']}"}

        # Admin credits distributor ₹3000
        http.post(f"{API}/wallet/transfer", headers=admin_hdrs,
                  json={"user_id": dist["user_id"], "amount": 3000, "kind": "credit"})

        # Distributor creates a retailer
        ret_email = _uniq("TEST_dret")
        ret_pw = "Ret@12345"
        r = http.post(f"{API}/users", headers=dist_hdrs, json={
            "name": "Downline Ret", "email": ret_email, "password": ret_pw, "role": "retailer"
        })
        assert r.status_code == 200, r.text
        ret = r.json()
        # Distributor credits retailer
        r = http.post(f"{API}/wallet/transfer", headers=dist_hdrs,
                      json={"user_id": ret["user_id"], "amount": 500, "kind": "credit"})
        assert r.status_code == 200

        # Retailer does 2 recharges
        ret_login = http.post(f"{API}/auth/login", json={"email": ret_email, "password": ret_pw})
        ret_hdrs = {"Authorization": f"Bearer {ret_login.json()['token']}"}
        successes = 0
        for _ in range(8):
            r = http.post(f"{API}/recharge", headers=ret_hdrs, json={
                "service": "mobile_prepaid", "operator": "jio", "number": "9998887772", "amount": 50})
            if r.status_code == 200 and r.json()["status"] == "success":
                successes += 1
            if successes >= 2:
                break
        assert successes >= 1, "Could not do at least one successful recharge in 8 tries"

        # Now distributor fetches reports
        r = http.get(f"{API}/reports/summary", headers=dist_hdrs)
        assert r.status_code == 200
        data = r.json()
        user_ids_in_report = {u["user_id"] for u in data["by_user"]}
        # It must NOT include admin retailers unrelated to this distributor.
        # We assert that ALL user_ids reported ⊆ {distributor, downline_retailer}
        allowed = {dist["user_id"], ret["user_id"]}
        assert user_ids_in_report.issubset(allowed), \
            f"distributor sees non-downline users: {user_ids_in_report - allowed}"

    def test_retailer_reports_only_self(self, http, admin_hdrs):
        # Fresh retailer with one recharge
        email = _uniq("TEST_selfret")
        pw = "Ret@12345"
        reg = http.post(f"{API}/auth/register", json={"name": "Self R", "email": email, "password": pw})
        assert reg.status_code == 200
        retailer = reg.json()["user"]
        r_hdrs = {"Authorization": f"Bearer {reg.json()['token']}"}
        http.post(f"{API}/wallet/transfer", headers=admin_hdrs,
                  json={"user_id": retailer["user_id"], "amount": 300, "kind": "credit"})
        for _ in range(4):
            r = http.post(f"{API}/recharge", headers=r_hdrs, json={
                "service": "mobile_prepaid", "operator": "jio", "number": "9998887773", "amount": 50})
            if r.status_code == 200 and r.json()["status"] == "success":
                break
        r = http.get(f"{API}/reports/summary", headers=r_hdrs)
        assert r.status_code == 200
        data = r.json()
        for u in data["by_user"]:
            assert u["user_id"] == retailer["user_id"], \
                f"retailer sees other user in report: {u}"


# ---------- Reports nav visibility (roles allowed to hit endpoint) ----------
class TestReportsAccess:
    def test_retailer_can_call_reports(self, http, admin_hdrs):
        email = _uniq("TEST_navret")
        pw = "Ret@12345"
        reg = http.post(f"{API}/auth/register", json={"name": "Nav R", "email": email, "password": pw})
        assert reg.status_code == 200
        r = http.get(f"{API}/reports/summary",
                     headers={"Authorization": f"Bearer {reg.json()['token']}"})
        assert r.status_code == 200
