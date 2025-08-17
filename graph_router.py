from llm import LLMInterface
from state import PRDBuilderState, IntentType, SectionStatus
from langgraph.graph import END
def route_after_classification(state: PRDBuilderState) -> str:
    """Route based on intent classification"""
    intent = state["intent_classification"]
    
    if intent == IntentType.SECTION_UPDATE or intent == IntentType.OFF_TARGET_UPDATE or intent == IntentType.REVISION:
        return "section_updater"
    elif intent == IntentType.META_QUERY:
        return "meta_responder"  
    elif intent == IntentType.OFF_TOPIC:
        return "off_topic_responder"
    else:
        return "section_updater"  # Default

def route_after_update(state: PRDBuilderState) -> str:
	"""Route after section update"""
	# Trigger light assembly when requested (e.g., after section completion)
	if state.get("run_assembler"):
		return "assembler"
	if state["config"].current_section is None:
		# All sections complete
		return "assembler"
	elif state.get("needs_human_input"):
		# If human input is needed (e.g., low completion score), wait for user
		return "human_input"
	else:
		return "section_questioner"

def route_after_assembler(state: PRDBuilderState) -> str:
	"""Resume flow after assembly."""
	# If all sections complete, stay in review for user approval/export
	if state["config"].current_section is None:
		return "human_input"
	# Otherwise, continue building next questions
	return "section_questioner"

def route_after_human_input(state: PRDBuilderState) -> str:
    stage = state["current_stage"]
    
    if stage == "init":
        return "idea_normalizer"
    elif stage == "plan":
        return "section_questioner"
    elif stage == "build":
        msg = state["latest_user_input"]
        current = state["config"].current_section
        if current:
            section = state["prd_sections"][current]
            if section.status == SectionStatus.PENDING:
                # Heuristic: treat a strong Problem Statement reply as an answer, not a “kick”
                text = msg.lower()
                if current == "problem_statement" and len(text) >= 120 and any(k in text for k in ("product","users","user","value")):
                    return "intent_classifier"
                # LLM detector (already in your file)
                try:
                    llm = LLMInterface()
                    res = llm.is_substantive_section_answer(current, msg, section.checklist_items)
                    if res.get("substantive") and float(res.get("confidence", 0)) >= 0.6:
                        return "intent_classifier"
                except Exception:
                    pass
                return "section_questioner"
        return "intent_classifier"
    elif stage == "review":
        user_input = state["latest_user_input"].lower()
        if "export" in user_input or "finish" in user_input:
            return "exporter"
        elif "refine" in user_input or "polish" in user_input:
            return "refiner"
        else:
            return "intent_classifier"
    else:
        from langgraph.graph import END
        return END