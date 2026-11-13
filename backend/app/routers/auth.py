from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import SignupIn,LoginIn,UserOut
from ..security import hash_password,verify_password,token_for,current_user
router=APIRouter(prefix="/api/auth",tags=["Authentication"])
@router.post("/signup",response_model=UserOut)
def signup(x:SignupIn,db:Session=Depends(get_db)):
    email=x.email.lower()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409,"Email already registered")
    u=User(name=x.name.strip(),email=email,password_hash=hash_password(x.password))
    db.add(u);db.commit();db.refresh(u);return u
@router.post("/login")
def login(x:LoginIn,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=x.email.lower()).first()
    if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":token_for(u.id),"token_type":"bearer","user":UserOut.model_validate(u)}
@router.get("/me",response_model=UserOut)
def me(u=Depends(current_user)): return u
@router.post("/logout")
def logout(u=Depends(current_user)): return {"success":True,"message":"Discard the bearer token on the client."}
