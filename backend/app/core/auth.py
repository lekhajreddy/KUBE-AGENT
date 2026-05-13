"""
KubeMind — JWT Authentication & RBAC
Handles user registration, login, API key management, and role-based access control.
"""
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Security, WebSocket, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger("kubemind.auth")

# ── Password hashing ─────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT tokens ────────────────────────────────────────────────────────────────
def create_access_token(data: Dict[str, Any], expires_hours: int = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        hours=expires_hours or settings.JWT_EXPIRY_HOURS
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ── API Key generation ────────────────────────────────────────────────────────
def generate_api_key() -> str:
    """Generate a secure API key for cluster agents."""
    return f"km_{secrets.token_urlsafe(32)}"


def generate_cluster_id() -> str:
    return str(uuid.uuid4())[:12]


# ── FastAPI dependencies ──────────────────────────────────────────────────────
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Dict[str, Any]:
    """Extract and validate JWT from Authorization header."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return payload


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Optional[Dict[str, Any]]:
    """Extract JWT if present, return None otherwise (for optional auth)."""
    if not credentials:
        return None
    try:
        return decode_token(credentials.credentials)
    except HTTPException:
        return None


async def get_ws_user(websocket: WebSocket) -> Optional[Dict[str, Any]]:
    """Extract JWT from WebSocket query params."""
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        return decode_token(token)
    except HTTPException:
        return None


def require_role(required_role: str):
    """Dependency factory that checks user role."""
    async def _check(user: Dict = Depends(get_current_user)):
        user_role = user.get("role", "viewer")
        role_hierarchy = {"admin": 3, "operator": 2, "viewer": 1}
        if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role, 0):
            raise HTTPException(
                status_code=403,
                detail=f"Requires {required_role} role, you have {user_role}",
            )
        return user
    return _check
