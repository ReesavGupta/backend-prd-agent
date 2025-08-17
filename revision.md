# PRD Builder System - Comprehensive System Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [LangGraph Workflow](#langgraph-workflow)
4. [State Management](#state-management)
5. [LLM Integration](#llm-integration)
6. [RAG Service](#rag-service)
7. [Database Layer](#database-layer)
8. [API Endpoints](#api-endpoints)
9. [Data Flow](#data-flow)
10. [Performance & Caching](#performance--caching)
11. [Error Handling](#error-handling)
12. [Deployment & Configuration](#deployment--configuration)

## System Overview

The PRD Builder is an AI-powered system that converts a one-liner product idea into a complete Product Requirements Document (PRD) using LangGraph orchestration. The system employs a human-in-the-loop approach where AI guides users through structured PRD creation while maintaining conversation context and ensuring document completeness.

**Core Capabilities:**
- Convert vague product ideas into structured PRDs
- Interactive Q&A for each PRD section
- Real-time document assembly and validation
- RAG-powered document ingestion and context retrieval
- Multi-format export (Markdown, PDF)
- Version control and session management
- Technical diagram generation (flowcharts, ER diagrams)

## Architecture Components

### 1. Main Application (`main.py`)
The FastAPI application that serves as the entry point and orchestrates all system operations.

**Key Features:**
- RESTful API endpoints for session management
- File upload handling for RAG document ingestion
- Streaming responses for real-time updates
- CORS middleware for frontend integration
- Performance monitoring with process time headers

**Core Endpoints:**
- `POST /sessions` - Start new PRD building session
- `POST /sessions/{id}/message` - Send messages to existing session
- `GET /sessions/{id}/prd` - Retrieve current PRD draft
- `POST /sessions/{id}/refine` - Apply editorial refinement
- `POST /sessions/{id}/export` - Export final PRD
- `GET /sessions/{id}/stream` - Stream real-time updates
- `POST /sessions/{id}/message-with-files` - Upload documents for RAG context

### 2. PRD Builder Core (`prd_builder.py`)
The main orchestrator class that manages the entire PRD building workflow.

**Responsibilities:**
- Session lifecycle management
- LangGraph workflow execution
- RAG service integration
- Database persistence
- Caching and performance optimization

**Key Methods:**
- `start_session()` - Initialize new PRD building session
- `send_message()` - Process user input and advance workflow
- `get_prd_draft()` - Retrieve current PRD state
- `export_prd()` - Generate final PRD document
- `generate_flowchart()` - Create technical diagrams
- `ask_prd_question()` - RAG-powered PRD querying

### 3. LangGraph Workflow (`graph.py`)
Defines the core workflow as a directed graph with conditional routing and human-in-the-loop nodes.

**Graph Structure:**
```
START → idea_normalizer → section_planner → section_questioner → human_input
  ↓           ↓              ↓                ↓              ↓
human_input ← meta_responder ← intent_classifier → section_updater → assembler
  ↓           ↓              ↓                ↓              ↓
exporter → END
```

**Key Characteristics:**
- **Conditional Edges**: Dynamic routing based on user intent and workflow state
- **Human-in-the-Loop**: Interrupt nodes for user input and feedback
- **State Persistence**: Checkpoint-based state management across workflow steps
- **Flexible Routing**: Context-aware decision making for workflow progression

## LangGraph Workflow

### Workflow Nodes

#### 1. Idea Normalizer Node
**Purpose**: Process and clarify initial product ideas
**Functionality**:
- Analyzes raw user input for completeness
- Generates clarifying questions if needed
- Normalizes idea into structured format
- Determines if additional context is required

**LLM Integration**:
- Uses GPT-4o for idea analysis
- Returns structured JSON with clarification needs
- Limits to maximum 2 clarifying questions
- Proceeds when sufficient context is available

#### 2. Section Planner Node
**Purpose**: Create structured PRD section plan
**Functionality**:
- Defines section order based on dependencies
- Sets initial workflow stage to "build"
- Establishes current section focus
- Presents plan to user for confirmation

**Section Dependencies**:
```
problem_statement → goals → user_personas → core_features → user_flows
     ↓              ↓         ↓            ↓           ↓
technical_architecture ← success_metrics ← risks ← constraints ← timeline
```

#### 3. Section Questioner Node
**Purpose**: Generate targeted questions for each PRD section
**Functionality**:
- Creates context-aware questions based on section requirements
- Integrates RAG context from uploaded documents
- Manages section status progression
- Ensures focused information gathering

**Question Generation**:
- Uses section-specific checklists from `prompts.py`
- Incorporates conversation history and PRD snapshot
- Generates exactly 2 questions per section
- Adapts questions based on completion progress

#### 4. Intent Classifier Node
**Purpose**: Classify user input to determine workflow routing
**Functionality**:
- Analyzes user messages for intent patterns
- Routes to appropriate workflow nodes
- Maintains conversation context and focus

**Intent Types**:
- `section_update`: Direct answer to current section questions
- `off_target_update`: Information for different section
- `revision`: Request to modify existing content
- `meta_query`: Questions about progress or process
- `off_topic`: Unrelated conversation content

#### 5. Section Updater Node
**Purpose**: Update PRD sections based on user input
**Functionality**:
- Merges user input with existing section content
- Calculates completion scores based on checklist criteria
- Manages section status transitions
- Handles dependency updates and stale content marking

**Completion Scoring**:
- Uses LLM-based content analysis
- Applies section-specific scoring heuristics
- Tracks dependencies and cross-references
- Manages section advancement logic

#### 6. Assembler Node
**Purpose**: Compile and assemble complete PRD document
**Functionality**:
- Combines all completed sections into final document
- Generates professional document title
- Creates PRD snapshot for export
- Manages document consistency and formatting

**Assembly Process**:
- Iterates through section order
- Applies content cleaning and formatting
- Generates document metadata
- Creates version control entries

#### 7. Refiner Node
**Purpose**: Apply editorial improvements to completed PRD
**Functionality**:
- Enhances clarity and consistency
- Enforces measurable metrics
- Aligns terminology across sections
- Improves overall document quality

#### 8. Exporter Node
**Purpose**: Generate final PRD exports
**Functionality**:
- Creates versioned PRD documents
- Supports multiple export formats
- Manages version history
- Prepares documents for external use

### Workflow Routing (`graph_router.py`)

**Routing Logic**:
- **After Classification**: Routes to appropriate handler based on intent
- **After Update**: Determines if assembler should run or continue questioning
- **After Assembler**: Routes based on completion status
- **After Human Input**: Context-aware routing based on current stage

**Conditional Logic**:
```python
def route_after_classification(state: PRDBuilderState) -> str:
    intent = state["intent_classification"]
    if intent == IntentType.SECTION_UPDATE:
        return "section_updater"
    elif intent == IntentType.META_QUERY:
        return "meta_responder"
    # ... additional routing logic
```

## State Management

### State Structure (`state.py`)

**Core State Components**:
```python
class PRDBuilderState(TypedDict):
    # Session Configuration
    config: SessionConfig
    
    # User Interaction
    messages: List[BaseMessage]
    latest_user_input: str
    
    # PRD Content
    normalized_idea: str
    prd_sections: Dict[str, PRDSection]
    section_order: List[str]
    prd_snapshot: str
    
    # Workflow Control
    current_stage: Literal["init", "plan", "build", "assemble", "review", "export"]
    intent_classification: Optional[IntentType]
    target_section: Optional[str]
    
    # Memory Management
    conversation_summary: str
    glossary: Dict[str, str]
    
    # Human-in-the-Loop Control
    needs_human_input: bool
    human_feedback: Optional[str]
    checkpoint_reason: str
    
    # RAG Integration
    rag_enabled: bool
    rag_context: str
    rag_sources: List[str]
```

**Section Status Management**:
```python
class SectionStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STALE = "stale"  # For dependency updates
```

**State Persistence**:
- Uses LangGraph checkpoint system
- Supports multiple backends (MongoDB, SQLite)
- Maintains conversation history across sessions
- Enables workflow resumption and recovery

## LLM Integration

### LLM Interface (`llm.py`)

**Core LLM Operations**:
- **Idea Normalization**: Converts raw ideas to structured format
- **Intent Classification**: Determines user message intent
- **Question Generation**: Creates targeted section questions
- **Content Updates**: Merges user input with existing content
- **Conversation Summarization**: Maintains context across turns
- **Diagram Generation**: Creates technical flowcharts and ER diagrams

**Model Configuration**:
- **Primary Model**: GPT-4o for complex reasoning tasks
- **Classifier Model**: GPT-4o-mini for cost-efficient classification
- **Temperature Settings**: 0.1 for consistency, 0.0 for classification

**Prompt Engineering**:
- Structured JSON outputs for reliable parsing
- Context-aware prompts incorporating conversation history
- Section-specific templates with checklist integration
- Error handling and fallback mechanisms

### Prompt Templates (`prompts.py`)

**PRD Section Templates**:
- **Mandatory Sections**: Problem Statement, Goals, User Personas, Core Features, User Flows, Success Metrics, Risks, Constraints, Timeline
- **Optional Sections**: Technical Architecture, Open Questions, Out of Scope, Future Ideas
- **Dependency Management**: Section ordering based on logical dependencies
- **Checklist Integration**: Specific criteria for each section completion

**Technical Diagram Prompts**:
- **Flowchart Types**: System Architecture, User Flow, Data Flow, Deployment
- **ER Diagram Types**: Database Schema, Data Model, User Data Structure, API Schema
- **Mermaid Integration**: Structured output for diagram rendering

## RAG Service

### Complete RAG Service (`RAGService.py`)

**Document Ingestion Pipeline**:
1. **PDF Processing**: Multiple conversion engines (pymupdf4llm, unstructured, PyPDF fallback)
2. **Text Chunking**: Header-aware splitting with configurable chunk sizes
3. **Embedding Generation**: Nomic embeddings for semantic search
4. **Vector Storage**: Pinecone integration for scalable retrieval

**Retrieval Pipeline**:
- **Semantic Search**: MMR (Maximal Marginal Relevance) retrieval
- **Metadata Filtering**: Session-specific document isolation
- **Context Integration**: RAG context injection into LLM prompts
- **Fallback Handling**: Graceful degradation when RAG fails

**Key Features**:
- **Multi-format Support**: PDF, Markdown, and text documents
- **High-fidelity Conversion**: Preserves document structure and formatting
- **Scalable Storage**: Pinecone vector database for production use
- **Session Isolation**: Metadata-based document separation

## Database Layer

### MongoDB Service (`database/database.py`)

**Data Models**:
- **PRD Documents**: Complete PRD data with metadata
- **Chat History**: Conversation logs for analysis and debugging
- **User Sessions**: Session state and configuration data

**Operations**:
- **Async Operations**: Motor-based async MongoDB client
- **Version Control**: Incremental versioning for PRD updates
- **Data Persistence**: Long-term storage of completed PRDs
- **Query Optimization**: Indexed queries for performance

### Redis Service (`database/redis.py`)

**Caching Strategy**:
- **PRD Cache**: Session-specific PRD data caching
- **Diagram Cache**: Generated technical diagrams
- **Performance Optimization**: Reduced database load and response times
- **TTL Management**: Configurable cache expiration

**Cache Keys**:
- `prd:cache:{session_id}` - PRD data caching
- `diagram:{session_id}:{diagram_type}` - Technical diagram caching

## API Endpoints

### Session Management
```http
POST /sessions
{
  "user_id": "string",
  "idea": "string"
}
```

### Message Processing
```http
POST /sessions/{session_id}/message
{
  "message": "string"
}
```

### File Upload with RAG
```http
POST /sessions/{session_id}/message-with-files
Content-Type: multipart/form-data
message: string
files: file[]
```

### Real-time Streaming
```http
GET /sessions/{session_id}/stream?message={message}
Accept: text/event-stream
```

### PRD Operations
```http
GET /sessions/{session_id}/prd
POST /sessions/{session_id}/refine
POST /sessions/{session_id}/export
POST /sessions/{session_id}/save
```

### Technical Diagrams
```http
POST /sessions/{session_id}/flowchart
POST /sessions/{session_id}/er-diagram
```

### RAG Querying
```http
POST /sessions/{session_id}/ask
{
  "message": "string"
}
```

## Data Flow

### 1. Session Initialization
```
User Input → Idea Normalizer → Section Planner → Human Input Wait
```

### 2. Section Building
```
Human Input → Intent Classifier → Section Updater → Assembler → Human Input Wait
```

### 3. RAG Integration
```
File Upload → PDF Processing → Text Chunking → Embedding → Vector Storage
Query → Semantic Search → Context Retrieval → LLM Integration
```

### 4. Document Assembly
```
Section Updates → Content Validation → Dependency Checking → Document Assembly
Final Review → Export Generation → Version Control
```

## Performance & Caching

### Caching Strategy
- **Redis Caching**: Session data, PRD drafts, generated diagrams
- **TTL Management**: Configurable expiration for different data types
- **Cache Invalidation**: Automatic cleanup of expired data
- **Performance Monitoring**: Process time headers for latency tracking

### Optimization Techniques
- **Lazy Loading**: RAG service initialization only when needed
- **Batch Operations**: Efficient database operations for bulk data
- **Streaming Responses**: Real-time updates without blocking
- **Connection Pooling**: Database connection optimization

## Error Handling

### Graceful Degradation
- **RAG Failures**: Fallback to basic text processing
- **LLM Errors**: Retry mechanisms and fallback responses
- **Database Issues**: Graceful degradation with local storage
- **Network Problems**: Connection retry and timeout handling

### Error Recovery
- **Session Recovery**: Checkpoint-based workflow resumption
- **State Validation**: Automatic state consistency checks
- **Fallback Mechanisms**: Alternative processing paths when primary fails
- **User Communication**: Clear error messages and recovery instructions

## Deployment & Configuration

### Environment Variables
```bash
# LLM Configuration
OPENAI_API_KEY=your_openai_key

# Database Configuration
MONGODB_URI=mongodb://localhost:27017
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=your_username
REDIS_PASSWORD=your_password

# RAG Configuration
NOMIC_KEY=your_nomic_key
PINECONE_KEY=your_pinecone_key
PINECONE_INDEX_NAME=rag-index

# PDF Processing
PDF_TO_MD_ENGINE=pymupdf4llm  # or unstructured
```

### Dependencies
```toml
# Core Dependencies
langgraph>=0.2.0
langchain>=0.2.0
fastapi>=0.104.0
uvicorn>=0.24.0

# LLM Providers
langchain-openai>=0.1.0
langchain-groq>=0.1.0

# Vector Database
langchain-pinecone>=0.1.0
pinecone-client>=3.0.0

# Embeddings
langchain-nomic>=0.1.0

# Database
motor>=3.3.0
redis>=5.0.0

# PDF Processing
pymupdf4llm>=0.1.0
unstructured>=0.12.0
```

### Deployment Considerations
- **Scalability**: Horizontal scaling with load balancers
- **Monitoring**: Application metrics and performance tracking
- **Security**: API key management and access control
- **Backup**: Database backup and recovery procedures
- **CI/CD**: Automated testing and deployment pipelines

## System Strengths

1. **Human-in-the-Loop**: Maintains user control while providing AI assistance
2. **Structured Workflow**: Systematic PRD building with clear progression
3. **Context Awareness**: Maintains conversation history and document state
4. **RAG Integration**: Leverages external documents for enhanced context
5. **Flexible Routing**: Dynamic workflow adaptation based on user intent
6. **Version Control**: Complete audit trail of PRD development
7. **Multi-format Export**: Support for various output formats
8. **Technical Diagram Generation**: Automatic creation of visual documentation

## System Limitations

1. **LLM Dependency**: Requires reliable LLM API access
2. **Context Window**: Limited by LLM context length constraints
3. **RAG Complexity**: Document processing can be resource-intensive
4. **State Management**: Complex state transitions require careful testing
5. **Error Handling**: Graceful degradation requires extensive fallback logic

## Future Enhancements

1. **Multi-modal Input**: Support for images, audio, and video
2. **Collaborative Editing**: Real-time multi-user PRD development
3. **Advanced Analytics**: PRD quality scoring and improvement suggestions
4. **Integration APIs**: Connect with project management and development tools
5. **Custom Templates**: User-defined PRD section templates
6. **Advanced RAG**: Multi-source document integration and synthesis
7. **Performance Optimization**: Caching improvements and query optimization
8. **Security Enhancements**: Role-based access control and audit logging

---

*This document provides a comprehensive overview of the PRD Builder system architecture, components, and workflow. For specific implementation details, refer to the individual source code files and their associated documentation.*
