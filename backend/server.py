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
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = "HS256"
ACCESS_TTL = timedelta(days=7)

Role = Literal["admin", "master_distributor", "distributor", "retailer"]
ROLE_HIERARCHY = {"admin": 4, "master_distributor": 3, "distributor": 2, "retailer": 1}

app = FastAPI(title="RechargePro API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("rechargepro")


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


# ---------- Startup ----------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.transactions.create_index([("user_id", 1), ("created_at", -1)])
    await db.wallet_ledger.create_index([("user_id", 1), ("created_at", -1)])

    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_pw = os.environ.get("ADMIN_PASSWORD")
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
        logger.info(f"Admin seeded: {admin_email}")
    elif not verify_password(admin_pw, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
                                  {"$set": {"password_hash": hash_password(admin_pw)}})
        logger.info("Admin password updated from env")

@app.on_event("shutdown")
async def shutdown():
    client.close()


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
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if user.get("status") == "blocked":
        raise HTTPException(403, "Account is blocked")
    token = create_token(user["user_id"], user["email"], user["role"])
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"token": token, "user": user}

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
        "commission": round(body.amount * 0.02, 2) if status == "success" else 0,
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


# ---------- Mount ----------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
