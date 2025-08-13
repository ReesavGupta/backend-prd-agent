# PRD — ThinkingLens PRD Builder Agent (Technical)

**Owner:** [You]  
**Date:** 13 Aug 2025  
**Status:** Draft v2 (Technical Expansion)  
**Scope:** End-to-end product + architecture spec for a collaborative PRD-building agent with LangGraph orchestration, single-LLM runtime, dynamic prompt swapping, and HITL workflows.

## 1. Product Summary

An AI workspace that guides a user from a one-liner idea to a complete, high-quality PRD. The agent asks section-specific questions, classifies user intent each turn (on-track, off-target, meta, off-topic), updates the PRD JSON, continuously assembles/refines the draft, and keeps the experience collaborative and nudging.

**Non-goals (v1):** Organizational knowledge mining (OKRs/Confluence import), multi-doc retrieval, multi-user live co-editing (view-only is fine), and external workflow integrations.

## 2. Success Criteria

- **Completion Rate:** ≥ 70% of sessions produce a PRD with all mandatory sections filled.
- **Quality:** ≥ 4/5 average score on ThinkingLens rubric (clarity, completeness, measurability, cross-linkage, stakeholder readiness).
- **Latency:** p50 turn latency ≤ 2.5s; p95 ≤ 5s.
- **Cost:** ≤ $0.10 per 10 message turns (using small classifier + mid-tier gen model).
- **Reliability:** ≥ 99.5% successful turn processing; no state loss.

## 3. User Workflow (HITL)

1. **Enter Idea → Workspace:** User lands on a persistent workspace bound to `session_id`.
2. **Stage 0 (Normalize):** Agent clarifies ambiguities; writes a normalized idea summary; opens PRD shell.
3. **Stage 1 (Plan Sections):** Agent proposes section list; confirms or edits with user.
4. **Stage 2 (Build Sections):** Agent asks targeted questions; user responds; agent classifies intent; updates PRD JSON accordingly; nudge back to focus section when needed.
5. **Stage 3 (Assemble & Refine):** After each update, PRD is merged; consistency pass + refinement prompt applied.
6. **Stage 4 (Review & Finalize):** User edits inline; agent suggests improvements; export Markdown/PDF; version snapshot saved.

**Edge-case handling (always on):** Off-target updates, revisions to earlier sections, meta queries ("what do we have?"), off-topic queries ("weather?") → handled then gently redirected.

## 4. Functional Requirements

### 4.1 Stage 0 — Initialization & Idea Normalization

- **Inputs:** One-liner idea (free text).
- **Agent behavior:** Ask up to 3 clarifying questions (scope, audience, modality, markets), then produce a 2–3 sentence normalized idea.
- **Data written:** New session row; normalized idea; PRD JSON scaffold; initial conversation summary.
- **UI:** Workspace shows normalized idea + section outline panel.

**Technical specifics**
- **Session state creation:** Generate `session_id` (UUID); persist user, timestamps, status.
- **PRD scaffold (keys):** Problem Statement, Goals, Success Metrics, User Personas, Core Features, User Flows, Technical Architecture, Constraints, Risks, Timeline, Open Questions, Out of Scope, Future Ideas. (Keys are configurable per template.)
- **Latency budget:** 600–900ms (one mid-tier LLM call).

### 4.2 Stage 1 — Section Planning

- **Inputs:** Normalized idea + optional user preferences (platform, geography).
- **Agent behavior:** Select mandatory + conditional sections; order by dependency (Problem → Goals → Personas → Features → Flows → Tech → Metrics → Risks).
- **Data written:** Section registry with status per section (`pending | in_progress | completed`); `current_section` pointer.

**Technical specifics**
- **Section planner heuristic:** Always include mandatory sections; add optional (e.g., Compliance) if keywords detected (finance/health/edtech).
- **Validation:** Ensure each mandatory section has a question plan (2–4 core prompts).
- **Latency budget:** 400–700ms.

### 4.3 Stage 2 — Guided Section Building (turn loop)

