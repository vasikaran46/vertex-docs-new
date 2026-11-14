from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import AuthOut,SignupIn,LoginIn,UserOut
from ..security import hash_password,verify_password,token_for,current_user
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
    return session_for(u)

@router.post("/login",response_model=AuthOut)
def login(x:LoginIn,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=normalized_email(x.email)).first()
    if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,"Incorrect email or password")
    return session_for(u)

@router.get("/me",response_model=UserOut)
def me(u=Depends(current_user)): return u

@router.post("/logout")
def logout(u=Depends(current_user)): return {"success":True,"message":"Discard the bearer token on the client."}
