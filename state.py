from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
from langchain.schema import BaseMessage
from typing import Any, TypedDict, Annotated, Dict, List, Optional, Literal
from langgraph.graph.message import add_messages

class SectionStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    STALE = "stale"

class IntentType(Enum):
    SECTION_UPDATE = "section_update"
    OFF_TARGET_UPDATE = "off_target_update"
    REVISION = "revision"
    META_QUERY = "meta_query"
    OFF_TOPIC = "off_topic"

@dataclass
class PRDSection:
    key: str
    content: str = ""
    status: SectionStatus = SectionStatus.PENDING
    last_updated: datetime = field(default_factory=datetime.now)
    dependencies: List[str] = field(default_factory=list)
    checklist_items: List[str] = field(default_factory=list)
    completion_score: float = 0.0

@dataclass 
class SessionConfig:
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    current_section: Optional[str] = None
    turn_counter: int = 0

class PRDBuilderState(TypedDict):
    # Core session data
    config: SessionConfig
    
    # User interaction
    messages: Annotated[List[BaseMessage], add_messages]
    latest_user_input: str
    
    # PRD content
    normalized_idea: str
    prd_sections: Dict[str, PRDSection]
    section_order: List[str]
    prd_snapshot: str
    issues_list: List[str]
    versions: List[Dict[str, Any]]
    
    # Workflow control
    current_stage: Literal["init", "plan", "build", "assemble", "review", "export"]
    intent_classification: Optional[IntentType]
    target_section: Optional[str]
    
    # Memory management
    conversation_summary: str
    glossary: Dict[str, str]
    
    # Human-in-the-loop control
    needs_human_input: bool
    human_feedback: Optional[str]
    checkpoint_reason: str
    # Assembler control
    run_assembler: bool