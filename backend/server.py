from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import random
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# ---------- Setup ----------
# Read Mongo config defensively so the module can still import (and /api/health
# can respond with a helpful diagnostic) even when env vars are missing.
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'test_database')
_MONGO_URL_MISSING = 'MONGO_URL' not in os.environ
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

JWT_SECRET = os.environ.get('JWT_SECRET', 'change-me-in-env')
JWT_ALGO = "HS256"
ACCESS_TTL = timedelta(days=7)

Role = Literal["admin", "master_distributor", "distributor", "retailer"]
ROLE_HIERARCHY = {"admin": 4, "master_distributor": 3, "distributor": 2, "retailer": 1}


async def _ensure_admin_seeded():
    """Idempotent: create admin from env if missing, resync password if stale.
    Called from FastAPI lifespan AND lazily from login (so deploys without a
    reliable startup event — e.g. Vercel Services cold start — still work)."""
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_pw = os.environ.get("ADMIN_PASSWORD")
    if not admin_email or not admin_pw:
        return
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "user_id": new_id("adm"),
            "name": "Super Admin",
            "email": admin_email,
            "password_hash": hash_password(admin_pw),
            "role": "admin",
            "wallet_balance": 0.0,
            "parent_id": None,
            "phone": None,
            "status": "active",
            "created_at": utc_now(),
        })
        logger.info(f"Admin seeded lazily: {admin_email}")
    elif not verify_password(admin_pw, existing.get("password_hash", "")):
        await db.users.update_one({"email": admin_email},
                                  {"$set": {"password_hash": hash_password(admin_pw)}})
        logger.info("Admin password updated from env")


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("user_id", unique=True)
        await db.transactions.create_index([("user_id", 1), ("created_at", -1)])
        await db.wallet_ledger.create_index([("user_id", 1), ("created_at", -1)])
        await _ensure_admin_seeded()
    except Exception as e:
        logger.exception(f"lifespan startup: {e}")
    yield
    client.close()


app = FastAPI(title="RechargePro API", lifespan=lifespan)
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("rechargepro")

# Loud startup log so the target Mongo host is visible in deployment logs.
_mongo_host_safe = mongo_url.split("@")[-1].split("/")[0] if "@" in mongo_url else mongo_url
logger.info(f"Mongo config → host={_mongo_host_safe} db={db_name} env_MONGO_URL_set={not _MONGO_URL_MISSING}")
if _MONGO_URL_MISSING:
    logger.warning("MONGO_URL env var is NOT SET — falling back to mongodb://localhost:27017 which will fail on Vercel/production. Set MONGO_URL to your MongoDB Atlas connection string.")


# ---------- Utils ----------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + ACCESS_TTL,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def new_id(prefix="usr") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- Models ----------
class RegisterInput(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Role = "retailer"
    phone: Optional[str] = None

class LoginInput(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    user_id: str
    name: str
    email: str
    role: Role
    phone: Optional[str] = None
    parent_id: Optional[str] = None
    wallet_balance: float = 0.0
    status: str = "active"
    created_at: str

class WalletTxInput(BaseModel):
    user_id: str
    amount: float
    note: Optional[str] = None
    kind: Literal["credit", "debit"] = "credit"

class RechargeInput(BaseModel):
    service: Literal["mobile_prepaid", "dth", "electricity", "data_card"]
    operator: str
    number: str
    amount: float
    circle: Optional[str] = None

class CreateUserByAdmin(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Role
    phone: Optional[str] = None
    parent_id: Optional[str] = None


# ---------- Auth Dependency ----------
async def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user

def require_role(*roles: str):
    async def _dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"Requires role: {roles}")
        return user
    return _dep



# ---------- Auth Routes ----------
@api.post("/auth/register")
async def register(body: RegisterInput):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    # Public signups default to retailer status pending admin approval
    role = "retailer" if body.role == "retailer" else body.role
    user_id = new_id("usr")
    doc = {
        "user_id": user_id,
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": role,
        "phone": body.phone,
        "parent_id": None,
        "wallet_balance": 0.0,
        "status": "active",
        "created_at": utc_now(),
    }
    await db.users.insert_one(doc)
    token = create_token(user_id, email, role)
    doc.pop("password_hash")
    doc.pop("_id", None)
    return {"token": token, "user": doc}

@api.post("/auth/login")
async def login(body: LoginInput):
    email = body.email.lower()
    try:
        # Lazy admin seed on first login attempt (works even if the startup
        # event didn't fire — common on Vercel Python Services cold starts).
        # Wrapped in its own try so a seed failure doesn't turn login into 500.
        if email == (os.environ.get("ADMIN_EMAIL") or "").lower():
            try:
                await _ensure_admin_seeded()
            except Exception as e:
                logger.exception(f"admin seed failed: {e}")
        user = await db.users.find_one({"email": email})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"login db lookup failed: {e}")
        hint = ""
        if _MONGO_URL_MISSING or "localhost:27017" in str(e):
            hint = " MONGO_URL env var is not set on this deployment — set it to your MongoDB Atlas connection string and redeploy."
        raise HTTPException(500, f"Database error: {type(e).__name__}.{hint} Check /api/health for full diagnostics.")
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid email or password")
    if user.get("status") == "blocked":
        raise HTTPException(403, "Account is blocked")
    token = create_token(user["user_id"], user["email"], user["role"])
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"token": token, "user": user}


