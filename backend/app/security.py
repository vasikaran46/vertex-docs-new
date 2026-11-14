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
    return user
