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
    },
    "open_questions": {
        "title": "Open Questions",
        "mandatory": False,
        "dependencies": [],
        "checklist": [
            "List unknowns clearly",
            "Assign owner for each question",
            "Define next step to resolve"
        ]
    },
    "out_of_scope": {
        "title": "Out of Scope",
        "mandatory": False,
        "dependencies": [],
        "checklist": [
            "Explicitly list exclusions",
            "Clarify reasons for exclusion",
            "Note revisit conditions"
        ]
    },
    "future_ideas": {
        "title": "Future Ideas",
        "mandatory": False,
        "dependencies": [],
        "checklist": [
            "Capture high-potential ideas",
            "Note assumptions and risks",
            "Rough sequencing (later phases)"
        ]
    },
}

FLOWCHART_PROMPTS = {
    "system_architecture": (
        "Generate a system architecture flowchart showing:\n"
        "- Frontend components (web app, mobile app)\n"
        "- Backend services (API, database, AI engine)\n"
        "- External integrations (CRM, third-party APIs)\n"
        "- Data flow between components\n"
        "- Security layers and authentication"
    ),
    "user_flow": (
        "Generate a user journey flowchart showing:\n"
        "- User entry points\n"
        "- Main user interactions\n"
        "- Decision points and branches\n"
        "- Error handling paths\n"
        "- Success completion flows"
    ),
    "data_flow": (
        "Generate a data flow diagram showing:\n"
        "- Data sources and inputs\n"
        "- Processing steps and transformations\n"
        "- Storage locations\n"
        "- Data outputs and destinations\n"
        "- Data validation and error handling"
    ),
    "deployment": (
        "Generate a deployment architecture flowchart showing:\n"
        "- Development environment\n"
        "- Staging and testing\n"
        "- Production deployment\n"
        "- Monitoring and logging\n"
        "- Backup and recovery processes"
    )
}


ER_DIAGRAM_PROMPTS = {
    "database_schema": (
        "Generate a database schema ER diagram showing:\n"
        "- All major entities mentioned in the PRD\n"
        "- Relationships between entities\n"
        "- Key attributes for each entity\n"
        "- Primary and foreign keys\n"
        "- Cardinality (one-to-many, many-to-many)\n"
        "- Any specific data requirements mentioned"
    ),
    "data_model": (
        "Generate a comprehensive data model showing:\n"
        "- Core business entities\n"
        "- Data flow relationships\n"
        "- Storage requirements\n"
        "- Data validation rules\n"
        "- Integration points with external systems"
    ),
    "user_data_structure": (
        "Generate a user data structure diagram showing:\n"
        "- User profiles and roles\n"
        "- User preferences and settings\n"
        "- Activity tracking and history\n"
        "- Authentication and permissions\n"
        "- Data privacy considerations"
    ),
    "api_schema": (
        "Generate an API schema diagram showing:\n"
        "- API endpoints and methods\n"
        "- Request/response data structures\n"
        "- Authentication mechanisms\n"
        "- Rate limiting and quotas\n"
        "- Error handling structures"
    )
}