- **Inputs per turn:** Latest user message; `session_id`.
- **Flow per turn:**
  1. **State fetch:** Load `current_section`, PRD JSON (only section-in-focus + compact snapshot), rolling conversation summary.
  2. **Intent classification:** Determine one of: `section_update`, `off_target_update` (+ target section), `revision` (+ target section), `meta_query`, `off_topic`.
  3. **Route & act:**
     - `section_update`: Update current section; mark completeness (threshold via checklist); if done → advance pointer.
     - `off_target_update`: Update that section first; acknowledge; resume current.
     - `revision`: Replace targeted section; mark downstream sections "stale" if dependencies exist (e.g., Personas change → Flows stale).
     - `meta_query`: Return status/summary; offer "continue or revise?" CTA.
     - `off_topic`: Brief answer (if allowed), then nudge back.
  4. **Assemble & refine (light):** Merge draft; micro-consistency checks on impacted sections (terminology, metrics references).
  5. **Respond:** Return agent message, updated section snippet, progress, optional "full draft" on demand.

**Technical specifics**
- **Dynamic prompt swapping:** Single LLM runtime with section-specific system prompts, checklist, and acceptance criteria.
- **Conversation memory:** Incremental summarization (rolling buffer → compress every 5–8 turns); never resend full history.
- **PRD context:** Inject full text of section-in-focus + 300–500 token PRD snapshot; avoid entire PRD unless at checkpoints.
- **Completeness rubric (per section):** E.g., Success Metrics must include baseline, target, timeframe, owner, measurement source.
- **Latency budget:** p50 1.6–2.2s (classifier ~150–250ms + gen ~1.2–1.7s).

### 4.4 Stage 3 — PRD Assembly & Refinement

- **Trigger:** After each material update (or when user clicks "Refine now").
- **Behavior:** Merge all sections; run cross-section checks; apply refinement prompt to entire PRD when within context; else run targeted pair-wise reconciliations (e.g., Goals ↔ Metrics).
- **Outputs:** Updated PRD draft; issues list (inconsistencies, missing links, vague claims).

**Technical specifics**
- **Consistency checks:**
  - *Terminology alignment:* Build a canonical glossary from high-frequency terms; flag synonyms drift.
  - *Entity naming:* Ensure entity names match across Features/Flows/Tech.
  - *Goal ↔ Metrics linkage:* Each Goal should map to ≥1 KPI with timeframe.
  - *Persona ↔ Flow coherence:* Each flow references a known persona.
- **Refinement mode:** Same LLM, different "editor" prompt; optional upscale model for final pass.
- **Latency budget:** Light merge 200–400ms; full-doc refinement 1.5–3.0s (runs at milestones).

### 4.5 Stage 4 — Review, Versioning, Export

- **UI:** Side-by-side PRD viewer/editor; inline suggestions; section completeness badges.
- **Agent assist:** "Tighten phrasing", "Make metrics measurable", "Align flows with personas".
- **Versioning:** Snapshot on significant changes and at export; retain diff metadata.
- **Export:** Markdown, PDF; REST endpoint for retrieval; signed URL with expiry.

**Technical specifics**
- **Change tracking:** Compute textual diffs per section; attach to version metadata.
- **Finalization:** Lock version; record approver; save rubric score; immutable export.

## 5. Data Model (Conceptual)

- **Session:** `session_id`, `user_id`, `created_at`, `updated_at`, `status`, `current_section`, `turn_counter`.
- **PRD State:** Map of section keys → `{content, status, last_editor, last_updated, dependencies[]}` ; plus `issues[]`, `snapshot_summary`.
- **Conversation:** Structured log with `role`, `content`, `intent`, `section_target`, `latency`, `cost_estimate`.
- **Versions:** `version_id`, `session_id`, `created_at`, `by`, `rubric_scores{}`, `export_links{md,pdf}`.

*(Describe in DB as normalized tables or JSON columns; keep sections as JSONB for flexible schemas.)*

## 6. API Surface (Descriptive)

- **POST /sessions** — start session with idea; returns `session_id`, normalized idea, section plan.
- **POST /sessions/{id}/message** — turn endpoint; body: message text; returns agent reply, updated section snippet, progress, optionally full draft.
- **GET /sessions/{id}/prd** — fetch assembled PRD (latest or specific version via query).
- **POST /sessions/{id}/refine** — force refinement pass; returns updated draft + issues.
- **POST /sessions/{id}/export** — create export; returns signed links.
- **GET /sessions/{id}/versions** — list versions; **GET /sessions/{id}/versions/{vid}** — fetch a version.

