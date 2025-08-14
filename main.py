import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from time import perf_counter
from prd_builder import ThinkingLensPRDBuilder

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
    return agent.export_prd(session_id=session_id, format="markdown")

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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)