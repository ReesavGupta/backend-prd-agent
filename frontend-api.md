# ThinkingLens PRD Builder - Frontend API Documentation

## Overview

The ThinkingLens PRD Builder is an AI-powered system that converts one-liner ideas into complete Product Requirements Documents (PRDs) using LangGraph orchestration. This document provides comprehensive API documentation for building a complete frontend application.

## Base URL
```
http://localhost:8000
```

## Authentication
Currently, the system uses simple user_id-based sessions. No authentication tokens are required.

---

## Core Endpoints

### 1. Start New Session

**Endpoint:** `POST /sessions`

**Description:** Creates a new PRD building session with an initial idea.

**Request Body:**
```json
{
  "user_id": "string",
  "idea": "string"
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "message": "string",
  "stage": "init|plan|build|assemble|review|export",
  "needs_input": boolean
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "idea": "An AI-powered task management app for teams"
  }'
```

---

### 2. Send Message

**Endpoint:** `POST /sessions/{session_id}/message`

**Description:** Sends a message to continue building the PRD. The AI agent will process the message and either ask questions or update sections.

**Path Parameters:**
- `session_id`: UUID of the session

**Request Body:**
```json
{
  "message": "string"
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "message": "string",
  "stage": "string",
  "needs_input": boolean,
  "current_section": "string"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/sessions/abc-123/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Our target users are product managers and team leads"
  }'
```

---

### 3. Send Message with File Attachments

**Endpoint:** `POST /sessions/{session_id}/message-with-files`

**Description:** Sends a message with file attachments for RAG (Retrieval Augmented Generation). Supports PDF files that will be processed and used as context.

**Path Parameters:**
- `session_id`: UUID of the session

**Request Body:** `multipart/form-data`
- `message`: string (form field)
- `files`: array of files (optional)

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "message": "string",
  "stage": "string",
  "needs_input": boolean,
  "current_section": "string"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/sessions/abc-123/message-with-files" \
  -F "message=Please analyze this research document" \
  -F "files=@research.pdf"
```

---

### 4. Get PRD Draft

**Endpoint:** `GET /sessions/{session_id}/prd`

**Description:** Retrieves the current state of the PRD being built.

**Path Parameters:**
- `session_id`: UUID of the session

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "normalized_idea": "string",
  "current_stage": "string",
  "current_section": "string",
  "sections_completed": {
    "problem_statement": {
      "title": "Problem Statement",
      "content": "string",
      "status": "completed|in_progress|pending",
      "completion_score": 0.9,
      "last_updated": "2025-01-15T10:30:00"
    }
  },
  "sections_in_progress": {
    "goals": {
      "title": "Goals & Objectives",
      "content": "string",
      "status": "in_progress",
      "completion_score": 0.6,
      "last_updated": "2025-01-15T10:35:00"
    }
  },
  "prd_snapshot": "string",
  "issues": ["string"],
  "progress": "4/13 sections completed"
}
```

---

### 5. Generate Technical Flowchart

**Endpoint:** `POST /sessions/{session_id}/flowchart`

**Description:** Generates a technical flowchart in Mermaid format based on the current PRD state.

**Path Parameters:**
- `session_id`: UUID of the session

**Query Parameters:**
- `flowchart_type`: string (default: "system_architecture")

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "flowchart_type": "system_architecture",
  "mermaid_code": "flowchart TD\n    A[Start] --> B{Decision?}\n    B -->|Yes| C[Process]\n    B -->|No| D[End]",
  "prd_sections_used": ["problem_statement", "core_features"],
  "generated_at": "2025-01-15T10:40:00",
  "cached": false
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/sessions/abc-123/flowchart?flowchart_type=system_architecture"
```

---

### 6. Generate ER Diagram

**Endpoint:** `POST /sessions/{session_id}/er-diagram`

**Description:** Generates an Entity-Relationship diagram in Mermaid format based on the current PRD state.

**Path Parameters:**
- `session_id`: UUID of the session

**Query Parameters:**
- `diagram_type`: string (default: "database_schema")

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "diagram_type": "database_schema",
  "mermaid_code": "erDiagram\n    User {\n        id int PK\n        name string\n    }\n    Project {\n        id int PK\n        user_id int FK\n        name string\n    }",
  "prd_sections_used": ["core_features", "technical_architecture"],
  "generated_at": "2025-01-15T10:45:00"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/sessions/abc-123/er-diagram?diagram_type=database_schema"
```

---

### 7. Save Session to Database

**Endpoint:** `POST /sessions/{session_id}/save`

**Description:** Permanently saves the current session state to MongoDB, including generated diagrams.

**Path Parameters:**
- `session_id`: UUID of the session

**Response:**
```json
{
  "status": "success",
  "message": "Session saved successfully",
  "session_id": "uuid-string",
  "prd_id": "string",
  "saved_at": "2025-01-15T10:50:00"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/sessions/abc-123/save"
```

---

### 8. Export PRD

