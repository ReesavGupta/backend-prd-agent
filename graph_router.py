from state import PRDBuilderState, IntentType
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
    if state["config"].current_section is None:
        # All sections complete
        return "assembler"
    else:
        # Continue with current section
        return "section_questioner"

def route_after_human_input(state: PRDBuilderState) -> str:
    """Route after receiving human input"""
    stage = state["current_stage"]
    
    if stage == "init":
        return "idea_normalizer"
    elif stage == "plan":
        return "section_questioner" 
    elif stage == "build":
        return "intent_classifier"
    elif stage == "review":
        # Check what user wants to do
        user_input = state["latest_user_input"].lower()
        if "export" in user_input or "finish" in user_input:
            return "exporter"
        elif "refine" in user_input or "polish" in user_input:
            return "refiner"
        elif "edit" in user_input or "review" in user_input:
            return "intent_classifier" 
        else:
            return "intent_classifier"
    else:
        return END