@api.get("/health")
async def health():
    """Diagnostic endpoint for deployment troubleshooting."""
    info = {
        "app": "rechargepro-api",
        "time": utc_now(),
        "env": {
            "MONGO_URL_set": bool(os.environ.get("MONGO_URL")),
            "DB_NAME_set": bool(os.environ.get("DB_NAME")),
            "JWT_SECRET_set": bool(os.environ.get("JWT_SECRET")),
            "ADMIN_EMAIL_set": bool(os.environ.get("ADMIN_EMAIL")),
            "ADMIN_PASSWORD_set": bool(os.environ.get("ADMIN_PASSWORD")),
        },
        "mongo": {"ok": False, "error": None, "admin_seeded": False, "user_count": 0, "host": mongo_url.split("@")[-1].split("/")[0] if "@" in mongo_url else mongo_url.replace("mongodb://", "").split("/")[0]},
    }
    try:
        # ping the DB
        await client.admin.command("ping")
        info["mongo"]["ok"] = True
        # count users + admin presence
        info["mongo"]["user_count"] = await db.users.count_documents({})
        admin_email = os.environ.get("ADMIN_EMAIL")
        if admin_email:
            info["mongo"]["admin_seeded"] = bool(
                await db.users.find_one({"email": admin_email.lower()}, {"_id": 1})
            )
    except Exception as e:
        info["mongo"]["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return info

@api.get("/auth/me", response_model=UserOut)
async def me(user=Depends(get_current_user)):
    return user

@api.post("/auth/logout")
async def logout():
    return {"ok": True}


# ---------- Users / Network ----------
@api.get("/users", response_model=List[UserOut])
async def list_users(user=Depends(get_current_user)):
    q = {}
    if user["role"] == "admin":
        q = {}
    elif user["role"] == "master_distributor":
        q = {"$or": [{"parent_id": user["user_id"]}, {"user_id": user["user_id"]}]}
        # include grand-children
        distributor_ids = [u["user_id"] async for u in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        if distributor_ids:
            q = {"$or": [{"parent_id": user["user_id"]}, {"parent_id": {"$in": distributor_ids}}]}
    elif user["role"] == "distributor":
        q = {"parent_id": user["user_id"]}
    else:
        return []
    docs = await db.users.find(q, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    return docs

@api.post("/users", response_model=UserOut)
async def create_user(body: CreateUserByAdmin, user=Depends(get_current_user)):
    # role-based creation rules
    if user["role"] == "retailer":
        raise HTTPException(403, "Retailers cannot create users")
    if ROLE_HIERARCHY[user["role"]] <= ROLE_HIERARCHY[body.role]:
        raise HTTPException(403, "Cannot create user with equal or higher role")
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already exists")
    parent_id = body.parent_id or user["user_id"]
    if user["role"] != "admin":
        parent_id = user["user_id"]
    user_id = new_id(body.role[:3])
    doc = {
        "user_id": user_id,
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "phone": body.phone,
        "parent_id": parent_id,
        "wallet_balance": 0.0,
        "status": "active",
        "created_at": utc_now(),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash")
    doc.pop("_id", None)
    return doc

@api.patch("/users/{user_id}/status")
async def toggle_status(user_id: str, status: str, user=Depends(require_role("admin", "master_distributor", "distributor"))):
    if status not in ("active", "blocked"):
        raise HTTPException(400, "Invalid status")
    await db.users.update_one({"user_id": user_id}, {"$set": {"status": status}})
    return {"ok": True}


# ---------- Wallet ----------
@api.get("/wallet/balance")
async def wallet_balance(user=Depends(get_current_user)):
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "wallet_balance": 1})
    return {"balance": float(fresh.get("wallet_balance", 0))}

@api.get("/wallet/ledger")
async def wallet_ledger(user=Depends(get_current_user), limit: int = 100):
    docs = await db.wallet_ledger.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs

@api.post("/wallet/transfer")
async def wallet_transfer(body: WalletTxInput, user=Depends(get_current_user)):
    """
    - admin can credit/debit any user (money materialises).
    - distributors/master_distributors transfer from own balance to their downline.
    """
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be > 0")
    target = await db.users.find_one({"user_id": body.user_id})
    if not target:
        raise HTTPException(404, "Target user not found")

    if user["role"] == "admin":
        delta = body.amount if body.kind == "credit" else -body.amount
        await db.users.update_one({"user_id": body.user_id}, {"$inc": {"wallet_balance": delta}})
        await db.wallet_ledger.insert_one({
            "id": new_id("wl"),
            "user_id": body.user_id,
            "amount": delta,
            "type": body.kind,
            "note": body.note or f"Admin {body.kind}",
            "by": user["user_id"],
            "by_name": user["name"],
            "created_at": utc_now(),
        })
        return {"ok": True}

    # Downline check for distributors / master_distributors
    if user["role"] in ("master_distributor", "distributor"):
        # ensure target is direct or grand-child
        chain_ids = {user["user_id"]}
        children = [c["user_id"] async for c in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        chain_ids.update(children)
        if user["role"] == "master_distributor":
            for cid in children:
                gc = [g["user_id"] async for g in db.users.find({"parent_id": cid}, {"user_id": 1})]
                chain_ids.update(gc)
        if body.user_id not in chain_ids or body.user_id == user["user_id"]:
            raise HTTPException(403, "Target is not in your downline")
        sender = await db.users.find_one({"user_id": user["user_id"]}, {"wallet_balance": 1})
        if float(sender.get("wallet_balance", 0)) < body.amount:
            raise HTTPException(400, "Insufficient balance")
        # Transfer
        await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -body.amount}})
        await db.users.update_one({"user_id": body.user_id}, {"$inc": {"wallet_balance": body.amount}})
        ts = utc_now()
        await db.wallet_ledger.insert_many([
            {"id": new_id("wl"), "user_id": user["user_id"], "amount": -body.amount, "type": "transfer_out",
             "note": f"Transfer to {target['name']}", "by": user["user_id"], "by_name": user["name"], "created_at": ts},
            {"id": new_id("wl"), "user_id": body.user_id, "amount": body.amount, "type": "transfer_in",
             "note": f"Received from {user['name']}", "by": user["user_id"], "by_name": user["name"], "created_at": ts},
        ])
        return {"ok": True}

    raise HTTPException(403, "Not allowed")