**Endpoint:** `POST /sessions/{session_id}/export`

**Description:** Triggers the export process to generate the final PRD document.

**Path Parameters:**
- `session_id`: UUID of the session

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "message": "string",
  "stage": "string",
  "needs_input": boolean,
  "current_section": "string"
}
```

---

### 9. Refine PRD

**Endpoint:** `POST /sessions/{session_id}/refine`

**Description:** Triggers the refinement process to improve the current PRD.

**Path Parameters:**
- `session_id`: UUID of the session

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "message": "string",
  "stage": "string",
  "needs_input": boolean,
  "current_section": "string"
}
```

---

### 10. List Versions

**Endpoint:** `GET /sessions/{session_id}/versions`

**Description:** Retrieves a list of all versions for a session.

**Path Parameters:**
- `session_id`: UUID of the session

**Response:**
```json
{
  "status": "success",
  "session_id": "uuid-string",
  "versions": [
    {
      "version_id": "string",
      "created_at": "2025-01-15T10:00:00",
      "description": "string"
    }
  ]
}
```

---

### 11. Get Specific Version

**Endpoint:** `GET /sessions/{session_id}/versions/{version_id}`

**Description:** Retrieves a specific version of a session.

**Path Parameters:**
- `session_id`: UUID of the session
- `version_id`: UUID of the version

**Response:**
```json
{
  "status": "success",
  "session_id": "uuid-string",
  "version": {
    "version_id": "string",
    "created_at": "2025-01-15T10:00:00",
    "description": "string",
    "data": {}
  }
}
```

---

### 12. Stream Messages (Server-Sent Events)

**Endpoint:** `GET /sessions/{session_id}/stream`

**Description:** Streams real-time updates during PRD building process using Server-Sent Events.

**Path Parameters:**
- `session_id`: UUID of the session

**Query Parameters:**
- `message`: string (the message to process)

**Response:** Server-Sent Events stream
```
data: {"stage": "build", "current_section": "goals", "needs_input": false, "last_message": "What are your primary goals?"}

data: {"stage": "build", "current_section": "goals", "needs_input": true, "last_message": "Please provide your goals and objectives."}
```

---

## Data Models

### PRD Section Structure

Each PRD section follows this structure:

```json
{
  "key": "string",
  "title": "string",
  "content": "string",
  "status": "pending|in_progress|completed|stale",
  "last_updated": "datetime",
  "dependencies": ["string"],
  "checklist_items": ["string"],
  "completion_score": 0.0
}
```

### Available PRD Sections

The system supports the following sections in order:

1. **problem_statement** (mandatory)
2. **goals** (mandatory, depends on problem_statement)
3. **success_metrics** (mandatory, depends on goals)
4. **user_personas** (mandatory, depends on problem_statement)
5. **core_features** (mandatory, depends on user_personas, goals)
6. **user_flows** (mandatory, depends on core_features, user_personas)
7. **technical_architecture** (optional, depends on core_features)
8. **constraints** (mandatory)
9. **risks** (mandatory, depends on core_features)
10. **timeline** (mandatory, depends on core_features)
11. **resources** (mandatory, depends on timeline)
12. **success_criteria** (mandatory, depends on success_metrics)
13. **next_steps** (mandatory, depends on all sections)

### Session Stages

The PRD building process follows these stages:

1. **init**: Initial setup and idea normalization
2. **plan**: Planning the PRD structure and sections
3. **build**: Building individual sections
4. **assemble**: Assembling the complete PRD
5. **review**: Reviewing and refining the PRD
6. **export**: Final export and completion

---

## Workflow States

### Human Input Required

When `needs_input: true`, the system is waiting for user input. The frontend should:

1. Display the current question/message
2. Show the current section being worked on
3. Provide an input field for the user's response
4. Send the response via the message endpoint

### Section Completion

When a section is completed:
- `status` changes to "completed"
- `completion_score` reaches 0.9 or higher
- The system automatically moves to the next section

### RAG Integration

When files are uploaded:
1. PDFs are processed and converted to markdown
2. Content is chunked and embedded
3. Relevant context is retrieved for each message
4. RAG context is included in AI responses

---

## Error Handling

### Common Error Responses

```json
{
  "status": "error",
  "message": "Error description"
}
```

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (invalid input)
- `404`: Not Found (session not found)
- `500`: Internal Server Error

---

## Frontend Implementation Guide

### 1. Session Management

```javascript
// Start a new session
const startSession = async (userId, idea) => {
  const response = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, idea })
  });
  return response.json();
};

// Store session ID for subsequent requests
localStorage.setItem('sessionId', response.session_id);
```

### 2. Real-time Updates

```javascript
// Use Server-Sent Events for real-time updates
const streamUpdates = (sessionId, message) => {
  const eventSource = new EventSource(`/sessions/${sessionId}/stream?message=${encodeURIComponent(message)}`);
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateUI(data);
    
    if (data.needs_input) {
      eventSource.close();
      showInputField();
    }
  };
};
```

