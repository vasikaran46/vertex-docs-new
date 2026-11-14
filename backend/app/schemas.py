from typing import Literal
from pydantic import BaseModel,EmailStr,Field
class SignupIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):
    email:EmailStr
    password:str
class UserOut(BaseModel):
    id:int; name:str; email:str; theme:str; language:str; avatar:str
    class Config: from_attributes=True
class AuthOut(BaseModel):
    access_token:str
    token_type:Literal["bearer"]="bearer"
    user:UserOut
class PreferencesIn(BaseModel):
    theme:Literal[
        "forest-light","forest-dark","rose-light","rose-dark","graphite-light","graphite-dark",
        "cocoa-light","cocoa-dark","amber-light","amber-dark","ocean-light","ocean-dark",
        "green-white-light","green-white-dark","midnight-luxury-light","midnight-luxury-dark",
        "sage-balance-light","sage-balance-dark","nordic-espresso-light","nordic-espresso-dark",
        "steel-minimalist-light","steel-minimalist-dark","warm-plum-light","warm-plum-dark",
        "deep-teal-light","deep-teal-dark",
        "forest","rose","graphite","cocoa","amber","ocean","porcelain","mint","sand","sage","dark","light",
    ]|None=None
    language:str|None=None
    avatar:Literal["robo","nova","finn","milo","pip","wiz"]|None=None
class ChatTurn(BaseModel):
    role:Literal["user","assistant"]
    content:str=Field(min_length=1,max_length=12000)
class ChatIn(BaseModel):
    message:str=Field(min_length=1,max_length=12000)
    language:Literal["en","ta","hi","ml","te","kn","ja","de","sa","bn","fr","es","tanglish"]="en"
    conversation_id:int|None=None
    context:str|None=Field(default=None,max_length=12000)
    image_data:str|None=Field(default=None,max_length=6000000)
    image_media_type:Literal["image/png","image/jpeg","image/webp"]="image/png"
    history:list[ChatTurn]=Field(default_factory=list,max_length=12)
class DocumentChatIn(BaseModel):
    message:str=Field(min_length=1,max_length=12000)
    language:Literal["en","ta","hi","ml","te","kn","ja","de","sa","bn","fr","es","tanglish"]="en"
    history:list[ChatTurn]=Field(default_factory=list,max_length=12)
class DocumentLanguageIn(BaseModel):
    language:Literal["en","ta","hi","ml","te","kn","ja","de","sa","bn","fr","es","tanglish"]="en"
class DocumentTranslationIn(BaseModel):
    source_language:Literal["auto","en","ta","hi","ml","te","kn","ja","de","sa","bn","fr","es","tanglish"]="auto"
    target_language:Literal["en","ta","hi","ml","te","kn","ja","de","sa","bn","fr","es","tanglish"]
class TranslationIn(BaseModel):
    text:str=Field(min_length=1,max_length=20000)
    source_language:Literal["auto","en","ta","hi","ml","te","kn","ja","de","sa","bn","fr","es","tanglish"]="auto"
    target_language:Literal["en","ta","hi","ml","te","kn","ja","de","sa","bn","fr","es","tanglish"]
class TemplateRenderIn(BaseModel):
    template:Literal["resume","cover-letter","business-letter","meeting-notes","project-proposal","invoice"]
    layout:Literal["modern","classic","compact"]="modern"
    accent:Literal["forest","rose","graphite","cocoa","amber","ocean"]="forest"
    full_name:str=Field(default="Your Name",max_length=120)
    title:str=Field(default="",max_length=160)
    email:str=Field(default="",max_length=160)
    phone:str=Field(default="",max_length=80)
    location:str=Field(default="",max_length=160)
    website:str=Field(default="",max_length=200)
    recipient:str=Field(default="",max_length=160)
    company:str=Field(default="",max_length=160)
    date:str=Field(default="",max_length=80)
    subject:str=Field(default="",max_length=200)
    summary:str=Field(default="",max_length=3000)
    experience:str=Field(default="",max_length=8000)
    education:str=Field(default="",max_length=5000)
    skills:str=Field(default="",max_length=2000)
    body:str=Field(default="",max_length=12000)
    photo_data:str|None=Field(default=None,max_length=3000000)
class EditorExportIn(BaseModel):
    content:str=Field(default="",max_length=50000)
    image_data:str|None=Field(default=None,max_length=6000000)
    drawing_data:str|None=Field(default=None,max_length=6000000)
    page_preview_data:str|None=Field(default=None,max_length=6000000)
    output_format:Literal["pdf","docx","txt"]="pdf"
    page_size:Literal["A4","Letter"]="A4"
