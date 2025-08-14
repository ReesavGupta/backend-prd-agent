from datetime import datetime
from state import PRDBuilderState
from llm import LLMInterface
from langchain.schema import AIMessage
from prompts import PRD_TEMPLATE_SECTIONS
from state import PRDSection, SectionStatus, IntentType

def idea_normalizer_node(state: PRDBuilderState) -> PRDBuilderState:
    llm = LLMInterface()

    raw_idea = state["latest_user_input"]

    normalized_idea = llm.normalize_idea(raw_idea)

    # Ensure normalized_idea is a string
    if isinstance(normalized_idea, list):
        normalized_idea = "\n".join(str(item) for item in normalized_idea)
    elif not isinstance(normalized_idea, str):
        normalized_idea = str(normalized_idea)

    if "?" in normalized_idea and len(normalized_idea.split("?")) > 1:
        # Need human input for clarification
        state["needs_human_input"] = True
        state["checkpoint_reason"] = "Need clarification for product idea"
        state["messages"].append(AIMessage(content=normalized_idea))
        return state

    state["normalized_idea"] = normalized_idea
    state["current_stage"] = "plan"
    state["messages"].append(AIMessage(content=f"Great! I've understood your idea:\n\n{normalized_idea}\n\nNow let's plan the PRD sections..."))

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
        "problem_statement", "goals", "user_personas", "success_metrics",
        "core_features", "user_flows", "constraints", "risks", "timeline"
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
    state["needs_human_input"] = True
    state["checkpoint_reason"] = "Confirm PRD section plan"
    
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
                              if v.status == SectionStatus.COMPLETED]
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
    
    section = state["prd_sections"][target_section]
    
    # Build context for update
    context = {
        "normalized_idea": state["normalized_idea"],
        "prd_sections": {k: v.content for k, v in state["prd_sections"].items() if v.content}
    }
    
    # Update section content
    update_result = llm.update_section_content(
        target_section, user_input, section.content, context
    )
    
    # Apply updates
    section.content = update_result["updated_content"]
    section.completion_score = update_result["completion_score"]
    section.last_updated = datetime.now()
    
    # Check if section is complete
    if section.completion_score >= 0.8:
        section.status = SectionStatus.COMPLETED
        
        # Move to next section
        current_idx = state["section_order"].index(target_section)
        if current_idx + 1 < len(state["section_order"]):
            state["config"].current_section = state["section_order"][current_idx + 1]
        else:
            state["config"].current_section = None  # All sections done
        
        state["messages"].append(AIMessage(content=f"✅ {PRD_TEMPLATE_SECTIONS[target_section]['title']} section completed!"))
    else:
        # Continue with more questions
        if update_result["next_questions"] != "complete":
            state["messages"].append(AIMessage(content=update_result["next_questions"]))
    
    state["prd_sections"][target_section] = section
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
    
    # Simple consistency check (in real implementation, this would be more sophisticated)
    issues = []
    if len(state["glossary"]) == 0:
        issues.append("Consider defining key terms in a glossary")
    
    state["issues_list"] = issues
    state["current_stage"] = "review"
    
    # Present assembled PRD
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
    
    return state

def exporter_node(state: PRDBuilderState) -> PRDBuilderState:
    """Export the final PRD"""
    
    # Create final version
    export_content = state["prd_snapshot"]
    
    # In real implementation, this would generate PDF, save to database, etc.
    export_info = {
        "markdown": export_content,
        "session_id": state["config"].session_id,
        "created_at": datetime.now().isoformat(),
        "version": "1.0"
    }
    
    message = f"""📄 **PRD Export Complete!**

    Your PRD has been successfully created and is ready for use!

    **Summary:**
    - **Sections completed:** {len([s for s in state['prd_sections'].values() if s.status == SectionStatus.COMPLETED])}
    - **Word count:** ~{len(state['prd_snapshot'].split())} words
    - **Session ID:** {state['config'].session_id}

    The PRD includes all essential sections and is ready to share with stakeholders.

    Thank you for using ThinkingLens PRD Builder! 🚀"""
        
    state["messages"].append(AIMessage(content=message))
    state["current_stage"] = "export"
    
    return state