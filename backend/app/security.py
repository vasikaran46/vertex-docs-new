<<<<<<< HEAD
import os
from datetime import datetime,timedelta,timezone
from jose import jwt,JWTError
from passlib.context import CryptContext
from fastapi import Depends,HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
oauth=OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def hash_password(p): return pwd.hash(p)
def verify_password(p,h):
    try: return pwd.verify(p,h)
    except (TypeError,ValueError): return False
def token_for(uid):
    exp=datetime.now(timezone.utc)+timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES","720")))
    return jwt.encode({"sub":str(uid),"exp":exp},os.getenv("SECRET_KEY","dev-only-change-me"),algorithm="HS256")
def current_user(token:str=Depends(oauth),db:Session=Depends(get_db)):
    try: uid=int(jwt.decode(token,os.getenv("SECRET_KEY","dev-only-change-me"),algorithms=["HS256"])["sub"])
    except Exception: raise HTTPException(401,"Invalid or expired session")
    user=db.get(User,uid)
    if not user: raise HTTPException(401,"Invalid session")
=======
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from uuid import UUID
from urllib.parse import urlsplit

from jose import jwk, jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
_JWKS_CACHE: dict[str, tuple[float, dict]] = {}
_JWKS_LOCK = threading.Lock()
_JWKS_TTL_SECONDS = 600


@dataclass(frozen=True)
class SupabaseIdentity:
    auth_user_id: str
    email: str


def hash_password(password):
    return pwd.hash(password)


def verify_password(password, password_hash):
    try:
        return bool(password_hash) and pwd.verify(password, password_hash)
    except (TypeError, ValueError):
        return False


def token_for(uid):
    exp = datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "720")))
    return jwt.encode({"sub": str(uid), "exp": exp}, os.getenv("SECRET_KEY", "dev-only-change-me"), algorithm="HS256")


def _supabase_project_url() -> str:
    value = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    parsed = urlsplit(value)
    if not parsed.netloc or parsed.scheme not in {"https", "http"}:
        raise HTTPException(401, "Invalid Supabase session")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(401, "Invalid Supabase session")
    return value


def _get_supabase_jwks(jwks_url: str) -> dict:
    now = time.monotonic()
    cached = _JWKS_CACHE.get(jwks_url)
    if cached and cached[0] > now:
        return cached[1]
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get(jwks_url)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            with urlopen(jwks_url, timeout=5) as response:
                document = json.loads(response.read())
            if not isinstance(document.get("keys"), list):
                raise ValueError("Invalid JWKS")
        except Exception:
            raise HTTPException(401, "Invalid Supabase session") from None
        _JWKS_CACHE[jwks_url] = (time.monotonic() + _JWKS_TTL_SECONDS, document)
        return document


def _verify_with_auth_api(token: str, project_url: str, expected_user_id: str) -> SupabaseIdentity:
    # Supabase recommends Auth-server verification for shared-secret signing
    # keys. The publishable key is public and is never used to sign or elevate.
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not publishable_key:
        raise HTTPException(401, "Invalid Supabase session")
    request = Request(
        f"{project_url}/auth/v1/user",
        headers={"apikey": publishable_key, "Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            user = json.loads(response.read())
        auth_user_id = str(UUID(str(user.get("id", ""))))
        email = user.get("email")
        if auth_user_id != expected_user_id or not isinstance(email, str) or not email.strip():
            raise ValueError("Invalid authenticated user")
        return SupabaseIdentity(auth_user_id, email.strip().lower())
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid Supabase session") from None


def verify_supabase_access_token(token: str) -> SupabaseIdentity:
    project_url = _supabase_project_url()
    issuer = f"{project_url}/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        unverified_claims = jwt.get_unverified_claims(token)
        if unverified_claims.get("iss") != issuer:
            raise ValueError("Invalid issuer")
        auth_user_id = str(UUID(str(unverified_claims.get("sub", ""))))
        algorithm = header.get("alg")
        if algorithm in {"RS256", "ES256"}:
            jwks_url = f"{project_url}/auth/v1/.well-known/jwks.json"
            keys = _get_supabase_jwks(jwks_url).get("keys", [])
            matching_key = next(
                (
                    key for key in keys
                    if key.get("kid") == header.get("kid")
                    and key.get("use", "sig") == "sig"
                    and key.get("alg", algorithm) == algorithm
                ),
                None,
            )
            if matching_key is None:
                raise ValueError("Signing key not found")
            verified_claims = jwt.decode(
                token,
                jwk.construct(matching_key, algorithm=algorithm),
                algorithms=[algorithm],
                audience="authenticated",
                issuer=issuer,
            )
            email = verified_claims.get("email")
            if "exp" not in verified_claims or str(UUID(str(verified_claims.get("sub", "")))) != auth_user_id:
                raise ValueError("Required claims are missing")
            if not isinstance(email, str) or not email.strip():
                raise ValueError("Verified email is missing")
            return SupabaseIdentity(auth_user_id, email.strip().lower())
        # Handles legacy HS256 signing keys and other Supabase-supported
        # algorithms without ever storing or receiving the signing secret.
        return _verify_with_auth_api(token, project_url, auth_user_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid Supabase session") from None


def _legacy_user_from_token(token: str, db: Session) -> User:
    try:
        uid = int(jwt.decode(token, os.getenv("SECRET_KEY", "dev-only-change-me"), algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Invalid or expired session") from None
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Invalid session")
    return user


def current_supabase_identity(token: str = Depends(oauth)) -> SupabaseIdentity:
    return verify_supabase_access_token(token)


def current_user(token: str = Depends(oauth), db: Session = Depends(get_db)) -> User:
    try:
        claims = jwt.get_unverified_claims(token)
    except Exception:
        return _legacy_user_from_token(token, db)
    if not isinstance(claims, dict):
        raise HTTPException(401, "Invalid or expired session")
    if claims.get("iss") is None:
        return _legacy_user_from_token(token, db)

    identity = verify_supabase_access_token(token)
    user = db.query(User).filter(User.supabase_auth_id == identity.auth_user_id).first()
    if not user:
        raise HTTPException(401, "Supabase account is not linked")
    return user


def current_admin(user: User = Depends(current_user)):
    """Require an authenticated user whose persisted account is an administrator."""
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required")
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return user
