from langgraph.graph import StateGraph, START, END
from state import PRDBuilderState
from graph_nodes import idea_normalizer_node, refiner_node, revision_handler_node, section_planner_node, section_questioner_node, intent_classifier_node, section_updater_node, meta_responder_node, off_topic_responder_node, assembler_node, exporter_node, human_input_node
from langgraph.types import  interrupt
from graph_router import route_after_classification, route_after_human_input, route_after_update, route_after_assembler


def create_prd_builder_graph():
    """Create the main PRD builder graph with human-in-the-loop"""
    
    # Initialize the StateGraph
    workflow = StateGraph(PRDBuilderState)
    
    # Add all nodes
    workflow.add_node("idea_normalizer", idea_normalizer_node)
    workflow.add_node("section_planner", section_planner_node)
    workflow.add_node("section_questioner", section_questioner_node)
    workflow.add_node("intent_classifier", intent_classifier_node)
    workflow.add_node("section_updater", section_updater_node)
    workflow.add_node("meta_responder", meta_responder_node)
    workflow.add_node("off_topic_responder", off_topic_responder_node)
    workflow.add_node("assembler", assembler_node)
    workflow.add_node("exporter", exporter_node)
    workflow.add_node("refiner", refiner_node)
    workflow.add_node("revision_handler", revision_handler_node)

    # From assembler: conditional resume
    workflow.add_conditional_edges("assembler", route_after_assembler)

    # From refiner: wait for human review input
    workflow.add_edge("refiner", "human_input")

    # From exporter: end
    workflow.add_edge("exporter", END)
    
    # Human-in-the-loop node
    workflow.add_node("human_input", human_input_node)
    
    # Define edges
    workflow.add_edge(START, "idea_normalizer")
    
    # From idea_normalizer: either need human input or proceed to planning
    workflow.add_conditional_edges(
        "idea_normalizer",
        lambda state: "human_input" if state["needs_human_input"] else "section_planner"
    )
    
    # From section_planner: always need human confirmation  
    workflow.add_edge("section_planner", "section_questioner")
    
    # From section_questioner: always wait for human input
    workflow.add_edge("section_questioner", "human_input")
    
    # From human_input: route based on current stage
    workflow.add_conditional_edges("human_input", route_after_human_input)
    
    # From intent_classifier: route based on classified intent
    workflow.add_conditional_edges("intent_classifier", route_after_classification)
    
    # From section_updater: either continue questioning or move to assembly
    workflow.add_conditional_edges("section_updater", route_after_update)
    
    # From meta_responder: back to human input
    workflow.add_edge("meta_responder", "human_input")
    
    # From off_topic_responder: back to questioner
    workflow.add_edge("off_topic_responder", "section_questioner")

    # IMPORTANT: Remove these conflicting edges - the router already handles this
    # workflow.add_edge("intent_classifier", "revision_handler")
    # workflow.add_edge("revision_handler", "section_updater")
    
    return workflow