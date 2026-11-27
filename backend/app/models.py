from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, false, func
from sqlalchemy.schema import FetchedValue
from sqlalchemy.orm import Mapped,mapped_column,relationship
from .database import Base
class User(Base):
    __tablename__="users"
    __mapper_args__={"eager_defaults":False}
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(120))
    email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
    password_hash:Mapped[str|None]=mapped_column(String(255),nullable=True)
    theme:Mapped[str]=mapped_column(String(24),default="violet")
    language:Mapped[str]=mapped_column(String(20),default="en")
    avatar:Mapped[str]=mapped_column(String(80),default="pip")
    # Nullable during phased Supabase Auth rollout; existing integer IDs remain
    # the application identity and all document/activity foreign keys stay intact.
    supabase_auth_id:Mapped[str|None]=mapped_column(
        Uuid(as_uuid=False),nullable=True,unique=True,index=True,deferred=True,server_default=FetchedValue()
    )
    # Deferred and server-defaulted so legacy user reads/inserts do not require
    # the additive column until its approved migration has been applied.
    is_admin:Mapped[bool]=mapped_column(Boolean,nullable=False,server_default=false(),deferred=True)
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

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20)) # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ActivityLog(Base):
    __tablename__="activity_logs"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),nullable=False)
    action:Mapped[str]=mapped_column(String(80),nullable=False)
    entity_type:Mapped[str]=mapped_column(String(80),nullable=False)
    entity_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    # `metadata` is reserved by Declarative; this maps the DB column of that
    # name to a safe JSON value through a non-reserved Python attribute.
    metadata_json:Mapped[dict]=mapped_column("metadata",JSON,nullable=False,default=dict,server_default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow,server_default=func.current_timestamp())

    __table_args__=(
        Index("ix_activity_logs_user_created_at","user_id","created_at"),
        Index("ix_activity_logs_action_created_at","action","created_at"),
    )


class HistoryEvent(Base):
    """Persistent, per-user record of document operations shown on Document History."""
    __tablename__="history_events"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    # Plain integer (no FK) so history survives after a document is deleted.
    document_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    file_name:Mapped[str|None]=mapped_column(String(255),nullable=True)
    file_type:Mapped[str|None]=mapped_column(String(24),nullable=True)
    action:Mapped[str]=mapped_column(String(80))
    category:Mapped[str]=mapped_column(String(24),default="other")
    detail:Mapped[str|None]=mapped_column(String(300),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)


class Notification(Base):
    __tablename__="notifications"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    kind:Mapped[str]=mapped_column(String(40),default="info")
    title:Mapped[str]=mapped_column(String(160))
    message:Mapped[str|None]=mapped_column(String(400),nullable=True)
    document_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    is_read:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,index=True)


class DocumentShare(Base):
    __tablename__="document_shares"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    document_id:Mapped[int]=mapped_column(ForeignKey("documents.id",ondelete="CASCADE"),index=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    token:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    recipient_email:Mapped[str|None]=mapped_column(String(255),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    revoked:Mapped[bool]=mapped_column(Boolean,default=False)
    download_count:Mapped[int]=mapped_column(Integer,default=0)
    emailed:Mapped[bool]=mapped_column(Boolean,default=False)


class SignatureRequest(Base):
    __tablename__="signature_requests"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    document_id:Mapped[int]=mapped_column(ForeignKey("documents.id",ondelete="CASCADE"),index=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    signer_name:Mapped[str]=mapped_column(String(120))
    signer_email:Mapped[str]=mapped_column(String(255))
    message:Mapped[str|None]=mapped_column(String(500),nullable=True)
    token:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    status:Mapped[str]=mapped_column(String(16),default="pending")  # pending|signed|declined|cancelled|expired
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    signature_text:Mapped[str|None]=mapped_column(String(160),nullable=True)
    signed_document_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    emailed:Mapped[bool]=mapped_column(Boolean,default=False)


class PdfAnnotationSet(Base):
    """One JSON annotation set per document, so annotations survive reload and re-open."""
    __tablename__="pdf_annotation_sets"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    document_id:Mapped[int]=mapped_column(ForeignKey("documents.id",ondelete="CASCADE"),unique=True,index=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    annotations:Mapped[list]=mapped_column(JSON,default=list)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