# ---------- Operators ----------
OPERATORS = {
    "mobile_prepaid": [
        {"code": "airtel", "name": "Airtel"},
        {"code": "jio", "name": "Reliance Jio"},
        {"code": "vi", "name": "Vi (Vodafone Idea)"},
        {"code": "bsnl", "name": "BSNL"},
    ],
    "dth": [
        {"code": "tata_play", "name": "Tata Play"},
        {"code": "dish_tv", "name": "Dish TV"},
        {"code": "airtel_dth", "name": "Airtel Digital TV"},
        {"code": "d2h", "name": "D2H"},
    ],
    "electricity": [
        {"code": "adani", "name": "Adani Electricity"},
        {"code": "tata_power", "name": "Tata Power"},
        {"code": "bses_rajdhani", "name": "BSES Rajdhani"},
        {"code": "mseb", "name": "MSEB Maharashtra"},
    ],
    "data_card": [
        {"code": "jio_fiber", "name": "Jio Fiber"},
        {"code": "airtel_xstream", "name": "Airtel Xstream"},
        {"code": "acttv", "name": "ACT Broadband"},
    ],
}

@api.get("/operators")
async def get_operators():
    return OPERATORS


# ---------- Recharge (mock) ----------
@api.post("/recharge")
async def do_recharge(body: RechargeInput, user=Depends(get_current_user)):
    if body.amount <= 0:
        raise HTTPException(400, "Amount must be > 0")
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"wallet_balance": 1})
    if float(fresh.get("wallet_balance", 0)) < body.amount:
        raise HTTPException(400, "Insufficient wallet balance")

    # mock success ~90%
    status = "success" if random.random() < 0.9 else "failed"
    op_ref = f"TXN{uuid.uuid4().hex[:10].upper()}"

    commission_rate = await get_commission_rate(user, body.service, body.operator, body.amount)
    commission = round(body.amount * commission_rate, 2) if status == "success" else 0

    tx = {
        "id": new_id("tx"),
        "user_id": user["user_id"],
        "user_name": user["name"],
        "user_role": user["role"],
        "service": body.service,
        "operator": body.operator,
        "number": body.number,
        "amount": body.amount,
        "circle": body.circle,
        "status": status,
        "operator_ref": op_ref,
        "commission": commission,
        "commission_rate": commission_rate,
        "created_at": utc_now(),
    }

    if status == "success":
        await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"wallet_balance": -body.amount}})
        await db.wallet_ledger.insert_one({
            "id": new_id("wl"),
            "user_id": user["user_id"],
            "amount": -body.amount,
            "type": "recharge",
            "note": f"{body.service.replace('_',' ').title()} recharge {body.number}",
            "by": user["user_id"], "by_name": user["name"],
            "created_at": utc_now(),
        })
        # commission credit
        if tx["commission"] > 0:
            await db.users.update_one({"user_id": user["user_id"]}, {"$inc": {"wallet_balance": tx["commission"]}})
            await db.wallet_ledger.insert_one({
                "id": new_id("wl"),
                "user_id": user["user_id"],
                "amount": tx["commission"],
                "type": "commission",
                "note": f"Commission on {op_ref}",
                "by": "system", "by_name": "System",
                "created_at": utc_now(),
            })
    await db.transactions.insert_one(tx)
    tx.pop("_id", None)
    return tx

