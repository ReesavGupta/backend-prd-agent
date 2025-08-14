import time
import requests


BASE_URL = "http://localhost:8000"


def post(path: str, data: dict):
    r = requests.post(f"{BASE_URL}{path}", json=data)
    r.raise_for_status()
    return r.json()


def get(path: str):
    r = requests.get(f"{BASE_URL}{path}")
    r.raise_for_status()
    return r.json()


def wait_for_section_completion(session_id: str, section_key: str, timeout_s: float = 10.0, interval_s: float = 0.8) -> bool:
    """Poll GET /prd until a section shows as completed or timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        prd = get(f"/sessions/{session_id}/prd")
        completed = prd.get("sections_completed", {})
        if section_key in completed:
            return True
        time.sleep(interval_s)
    return False


def main():
    # 1) Start a session
    start = post(
        "/sessions",
        {
            "user_id": "u1",
            "idea": (
                "AI app that guides PMs from a one-liner idea to a complete PRD using LangGraph "
                "(single runtime) with HITL. Primary users: PMs at seed/Series A startups. "
                "Exports Markdown/PDF."
            ),
        },
    )
    print("start:", start)
    sid = start["session_id"]

    # 2) Answer Problem Statement with a substantive message (to trigger completion)
    problem_statement_answer = (
        "Product: An AI workspace that guides PMs from a one-liner to a complete PRD using "
        "LangGraph + HITL. Users: PMs at seed/Series A startups. Value: faster PRDs with "
        "measurable KPIs, section-specific prompts, continuous assemble/refine, clean Markdown/PDF "
        "export. Problem: current PRD creation is slow and inconsistent; this makes outcomes "
        "measurable and faster."
    )

    # The first build turn pauses at human_input; resume with the answer
    resp = post(f"/sessions/{sid}/message", {"message": problem_statement_answer})
    print("answer(problem_statement):", resp)

    assert (
        wait_for_section_completion(sid, "problem_statement", timeout_s=20.0)
    ), "Problem Statement did not complete in time"

    # 3) Provide answers for subsequent sections in order
    section_to_answer = {
        "goals": (
            "Primary goal: Achieve a 50% reduction in time to produce a complete PRD within 60 days; "
            "Secondary goals: Improve PRD measurability and cross-linkage; Business impact: faster cycle times and clearer requirements."
        ),
        "user_personas": (
            "Primary persona: Startup PM (3-7 years exp), needs guided structure and measurable outputs; "
            "Secondary personas: Eng leads and Designers who review PRDs; Journeys: draft → iterate → finalize."
        ),
        "core_features": (
            "Guided Q&A, section-specific prompts, intent classifier, assembler/refiner, export to Markdown/PDF; "
            "MVP includes planner, questioner, updater, assembler, export."
        ),
        "user_flows": (
            "Flow1: Enter idea → plan → question/answer loop → assemble/refine → export; "
            "Flow2: Revise a completed section triggers stale dependencies and re-check."
        ),
        "technical_architecture": (
            "LangGraph orchestration with single LLM runtime; FastAPI backend; In-memory/SQLite checkpointer; "
            "OpenAI models; persistence of state; optional Redis cache."
        ),
        "success_metrics": (
            "KPI1: Time-to-PRD baseline 10d → target 5d in 60 days; KPI2: PRD completeness score ≥ 0.8; "
            "Owner: PM Ops; Data source: app telemetry; timeframe: Q3."
        ),
        "constraints": (
            "Technical: API quotas, token limits; Business: cost ceiling per PRD; Resources: 1-2 engs; "
            "Assumptions: access to OpenAI; stable environment."
        ),
        "risks": (
            "Technical: LLM variability; Market: PRD tools competition; Mitigations: heuristics, caching, and HITL; "
            "Impact/Probability assessed per release."
        ),
        "timeline": (
            "Milestones: MVP in 4 weeks, Beta in 8 weeks; Dependencies: model access, deployment; "
            "Resources allocated and buffer included."
        ),
    }

    # We'll loop until either we finish mandatory sections or hit a cap
    mandatory_sections = [
        "goals",
        "user_personas",
        "core_features",
        "user_flows",
        "technical_architecture",
        "success_metrics",
        "risks",
        "constraints",
        "timeline",
    ]

    for _ in range(20):  # hard cap on turns
        prd = get(f"/sessions/{sid}/prd")
        current = prd.get("current_section")
        stage = prd.get("current_stage")
        if stage == "review" or current is None:
            break
        if current not in section_to_answer:
            # Ask for a status to keep moving
            post(f"/sessions/{sid}/message", {"message": "status"})
            time.sleep(0.5)
            continue
        msg = section_to_answer[current]
        r = post(f"/sessions/{sid}/message", {"message": msg})
        print(f"answer({current}):", {k: r.get(k) for k in ("stage", "current_section", "needs_input")})
        # give the graph a moment and check completion
        wait_for_section_completion(sid, current, timeout_s=15.0)

        # If all mandatory sections are done, we're done
        prd2 = get(f"/sessions/{sid}/prd")
        done = set(prd2.get("sections_completed", {}).keys())
        if all(s in done for s in mandatory_sections):
            break

    # 4) Refine (enter review stage)
    refine_res = post(f"/sessions/{sid}/refine", {})
    print("refine:", {k: refine_res.get(k) for k in ("stage", "needs_input")})

    # 5) Export and verify version appears
    export_res = post(f"/sessions/{sid}/export", {})
    print("export:", {k: export_res.get(k) for k in ("stage", "needs_input")})

    versions = get(f"/sessions/{sid}/versions")
    print("versions:", versions)
    assert versions.get("versions"), "No versions recorded after export"

    print("FULL E2E PASS ✅")


if __name__ == "__main__":
    main()


