from datetime import datetime
import uuid
from langgraph.types import interrupt
from state import PRDBuilderState
from llm import LLMInterface
from langchain.schema import AIMessage
from prompts import PRD_TEMPLATE_SECTIONS
from state import PRDSection, SectionStatus, IntentType
from langchain_core.prompts import ChatPromptTemplate

def idea_normalizer_node(state: PRDBuilderState) -> PRDBuilderState:
	llm = LLMInterface()

	raw_idea = state["latest_user_input"]
	result = llm.normalize_idea(raw_idea)

	# If we still need clarification, ask questions and pause
	if result.get("needs_clarification") and result.get("clarifying_questions"):
		qs = "\n".join(f"- {q}" for q in result["clarifying_questions"])
		state["needs_human_input"] = True
		state["checkpoint_reason"] = "Need clarification for product idea"
		state["messages"].append(AIMessage(content=f"To proceed, please answer:\n{qs}"))
		return state

	# Otherwise, proceed
	state["normalized_idea"] = result.get("normalized", "").strip()
	state["current_stage"] = "plan"
	state["messages"].append(AIMessage(content=f"Great! I've understood your idea:\n\n{state['normalized_idea']}\n\nNow let's plan the PRD sections..."))

	# initialize prd sections
	sections = {}
	section_order = []
	for key, template in PRD_TEMPLATE_SECTIONS.items():
		sections[key] = PRDSection(
			key=key,
			checklist_items=template["checklist"],
			dependencies=template["dependencies"]
		)
		if template["mandatory"]:
			section_order.append(key)
	state["prd_sections"] = sections
	state["section_order"] = section_order
	return state


def section_planner_node(state: PRDBuilderState) -> PRDBuilderState:
    """Stage 1: Plan which sections to include and their order"""
    
    # Default section order based on dependencies
    ordered_sections = [
        "problem_statement",
        "goals",
        "user_personas",
        "core_features",
        "user_flows",
        "technical_architecture",
        "success_metrics",
        "risks",
        "constraints",
        "timeline"
    ]
    
    # Set the first section as current
    state["section_order"] = ordered_sections
    state["config"].current_section = ordered_sections[0]
    state["current_stage"] = "build"
    
    # Present the plan to user
    section_list = "\n".join([f"{i+1}. {PRD_TEMPLATE_SECTIONS[key]['title']}" 
                             for i, key in enumerate(ordered_sections)])
    
    message = f"""Perfect! Here's our PRD building plan:
        {section_list}
        We'll go through each section systematically. Ready to start with the Problem Statement?"""
    
    state["messages"].append(AIMessage(content=message))
    state["needs_human_input"] = False
    state["checkpoint_reason"] = ""
    
    print("="*20)
    print(state)
    print("="*20)

    return state


def section_questioner_node(state: PRDBuilderState) -> PRDBuilderState:
    """Ask targeted questions for the current section"""
    llm = LLMInterface()
    current_section = state["config"].current_section
    
    if not current_section:
        # All sections complete, move to assembly
        state["current_stage"] = "assemble"
        return state
    
    # Get current section info
    section = state["prd_sections"][current_section]
    
    # Generate context for question generation
    context = {
        "normalized_idea": state["normalized_idea"],
        "current_content": section.content,
        "completed_sections": [k for k, v in state["prd_sections"].items() 
                              if v.status == SectionStatus.COMPLETED],
        "conversation_summary": state.get("conversation_summary", ""),
        "prd_snapshot": state.get("prd_snapshot", "")[:2000],
        "rag_context": state.get("rag_context", ""),
    }
    
    # Generate questions
    questions = llm.generate_section_questions(current_section, context)
    
    # Update section status
    section.status = SectionStatus.IN_PROGRESS
    state["prd_sections"][current_section] = section
    
    # Send questions and wait for human input
    state["messages"].append(AIMessage(content=questions))
    state["needs_human_input"] = True
    state["checkpoint_reason"] = f"Gathering info for {PRD_TEMPLATE_SECTIONS[current_section]['title']}"
    
    print("="*20)
    print(state)
    print("="*20)

    return state

