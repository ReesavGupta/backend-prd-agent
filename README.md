# ThinkingLens PRD Builder

> **Transform one-liner ideas into comprehensive Product Requirements Documents (PRDs) using AI-powered orchestration**

A sophisticated backend system that leverages LangGraph to orchestrate multiple AI agents in converting simple product ideas into detailed, structured PRDs through an intelligent human-in-the-loop workflow.

## 🚀 What It Does

The ThinkingLens PRD Builder takes a single sentence product idea and transforms it into a complete, professional PRD through:

- **Intelligent Section Planning**: Automatically identifies and structures required PRD sections
- **Dynamic Content Generation**: AI-powered content creation with context-aware updates
- **Human-in-the-Loop Refinement**: Continuous collaboration between AI and human stakeholders
- **Intent Classification**: Smart routing of user inputs to appropriate processing nodes
- **Version Control**: Track changes and maintain PRD evolution history
- **Multi-Format Export**: Generate PRDs in Markdown, PDF, and other formats

## 🏗️ Architecture

### Core Components

- **LangGraph Orchestration**: Multi-node workflow with conditional routing
- **Single-LLM Runtime**: Dynamic prompt swapping for different node types
- **State Management**: Persistent session state with MongoDB + Redis caching
- **RAG Integration**: Context-aware responses using document analysis
- **Streaming API**: Real-time updates during PRD generation

### Workflow Nodes

```
START → IdeaNormalizer → SectionPlanner → SectionQuestioner → HumanInput
  ↓           ↓              ↓               ↓              ↓
IntentClassifier → SectionUpdater → Assembler → Refiner → Exporter → END
  ↓              ↓              ↓         ↓
MetaResponder   OffTopicResponder    HumanInput
```

### Node Functions

- **IdeaNormalizer**: Refines and structures initial product ideas
- **SectionPlanner**: Identifies required PRD sections and dependencies
- **SectionQuestioner**: Generates targeted questions for each section
- **IntentClassifier**: Routes user inputs to appropriate processing paths
- **SectionUpdater**: Updates PRD content based on user feedback
- **Assembler**: Combines sections into cohesive document
- **Refiner**: Polishes and improves overall PRD quality
- **Exporter**: Generates final outputs in various formats

## 🛠️ Tech Stack

- **Framework**: FastAPI + Uvicorn
- **AI Orchestration**: LangGraph + LangChain
- **Database**: MongoDB (primary) + Redis (caching)
- **LLM Integration**: OpenAI, Groq, Nomic
- **Vector Database**: Pinecone
- **Document Processing**: PyMuPDF, Unstructured
- **Python**: 3.11+

## 📡 API Endpoints

### Core PRD Operations
- `POST /sessions` - Start new PRD session
- `POST /sessions/{id}/message` - Send message/feedback
- `GET /sessions/{id}/prd` - Retrieve current PRD draft
- `POST /sessions/{id}/refine` - Trigger refinement process
- `POST /sessions/{id}/export` - Export final PRD

### Advanced Features
- `GET /sessions/{id}/stream` - Real-time streaming updates
- `POST /sessions/{id}/message-with-files` - Upload supporting documents
- `POST /sessions/{id}/flowchart` - Generate technical diagrams
- `POST /sessions/{id}/er-diagram` - Create database schemas
- `GET /sessions/{id}/versions` - Access version history

### Session Management
- `POST /sessions/{id}/save` - Persist session to database
- `GET /sessions/{id}/versions/{vid}` - Retrieve specific version

## 🔄 Workflow States

The system tracks PRD sections with:
- **Status**: Pending, In Progress, Completed, Stale
- **Dependencies**: Section relationships and prerequisites
- **Completion Score**: Progress tracking per section
- **Checklist Items**: Actionable tasks for each section

## 🎯 Intent Classification

User inputs are automatically classified into:
- **Section Update**: Modify specific PRD sections
- **Off-Target Update**: Address non-section specific changes
- **Revision**: General document improvements
- **Meta Query**: Questions about the process itself
- **Off Topic**: Unrelated inputs

## 📊 Performance & Scalability

- **Response Time**: P50 ≤ 2.5 seconds
- **Caching**: Redis-based session and context caching
- **Database**: JSONB storage for flexible schema evolution
- **Versioning**: Incremental updates with full history tracking

## 🚦 Getting Started

### Prerequisites
- Python 3.11+
- MongoDB instance
- Redis server
- API keys for LLM providers

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd prd-backend

# Install dependencies
pip install -e .

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the application
python main.py
```

### Environment Variables
```bash
# Database
MONGODB_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379

# LLM Providers
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
NOMIC_API_KEY=your_nomic_key

# Vector Database
PINECONE_API_KEY=your_pinecone_key
```

## 🔍 Usage Example

```python
import requests

# Start a new PRD session
response = requests.post("http://localhost:8000/sessions", json={
    "user_id": "user123",
    "idea": "A mobile app for finding local coffee shops with real-time availability"
})

session_id = response.json()["session_id"]

# Send feedback to improve the PRD
requests.post(f"http://localhost:8000/sessions/{session_id}/message", json={
    "message": "Add user authentication and payment integration requirements"
})

# Get the current PRD draft
prd = requests.get(f"http://localhost:8000/sessions/{session_id}/prd")
```

## 🧪 Testing

```bash
# Run end-to-end tests
python -m pytest tests/e2e.py

# Run full integration tests
python -m pytest tests/full_e2e.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request


## 🆘 Support

For questions, issues, or contributions, please open an issue in the repository or contact the development team.

---

**Built with ❤️ using LangGraph, FastAPI, and modern AI orchestration techniques**