### 3. File Upload

```javascript
// Handle file uploads with messages
const sendMessageWithFiles = async (sessionId, message, files) => {
  const formData = new FormData();
  formData.append('message', message);
  
  files.forEach(file => {
    formData.append('files', file);
  });
  
  const response = await fetch(`/sessions/${sessionId}/message-with-files`, {
    method: 'POST',
    body: formData
  });
  return response.json();
};
```

### 4. Diagram Generation

```javascript
// Generate and display Mermaid diagrams
const generateFlowchart = async (sessionId, type = 'system_architecture') => {
  const response = await fetch(`/sessions/${sessionId}/flowchart?flowchart_type=${type}`, {
    method: 'POST'
  });
  const data = await response.json();
  
  if (data.status === 'success') {
    // Use Mermaid.js to render the diagram
    mermaid.render('flowchart', data.mermaid_code);
  }
};
```

### 5. Progress Tracking

```javascript
// Track PRD building progress
const getProgress = async (sessionId) => {
  const response = await fetch(`/sessions/${sessionId}/prd`);
  const data = await response.json();
  
  const completed = Object.keys(data.sections_completed).length;
  const total = 13; // Total number of sections
  const progress = (completed / total) * 100;
  
  updateProgressBar(progress);
  displaySections(data.sections_completed, data.sections_in_progress);
};
```

---

## Best Practices

### 1. User Experience
- Show clear progress indicators
- Display current section and what's needed
- Provide helpful examples for each section
- Allow users to save work frequently

### 2. Error Handling
- Implement retry logic for failed requests
- Show user-friendly error messages
- Handle network disconnections gracefully
- Validate input before sending

### 3. Performance
- Cache PRD data locally
- Use optimistic updates for better UX
- Implement proper loading states
- Batch requests when possible

### 4. Accessibility
- Provide keyboard navigation
- Include proper ARIA labels
- Support screen readers
- Ensure color contrast compliance

---

## Complete Frontend Example

Here's a minimal but complete frontend implementation:

```html
<!DOCTYPE html>
<html>
<head>
    <title>PRD Builder</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head>
<body>
    <div id="app">
        <h1>PRD Builder</h1>
        
        <!-- Session Start -->
        <div id="session-start">
            <input type="text" id="userId" placeholder="User ID">
            <textarea id="idea" placeholder="Describe your idea"></textarea>
            <button onclick="startSession()">Start Building PRD</button>
        </div>
        
        <!-- PRD Building Interface -->
        <div id="prd-interface" style="display: none;">
            <div id="progress"></div>
            <div id="current-section"></div>
            <div id="messages"></div>
            <input type="text" id="userInput" placeholder="Your response...">
            <button onclick="sendMessage()">Send</button>
            <button onclick="generateFlowchart()">Generate Flowchart</button>
            <button onclick="saveSession()">Save Session</button>
        </div>
        
        <!-- Diagrams -->
        <div id="diagrams"></div>
    </div>
    
    <script>
        let sessionId = null;
        
        async function startSession() {
            const userId = document.getElementById('userId').value;
            const idea = document.getElementById('idea').value;
            
            const response = await fetch('/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, idea })
            });
            
            const data = await response.json();
            if (data.status === 'success') {
                sessionId = data.session_id;
                document.getElementById('session-start').style.display = 'none';
                document.getElementById('prd-interface').style.display = 'block';
                updateInterface(data);
            }
        }
        
        async function sendMessage() {
            const message = document.getElementById('userInput').value;
            document.getElementById('userInput').value = '';
            
            const response = await fetch(`/sessions/${sessionId}/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });
            
            const data = await response.json();
            updateInterface(data);
        }
        
        function updateInterface(data) {
            document.getElementById('current-section').textContent = `Current Section: ${data.current_section || 'N/A'}`;
            document.getElementById('messages').innerHTML += `<p><strong>AI:</strong> ${data.message}</p>`;
            
            if (data.needs_input) {
                document.getElementById('userInput').focus();
            }
        }
        
        async function generateFlowchart() {
            const response = await fetch(`/sessions/${sessionId}/flowchart`, {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.status === 'success') {
                const diagramDiv = document.getElementById('diagrams');
                diagramDiv.innerHTML = `<div class="mermaid">${data.mermaid_code}</div>`;
                mermaid.init();
            }
        }
        
        async function saveSession() {
            const response = await fetch(`/sessions/${sessionId}/save`, {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.status === 'success') {
                alert('Session saved successfully!');
            }
        }
    </script>
</body>
</html>
```

---

## Conclusion

This API provides everything needed to build a complete PRD agent frontend. The system handles:

- ✅ Session management
- ✅ Real-time AI interactions
- ✅ File uploads and RAG
- ✅ Diagram generation
- ✅ Progress tracking
- ✅ Data persistence
- ✅ Version control

The frontend can be built using any framework (React, Vue, Angular, vanilla JS) and will provide a smooth, interactive experience for building comprehensive PRDs.