def intent_classifier_node(state: PRDBuilderState) -> PRDBuilderState:
    """Classify user intent and determine routing"""
    llm = LLMInterface()
    user_message = state["latest_user_input"]
    current_section = state["config"].current_section or ""
    
    # Build context
    context = f"Normalized idea: {state['normalized_idea']}\nCurrent progress: {len([s for s in state['prd_sections'].values() if s.status == SectionStatus.COMPLETED])} sections done"
    
    classification = llm.classify_intent(user_message, current_section, context)
    
    state["intent_classification"] = IntentType(classification["intent"])
    state["target_section"] = classification.get("target_section")
    

    print("="*20)
    print(state)
    print("="*20)

    return state

def section_updater_node(state: PRDBuilderState) -> PRDBuilderState:
    """Update PRD sections based on classified intent"""
    llm = LLMInterface()
    
    intent = state["intent_classification"]
    target_section = state["target_section"] or state["config"].current_section
    user_input = state["latest_user_input"]
    
    if target_section not in state["prd_sections"]:
        return state
    
    original_current = state["config"].current_section
    section = state["prd_sections"][target_section]
    
    # Build context for update
    context = {
        "normalized_idea": state["normalized_idea"],
        "prd_sections": {k: v.content for k, v in state["prd_sections"].items() if v.content},
        "conversation_summary": state.get("conversation_summary", ""),
        "prd_snapshot": state.get("prd_snapshot", "")[:2000],
        "rag_context": state.get("rag_context", ""),
    }
    
    # Update section content
    update_result = llm.update_section_content(
        target_section, user_input, section.content, context
    )
    
    # Apply updates
    section.content = update_result["updated_content"]
    section.completion_score = update_result["completion_score"]
    section.last_updated = datetime.now()
    
    # Mark dependencies stale on revision
    if intent == IntentType.REVISION:
        for k, s in state["prd_sections"].items():
            if target_section in s.dependencies and s.status == SectionStatus.COMPLETED:
                s.status = SectionStatus.STALE
                state["prd_sections"][k] = s
    
    # Check if section is complete
    if section.completion_score >= 0.8:
        section.status = SectionStatus.COMPLETED
        
        # Advance only if we're working on the current section
        current_idx = state["section_order"].index(target_section)
        
        if current_idx + 1 < len(state["section_order"]):
            state["config"].current_section = state["section_order"][current_idx + 1]
        else:
            state["config"].current_section = None  # All sections done
        
        state["messages"].append(AIMessage(content=f"✅ {PRD_TEMPLATE_SECTIONS[target_section]['title']} section completed!"))
        state["run_assembler"] = True
    else:
        # Continue with more questions
        if update_result["next_questions"] != "complete":
            state["messages"].append(AIMessage(content=update_result["next_questions"]))
    
    # If this was an off-target update, restore focus
    if intent == IntentType.OFF_TARGET_UPDATE and original_current:
        state["config"].current_section = original_current
    
    state["prd_sections"][target_section] = section
    
    # Increment turn counter and summarize conversation every 6 turns
    try:
        state["config"].turn_counter += 1
    except Exception:
        pass
    if state["config"].turn_counter % 6 == 0:
        try:
            recent_summary = llm.summarize_conversation(state["messages"], state.get("conversation_summary", ""))
            state["conversation_summary"] = recent_summary
        except Exception:
            pass
    
    return state

def meta_responder_node(state: PRDBuilderState) -> PRDBuilderState:
    """Handle meta queries about progress and status"""
    completed = [k for k, v in state["prd_sections"].items() if v.status == SectionStatus.COMPLETED]
    in_progress = [k for k, v in state["prd_sections"].items() if v.status == SectionStatus.IN_PROGRESS]
    pending = [k for k, v in state["prd_sections"].items() if v.status == SectionStatus.PENDING]
    
    response = f"""📊 **PRD Progress Status**

        ✅ **Completed ({len(completed)}):** {', '.join([PRD_TEMPLATE_SECTIONS[k]['title'] for k in completed])}

        🚧 **In Progress ({len(in_progress)}):** {', '.join([PRD_TEMPLATE_SECTIONS[k]['title'] for k in in_progress])}

        ⏳ **Pending ({len(pending)}):** {', '.join([PRD_TEMPLATE_SECTIONS[k]['title'] for k in pending])}

        Would you like to continue with the current section, review a completed section, or see the full draft so far?"""
            
    state["messages"].append(AIMessage(content=response))
    state["needs_human_input"] = True
    state["checkpoint_reason"] = "User requested status update"
    
    return state

