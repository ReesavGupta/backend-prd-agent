import os
from typing import List
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from time import perf_counter
from database.database import MongoDBService
from database.redis import RedisService
from prd_builder import ThinkingLensPRDBuilder
from fastapi.responses import StreamingResponse
from langgraph.types import Command
import json

app = FastAPI(title="ThinkingLens PRD Builder")
agent = ThinkingLensPRDBuilder()

# CORS (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple latency middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-ms"] = str(round((perf_counter() - start) * 1000, 1))
    return response

class StartSessionRequest(BaseModel):
    user_id: str
    idea: str

class MessageRequest(BaseModel):
    message: str

@app.post("/sessions")
def start_session(body: StartSessionRequest):
    return agent.start_session(user_id=body.user_id, initial_idea=body.idea)

@app.post("/sessions/{session_id}/message")
def send_message(session_id: str, body: MessageRequest):
    res = agent.send_message(session_id=session_id, message=body.message)
    if res.get("status") != "success":
        raise HTTPException(status_code=400, detail=res.get("message", "error"))
    return res

@app.get("/sessions/{session_id}/prd")
def get_prd(session_id: str):
    res = agent.get_prd_draft(session_id)
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "not found"))
    return res

@app.post("/sessions/{session_id}/refine")
def refine(session_id: str):
    res = agent.send_message(session_id=session_id, message="refine")
    if res.get("status") != "success":
        raise HTTPException(status_code=400, detail=res.get("message", "error"))
    return res

@app.post("/sessions/{session_id}/export")
def export(session_id: str):
	res = agent.send_message(session_id=session_id, message="export")
	if res.get("status") != "success":
		raise HTTPException(status_code=400, detail=res.get("message", "error"))
	return res
    
@app.get("/sessions/{session_id}/stream")
def stream_message(session_id: str, message: str):
    def event_stream():
        thread_config = {"configurable": {"thread_id": session_id}}
        snapshot = agent.app.get_state(thread_config)
        if not snapshot.values:
            yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
            return

        pending_next = getattr(snapshot, "next", None)
        is_waiting_human = False
        if isinstance(pending_next, (list, tuple)):
            is_waiting_human = "human_input" in pending_next
        elif isinstance(pending_next, str):
            is_waiting_human = pending_next == "human_input"
        else:
            is_waiting_human = bool(snapshot.values.get("needs_human_input", False))

        input_payload = Command(resume=message) if is_waiting_human else {
            "latest_user_input": message,
            "needs_human_input": False,
        }

        try:
            for ev in agent.app.stream(input_payload, config=thread_config, stream_mode="values"):
                out = {
                    "stage": ev.get("current_stage"),
                    "current_section": (ev["config"].current_section if "config" in ev else None),
                    "needs_input": ev.get("needs_human_input", False),
                    "last_message": (ev["messages"][-1].content if ev.get("messages") else None),
                }
                yield f"data: {json.dumps(out)}\n\n"
                if ev.get("needs_human_input"):
                    break
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
    
@app.get("/sessions/{session_id}/versions")
def list_versions(session_id: str):
    res = agent.list_versions(session_id)
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "not found"))
    return res

@app.get("/sessions/{session_id}/versions/{version_id}")
def get_version(session_id: str, version_id: str):
    res = agent.get_version(session_id, version_id)
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "not found"))
    return res

@app.post("/sessions/{session_id}/message-with-files")
async def send_message_with_files(session_id: str, files: List[UploadFile] = File(...)):
	saved_paths: List[str] = []
	if files:
		upload_dir = os.path.join("uploads", session_id)
		os.makedirs(upload_dir, exist_ok=True)
		for f in files:
			filename = f.filename or "upload"
			dest = os.path.join(upload_dir, filename)
			with open(dest, "wb") as out:
				out.write(await f.read())
			saved_paths.append(dest)
	res = agent.send_message(session_id=session_id, message="", attachments=saved_paths if saved_paths else None)
	if res.get("status") != "success":
		raise HTTPException(status_code=400, detail=res.get("message", "error"))
	return res

@app.post("/sessions/{session_id}/flowchart")
def generate_flowchart(session_id: str, flowchart_type: str = "system_architecture"):
    """Generate a technical flowchart based on the PRD"""
    res = agent.generate_flowchart(session_id=session_id, flowchart_type=flowchart_type)
    if res.get("status") != "success":
        raise HTTPException(status_code=400, detail=res.get("message", "error"))
    return res

@app.post("/sessions/{session_id}/er-diagram")
def generate_er_diagram(session_id: str, diagram_type: str = "database_schema"):
    """Generate an ER diagram based on the PRD"""
    res = agent.generate_er_diagram(session_id=session_id, diagram_type=diagram_type)
    if res.get("status") != "success":
        raise HTTPException(status_code=400, detail=res.get("message", "error"))
    return res

@app.post("/sessions/{session_id}/save")
async def save_session(session_id: str):
    """Save the current session to database permanently"""
    try:
        result = agent.save_session_to_database(session_id)
        return result
    except Exception as e:
        return {"status": "error", "message": f"Failed to save session: {str(e)}"}

@app.post("/sessions/{session_id}/ask")
async def ask_prd_question(session_id: str, body: MessageRequest):
    """Ask questions about the completed PRD using RAG context"""
    try:
        result = agent.ask_prd_question(session_id=session_id, question=body.message)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("message", "error"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)