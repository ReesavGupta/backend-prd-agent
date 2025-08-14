import uuid
from datetime import datetime
from graph import create_prd_builder_graph
from typing import Dict, Any, cast
from state import SessionConfig, PRDBuilderState, SectionStatus
from langchain.schema import HumanMessage
from prompts import PRD_TEMPLATE_SECTIONS
from langgraph.checkpoint.sqlite import SqliteSaver 
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

class ThinkingLensPRDBuilder:
    """Main interface for the PRD Builder Agent"""
    
    def __init__(self, checkpointer: BaseCheckpointSaver | None = None):
        self.workflow = create_prd_builder_graph()
        # Default to in-memory checkpointer for thread-safety during development
        if checkpointer is not None:
            self._checkpointer_cm = None
            self.checkpointer = checkpointer
        else:
            self._checkpointer_cm = None
            self.checkpointer = InMemorySaver()

        self.app = self.workflow.compile(checkpointer=self.checkpointer)
        
    def __del__(self):
        cm = getattr(self, "_checkpointer_cm", None)
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass

    def start_session(self, user_id: str, initial_idea: str) -> Dict:
        """Start a new PRD building session"""
        
        session_id = str(uuid.uuid4())
        config = SessionConfig(session_id=session_id, user_id=user_id)
        
        initial_state = PRDBuilderState(
            config=config,
            messages=[HumanMessage(content=initial_idea)],
            latest_user_input=initial_idea,
            normalized_idea="",
            prd_sections={},
            section_order=[],
            prd_snapshot="",
            issues_list=[],
            current_stage="init",
            intent_classification=None,
            target_section=None,
            conversation_summary="",
            glossary={},
            needs_human_input=False,
            human_feedback=None,
            versions=[],
            checkpoint_reason="",
            run_assembler=False
        )
        
        thread_config:RunnableConfig = {"configurable": {"thread_id": session_id}}
        
        # Run until first human input needed
        result = self.app.invoke(initial_state, config=thread_config)
        
        return {
            "session_id": session_id,
            "status": "success", 
            "message": result["messages"][-1].content if result["messages"] else "Session started",
            "stage": result["current_stage"],
            "needs_input": result.get("needs_human_input", False)
        }
    
    def send_message(self, session_id: str, message: str) -> Dict:
        """Send a message to an existing session"""
        
        thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        
        # Get current state
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
        
        try:
            # Determine if we are currently paused at an interrupt/human input
            pending_next = getattr(snapshot, "next", None)
            print(f"[PRD] snapshot.next for {session_id}: {pending_next}")
            is_waiting_human = False
            if pending_next and isinstance(pending_next, (list, tuple)):
                is_waiting_human = "human_input" in pending_next
            elif isinstance(pending_next, str):
                is_waiting_human = pending_next == "human_input"
            else:
                # Fallback to state flag if next is unavailable
                try:
                    is_waiting_human = bool(snapshot.values.get("needs_human_input", False))
                except Exception:
                    is_waiting_human = False

            if is_waiting_human:
                print(f"[PRD] Resuming interrupt for session {session_id} via Command(resume)")
                try:
                    # Prefer stream for robust resume semantics
                    events = list(self.app.stream(Command(resume=message), config=thread_config, stream_mode="values"))
                    result = events[-1] if events else self.app.get_state(thread_config).values
                except Exception as resume_exc:
                    # Log and fallback to standard invoke to avoid hard failure in dev
                    print(f"[PRD][WARN] Resume failed for {session_id}: {resume_exc}")
                    user_input:PRDBuilderState  = cast (PRDBuilderState, {"latest_user_input": message, "needs_human_input": False})
                    events = list(self.app.stream(user_input, config=thread_config, stream_mode="values"))
                    result = events[-1] if events else self.app.get_state(thread_config).values
            else:
                print(f"[PRD] Continuing session {session_id} without interrupt")
                user_input:PRDBuilderState  = cast (PRDBuilderState, {"latest_user_input": message, "needs_human_input": False})
                events = list(self.app.stream(user_input, config=thread_config, stream_mode="values"))
                result = events[-1] if events else self.app.get_state(thread_config).values
            
            return {
                "session_id": session_id,
                "status": "success",
                "message": result["messages"][-1].content if result["messages"] else "Processed",
                "stage": result["current_stage"],
                "needs_input": result.get("needs_human_input", False),
                "current_section": result["config"].current_section
            }
            
        except Exception as e:
            print(f"[PRD][ERROR] send_message failed for {session_id}: {e}")
            return {"status": "error", "message": f"Error processing message: {str(e)}"}
    
    def get_prd_draft(self, session_id: str) -> Dict:
        """Get the current PRD draft"""
        thread_config:RunnableConfig = {"configurable": {"thread_id": session_id}}
        
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
        
        state = snapshot.values
        
        # Build current draft
        sections_completed = {}
        sections_in_progress = {}
        
        for key, section in state["prd_sections"].items():
            section_info = {
                "title": PRD_TEMPLATE_SECTIONS[key]["title"],
                "content": section.content,
                "status": section.status.value,
                "completion_score": section.completion_score,
                "last_updated": section.last_updated.isoformat() if section.last_updated else None
            }
            
            if section.status == SectionStatus.COMPLETED:
                sections_completed[key] = section_info
            elif section.status == SectionStatus.IN_PROGRESS:
                sections_in_progress[key] = section_info
        
        return {
            "session_id": session_id,
            "status": "success",
            "normalized_idea": state.get("normalized_idea", ""),
            "current_stage": state.get("current_stage", ""),
            "current_section": state["config"].current_section,
            "sections_completed": sections_completed,
            "sections_in_progress": sections_in_progress,
            "prd_snapshot": state.get("prd_snapshot", ""),
            "issues": state.get("issues_list", []),
            "progress": f"{len(sections_completed)}/{len(state['prd_sections'])} sections completed"
        }
    
    def export_prd(self, session_id: str, format: str = "markdown") -> Dict:
        """Export the final PRD"""
        thread_config:RunnableConfig = {"configurable": {"thread_id": session_id}}
        
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
        
        state = snapshot.values
        
        if format == "markdown":
            content = state.get("prd_snapshot", "PRD not yet assembled")
            
            return {
                "session_id": session_id,
                "status": "success",
                "format": "markdown",
                "content": content,
                "filename": f"prd_{session_id}.md",
                "created_at": datetime.now().isoformat()
            }
        
        return {"status": "error", "message": f"Format {format} not supported"}

    def list_versions(self, session_id: str) -> Dict:
        thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
        state = snapshot.values
        return {"status": "success", "session_id": session_id, "versions": state.get("versions", [])}

    def get_version(self, session_id: str, version_id: str) -> Dict:
        thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
        versions = snapshot.values.get("versions", [])
        for v in versions:
            if v.get("version_id") == version_id:
                return {"status": "success", "session_id": session_id, "version": v}
        return {"status": "error", "message": "Version not found"}