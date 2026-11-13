from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import current_user
from ..schemas import PreferencesIn,UserOut
router=APIRouter(prefix="/api/settings",tags=["Settings"])
@router.get("/preferences",response_model=UserOut)
def get_prefs(u=Depends(current_user)): return u
@router.put("/preferences",response_model=UserOut)
def set_prefs(x:PreferencesIn,db:Session=Depends(get_db),u=Depends(current_user)):
    if x.theme is not None:
        legacy_themes={
            "light":"forest-light","dark":"graphite-dark","porcelain":"graphite-light",
            "forest":"forest-light","rose":"rose-light","graphite":"graphite-light",
            "cocoa":"cocoa-light","amber":"amber-light","ocean":"ocean-light",
            "mint":"forest-light","sand":"cocoa-light","sage":"forest-light",
        }
        u.theme=legacy_themes.get(x.theme,x.theme)
    if x.language is not None: u.language=x.language
    if x.avatar is not None: u.avatar=x.avatar
    db.commit();db.refresh(u);return u
