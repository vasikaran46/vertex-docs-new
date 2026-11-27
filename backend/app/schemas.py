from datetime import datetime
from typing import Literal
from pydantic import BaseModel,EmailStr,Field
class SignupIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):
    email:EmailStr
    password:str
class SupabaseProfileIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
class UserOut(BaseModel):
    id:int; name:str; email:str; theme:str; language:str; avatar:str
    class Config: from_attributes=True
class AuthOut(BaseModel):
    access_token:str
    token_type:Literal["bearer"]="bearer"
    user:UserOut
class PreferencesIn(BaseModel):
    # Theme ids are validated by shape rather than a fixed list so new colour themes can ship
    # from the frontend without a schema change. Legacy ids ("forest-dark", "dark", ...) are still accepted.
    theme:str|None=Field(default=None,pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",min_length=2,max_length=24)
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
class HumanizeIn(BaseModel):
    text:str=Field(min_length=1,max_length=20000)
    writing_style:Literal["simple","professional","conversational","academic"]="simple"
    strength:int=Field(default=3,ge=1,le=5)
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

class ChatSessionCreate(BaseModel):
    title: str | None = Field(default="New chat", max_length=200)

class ChatSessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)

class ChatMessageCreate(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    language: str | None = None
    document_id: int | None = None
    attachment_name: str | None = None

class ChatMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    language: str | None = None
    document_id: int | None = None
    attachment_name: str | None = None
    created_at: datetime
    class Config:
        from_attributes = True

class ChatSessionOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class ChatSessionDetailOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageOut]
    class Config:
        from_attributes = True
