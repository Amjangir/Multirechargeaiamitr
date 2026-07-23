"""
Iteration 6: Vercel deploy manifest validation + backend regression smoke.

Verifies:
  1. /app/vercel.json exists at repo root and parses as valid JSON.
  2. Root vercel.json uses Vercel's `services` schema with correct
     frontend (root=frontend, framework=create-react-app, buildCommand=yarn build,
     outputDirectory=build) and backend (root=backend, entrypoint=server:app).
  3. rewrites route /api/(.*) -> service backend and /(.*) -> service frontend.
  4. /app/frontend/vercel.json has been removed.
  5. Backend server still runs (unauth /api/auth/me -> 401).
  6. Admin login still works end-to-end and returns a token.
  7. Authenticated GET /api/wallet/balance returns 200 with a `balance` field.
  8. Frontend still serves HTML at the external URL (has a <div id="root">).
"""

import json
import os
import re
from pathlib import Path

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fall back to reading frontend/.env because backend tests run outside CRA context.
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break

assert BASE_URL, "REACT_APP_BACKEND_URL must be set (either in env or /app/frontend/.env)"
BASE_URL = BASE_URL.rstrip("/")

ADMIN_EMAIL = "admin@rechargepro.com"
ADMIN_PASSWORD = "Admin@12345"


# ---------- Vercel manifest schema tests ----------

class TestVercelManifest:
    """Static-file validation of /app/vercel.json — no network calls."""

    @pytest.fixture(scope="class")
    def vercel_cfg(self):
        path = Path("/app/vercel.json")
        assert path.exists(), "/app/vercel.json is missing at repo root"
        with path.open() as f:
            return json.load(f)  # will raise if not valid JSON

    def test_root_vercel_json_exists_and_is_valid_json(self, vercel_cfg):
        assert isinstance(vercel_cfg, dict)

    def test_old_frontend_vercel_json_removed(self):
        assert not Path("/app/frontend/vercel.json").exists(), (
            "/app/frontend/vercel.json still exists — it will conflict with the root services config"
        )

    def test_services_object_present(self, vercel_cfg):
        assert "services" in vercel_cfg, "top-level 'services' key missing"
        assert isinstance(vercel_cfg["services"], dict)
        assert "frontend" in vercel_cfg["services"]
        assert "backend" in vercel_cfg["services"]

    def test_frontend_service_config(self, vercel_cfg):
        fe = vercel_cfg["services"]["frontend"]
        assert fe.get("root") == "frontend", f"frontend.root should be 'frontend', got {fe.get('root')!r}"
        assert fe.get("framework") == "create-react-app", (
            f"frontend.framework should be 'create-react-app', got {fe.get('framework')!r}"
        )
        assert fe.get("buildCommand") == "yarn build", (
            f"frontend.buildCommand must be 'yarn build' (yarn required per platform rules), got {fe.get('buildCommand')!r}"
        )
        assert fe.get("outputDirectory") == "build", (
            f"frontend.outputDirectory should be 'build', got {fe.get('outputDirectory')!r}"
        )
        # Sanity: must not use npm.
        assert "npm" not in fe.get("buildCommand", "").lower()
        install = fe.get("installCommand", "")
        if install:
            assert "npm" not in install.lower(), (
                "frontend.installCommand must not use npm; yarn is required"
            )

    def test_backend_service_config(self, vercel_cfg):
        be = vercel_cfg["services"]["backend"]
        assert be.get("root") == "backend", f"backend.root should be 'backend', got {be.get('root')!r}"
        assert be.get("entrypoint") == "server:app", (
            f"backend.entrypoint should be 'server:app' (matches server.py's `app = FastAPI()`), got {be.get('entrypoint')!r}"
        )

    def test_backend_entrypoint_matches_actual_module(self):
        """server:app must map to a real `app` object in /app/backend/server.py."""
        server_src = Path("/app/backend/server.py").read_text()
        assert re.search(r"^app\s*=\s*FastAPI\(", server_src, re.MULTILINE), (
            "server.py must expose a module-level `app = FastAPI(...)` to match entrypoint 'server:app'"
        )

    def test_rewrites_present_and_shaped_correctly(self, vercel_cfg):
        rewrites = vercel_cfg.get("rewrites")
        assert isinstance(rewrites, list) and len(rewrites) >= 2, (
            "top-level 'rewrites' must be a list with at least 2 entries"
        )
        # Build a source -> destination map.
        by_source = {r.get("source"): r.get("destination") for r in rewrites}
        assert "/api/(.*)" in by_source, "missing /api/(.*) rewrite"
        assert "/(.*)" in by_source, "missing /(.*) rewrite"

        api_dest = by_source["/api/(.*)"]
        assert isinstance(api_dest, dict) and api_dest.get("service") == "backend", (
            f"/api/(.*) must route to service 'backend', got {api_dest!r}"
        )
        catchall_dest = by_source["/(.*)"]
        assert isinstance(catchall_dest, dict) and catchall_dest.get("service") == "frontend", (
            f"/(.*) must route to service 'frontend', got {catchall_dest!r}"
        )

    def test_rewrite_order_api_before_catchall(self, vercel_cfg):
        """Vercel evaluates rewrites in order — /api/(.*) MUST come before /(.*)."""
        sources = [r.get("source") for r in vercel_cfg["rewrites"]]
        api_idx = sources.index("/api/(.*)")
        catch_idx = sources.index("/(.*)")
        assert api_idx < catch_idx, (
            f"/api/(.*) rewrite (index {api_idx}) must come before /(.*) (index {catch_idx}) "
            "or all /api requests will be routed to the frontend"
        )


# ---------- Backend regression smoke ----------

@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"login response missing token field: keys={list(data.keys())}"
    return token


class TestBackendSmoke:
    """Prove the Vercel manifest change did not regress the running backend."""

    def test_backend_reachable_unauth_me_returns_401(self, api):
        r = api.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 401, (
            f"Expected 401 from /api/auth/me without token, got {r.status_code}: {r.text[:200]}"
        )

    def test_admin_login_returns_token(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_wallet_balance_with_admin_token(self, api, admin_token):
        r = api.get(
            f"{BASE_URL}/api/wallet/balance",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, f"/api/wallet/balance failed: {r.status_code} {r.text}"
        data = r.json()
        assert "balance" in data, f"wallet balance response missing 'balance' key: {data}"
        assert isinstance(data["balance"], (int, float)), (
            f"balance should be numeric, got {type(data['balance']).__name__}"
        )

    def test_frontend_still_serves_html(self, api):
        # Hit the external URL root — should return HTML with a React root div.
        r = requests.get(BASE_URL, timeout=15)
        assert r.status_code == 200, f"Frontend root returned {r.status_code}"
        body = r.text.lower()
        assert "<div id=\"root\"" in body or "<div id='root'" in body or 'id="root"' in body, (
            "Frontend HTML does not contain a React root div — CRA output may be broken"
        )
