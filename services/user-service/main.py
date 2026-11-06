import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, timedelta

from ecommerce_common.config import BaseServiceSettings
from ecommerce_common.database import serialize_doc
from ecommerce_common.logging import setup_logger
from ecommerce_common.middleware import register_base_middlewares
from ecommerce_common.security import (
    TokenUser,
    create_jwt_token,
    get_current_user_dependency,
    hash_password,
    require_roles,
    verify_password,
)
from fastapi import Depends, FastAPI, HTTPException, status
from models import (
    AddressCreate,
    AddressResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
    utc_now,
)
from motor.motor_asyncio import AsyncIOMotorClient
from prometheus_client import Counter, Histogram, make_asgi_app

logger = setup_logger("user-service")


class Settings(BaseServiceSettings):
    SERVICE_NAME: str = "user-service"
    DATABASE_NAME: str = os.getenv("USER_DB_NAME", "user_db")
    PORT: int = int(os.getenv("USER_SERVICE_PORT", "8001"))


settings = Settings()
client: AsyncIOMotorClient | None = None
db = None

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP Request Duration", ["endpoint"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db
    logger.info(
        f"Connecting to MongoDB at {settings.MONGO_URI} ({settings.DATABASE_NAME})"
    )
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.DATABASE_NAME]

    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.refresh_tokens.create_index("token", unique=True)
    await db.addresses.create_index([("user_id", 1), ("is_default", -1)])

    # Seed initial admin if not present
    admin_exists = await db.users.find_one({"email": "admin@ecommerce.local"})
    if not admin_exists:
        admin_doc = {
            "_id": str(uuid.uuid4()),
            "email": "admin@ecommerce.local",
            "password_hash": hash_password("AdminPass123!"),
            "first_name": "Admin",
            "last_name": "Master",
            "role": "ADMIN",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await db.users.insert_one(admin_doc)
        logger.info("Default admin user seeded: admin@ecommerce.local")

    yield
    client.close()
    logger.info("User service shutdown")


app = FastAPI(title="User Service", version="1.0.0", lifespan=lifespan)
register_base_middlewares(app)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

get_current_user = get_current_user_dependency(
    secret_key=settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    try:
        await db.command("ping")
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unready: {e}")


@app.post(
    "/api/v1/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(request: UserRegisterRequest):
    existing = await db.users.find_one({"email": request.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user_id = str(uuid.uuid4())
    # Restrict roles in public registration
    assigned_role = "CUSTOMER"
    if request.role in ["ADMIN", "OPERATIONS"]:
        assigned_role = request.role  # Allowed in test/seed environments

    user_doc = {
        "_id": user_id,
        "email": request.email.lower(),
        "password_hash": hash_password(request.password),
        "first_name": request.first_name,
        "last_name": request.last_name,
        "role": assigned_role,
        "is_active": True,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    await db.users.insert_one(user_doc)

    access_token = create_jwt_token(
        payload={"sub": user_id, "email": user_doc["email"], "role": assigned_role},
        secret_key=settings.JWT_SECRET_KEY,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = str(uuid.uuid4())
    await db.refresh_tokens.insert_one(
        {
            "token": refresh_token,
            "user_id": user_id,
            "expires_at": utc_now()
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "revoked": False,
            "created_at": utc_now(),
        }
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        email=user_doc["email"],
        role=assigned_role,
    )


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(request: UserLoginRequest):
    user = await db.users.find_one({"email": request.email.lower()})
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    user_id = str(user["_id"])
    access_token = create_jwt_token(
        payload={"sub": user_id, "email": user["email"], "role": user["role"]},
        secret_key=settings.JWT_SECRET_KEY,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = str(uuid.uuid4())
    await db.refresh_tokens.insert_one(
        {
            "token": refresh_token,
            "user_id": user_id,
            "expires_at": utc_now()
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "revoked": False,
            "created_at": utc_now(),
        }
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        email=user["email"],
        role=user["role"],
    )


@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    token_doc = await db.refresh_tokens.find_one(
        {"token": request.refresh_token, "revoked": False}
    )
    if not token_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    expires_at = token_doc["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < utc_now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        )

    # Rotate refresh token
    await db.refresh_tokens.update_one(
        {"_id": token_doc["_id"]}, {"$set": {"revoked": True}}
    )

    user = await db.users.find_one({"_id": token_doc["user_id"]})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user_id = str(user["_id"])
    new_access_token = create_jwt_token(
        payload={"sub": user_id, "email": user["email"], "role": user["role"]},
        secret_key=settings.JWT_SECRET_KEY,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh_token = str(uuid.uuid4())
    await db.refresh_tokens.insert_one(
        {
            "token": new_refresh_token,
            "user_id": user_id,
            "expires_at": utc_now()
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "revoked": False,
            "created_at": utc_now(),
        }
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user_id=user_id,
        email=user["email"],
        role=user["role"],
    )


@app.post("/api/v1/auth/logout")
async def logout(
    request: RefreshTokenRequest, user: TokenUser = Depends(get_current_user)
):
    await db.refresh_tokens.update_many(
        {"token": request.refresh_token, "user_id": user.user_id},
        {"$set": {"revoked": True, "revoked_at": utc_now()}},
    )
    return {"message": "Successfully logged out"}


@app.get("/api/v1/users/me", response_model=UserProfileResponse)
async def get_my_profile(user: TokenUser = Depends(get_current_user)):
    user_doc = await db.users.find_one({"_id": user.user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    addresses = await db.addresses.find({"user_id": user.user_id}).to_list(100)
    addr_list = [
        AddressResponse(
            id=str(a["_id"]),
            title=a.get("title", "Home"),
            street=a["street"],
            city=a["city"],
            state=a["state"],
            postal_code=a["postal_code"],
            country=a.get("country", "US"),
            is_default=a.get("is_default", False),
            created_at=a.get("created_at", utc_now()),
        )
        for a in addresses
    ]

    return UserProfileResponse(
        id=str(user_doc["_id"]),
        email=user_doc["email"],
        first_name=user_doc["first_name"],
        last_name=user_doc["last_name"],
        role=user_doc["role"],
        is_active=user_doc.get("is_active", True),
        addresses=addr_list,
        created_at=user_doc["created_at"],
    )


@app.post("/api/v1/users/me/addresses", response_model=AddressResponse)
async def add_address(
    address_in: AddressCreate, user: TokenUser = Depends(get_current_user)
):
    if address_in.is_default:
        await db.addresses.update_many(
            {"user_id": user.user_id}, {"$set": {"is_default": False}}
        )

    addr_id = str(uuid.uuid4())
    doc = address_in.model_dump()
    doc["_id"] = addr_id
    doc["user_id"] = user.user_id
    doc["created_at"] = utc_now()

    await db.addresses.insert_one(doc)
    return AddressResponse(
        id=addr_id, **address_in.model_dump(), created_at=doc["created_at"]
    )


@app.get("/api/v1/users", dependencies=[Depends(require_roles(["ADMIN"]))])
async def list_all_users(user: TokenUser = Depends(get_current_user)):
    cursor = db.users.find().limit(100)
    users = await cursor.to_list(100)
    return [serialize_doc(u) for u in users]
