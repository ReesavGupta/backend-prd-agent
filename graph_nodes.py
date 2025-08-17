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

	# Add agent introduction if this is the first message
	if not state.get("messages") or len(state["messages"]) == 0:
		intro_message = """�� **Hi! I'm your PRD Agent**

I'm here to help you build a comprehensive Product Requirements Document (PRD) step by step. 

**What I'll help you with:**
• Break down your product idea into structured sections
• Ask targeted questions to gather the right information
• Build a professional, complete PRD document
• Ensure all critical aspects are covered

**How it works:**
1. Share your product idea
2. I'll ask questions for each section
3. We'll build the PRD together
4. You can revise and refine as needed"""
		
		state["messages"].append(AIMessage(content=intro_message))
		state["needs_human_input"] = True
		state["checkpoint_reason"] = "Waiting for user's product idea"
		return state

	raw_idea = state["latest_user_input"]
	
	# Check if we already have a normalized idea and are just adding context
	if state.get("normalized_idea") and state.get("current_stage") == "init":
		# We're in clarification mode - accumulate context
		accumulated_context = f"{state['normalized_idea']}\n\nAdditional context: {raw_idea}"
		result = llm.normalize_idea(accumulated_context)
	else:
		# First time processing the idea
		result = llm.normalize_idea(raw_idea)

	# If we still need clarification, ask questions and pause
	if result.get("needs_clarification") and result.get("clarifying_questions"):
		# Check if we've already asked these questions to avoid repetition
		asked_questions = state.get("asked_clarifying_questions", [])
		new_questions = []
		
		for q in result["clarifying_questions"]:
			if q not in asked_questions:
				new_questions.append(q)
		
		if new_questions:
			# Ask only new questions
			qs = "\n".join(f"- {q}" for q in new_questions)
			state["asked_clarifying_questions"] = asked_questions + new_questions
			state["needs_human_input"] = True
			state["checkpoint_reason"] = "Need clarification for product idea"
			state["messages"].append(AIMessage(content=f"To proceed, please answer:\n{qs}"))
			return state
		else:
			# All questions have been asked, proceed with what we have
			result["needs_clarification"] = False
			result["clarifying_questions"] = []

	# If we have enough context or no more clarification needed, proceed
	if not result.get("needs_clarification") or not result.get("clarifying_questions"):
		# Use the normalized idea (either from result or accumulated)
		if result.get("normalized"):
			state["normalized_idea"] = result.get("normalized", "").strip()
		elif state.get("normalized_idea"):
			# Keep existing normalized idea if no new normalization
			pass
		else:
			# Fallback - use the raw input as normalized
			state["normalized_idea"] = raw_idea.strip()
		
		state["current_stage"] = "plan"
		state["messages"].append(AIMessage(content=f"Great! I've understood your idea:\n\n**{state['normalized_idea']}**\n\nNow let's plan the PRD sections..."))

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
		
		# Clear any stored clarifying questions
		state["asked_clarifying_questions"] = []
		
		return state

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
    
    # Check if we already have questions pending for this section
    if state.get("needs_human_input") and state.get("checkpoint_reason", "").startswith("Gathering info for"):
        # Don't ask new questions if we're already waiting for answers
        return state
    
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
    
    state["run_assembler"] = True

    # Handle revisions differently
    if intent == IntentType.REVISION:
        # For revisions, don't auto-advance sections
        section.status = SectionStatus.IN_PROGRESS  # Reset to in-progress
        
        # Mark dependencies stale on revision
        for k, s in state["prd_sections"].items():
            if target_section in s.dependencies and s.status == SectionStatus.COMPLETED:
                s.status = SectionStatus.STALE
                state["prd_sections"][k] = s
        
        # Ask for confirmation of changes
        state["messages"].append(AIMessage(content=f"Updated {PRD_TEMPLATE_SECTIONS[target_section]['title']} section. Would you like to make more changes to this section or move on?"))
        state["needs_human_input"] = True
        state["checkpoint_reason"] = f"Revision completed for {PRD_TEMPLATE_SECTIONS[target_section]['title']} - awaiting confirmation"
        
    else:
        state["messages"].append(AIMessage(content=f"Updated {PRD_TEMPLATE_SECTIONS[target_section]['title']} section. Continuing with current section..."))
        # Regular section update logic
        if section.completion_score >= 0.8:
            section.status = SectionStatus.COMPLETED
            
            # Only advance if we're working on the current section
            if target_section == original_current:
                current_idx = state["section_order"].index(target_section)
                if current_idx + 1 < len(state["section_order"]):
                    state["config"].current_section = state["section_order"][current_idx + 1]
                else:
                    state["config"].current_section = None  # All sections done
                
                state["messages"].append(AIMessage(content=f"{PRD_TEMPLATE_SECTIONS[target_section]['title']} section completed!"))
                state["run_assembler"] = True
            else:
                # Off-target update - don't advance current section
                state["messages"].append(AIMessage(content=f" Updated {PRD_TEMPLATE_SECTIONS[target_section]['title']} section. Continuing with current section..."))
        else:
            # Continue with more questions
            if update_result["next_questions"] != "complete":
                state["messages"].append(AIMessage(content=update_result["next_questions"]))
            
            # If completion score is very low, it might be an off-topic response
            if section.completion_score < 0.3:
                state["needs_human_input"] = True
                state["checkpoint_reason"] = f"Low completion score for {PRD_TEMPLATE_SECTIONS[target_section]['title']} - may need clarification"
    
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
    state["needs_human_input"] = True
    state["checkpoint_reason"] = f"Redirecting focus back to {current_section_name} section"
    
    return state

