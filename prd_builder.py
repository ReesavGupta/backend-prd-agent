import os
import uuid
from datetime import datetime

from langchain_nomic.embeddings import NomicEmbeddings
from langchain_pinecone.vectorstores import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from graph import create_prd_builder_graph
from typing import Dict, Any, List, Optional, cast
from state import SessionConfig, PRDBuilderState, SectionStatus
from langchain.schema import HumanMessage
from prompts import PRD_TEMPLATE_SECTIONS
from langgraph.checkpoint.sqlite import SqliteSaver 
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from RAGService import CompleteRagService

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
        self.rag: Optional[CompleteRagService] = None


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
            run_assembler=False,
            rag_enabled=False,
            rag_context="",
            rag_sources=[]
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
    
    
    def send_message(self, session_id: str, message: str, attachments: List[str] | None = None) -> Dict:
        """Send a message to an existing session, optionally ingesting attachments for RAG."""
		
        thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
		
		# Get current state
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
		
        rag_context = ""
        try:
            if attachments:
                self._ensure_rag()
				# Ingest PDFs only
                for path in attachments:
                    if path.lower().endswith(".pdf"):
                        try:
                            self.rag.ingest_pdf(pdf_path=path, markdown_dir=f"ingested/{session_id}", extra_metadata={"session_id": session_id})
                        except Exception as ingest_exc:
                            print(f"[RAG][WARN] Failed to ingest {path}: {ingest_exc}")
				# Build initial context from the current message
                try:
                    docs = self.rag.semantic_search(query=message, k=5, fetch_k=50, metadata_filter={"session_id": session_id})
                    rag_context = "\n\n".join(d.page_content for d in docs)
                except Exception as srch_exc:
                    print(f"[RAG][WARN] Retrieval failed: {srch_exc}")
            else:
				# If session already has RAG docs, still retrieve for this message
                if bool(snapshot.values.get("rag_enabled", False)) and self.rag is not None:
                    try:
                        docs = self.rag.semantic_search(query=message, k=5, fetch_k=50, metadata_filter={"session_id": session_id})
                        rag_context = "\n\n".join(d.page_content for d in docs)
                    except Exception as srch_exc:
                        print(f"[RAG][WARN] Retrieval failed: {srch_exc}")
        except Exception as e:
            print(f"[RAG][ERROR] RAG pipeline error: {e}")
		
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
                try:
                    is_waiting_human = bool(snapshot.values.get("needs_human_input", False))
                except Exception:
                    is_waiting_human = False

            if is_waiting_human:
                print(f"[PRD] Resuming interrupt for session {session_id} via Command(resume)")
                resume_payload: Dict[str, Any] = {"data": message}
                if rag_context:
                    resume_payload["rag_context"] = rag_context
                    resume_payload["rag_enabled"] = True
                try:
                    events = list(self.app.stream(Command(resume=resume_payload), config=thread_config, stream_mode="values"))
                    result = events[-1] if events else self.app.get_state(thread_config).values
                except Exception as resume_exc:
                    print(f"[PRD][WARN] Resume failed for {session_id}: {resume_exc}")
                    user_input: PRDBuilderState = {"latest_user_input": message, "needs_human_input": False}
                    if rag_context:
                        user_input["rag_context"] = rag_context
                        user_input["rag_enabled"] = True
                    events = list(self.app.stream(user_input, config=thread_config, stream_mode="values"))
                    result = events[-1] if events else self.app.get_state(thread_config).values
            else:
                print(f"[PRD] Continuing session {session_id} without interrupt")
                user_input: PRDBuilderState = {"latest_user_input": message, "needs_human_input": False}
                if rag_context:
                    user_input["rag_context"] = rag_context
                    user_input["rag_enabled"] = True
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

    def _ensure_rag(self) -> None:
        if self.rag is not None:
            return
        nomic_key = os.getenv("NOMIC_KEY")
        pinecone_key = os.getenv("PINECONE_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "rag-index")
        if not nomic_key or not pinecone_key:
            raise RuntimeError("RAG not configured: set NOMIC_KEY and PINECONE_KEY")

        embedding_model = NomicEmbeddings(nomic_api_key=nomic_key, model="nomic-embed-text-v1.5")
        pc = Pinecone(api_key=pinecone_key)
        # Ensure index exists
        try:
            existing = pc.list_indexes().names()  # type: ignore[attr-defined]
        except Exception:
            try:
                existing = [idx.name for idx in pc.list_indexes()]  # type: ignore[assignment]
            except Exception:
                existing = []
        if index_name not in existing:
            pc.create_index(
                name=index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        index = pc.Index(index_name)
        vectorstore = PineconeVectorStore(embedding=embedding_model, index=index)
        self.rag = CompleteRagService(llm=None, vectorstore=vectorstore, embedding_model=embedding_model)