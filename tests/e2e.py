import requests

base = "http://localhost:8000"

def post(path, data):
	r = requests.post(f"{base}{path}", json=data); r.raise_for_status(); return r.json()
def get(path):
	r = requests.get(f"{base}{path}"); r.raise_for_status(); return r.json()

# 1) Start session
start = post("/sessions", {
	"user_id": "u1",
	"idea": "AI app that guides PMs from a one-liner to a complete PRD using LangGraph (single runtime) with HITL. Primary users: PMs at seed/Series A startups. Exports Markdown/PDF."
})
print(start)
sid = start["session_id"]

# 2) Kick to questioner (the first build turn asks questions)
post(f"/sessions/{sid}/message", {"message": "ok"})

# 3) Answer Problem Statement (substantive, ≥120 chars; includes product/users/value)
resp = post(f"/sessions/{sid}/message", {
	"message": "Product: An AI workspace that guides PMs from a one-liner to a complete PRD using LangGraph + HITL. Users: PMs at seed/Series A startups. Value: faster PRDs with measurable KPIs, section-specific prompts, continuous assemble/refine, clean Markdown/PDF export. Problem: current PRD creation is slow and inconsistent; this makes outcomes measurable and faster."
})
print(resp)

# 4) Check snapshot and progress
draft = get(f"/sessions/{sid}/prd")
print("snapshot_len:", len(draft.get("prd_snapshot", "")))
print("current_section:", draft.get("current_section"))
print("progress:", draft.get("progress"))