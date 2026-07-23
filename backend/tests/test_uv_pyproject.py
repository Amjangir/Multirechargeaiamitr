"""
Iteration 8: uv / pyproject.toml Vercel-deploy manifest fix.

Verifies:
  1. /app/backend/pyproject.toml exists with a [project] block declaring all
     runtime deps used by server.py.
  2. /app/backend/uv.lock exists, is v1/revision 3, requires-python >=3.11, and
     locks fastapi, motor, pymongo, pydantic, pyjwt, bcrypt.
  3. `uv lock --check` reports no drift.
  4. `uv sync --frozen` succeeds in a scratch venv (installs fastapi, motor, ...).
     The .venv is cleaned up at the end so supervisor doesn't reload.
  5. Version pins in pyproject.toml don't contradict requirements.txt for the
     packages listed in both.
  6. /app/backend/.venv does not exist after cleanup.
  7. /app/vercel.json still declares backend entrypoint=server:app, root=backend.
"""

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest


BACKEND_DIR = Path("/app/backend")
PYPROJECT = BACKEND_DIR / "pyproject.toml"
UV_LOCK = BACKEND_DIR / "uv.lock"
REQUIREMENTS = BACKEND_DIR / "requirements.txt"
VENV_DIR = BACKEND_DIR / ".venv"
UV_BIN = "/opt/bin/uv"

REQUIRED_RUNTIME_DEPS = {
    "fastapi",
    "uvicorn",
    "motor",
    "pymongo",
    "pydantic",
    "email-validator",
    "pyjwt",
    "bcrypt",
    "python-dotenv",
    "requests",
}


def _normalize(name: str) -> str:
    return name.lower().replace("_", "-")


def _split_spec(spec: str) -> tuple[str, str]:
    """Return (name, version-spec) split from a PEP 508-ish requirement string."""
    m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*(.*)$", spec)
    if not m:
        return spec.strip().lower(), ""
    return _normalize(m.group(1)), m.group(2).strip()


class TestPyprojectFile:
    """Static validation of /app/backend/pyproject.toml"""

    @pytest.fixture(scope="class")
    def cfg(self):
        assert PYPROJECT.exists(), "/app/backend/pyproject.toml is missing"
        with PYPROJECT.open("rb") as f:
            return tomllib.load(f)

    def test_project_block_present(self, cfg):
        assert "project" in cfg, "[project] block missing in pyproject.toml"
        proj = cfg["project"]
        assert proj.get("name"), "[project].name must be set"
        assert proj.get("requires-python"), "[project].requires-python must be set"
        # requires-python should permit 3.11+
        assert ">=3.11" in proj["requires-python"] or ">=3.10" in proj["requires-python"], (
            f"requires-python should be >=3.11 for Vercel, got {proj['requires-python']!r}"
        )

    def test_all_runtime_deps_declared(self, cfg):
        deps = cfg["project"].get("dependencies", [])
        assert deps, "[project].dependencies is empty"
        declared = {_split_spec(d)[0] for d in deps}
        missing = REQUIRED_RUNTIME_DEPS - declared
        assert not missing, (
            f"pyproject.toml missing required runtime deps: {sorted(missing)}. "
            f"Declared: {sorted(declared)}"
        )

    def test_tool_uv_package_false(self, cfg):
        """[tool.uv] package = false marks this as a dep-only workspace root."""
        tool = cfg.get("tool", {}).get("uv", {})
        assert tool.get("package") is False, (
            f"[tool.uv].package must be false to declare backend as dep-only workspace, "
            f"got tool.uv={tool!r}"
        )


class TestUvLock:
    """Static validation of /app/backend/uv.lock"""

    @pytest.fixture(scope="class")
    def lock_text(self):
        assert UV_LOCK.exists(), "/app/backend/uv.lock is missing"
        return UV_LOCK.read_text()

    def test_lockfile_header(self, lock_text):
        head = lock_text[:400]
        assert re.search(r"^version\s*=\s*1\b", head, re.MULTILINE), (
            f"uv.lock must start with `version = 1`; head={head[:120]!r}"
        )
        assert re.search(r"^revision\s*=\s*3\b", head, re.MULTILINE), (
            f"uv.lock must declare `revision = 3`; head={head[:200]!r}"
        )
        assert re.search(r'^requires-python\s*=\s*">=3\.11"', head, re.MULTILINE), (
            f"uv.lock requires-python must be `\">=3.11\"`; head={head[:200]!r}"
        )

    @pytest.mark.parametrize(
        "pkg",
        ["fastapi", "motor", "pymongo", "pydantic", "pyjwt", "bcrypt"],
    )
    def test_locked_package_present(self, lock_text, pkg):
        pattern = rf'^\s*name\s*=\s*"{re.escape(pkg)}"\s*$'
        assert re.search(pattern, lock_text, re.MULTILINE), (
            f"uv.lock missing locked entry for `{pkg}`"
        )