Auth via JWT; rate limits per user; idempotency keys to prevent double-writes.

## 7. Prompting Strategy (Descriptive)

- **Global guardrails:** Tone (concise, specific), rubric adherence, avoidance of hallucinated facts, always propose clarifying Qs before fabricating assumptions.
- **Section prompts:** Each contains role, objectives, acceptance checklist, failure modes, and input context placeholders (conversation summary, PRD snapshot, section-in-focus).
- **Refinement prompt:** Editor persona; explicit consistency checks; enforce measurable KPIs; trim fluff; maintain terminology map.
- **Classifier prompt:** Minimal context, JSON-only output, categories fixed (`section_update`, `off_target_update`, `revision`, `meta_query`, `off_topic`), and optional `target_section`.

## 8. Intent & Dialogue Policy

- **On-track** (`section_update`): Acknowledge, update, quickly validate against checklist, ask next most-informative question.
- **Off-target update:** Update correct section; brief confirmation; bridge back to current section with reason ("so we can complete dependency X").
- **Revision:** Update target; mark dependent sections stale; propose a quick recheck.
- **Meta query:** Provide crisp status (completed/pending), offer "continue" or "revise".
- **Off-topic:** Short friendly response (if allowed) + gentle nudge back; configurable strictness.

## 9. Context & Token Management

- **Conversation:** Rolling buffer of last 4–6 turns; incrementally summarized every N turns into a 150–250 token synopsis.
- **PRD Snapshot:** 300–500 tokens max; updated after material changes; organized as outline + section one-liners + unresolved issues.
- **Section Injection:** Full content of section-in-focus only; others appear in snapshot.
- **Checkpoints:** At section completion or "Show full draft," provide full merged PRD.

## 10. Performance, Reliability, Cost

- **Latency targets:** p50 ≤ 2.5s; p95 ≤ 5s per turn, including classification and DB ops.
- **Caching:** Redis for session hot state; DB as source of truth. Avoid reloading full PRD if only one section changed.
- **Throughput planning:** Single LLM endpoint concurrency with backpressure; queue burst traffic; degrade to minimal responses if overloaded.
- **Cost controls:** Use small model for classification; mid-tier model for generation; upscale only at final refinement or manual request.

## 11. Observability & Safety

- **Metrics:** Turn latency, LLM token in/out per turn, classifier accuracy, PRD completeness, rubric scores, export success rate.
- **Tracing:** Correlate `session_id` across classifier, generator, DB writes; structured logs with step spans.
- **Red-flags:** Long-running sections, repeated off-topic loops, contradiction spikes in consistency checks → surface as "agent needs help".
- **Data protection:** Store minimal PII; encrypt at rest; redact sensitive mentions in logs; signed export URLs with short TTL.

## 12. Evaluation Plan

- **Offline eval:** Golden conversation sets with expected intents, section outputs, and rubric scores.
- **Online guardrails:** A/B test question ordering; measure PRD completeness and user edits volume.
- **Human rating:** PMs rate PRDs for ThinkingLens criteria; target uplift vs baseline LLM PRDs.
- **Classifier QA:** Confusion matrix for intent categories; retrain if F1 < 0.9.

## 13. Risks & Mitigations

- **Risk:** Token blow-up on long PRDs → **Mitigation:** strict snapshot caps + section-only injection.
- **Risk:** User derails repeatedly → **Mitigation:** progressive nudging + "Focus mode" toggle.
- **Risk:** Inconsistent terminology → **Mitigation:** canonical glossary + enforcement in refinement.
- **Risk:** Cost creep → **Mitigation:** tiered model usage; throttle full-doc refinement.
- **Risk:** DB contention at scale → **Mitigation:** Redis cache, write-behind for heavy operations.

## 14. Rollout

- **Alpha:** Internal PMs, 20 users, weekly rubric review.
- **Beta:** 200 users; add export + versioning; gather latency & cost stats.
- **GA:** Stabilize APIs; optional org context import.

## 15. Acceptance Criteria

