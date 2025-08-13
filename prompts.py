PRD_TEMPLATE_SECTIONS = {
    "problem_statement": {
        "title": "Problem Statement",
        "mandatory": True,
        "dependencies": [],
        "checklist": [
            "Problem is clearly defined and specific",
            "Target users/personas are identified", 
            "Pain points are quantified where possible",
            "Current solutions' limitations are addressed"
        ]
    },
    "goals": {
        "title": "Goals & Objectives", 
        "mandatory": True,
        "dependencies": ["problem_statement"],
        "checklist": [
            "Primary goal is measurable and time-bound",
            "Secondary goals are listed",
            "Goals align with problem statement",
            "Business impact is articulated"
        ]
    },
    "success_metrics": {
        "title": "Success Metrics",
        "mandatory": True, 
        "dependencies": ["goals"],
        "checklist": [
            "Each metric has baseline, target, and timeframe",
            "Metrics owner is assigned",
            "Data source/measurement method is specified",
            "Leading and lagging indicators are included"
        ]
    },
    "user_personas": {
        "title": "User Personas",
        "mandatory": True,
        "dependencies": ["problem_statement"], 
        "checklist": [
            "Primary persona is detailed with demographics",
            "User needs and pain points are specified",
            "User journey touchpoints are identified",
            "Secondary personas are briefly described"
        ]
    },
    "core_features": {
        "title": "Core Features",
        "mandatory": True,
        "dependencies": ["user_personas", "goals"],
        "checklist": [
            "Features directly address user needs",
            "MVP features are prioritized",
            "Feature requirements are specific",
            "Technical feasibility is considered"
        ]
    },
    "user_flows": {
        "title": "User Flows", 
        "mandatory": True,
        "dependencies": ["core_features", "user_personas"],
        "checklist": [
            "Key user journeys are mapped",
            "Happy path and edge cases are covered",
            "Flow steps reference specific features",
            "User personas are connected to flows"
        ]
    },
    "technical_architecture": {
        "title": "Technical Architecture",
        "mandatory": False,
        "dependencies": ["core_features"],
        "checklist": [
            "High-level system components are defined",
            "Data flow is outlined",
            "Integration points are specified",
            "Scalability considerations are addressed"
        ]
    },
    "constraints": {
        "title": "Constraints & Assumptions",
        "mandatory": True,
        "dependencies": [],
        "checklist": [
            "Technical constraints are listed",
            "Business constraints are specified", 
            "Resource limitations are acknowledged",
            "Key assumptions are documented"
        ]
    },
    "risks": {
        "title": "Risks & Mitigation",
        "mandatory": True,
        "dependencies": ["core_features"],
        "checklist": [
            "Technical risks are identified",
            "Market/competitive risks are listed", 
            "Mitigation strategies are provided",
            "Risk probability and impact are assessed"
        ]
    },
    "timeline": {
        "title": "Timeline & Milestones",
        "mandatory": True,
        "dependencies": ["core_features"],
        "checklist": [
            "Key milestones are defined",
            "Dependencies between milestones are clear",
            "Resource allocation is considered",
            "Buffer time for unknowns is included"
        ]
    }
}