@api.get("/transactions")
async def list_transactions(user=Depends(get_current_user), limit: int = 200, status: Optional[str] = None, service: Optional[str] = None):
    q = {}
    if user["role"] == "retailer":
        q["user_id"] = user["user_id"]
    elif user["role"] == "distributor":
        child_ids = [u["user_id"] async for u in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        q["user_id"] = {"$in": [user["user_id"]] + child_ids}
    elif user["role"] == "master_distributor":
        d_ids = [u["user_id"] async for u in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        r_ids = []
        for did in d_ids:
            r_ids += [u["user_id"] async for u in db.users.find({"parent_id": did}, {"user_id": 1})]
        q["user_id"] = {"$in": [user["user_id"]] + d_ids + r_ids}
    if status: q["status"] = status
    if service: q["service"] = service
    docs = await db.transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs


# ---------- Stats ----------
@api.get("/stats/summary")
async def stats_summary(user=Depends(get_current_user)):
    # scope filter
    scope = {}
    if user["role"] == "retailer":
        scope["user_id"] = user["user_id"]
    elif user["role"] == "distributor":
        child_ids = [u["user_id"] async for u in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        scope["user_id"] = {"$in": [user["user_id"]] + child_ids}
    elif user["role"] == "master_distributor":
        d_ids = [u["user_id"] async for u in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        r_ids = []
        for did in d_ids:
            r_ids += [u["user_id"] async for u in db.users.find({"parent_id": did}, {"user_id": 1})]
        scope["user_id"] = {"$in": [user["user_id"]] + d_ids + r_ids}

    pipeline = [{"$match": scope}] if scope else []
    pipeline += [{"$group": {
        "_id": "$status",
        "count": {"$sum": 1},
        "amount": {"$sum": "$amount"},
        "commission": {"$sum": "$commission"},
    }}]
    agg = await db.transactions.aggregate(pipeline).to_list(20)
    result = {"success": {"count": 0, "amount": 0, "commission": 0},
              "failed": {"count": 0, "amount": 0, "commission": 0}}
    for row in agg:
        st = row["_id"] or "unknown"
        result[st] = {"count": row["count"], "amount": row["amount"], "commission": row.get("commission", 0)}

    # daily last 7d
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    day_pipeline = ([{"$match": {**scope, "created_at": {"$gte": since}}}] if scope else [{"$match": {"created_at": {"$gte": since}}}]) + [
        {"$group": {"_id": {"$substr": ["$created_at", 0, 10]},
                    "amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    daily = await db.transactions.aggregate(day_pipeline).to_list(30)

    # user counts (admin/upline)
    user_counts = {}
    if user["role"] == "admin":
        for r in ["admin", "master_distributor", "distributor", "retailer"]:
            user_counts[r] = await db.users.count_documents({"role": r})
    return {"tx": result, "daily": daily, "user_counts": user_counts}


# ---------- Password Reset ----------
import secrets

class ForgotInput(BaseModel):
    email: EmailStr

class ResetInput(BaseModel):
    token: str
    new_password: str

@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotInput):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    token = secrets.token_urlsafe(24)
    if user:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "expires_at": expires_at,
            "used": False,
            "created_at": utc_now(),
        })
        logger.info(f"[PASSWORD RESET] Link for {email}: /reset-password?token={token}")
    # Always return the token for demo purposes so the UI can show it (mock email flow)
    return {"ok": True, "reset_token": token if user else None}

@api.post("/auth/reset-password")
async def reset_password(body: ResetInput):
    tok = await db.password_reset_tokens.find_one({"token": body.token, "used": False})
    if not tok:
        raise HTTPException(400, "Invalid or used token")
    expires_at = tok["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Token expired")
    await db.users.update_one({"user_id": tok["user_id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    await db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"ok": True}


# ---------- Emergent OAuth Session Exchange ----------
import requests as _http

class SessionInput(BaseModel):
    session_id: str

@api.post("/auth/session")
async def auth_session(body: SessionInput):
    try:
        r = _http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
            timeout=10,
        )
    except Exception:
        raise HTTPException(400, "Session exchange failed")
    if r.status_code != 200:
        raise HTTPException(400, "Invalid session")
    data = r.json()
    email = (data.get("email") or "").lower()
    if not email:
        raise HTTPException(400, "Email missing from Google session")
    user = await db.users.find_one({"email": email})
    if not user:
        user = {
            "user_id": new_id("usr"),
            "name": data.get("name") or email.split("@")[0],
            "email": email,
            "password_hash": "",
            "role": "retailer",
            "phone": None,
            "parent_id": None,
            "wallet_balance": 0.0,
            "status": "active",
            "picture": data.get("picture"),
            "created_at": utc_now(),
        }
        await db.users.insert_one(user)
    else:
        await db.users.update_one({"email": email}, {"$set": {
            "name": data.get("name") or user.get("name"),
            "picture": data.get("picture"),
        }})
    token = create_token(user["user_id"], email, user["role"])
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"token": token, "user": user}


# ---------- Commission Rules ----------
DEFAULT_COMMISSION = 0.02

class CommissionRuleInput(BaseModel):
    service: Optional[str] = None
    operator: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[Role] = None
    rate: float
    min_amount: float = 0
    max_amount: Optional[float] = None   # None = unlimited

async def get_commission_rate(user, service, operator, amount) -> float:
    scope_checks = [
        {"user_id": user["user_id"], "role": None, "service": service, "operator": operator},
        {"user_id": user["user_id"], "role": None, "service": service, "operator": None},
        {"user_id": user["user_id"], "role": None, "service": None, "operator": None},
        {"user_id": None, "role": None, "service": service, "operator": operator},
        {"user_id": None, "role": None, "service": service, "operator": None},
        {"user_id": None, "role": user["role"], "service": service, "operator": operator},
        {"user_id": None, "role": user["role"], "service": service, "operator": None},
        {"user_id": None, "role": user["role"], "service": None, "operator": None},
    ]
    amount_clause = {
        "min_amount": {"$lte": amount},
        "$or": [{"max_amount": None}, {"max_amount": {"$gte": amount}}],
    }
    for scope in scope_checks:
        q = {**scope, **amount_clause}
        # pick highest-priority (narrowest range first): smallest max_amount, then largest min_amount
        r = await db.commission_rules.find(q).sort([("max_amount", 1), ("min_amount", -1)]).to_list(1)
        if r:
            return float(r[0]["rate"])
    return DEFAULT_COMMISSION

@api.get("/commissions")
async def list_commissions(user=Depends(require_role("admin"))):
    docs = await db.commission_rules.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs

@api.post("/commissions")
async def create_commission(body: CommissionRuleInput, user=Depends(require_role("admin"))):
    if body.rate < 0 or body.rate > 1:
        raise HTTPException(400, "Rate must be between 0 and 1 (e.g. 0.025 for 2.5%)")
    if body.max_amount is not None and body.max_amount < body.min_amount:
        raise HTTPException(400, "max_amount must be >= min_amount")
    doc = {
        "id": new_id("cm"),
        "service": body.service or None,
        "operator": body.operator or None,
        "user_id": body.user_id or None,
        "role": body.role or None,
        "rate": body.rate,
        "min_amount": float(body.min_amount or 0),
        "max_amount": float(body.max_amount) if body.max_amount is not None else None,
        "created_at": utc_now(),
    }
    await db.commission_rules.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.delete("/commissions/{rule_id}")
async def delete_commission(rule_id: str, user=Depends(require_role("admin"))):
    r = await db.commission_rules.delete_one({"id": rule_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Rule not found")
    return {"ok": True}


# ---------- User & Profile Edit ----------
class UpdateUserInput(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role: Optional[Role] = None
    status: Optional[str] = None

class UpdateMeInput(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None

@api.patch("/users/{target_id}")
async def update_user(target_id: str, body: UpdateUserInput, user=Depends(get_current_user)):
    target = await db.users.find_one({"user_id": target_id})
    if not target:
        raise HTTPException(404, "User not found")
    if user["role"] != "admin":
        allowed = False
        if target.get("parent_id") == user["user_id"]:
            allowed = True
        elif user["role"] == "master_distributor" and target.get("parent_id"):
            parent = await db.users.find_one({"user_id": target["parent_id"]}, {"parent_id": 1})
            if parent and parent.get("parent_id") == user["user_id"]:
                allowed = True
        if not allowed:
            raise HTTPException(403, "Not allowed to edit this user")
    updates = {}
    if body.name is not None: updates["name"] = body.name
    if body.phone is not None: updates["phone"] = body.phone
    if body.password: updates["password_hash"] = hash_password(body.password)
    if body.status is not None:
        if body.status not in ("active", "blocked"):
            raise HTTPException(400, "Invalid status")
        updates["status"] = body.status
    if body.role is not None:
        if user["role"] != "admin":
            raise HTTPException(403, "Only admin can change roles")
        updates["role"] = body.role
    if updates:
        await db.users.update_one({"user_id": target_id}, {"$set": updates})
    return {"ok": True}

@api.patch("/me")
async def update_me(body: UpdateMeInput, user=Depends(get_current_user)):
    updates = {}
    if body.name is not None: updates["name"] = body.name
    if body.phone is not None: updates["phone"] = body.phone
    if body.password: updates["password_hash"] = hash_password(body.password)
    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return {"ok": True}


# ---------- Reports ----------
async def _scope_query(user):
    if user["role"] == "retailer":
        return {"user_id": user["user_id"]}
    if user["role"] == "distributor":
        child_ids = [u["user_id"] async for u in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        return {"user_id": {"$in": [user["user_id"]] + child_ids}}
    if user["role"] == "master_distributor":
        d_ids = [u["user_id"] async for u in db.users.find({"parent_id": user["user_id"]}, {"user_id": 1})]
        r_ids = []
        for did in d_ids:
            r_ids += [u["user_id"] async for u in db.users.find({"parent_id": did}, {"user_id": 1})]
        return {"user_id": {"$in": [user["user_id"]] + d_ids + r_ids}}
    return {}

@api.get("/reports/summary")
async def reports_summary(user=Depends(get_current_user), start: Optional[str] = None, end: Optional[str] = None):
    scope = await _scope_query(user)
    match = {**scope, "status": "success"}
    if start: match["created_at"] = {**match.get("created_at", {}), "$gte": start}
    if end: match["created_at"] = {**match.get("created_at", {}), "$lte": end}

    pipeline_role = [{"$match": match}, {"$group": {
        "_id": "$user_role", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}, "commission": {"$sum": "$commission"}
    }}, {"$sort": {"amount": -1}}]
    by_role = await db.transactions.aggregate(pipeline_role).to_list(20)

    pipeline_service = [{"$match": match}, {"$group": {
        "_id": "$service", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}, "commission": {"$sum": "$commission"}
    }}, {"$sort": {"amount": -1}}]
    by_service = await db.transactions.aggregate(pipeline_service).to_list(20)

    pipeline_operator = [{"$match": match}, {"$group": {
        "_id": {"service": "$service", "operator": "$operator"},
        "count": {"$sum": 1}, "amount": {"$sum": "$amount"}, "commission": {"$sum": "$commission"}
    }}, {"$sort": {"amount": -1}}, {"$limit": 30}]
    by_operator = await db.transactions.aggregate(pipeline_operator).to_list(30)

    pipeline_user = [{"$match": match}, {"$group": {
        "_id": {"user_id": "$user_id", "user_name": "$user_name", "user_role": "$user_role"},
        "count": {"$sum": 1}, "amount": {"$sum": "$amount"}, "commission": {"$sum": "$commission"}
    }}, {"$sort": {"amount": -1}}, {"$limit": 20}]
    by_user = await db.transactions.aggregate(pipeline_user).to_list(20)

    slabs = [
        {"label": "0 – 99",       "min": 0,    "max": 99.99},
        {"label": "100 – 499",   "min": 100,  "max": 499.99},
        {"label": "500 – 999",   "min": 500,  "max": 999.99},
        {"label": "1000 – 4999", "min": 1000, "max": 4999.99},
        {"label": "5000+",       "min": 5000, "max": None},
    ]
    by_slab = []
    for s in slabs:
        cond = {**match, "amount": {"$gte": s["min"]}}
        if s["max"] is not None:
            cond["amount"]["$lte"] = s["max"]
        agg = await db.transactions.aggregate([
            {"$match": cond},
            {"$group": {"_id": None, "count": {"$sum": 1}, "amount": {"$sum": "$amount"}, "commission": {"$sum": "$commission"}}}
        ]).to_list(1)
        row = agg[0] if agg else {"count": 0, "amount": 0, "commission": 0}
        by_slab.append({"label": s["label"], "count": row["count"], "amount": row["amount"], "commission": row["commission"]})

    # daily last 30d
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    daily = await db.transactions.aggregate([
        {"$match": {**match, "created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$substr": ["$created_at", 0, 10]},
            "count": {"$sum": 1}, "amount": {"$sum": "$amount"}, "commission": {"$sum": "$commission"}
        }},
        {"$sort": {"_id": 1}},
    ]).to_list(60)

    return {
        "by_role": [{"role": r["_id"], **{k: r[k] for k in ("count", "amount", "commission")}} for r in by_role],
        "by_service": [{"service": r["_id"], **{k: r[k] for k in ("count", "amount", "commission")}} for r in by_service],
        "by_operator": [{"service": r["_id"]["service"], "operator": r["_id"]["operator"], **{k: r[k] for k in ("count", "amount", "commission")}} for r in by_operator],
        "by_user": [{"user_id": r["_id"]["user_id"], "user_name": r["_id"]["user_name"], "user_role": r["_id"]["user_role"], **{k: r[k] for k in ("count", "amount", "commission")}} for r in by_user],
        "by_slab": by_slab,
        "daily": daily,
    }


# ---------- Mount ----------
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api)