def off_topic_responder_node(state: PRDBuilderState) -> PRDBuilderState:
    """Handle off-topic queries with gentle redirection"""
    user_input = state["latest_user_input"]
    current_section_name = PRD_TEMPLATE_SECTIONS[state["config"].current_section]["title"] if state["config"].current_section else "PRD building"
    
    response = f"""I understand you're asking about something else, but let's keep our focus on building your PRD! 

    We're currently working on the **{current_section_name}** section. This will help ensure we create a comprehensive product requirements document.

    Shall we continue with the questions for this section?"""
    
    state["messages"].append(AIMessage(content=response))
    return state

def assembler_node(state: PRDBuilderState) -> PRDBuilderState:
	"""Assemble and refine the complete PRD"""
	
	# Build the complete PRD document
	prd_content = f"""# PRD: {state['normalized_idea']}

	**Created:** {state['config'].created_at.strftime('%Y-%m-%d %H:%M')}
	**Session:** {state['config'].session_id}

	"""
	
	for section_key in state["section_order"]:
		section = state["prd_sections"][section_key]
		if section.content:
			title = PRD_TEMPLATE_SECTIONS[section_key]["title"]
			prd_content += f"\n## {title}\n\n{section.content}\n"
	
	# Create snapshot
	state["prd_snapshot"] = prd_content
	
	# Simple consistency check
	issues = []
	if len(state["glossary"]) == 0:
		issues.append("Consider defining key terms in a glossary")
	state["issues_list"] = issues

	is_final = state["config"].current_section is None

	if is_final:
		state["current_stage"] = "review"
		message = f"""🎉 **PRD Assembly Complete!**

I've assembled your complete PRD. Here's what we've created:

{prd_content[:500]}{'...' if len(prd_content) > 500 else ''}

Would you like to:
1. Review and edit any sections
2. Export the final version
3. Add more details to specific sections

What would you prefer?"""
		state["messages"].append(AIMessage(content=message))
		state["needs_human_input"] = True
		state["checkpoint_reason"] = "PRD assembly complete - ready for review"
	else:
		# Light checkpoint: continue building
		state["current_stage"] = "build"
		state["needs_human_input"] = False
		state["checkpoint_reason"] = ""
		state["run_assembler"] = False

	return state

def exporter_node(state: PRDBuilderState) -> PRDBuilderState:
    """Export the final PRD"""
    
    export_content = state["prd_snapshot"]
    version = {
        "version_id": str(uuid.uuid4()),
        "session_id": state["config"].session_id,
        "created_at": datetime.now().isoformat(),
        "by": state["config"].user_id,
        "format": "markdown",
        "content": export_content,
    }
    versions = state.get("versions", [])
    versions.append(version)
    state["versions"] = versions
    
    message = f"""📄 **PRD Export Complete!**
    
    Your PRD has been successfully created and is ready for use!
    
    Versions saved: {len(state['versions'])}
    Latest version id: {version['version_id']}
    """
            
    state["messages"].append(AIMessage(content=message))
    state["current_stage"] = "export"
    
    return state
    
def refiner_node(state: PRDBuilderState) -> PRDBuilderState:
    """Refine the assembled PRD with an editorial pass and expand issues."""
    llm = LLMInterface()
    full_text = state.get("prd_snapshot", "")
    if not full_text:
        return state

    prompt_text = f"""Refine this PRD for clarity, consistency, and measurable KPIs.
    Return improved markdown only.
    {full_text}
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a concise PRD editor. Improve clarity, enforce measurable metrics, align terminology."),
        ("human", prompt_text)
    ])
    
    result = llm.model.invoke(prompt.format_messages())
    refined = str(result.content).strip() if result and result.content else full_text

    state["prd_snapshot"] = refined
    state["current_stage"] = "review"
    state["messages"].append(AIMessage(content="✍️ Applied an editorial pass. Would you like to export or continue editing?"))
    state["needs_human_input"] = True
    state["checkpoint_reason"] = "Refinement complete"
    return state
    
def human_input_node(state: PRDBuilderState) -> PRDBuilderState:
	state["needs_human_input"] = True
	value = interrupt(state.get("checkpoint_reason") or "Please provide input to continue")
	state["needs_human_input"] = False
	if isinstance(value, str):
		state["latest_user_input"] = value
	elif isinstance(value, dict):
		# Prefer a conventional resume payload shape {"data": <user_text>}
		if "data" in value:
			state["latest_user_input"] = value["data"]
		else:
			for k, v in value.items():
				state[k] = v
	else:
		state["latest_user_input"] = str(value)
	return state