def clean_section_content(content: str, section_title: str) -> str:
	"""Clean section content to remove duplicate headers and ensure proper formatting"""
	if not content:
		return ""
	
	clean_content = content.strip()
	
	# Remove any section headers that match the title
	header_patterns = [
		f"## {section_title}",
		f"### {section_title}",
		f"# {section_title}",
		f"{section_title}:",
		f"{section_title}"
	]
	
	# Find the first occurrence of any header pattern
	first_header_pos = -1
	first_header_pattern = None
	
	for pattern in header_patterns:
		pos = clean_content.find(pattern)
		if pos != -1 and (first_header_pos == -1 or pos < first_header_pos):
			first_header_pos = pos
			first_header_pattern = pattern
	
	# If we found a header, remove it and everything before it
	if first_header_pos != -1:
		# Find the end of the header line
		header_end = clean_content.find('\n', first_header_pos)
		if header_end == -1:
			# No newline found, remove everything
			clean_content = ""
		else:
			# Remove the header line and any leading whitespace
			clean_content = clean_content[header_end + 1:].strip()
	
	# Remove any duplicate headers that might exist in the middle of content
	for pattern in header_patterns:
		if pattern in clean_content:
			parts = clean_content.split(pattern)
			if len(parts) > 1:
				# Keep only the first occurrence and everything after it
				clean_content = parts[0] + parts[1]
	
	return clean_content.strip()

def assembler_node(state: PRDBuilderState) -> PRDBuilderState:
	"""Assemble and refine the complete PRD"""
	# Prevent multiple assembler runs in the same flow
	if state.get("assembler_last_run"):
		last_run = datetime.fromisoformat(state["assembler_last_run"])
		if (datetime.now() - last_run).total_seconds() < 5:  # 5 second cooldown
			return state
	
	# Mark assembler as run
	state["assembler_last_run"] = datetime.now().isoformat()
	
	if "professional_title" not in state or not state.get("professional_title"):
		llm = LLMInterface()
		professional_title = llm.generate_professional_title(state.get("normalized_idea", ""))
		state["professional_title"] = professional_title

	# Build the complete PRD document
	prd_content = f"""# PRD: {state['professional_title']}

        **Created:** {state['config'].created_at.strftime('%Y-%m-%d %H:%M')}
        **Session:** {state['config'].session_id}

        **Overview:** {state.get("normalized_idea", "")}

    	"""

	added_sections = set()
	
	# FIX: Only add sections that haven't been added yet to avoid duplicates
	for section_key in state["section_order"]:
		if section_key in added_sections:
			continue
			
		section = state["prd_sections"][section_key]
		if section.content:
			title = PRD_TEMPLATE_SECTIONS[section_key]["title"]
			# Use the robust content cleaning function
			clean_content = clean_section_content(section.content, title)
			
			# Content cleaned and ready for assembly
			
			prd_content += f"\n## {title}\n\n{clean_content}\n"
			added_sections.add(section_key)
	
	# Create snapshot
	state["prd_snapshot"] = prd_content
	
	# Final validation: Check for duplicate sections in the final content
	section_titles = [PRD_TEMPLATE_SECTIONS[key]["title"] for key in state["section_order"] if state["prd_sections"][key].content]
	for title in section_titles:
		header_count = prd_content.count(f"## {title}")
		if header_count > 1:
			print(f"WARNING: Duplicate section header found for '{title}' - {header_count} occurrences")
			# Fix the duplicate by keeping only the first occurrence
			parts = prd_content.split(f"## {title}")
			if len(parts) > 1:
				# Keep the first part and the first occurrence of the section
				fixed_content = parts[0] + f"## {title}" + parts[1]
				# Remove any remaining duplicates
				for i in range(2, len(parts)):
					fixed_content += parts[i]
				prd_content = fixed_content
				state["prd_snapshot"] = prd_content
				print(f"Fixed duplicate section '{title}'")
	
	# Reset assembler flag to prevent multiple calls
	state["run_assembler"] = False
	
	# Simple consistency check
	issues = []
	if len(state["glossary"]) == 0:
		issues.append("Consider defining key terms in a glossary")
	state["issues_list"] = issues

	is_final = state["config"].current_section is None

	if is_final:
		state["current_stage"] = "review"
		message = f"""🎉 **PRD Assembly Complete!**

        Your PRD is ready. If you'd like some enhancements, just say so.
        """
		state["messages"].append(AIMessage(content=message))
		state["needs_human_input"] = True
		state["checkpoint_reason"] = "PRD assembly complete - ready for review"
	else:
		# Light checkpoint: continue building
		state["current_stage"] = "build"
		state["needs_human_input"] = False
		state["checkpoint_reason"] = ""

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

def revision_handler_node(state: PRDBuilderState) -> PRDBuilderState:
    """Handle revision requests specifically"""
    if state["intent_classification"] != IntentType.REVISION:
        return state
    
    target_section = state["target_section"]
    if not target_section:
        return state
    
    # Set the target section as current for better context
    state["config"].current_section = target_section
    
    # Mark the section as in progress for revision
    section = state["prd_sections"][target_section]
    section.status = SectionStatus.IN_PROGRESS
    state["prd_sections"][target_section] = section
    
    return state