class TestVersionCompatibility:
    """Ensure requirements.txt and pyproject.toml don't contradict each other."""

    @pytest.fixture(scope="class")
    def req_pins(self):
        pins: dict[str, str] = {}
        for line in REQUIREMENTS.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, spec = _split_spec(line)
            if spec:
                pins[name] = spec
        return pins

    @pytest.fixture(scope="class")
    def pyproj_pins(self):
        with PYPROJECT.open("rb") as f:
            cfg = tomllib.load(f)
        pins: dict[str, str] = {}
        for dep in cfg["project"].get("dependencies", []):
            name, spec = _split_spec(dep)
            pins[name] = spec
        return pins

    def test_hard_pinned_versions_match(self, req_pins, pyproj_pins):
        """If both files pin a package with `==`, the exact version must match."""
        mismatches: list[str] = []
        for name, req_spec in req_pins.items():
            if not req_spec.startswith("=="):
                continue
            py_spec = pyproj_pins.get(name)
            if py_spec is None:
                # It's OK for pyproject to omit a package (e.g. dev-only deps)
                continue
            if py_spec != req_spec:
                mismatches.append(f"{name}: requirements.txt={req_spec!r} vs pyproject.toml={py_spec!r}")
        assert not mismatches, "Version pin contradictions:\n" + "\n".join(mismatches)


class TestUvCommands:
    """Reproduce the Vercel install steps: uv lock --check + uv sync --frozen."""

    def test_uv_binary_available(self):
        assert Path(UV_BIN).exists(), f"uv binary not found at {UV_BIN}"

    def test_uv_lock_check_passes(self):
        """`uv lock --check` must exit 0 — proves pyproject and lockfile are in sync."""
        # Make sure we're not accidentally sharing a .venv from a previous run.
        if VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)

        result = subprocess.run(
            [UV_BIN, "lock", "--check"],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"`uv lock --check` failed (rc={result.returncode})\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_uv_sync_frozen_succeeds(self):
        """`uv sync --frozen` must install all locked deps into a fresh venv."""
        # Ensure fresh state
        if VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        try:
            env = os.environ.copy()
            env["UV_LINK_MODE"] = "copy"  # container filesystems often can't hardlink cache
            result = subprocess.run(
                [UV_BIN, "sync", "--frozen"],
                cwd=str(BACKEND_DIR),
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
            assert result.returncode == 0, (
                f"`uv sync --frozen` failed (rc={result.returncode})\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
            # Sanity: the venv should now contain fastapi + motor.
            site_pkgs = list(VENV_DIR.glob("lib/python*/site-packages"))
            assert site_pkgs, f".venv/lib/python*/site-packages not found; venv layout unexpected"
            installed_names = {p.name.lower() for p in site_pkgs[0].iterdir() if p.is_dir()}
            for pkg in ("fastapi", "motor", "pymongo", "pydantic"):
                assert pkg in installed_names, (
                    f"expected `{pkg}` in freshly-synced venv site-packages, got: "
                    f"{sorted(installed_names)[:30]}..."
                )
        finally:
            # CRITICAL: never leave .venv behind (would confuse supervisor's file
            # watcher + pollute Vercel's build cache on next commit).
            if VENV_DIR.exists():
                shutil.rmtree(VENV_DIR, ignore_errors=True)

    def test_venv_cleaned_up(self):
        """Final assertion: .venv must not exist after the sync test."""
        assert not VENV_DIR.exists(), (
            f"{VENV_DIR} still present — must be cleaned so supervisor doesn't reload"
        )


class TestVercelJsonUnchanged:
    """Confirm /app/vercel.json backend service still points at server:app."""

    def test_backend_service_still_server_app(self):
        import json
        cfg = json.loads(Path("/app/vercel.json").read_text())
        be = cfg["services"]["backend"]
        assert be.get("root") == "backend"
        assert be.get("entrypoint") == "server:app"
