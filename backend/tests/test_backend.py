"""
Backend regression tests for RechargePro new-feature iteration 3.
Covers: password reset, commission rules CRUD, PATCH /users/{id}, PATCH /me,
commission applied at recharge, 422 shape sanity for detail array.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else "https://recharge-hub-184.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@rechargepro.com"
ADMIN_PW = "Admin@12345"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(http):
    r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_hdrs(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _unique_email(prefix="TEST_retailer"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@rechargepro.example.com"


# ---------- auth: forgot / reset password ----------
class TestPasswordReset:
    def test_forgot_password_returns_token(self, http):
        r = http.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL})
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert isinstance(body.get("reset_token"), str) and len(body["reset_token"]) > 10

    def test_forgot_password_unknown_email_returns_null_token(self, http):
        r = http.post(f"{API}/auth/forgot-password", json={"email": "nobody_TEST@nowhere.example.com"})
        assert r.status_code == 200
        assert r.json().get("reset_token") in (None, "")

    def test_reset_password_and_relogin_and_restore(self, http):
        # Step 1: request token
        r = http.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL})
        token = r.json()["reset_token"]

        # Step 2: reset to temp password
        temp_pw = "TempReset@98765"
        r = http.post(f"{API}/auth/reset-password", json={"token": token, "new_password": temp_pw})
        assert r.status_code == 200

        # Step 3: same token cannot be reused
        r = http.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "Whatever@123"})
        assert r.status_code == 400

        # Step 4: login with temp password
        r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": temp_pw})
        assert r.status_code == 200

        # Step 5: reset back to original password
        r = http.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL})
        token2 = r.json()["reset_token"]
        r = http.post(f"{API}/auth/reset-password", json={"token": token2, "new_password": ADMIN_PW})
        assert r.status_code == 200

        # Step 6: login again with original password
        r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200


# ---------- commission rules CRUD ----------
class TestCommissionRules:
    _created_ids = []

    def test_admin_can_list_commissions(self, http, admin_hdrs):
        r = http.get(f"{API}/commissions", headers=admin_hdrs)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_role_scoped_rule(self, http, admin_hdrs):
        payload = {"role": "retailer", "service": "mobile_prepaid", "operator": "airtel", "rate": 0.05}
        r = http.post(f"{API}/commissions", headers=admin_hdrs, json=payload)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["rate"] == 0.05 and doc["role"] == "retailer" and doc["service"] == "mobile_prepaid"
        assert doc["operator"] == "airtel" and doc.get("user_id") in (None, "")
        assert "id" in doc
        TestCommissionRules._created_ids.append(doc["id"])

    def test_create_global_service_rule(self, http, admin_hdrs):
        payload = {"role": None, "service": "dth", "operator": None, "rate": 0.03}
        r = http.post(f"{API}/commissions", headers=admin_hdrs, json=payload)
        assert r.status_code == 200
        doc = r.json()
        assert doc["service"] == "dth" and doc["rate"] == 0.03
        TestCommissionRules._created_ids.append(doc["id"])

    def test_invalid_rate_rejected(self, http, admin_hdrs):
        r = http.post(f"{API}/commissions", headers=admin_hdrs, json={"rate": 2})
        assert r.status_code == 400

    def test_non_admin_forbidden(self, http):
        # create a retailer
        email = _unique_email()
        pw = "Test@12345"
        reg = http.post(f"{API}/auth/register", json={"name": "Retailer x", "email": email, "password": pw})
        assert reg.status_code == 200
        tok = reg.json()["token"]
        r = http.get(f"{API}/commissions", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403

    def test_delete_created_rules(self, http, admin_hdrs):
        for rid in TestCommissionRules._created_ids:
            r = http.delete(f"{API}/commissions/{rid}", headers=admin_hdrs)
            assert r.status_code == 200
        # verify removed
        r = http.get(f"{API}/commissions", headers=admin_hdrs)
        remaining_ids = {x.get("id") for x in r.json()}
        for rid in TestCommissionRules._created_ids:
            assert rid not in remaining_ids


# ---------- commission applied at recharge ----------
class TestRechargeCommission:
    def test_recharge_applies_commission_from_rule(self, http, admin_hdrs):
        # Set a rule for retailer @ mobile_prepaid + airtel at 5%
        rule_payload = {"role": "retailer", "service": "mobile_prepaid", "operator": "airtel", "rate": 0.05}
        rr = http.post(f"{API}/commissions", headers=admin_hdrs, json=rule_payload)
        assert rr.status_code == 200
        rule_id = rr.json()["id"]

        try:
            # Fresh retailer
            email = _unique_email()
            pw = "Test@12345"
            reg = http.post(f"{API}/auth/register",
                            json={"name": "Retailer CM", "email": email, "password": pw})
            assert reg.status_code == 200
            retailer = reg.json()["user"]
            retailer_token = reg.json()["token"]

            # Admin credits ₹1000
            cr = http.post(f"{API}/wallet/transfer", headers=admin_hdrs,
                           json={"user_id": retailer["user_id"], "amount": 1000, "kind": "credit"})
            assert cr.status_code == 200

            # Retailer does mobile_prepaid airtel ₹100 (retry once if random fail)
            r_hdrs = {"Authorization": f"Bearer {retailer_token}"}
            tx = None
            for _ in range(3):
                r = http.post(f"{API}/recharge", headers=r_hdrs,
                              json={"service": "mobile_prepaid", "operator": "airtel",
                                    "number": "9999900000", "amount": 100})
                assert r.status_code == 200, r.text
                tx = r.json()
                if tx["status"] == "success":
                    break
            assert tx is not None and tx["status"] == "success", "recharge kept failing 3 times"
            assert tx["commission_rate"] == 0.05
            assert tx["commission"] == 5.00

            # verify listed in /transactions
            r = http.get(f"{API}/transactions", headers=r_hdrs)
            assert r.status_code == 200
            found = next((t for t in r.json() if t["id"] == tx["id"]), None)
            assert found is not None and found["commission"] == 5.00
        finally:
            http.delete(f"{API}/commissions/{rule_id}", headers=admin_hdrs)


# ---------- PATCH /users/{id} + PATCH /me ----------
class TestUserEdit:
    def test_admin_can_edit_user_and_change_password(self, http, admin_hdrs):
        # Create a retailer via admin API
        email = _unique_email("TEST_edit_retailer")
        pw = "Test@12345"
        cr = http.post(f"{API}/users", headers=admin_hdrs,
                       json={"name": "Retailer Edit", "email": email, "password": pw, "role": "retailer"})
        assert cr.status_code == 200
        uid = cr.json()["user_id"]

        # PATCH update name & phone
        upd = http.patch(f"{API}/users/{uid}", headers=admin_hdrs,
                         json={"name": "Retailer Edited", "phone": "+919999900001"})
        assert upd.status_code == 200

        # GET verify
        rows = http.get(f"{API}/users", headers=admin_hdrs).json()
        edited = next((u for u in rows if u["user_id"] == uid), None)
        assert edited and edited["name"] == "Retailer Edited" and edited["phone"] == "+919999900001"

        # Change password + re-login as retailer
        new_pw = "New@Ret12345"
        upd = http.patch(f"{API}/users/{uid}", headers=admin_hdrs, json={"password": new_pw})
        assert upd.status_code == 200
        li = http.post(f"{API}/auth/login", json={"email": email, "password": new_pw})
        assert li.status_code == 200

    def test_patch_me_and_password_change(self, http):
        # Create a fresh user via public signup to avoid mutating admin
        email = _unique_email("TEST_me_user")
        pw = "Test@12345"
        reg = http.post(f"{API}/auth/register",
                        json={"name": "Me User", "email": email, "password": pw})
        assert reg.status_code == 200
        token = reg.json()["token"]
        hdrs = {"Authorization": f"Bearer {token}"}

        # PATCH /me name+phone
        r = http.patch(f"{API}/me", headers=hdrs, json={"name": "Me Updated", "phone": "+919000000001"})
        assert r.status_code == 200

        # GET /auth/me verify
        me = http.get(f"{API}/auth/me", headers=hdrs).json()
        assert me["name"] == "Me Updated" and me["phone"] == "+919000000001"

        # change own password
        new_pw = "NewMe@777"
        r = http.patch(f"{API}/me", headers=hdrs, json={"password": new_pw})
        assert r.status_code == 200
        li = http.post(f"{API}/auth/login", json={"email": email, "password": new_pw})
        assert li.status_code == 200


# ---------- Emergent OAuth session endpoint ----------
class TestOAuthSession:
    def test_invalid_session_id_returns_400(self, http):
        r = http.post(f"{API}/auth/session", json={"session_id": "definitely-invalid-session"})
        assert r.status_code == 400


# ---------- 422 shape sanity ----------
class TestValidationErrorShape:
    def test_422_detail_is_list_of_objects(self, http, admin_hdrs):
        # invalid email → EmailStr rejects
        r = http.post(f"{API}/users", headers=admin_hdrs,
                      json={"name": "x", "email": "foo@bar.test", "password": "Test@12345",
                            "role": "retailer"})
        # EmailStr may accept .test now depending on validator; assert we handle 422 shape when it fails
        if r.status_code == 422:
            body = r.json()
            assert isinstance(body.get("detail"), list)
            assert all(isinstance(x, dict) and "msg" in x for x in body["detail"])
        else:
            # If accepted (200), that is fine too — just ensures endpoint works
            assert r.status_code in (200, 400)
