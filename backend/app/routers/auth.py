<<<<<<< HEAD
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import AuthOut,SignupIn,LoginIn,UserOut
from ..security import hash_password,verify_password,token_for,current_user
=======
from fastapi import APIRouter,Depends,Header,HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db
from ..activity import record_activity
from ..models import User
from ..schemas import AuthOut,SignupIn,LoginIn,UserOut,SupabaseProfileIn
from ..security import (
    hash_password, verify_password, token_for, current_user,
    current_supabase_identity, _legacy_user_from_token, SupabaseIdentity,
)
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
router=APIRouter(prefix="/api/auth",tags=["Authentication"])

def normalized_email(value:str): return value.strip().lower()

def session_for(user:User):
    return {"access_token":token_for(user.id),"token_type":"bearer","user":UserOut.model_validate(user)}

@router.post("/signup",response_model=AuthOut)
def signup(x:SignupIn,db:Session=Depends(get_db)):
    email=normalized_email(x.email)
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409,"Email already registered")
    u=User(name=x.name.strip(),email=email,password_hash=hash_password(x.password))
    db.add(u)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Email already registered")
    db.refresh(u)
<<<<<<< HEAD
=======
    record_activity(u.id,"auth.signup","user",u.id)
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return session_for(u)

@router.post("/login",response_model=AuthOut)
def login(x:LoginIn,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=normalized_email(x.email)).first()
    if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,"Incorrect email or password")
<<<<<<< HEAD
    return session_for(u)
=======
    result=session_for(u)
    record_activity(u.id,"auth.login","user",u.id)
    return result
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5

@router.get("/me",response_model=UserOut)
def me(u=Depends(current_user)): return u

@router.post("/logout")
def logout(u=Depends(current_user)): return {"success":True,"message":"Discard the bearer token on the client."}
<<<<<<< HEAD
=======


@router.post("/profile",response_model=UserOut)
def supabase_profile(
    x:SupabaseProfileIn,
    identity:SupabaseIdentity=Depends(current_supabase_identity),
    db:Session=Depends(get_db),
):
    """Create a local profile for this verified Supabase subject, without email linking."""
    linked=db.query(User).filter_by(supabase_auth_id=identity.auth_user_id).first()
    if linked: return linked
    email=normalized_email(identity.email)
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409,"Existing account requires secure account linking")
    u=User(
        name=x.name.strip(),email=email,password_hash=None,
        supabase_auth_id=identity.auth_user_id,is_admin=False,
    )
    if len(u.name)<2: raise HTTPException(422,"Name must contain at least two characters")
    db.add(u)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Account profile already exists")
    db.refresh(u)
    record_activity(u.id,"auth.signup","user",u.id)
    return u


@router.post("/link-supabase",response_model=UserOut)
def link_supabase_account(
    identity:SupabaseIdentity=Depends(current_supabase_identity),
    legacy_token:str=Header(...,alias="X-Legacy-Token"),
    db:Session=Depends(get_db),
):
    """Link only when the caller proves both the Supabase and legacy sessions."""
    legacy_user=_legacy_user_from_token(legacy_token,db)
    if normalized_email(identity.email)!=normalized_email(legacy_user.email):
        raise HTTPException(403,"Authenticated accounts do not match")
    if legacy_user.supabase_auth_id and legacy_user.supabase_auth_id!=identity.auth_user_id:
        raise HTTPException(409,"Account is already linked to another Supabase user")
    other=db.query(User).filter_by(supabase_auth_id=identity.auth_user_id).first()
    if other and other.id!=legacy_user.id:
        raise HTTPException(409,"Supabase account is already linked")
    if legacy_user.supabase_auth_id==identity.auth_user_id: return legacy_user
    legacy_user.supabase_auth_id=identity.auth_user_id
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Account is already linked")
    db.refresh(legacy_user)
    record_activity(legacy_user.id,"auth.supabase_link","user",legacy_user.id)
    return legacy_user


@router.post("/login-event")
def supabase_login_event(
    identity:SupabaseIdentity=Depends(current_supabase_identity),
    db:Session=Depends(get_db),
):
    user=db.query(User).filter_by(supabase_auth_id=identity.auth_user_id).first()
    if not user: raise HTTPException(401,"Supabase account is not linked")
    record_activity(user.id,"auth.login","user",user.id)
    return {"success":True}
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
