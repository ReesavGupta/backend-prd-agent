import os
import uuid
import asyncio
from datetime import datetime
from langchain_nomic.embeddings import NomicEmbeddings
from langchain_pinecone.vectorstores import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from pymongo import MongoClient
from database.database import MongoDBService
from database.redis import RedisService
from graph import create_prd_builder_graph
from typing import Dict, Any, List, Optional, cast
from llm import LLMInterface
from state import SessionConfig, PRDBuilderState, SectionStatus
from langchain.schema import HumanMessage
from prompts import PRD_TEMPLATE_SECTIONS 
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from RAGService import CompleteRagService
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.mongodb import MongoDBSaver

class ThinkingLensPRDBuilder:
    """Main interface for the PRD Builder Agent"""
    
    def __init__(self, checkpointer: BaseCheckpointSaver | None = None):
        self.workflow = create_prd_builder_graph()
        
        if checkpointer is not None:
            self.checkpointer = checkpointer
        else:
            if os.getenv("MONGODB_URI"):
                try:
                    client = MongoClient(os.getenv("MONGODB_URI"))
                    self.checkpointer = MongoDBSaver(client)
                    print(f"MongoDB checkpointer initialized successfully: {self.checkpointer}")
                except Exception as e:
                    print(f"MongoDB checkpointer failed: {e}")
                    self.checkpointer = SqliteSaver(conn="prd_sessions.db")
            else:
                self.checkpointer = SqliteSaver(conn="prd_sessions.db")

        self.app = self.workflow.compile(checkpointer=self.checkpointer)
        self.rag: Optional[CompleteRagService] = None

        try:
            self.mongodb_service = MongoDBService()
            self.redis_service = RedisService()
            print("Database services initialized successfully")
        except Exception as e:
            print(f"Database services initialization failed: {e}")
            self.mongodb_service = None
            self.redis_service = None
    
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
                
				# Ingest PDFs and text files
                for path in attachments:
                    if path.lower().endswith(".pdf"):
                        try:
                            result = self.rag.ingest_pdf(pdf_path=path, markdown_dir=f"ingested/{session_id}", extra_metadata={"session_id": session_id})
                        except Exception as ingest_exc:
                            print(f"[RAG][WARN] Failed to ingest PDF {path}: {ingest_exc}")
                    elif path.lower().endswith((".txt", ".md", ".text")):
                        try:
                            result = self.rag.ingest_text(text_path=path, extra_metadata={"session_id": session_id})
                        except Exception as ingest_exc:
                            print(f"[RAG][WARN] Failed to ingest text file {path}: {ingest_exc}")
                
                # Set RAG as enabled for this session
                # Update the session state to enable RAG
                try:
                    # Get current state again to ensure we have the latest
                    current_snapshot = self.app.get_state(thread_config)
                    if current_snapshot.values:
                        # Create a new state with RAG enabled
                        updated_state = dict(current_snapshot.values)
                        updated_state["rag_enabled"] = True
                        updated_state["rag_context"] = rag_context
                        
                        # Update the state
                        self.app.update_state(thread_config, updated_state)
                    else:
                        print(f"[RAG][WARN] Could not update session state - no current values")
                except Exception as state_update_exc:
                    print(f"[RAG][WARN] Failed to update session state: {state_update_exc}")
                
				# Build initial context from the current message
                try:
                    docs = self.rag.semantic_search(query=message, k=5, fetch_k=50, metadata_filter={"session_id": session_id})
                    rag_context = "\n\n".join(doc.page_content for doc in docs)
                except Exception as srch_exc:
                    print(f"[RAG][WARN] Retrieval failed: {srch_exc}")
            else:
				# If session already has RAG docs, still retrieve for this message
                if bool(snapshot.values.get("rag_enabled", False)) and self.rag is not None:
                    try:
                        docs = self.rag.semantic_search(query=message, k=5, fetch_k=50, metadata_filter={"session_id": session_id})
                        rag_context = "\n\n".join(doc.page_content for doc in docs)
                    except Exception as srch_exc:
                        print(f"[RAG][WARN] Retrieval failed: {srch_exc}")
        except Exception as e:
            print(f"[RAG][ERROR] RAG pipeline error: {e}")
		
        try:
			# Determine if we are currently paused at an interrupt/human input
            pending_next = getattr(snapshot, "next", None)
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
        
        total_sections = len(state["prd_sections"])
        completed_count = len(sections_completed)
        
        if completed_count == total_sections:
            # All sections are complete
            progress_text = f"🎉 All {total_sections} sections completed!"
        elif completed_count == 0:
            # No sections started
            progress_text = f"0/{total_sections} sections completed"
        else:
            # Some sections in progress
            active_sections = [k for k, v in state["prd_sections"].items() 
                             if v.content or v.status == SectionStatus.IN_PROGRESS]
            active_completed = [k for k in sections_completed.keys() 
                               if k in active_sections]
            progress_text = f"{len(active_completed)}/{len(active_sections)} active sections completed"
        
        llm = LLMInterface()
        title = llm.generate_professional_title(state.get("normalized_idea", ""))

        if "professional_title" not in state or not state.get("professional_title"):
            state["professional_title"] = title
        
        professional_title = state["professional_title"]
        

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
            "progress": progress_text,
            "professional_title": professional_title
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

    def generate_flowchart(self, session_id: str, flowchart_type: str = "system_architecture") -> Dict:
        """Generate a technical flowchart based on the current PRD state"""
        thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
        
        state = snapshot.values
        prd_snapshot = state.get("prd_snapshot", "")
        
        if not prd_snapshot:
            return {"status": "error", "message": "PRD not yet assembled"}
        
        try:
            # Check cache first
            cache_key = f"flowchart:{session_id}:{flowchart_type}"
            cached_result = self._get_from_cache(cache_key)

            if cached_result:
                return {
                    "session_id": session_id,
                    "status": "success",
                    "flowchart_type": flowchart_type,
                    "mermaid_code": cached_result,
                    "prd_sections_used": [k for k, v in state["prd_sections"].items() if v.status == SectionStatus.COMPLETED],
                    "generated_at": datetime.now().isoformat(),
                    "cached": True                    
                }

            llm = LLMInterface()
            mermaid_code = llm.generate_technical_flowchart(prd_snapshot, flowchart_type)
            if mermaid_code:
                self._cache_result(cache_key, mermaid_code, ttl=3600)             

            return {
                "session_id": session_id,
                "status": "success",
                "flowchart_type": flowchart_type,
                "mermaid_code": mermaid_code,
                "prd_sections_used": [k for k, v in state["prd_sections"].items() if v.status == SectionStatus.COMPLETED],
                "generated_at": datetime.now().isoformat(),
                "cached": False
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to generate flowchart: {str(e)}"}

    def generate_er_diagram(self, session_id: str, diagram_type: str = "database_schema") -> Dict:
        """Generate an ER diagram based on the current PRD state"""
        thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        
        snapshot = self.app.get_state(thread_config)
        if not snapshot.values:
            return {"status": "error", "message": "Session not found"}
        
        state = snapshot.values
        prd_snapshot = state.get("prd_snapshot", "")
        
        if not prd_snapshot:
            return {"status": "error", "message": "PRD not yet assembled"}
        
        try:
            llm = LLMInterface()
            mermaid_code = llm.generate_er_diagram(prd_snapshot, diagram_type)
            
            return {
                "session_id": session_id,
                "status": "success",
                "diagram_type": diagram_type,
                "mermaid_code": mermaid_code,
                "prd_sections_used": [k for k, v in state["prd_sections"].items() if v.status == SectionStatus.COMPLETED],
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to generate ER diagram: {str(e)}"}
        
    def _get_from_cache(self, key: str) -> Optional[str]:
        """Get cached result from Redis"""
        try:
            if not self.redis_service or not self.redis_service.redis_client:
                return None
                
            # Extract session_id and diagram_type from key
            parts = key.split(":")
            if len(parts) >= 3:
                session_id = parts[1]
                diagram_type = parts[2]
                return self.redis_service.get_cached_diagram(session_id, diagram_type)
        except Exception:
            pass
        return None

    def _cache_result(self, key: str, value: str, ttl: int = 3600) -> None:
        """Cache result in Redis"""
        try:
            # Extract session_id and diagram_type from key
            parts = key.split(":")
            if len(parts) >= 3:
                session_id = parts[1]
                diagram_type = parts[2]
                self.redis_service.cache_diagram(session_id, diagram_type, value)
        except Exception:
            pass
    
    def save_session_to_database(self, session_id: str) -> Dict:
        """Save the current session state to MongoDB permanently"""
        thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
        
        try:
            # Get current state
            snapshot = self.app.get_state(thread_config)
            if not snapshot.values:
                return {"status": "error", "message": "Session not found"}
            
            state = snapshot.values
            
            # Prepare data for MongoDB
            prd_data = {
                "session_id": session_id,
                "user_id": state.get("config").user_id,
                "normalized_idea": state.get("normalized_idea"),
                "prd_sections": state.get("prd_sections", {}),
                "conversation_summary": state.get("conversation_summary", ""),
                "prd_snapshot": state.get("prd_snapshot", ""),
                "current_stage": state.get("current_stage"),
                "current_section": state.get("current_section"),
                "rag_context": state.get("rag_context", ""),
                "rag_sources": state.get("rag_sources", []),
                "created_at": state["config"].created_at,
                "updated_at": datetime.now().isoformat(),
                "status": "saved"
            }
            
            # Generate and store diagrams
            try:
                flowchart = self.generate_flowchart(session_id, "system_architecture")
                er_diagram = self.generate_er_diagram(session_id, "database_schema")
                
                prd_data["diagrams"] = {
                    "system_architecture": flowchart.get("mermaid_code", ""),
                    "database_schema": er_diagram.get("mermaid_code", "")
                }
            except Exception as e:
                prd_data["diagrams"] = {"error": f"Failed to generate diagrams: {str(e)}"}
            
             # Save to MongoDB using your existing service
            try:
                if self.mongodb_service:
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        prd_id = loop.run_until_complete(
                            self.mongodb_service.save_prd(prd_data)
                        )
                        loop.close()
                    except Exception as e:
                        print(f"Async operation failed: {e}")
                        prd_id = "failed"
                else:
                    prd_id = "no_mongodb_service"
                
                # Cache the PRD data
                if self.redis_service:
                    self.redis_service.cache_prd(session_id, prd_data)
                
                return {
                    "status": "success",
                    "message": "Session saved successfully",
                    "session_id": session_id,
                    "prd_id": prd_id,
                    "saved_at": prd_data["updated_at"]
                }
                
            except Exception as e:
                return {"status": "error", "message": f"MongoDB save failed: {str(e)}"}
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to save session: {str(e)}"}
    
    def ask_prd_question(self, session_id: str, question: str) -> Dict:
        """Ask questions about the completed PRD using RAG context"""
        try:
            # Get current session state
            thread_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
            snapshot = self.app.get_state(thread_config)
            
            if not snapshot.values:
                return {"status": "error", "message": "Session not found"}
            
            state = snapshot.values
            
            # Check if PRD is completed
            if not state.get("prd_snapshot"):
                return {"status": "error", "message": "PRD not yet completed. Please finish building the PRD first."}
            
            # Ensure RAG is initialized
            self._ensure_rag()
            
            # Prepare context for the question
            prd_context = state.get("prd_snapshot", "")
            
            # Get RAG context from uploaded documents if available
            rag_context = ""
            if state.get("rag_enabled") and self.rag:
                try:
                    # Search for relevant documents
                    docs = self.rag.semantic_search(
                        query=question, 
                        k=5, 
                        fetch_k=50, 
                        metadata_filter={"session_id": session_id}
                    )
                    if docs:
                        rag_context = "\n\n".join(doc.page_content for doc in docs)
                except Exception as e:
                    print(f"[RAG][WARN] Failed to retrieve RAG context: {e}")
            
            # Combine PRD context with RAG context
            full_context = f"PRD Content:\n{prd_context}"
            if rag_context:
                full_context += f"\n\nAdditional Document Context:\n{rag_context}"
            
            # Generate answer using LLM
            llm = LLMInterface()
            answer = llm.generate_prd_answer(question, full_context)
            
            return {
                "status": "success",
                "answer": answer,
                "question": question,
                "session_id": session_id,
                "context_used": {
                    "prd_sections": len(state.get("prd_sections", {})),
                    "rag_documents": len(rag_context.split('\n\n')) if rag_context else 0
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to process question: {str(e)}"}


    def _clear_session_cache(self, session_id: str) -> None:
        """Clear all cached data for a session"""
        try:
            if not self.redis_service or not self.redis_service.redis_client:
                return
                
            # Clear PRD cache
            self.redis_service.redis_client.delete(f"prd:cache:{session_id}")
            
            # Clear diagram caches
            diagram_types = ["system_architecture", "user_flows", "database_schema"]
            for diagram_type in diagram_types:
                self.redis_service.redis_client.delete(f"diagram:{session_id}:{diagram_type}")
                
        except Exception:
            pass