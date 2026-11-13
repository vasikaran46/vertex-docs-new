from datetime import datetime
from sqlalchemy import String,Integer,ForeignKey,DateTime,Text
from sqlalchemy.orm import Mapped,mapped_column,relationship
from .database import Base
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(120))
    email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    theme:Mapped[str]=mapped_column(String(24),default="forest-light")
    language:Mapped[str]=mapped_column(String(20),default="en")
    avatar:Mapped[str]=mapped_column(String(80),default="pip")
class Document(Base):
    __tablename__="documents"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    original_name:Mapped[str]=mapped_column(String(255))
    stored_name:Mapped[str]=mapped_column(String(255),unique=True)
    content_type:Mapped[str]=mapped_column(String(120))
    size:Mapped[int]=mapped_column(Integer)
class AssistantConversation(Base):
    __tablename__="assistant_conversations"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    title:Mapped[str]=mapped_column(String(120),default="New chat")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,index=True)
class AssistantMessage(Base):
    __tablename__="assistant_messages"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    conversation_id:Mapped[int]=mapped_column(ForeignKey("assistant_conversations.id",ondelete="CASCADE"),index=True)
    role:Mapped[str]=mapped_column(String(16))
    content:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
