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
    theme:Mapped[str]=mapped_column(String(24),default="forest-light")
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
