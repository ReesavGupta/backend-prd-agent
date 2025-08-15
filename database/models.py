import uuid
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

class PRDStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class User(BaseModel):
    user_id: str = Field(..., primary_key=True)
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now())
    last_active: datetime = Field(default_factory=datetime.now())

class ChatMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now())
    message_type: str = "user"  # user, assistant, system
    metadata: Optional[Dict] = None

class PRDDocument(BaseModel):
    prd_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str
    title: str
    normalized_idea: str
    prd_sections: Dict[str, Dict]
    prd_snapshot: str
    status: PRDStatus = PRDStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.now())
    updated_at: datetime = Field(default_factory=datetime.now())
    published_at: Optional[datetime] = None
    
    # Diagrams
    flowcharts: Dict[str, str] = Field(default_factory=dict)  # type -> mermaid_code
    er_diagrams: Dict[str, str] = Field(default_factory=dict)  # type -> mermaid_code
    
    # Metadata
    version: int = 1
    tags: List[str] = Field(default_factory=list)
    completion_score: float = 0.0