- Users complete mandatory sections with agent guidance.
- Off-target, revision, meta, and off-topic intents are correctly handled and logged.
- PRD exports render cleanly (Markdown + PDF).
- Consistency checker flags and resolves at least 80% of detected issues.
- Versioning with diffs works; rollback is possible.

## 16. LangGraph Orchestration (Descriptive, no code)

### Graph Roles (Nodes)

1. **IdeaNormalizer**
   - Purpose: Clarify one-liner; produce normalized idea summary; seed PRD scaffold.
   - Inputs: Raw idea.
   - Outputs: Normalized idea; initial PRD shell; `current_section` = planner trigger.

2. **SectionPlanner**
   - Purpose: Decide required sections and order; create question plans per section.
   - Inputs: Normalized idea; template policy.
   - Outputs: Section registry with statuses and dependencies; first `current_section`.

3. **SectionQuestioner**
   - Purpose: Ask targeted, high-leverage questions for the `current_section`.
   - Inputs: `current_section`, PRD snapshot, conversation summary.
   - Outputs: A single question (or brief ask-list), expecting one user reply.

4. **IntentClassifier**
   - Purpose: Categorize the user reply.
   - Inputs: User reply, `current_section`.
   - Outputs: Intent label (`section_update`, `off_target_update`, `revision`, `meta_query`, `off_topic`) and optional target section.

5. **SectionUpdater**
   - Purpose: Mutate PRD state according to intent.
   - Inputs: Intent + target; prior section content; user reply.
   - Outputs: Updated section, completeness status; dependency invalidations if needed.

6. **MetaResponder**
   - Purpose: Serve PRD status/summary on meta queries.
   - Inputs: PRD state, progress.
   - Outputs: Concise snapshot and suggested next actions.

7. **OffTopicResponder**
   - Purpose: Briefly respond to unrelated queries and nudge back.
   - Inputs: User message, policy strictness.
   - Outputs: Short friendly response + bridge to `current_section`.

8. **Assembler**
   - Purpose: Merge sections into draft; produce issues list (terminology, linkage, metrics).
   - Inputs: PRD sections, glossary, dependency map.
   - Outputs: Assembled draft, updated snapshot, issues.

9. **Refiner**
   - Purpose: Apply editorial pass; enforce rubric; polish tone and cross-references.
   - Inputs: Assembled draft; rubric; glossary.
   - Outputs: Refined draft; suggested improvements; tracked changes summary.

10. **Exporter**
    - Purpose: Snapshot, version, and generate downloadable formats.
    - Inputs: Final draft and metadata.
    - Outputs: Version record; export links.

### Graph Control Flow

- **Start:** **IdeaNormalizer → SectionPlanner → SectionQuestioner**
- **Turn loop:** **SectionQuestioner → IntentClassifier →**
  - If `section_update` / `off_target_update` / `revision` → **SectionUpdater → Assembler → (Refiner if checkpoint) → SectionQuestioner**
  - If `meta_query` → **MetaResponder → SectionQuestioner**
  - If `off_topic` → **OffTopicResponder → SectionQuestioner**
- **End:** When all mandatory sections `completed` → **Assembler → Refiner → Exporter**

### State Management (Edges Persist/Read)

Each node reads the **Session State** (PRD JSON, `current_section`, conversation summary) from a state store and writes back only deltas.

The **Assembler** also updates the PRD snapshot and issues list used by downstream nodes.

### Operational Policies

- **Checkpoints:** After each section completion, run Assembler (light) and optionally Refiner (light).
- **Milestones:** After all mandatory sections, run full Refiner; block export until major issues are addressed or acknowledged.
- **Backpressure:** If turns exceed latency budget, skip light refinement in that turn and defer to next checkpoint.
- **Safety:** If classifier confidence low, ask a disambiguation question rather than guessing intent.

## 17. Appendix — ThinkingLens Rubric (Short)

- **Clarity:** Problem, users, and scope are concrete; no vague terms.
- **Completeness:** Mandatory sections present with acceptance checklists met.
- **Measurability:** KPIs are time-bound, owner-assigned, and data-sourced.
- **Cross-linkage:** Personas ↔ Flows; Goals ↔ Metrics; Features ↔ Constraints.
- **Stakeholder Readiness:** Risks, assumptions, alternatives, and timeline are explicit.