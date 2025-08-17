import re
import json
from typing import Dict, List
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from prompts import ER_DIAGRAM_PROMPTS, PRD_TEMPLATE_SECTIONS, FLOWCHART_PROMPTS
from dotenv import load_dotenv

load_dotenv()

class LLMInterface:
    def __init__(self, model_name : str = "gpt-4o"):
        self.model = ChatOpenAI(model=model_name, temperature=0.1)
        # Use an accessible small model for classification to avoid permission issues
        self.classifier_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def _json_from_text(self, text: str, default: Dict | None= None) -> Dict: 
        try:        
            return json.loads(text)
        except Exception:
            pass
        try:
            m = re.search(r"\{[\s\S]*\}", text)
            if m: 
                return json.loads(m.group(0))
        except Exception:
            pass
        return default or {}

    def normalize_idea(self, raw_idea: str) -> Dict:
        system = (
            'Normalize the user\'s product idea. Return JSON only:\n'
            '{\n'
            '  "needs_clarification": true|false,\n'
            '  "clarifying_questions": ["q1","q2"],\n'
            '  "normalized": "2-3 sentence summary covering product, target users, value"\n'
            '}\n'
            'Rules:\n'
            '- If the message already includes product, users, and value, set needs_clarification=false and clarifying_questions=[].\n'
            '- MAXIMUM 2 clarifying questions only. Never ask more than 2 questions.\n'
            '- Be lenient - if you can infer reasonable details, don\'t ask for clarification.\n'
            '- Only ask for clarification if absolutely essential information is missing.\n'
            '- Do not include any extra text outside JSON.'
        )
        messages = [SystemMessage(content=system), HumanMessage(content=raw_idea)]
        result = self.model.invoke(messages)
        payload = self._json_from_text(str(result.content).strip(), {
            "needs_clarification": False,
            "clarifying_questions": [],
            "normalized": str(result.content).strip()
        })
        payload["needs_clarification"] = bool(payload.get("needs_clarification", False))
        payload["clarifying_questions"] = payload.get("clarifying_questions", []) or []
        
        # Ensure maximum 2 clarifying questions
        if len(payload["clarifying_questions"]) > 2:
            payload["clarifying_questions"] = payload["clarifying_questions"][:2]
        
        payload["normalized"] = payload.get("normalized", "") or ""
        return payload

    def classify_intent(self, user_message: str, current_section: str, context: str) -> Dict:
        system = (
            "You are an expert at classifying user intent in PRD building conversations.\n"
            "Classify the user's intent and return JSON only, no extra text:\n"
            "{\n"
            '  "intent": "section_update|off_target_update|revision|meta_query|off_topic",\n'
            '  "target_section": "section_key_if_applicable",\n'
            '  "confidence": 0.0-1.0\n'
            "}\n\n"
            "Intent definitions:\n"
            "- section_update: User is answering questions for the current section\n"
            "- revision: User wants to change/update content in a completed section (look for words like 'change', 'update', 'replace', 'modify', 'edit')\n"
            "- off_target_update: User provides info for a different section than current\n"
            "- meta_query: User asks about status/progress/process\n"
            "- off_topic: Unrelated to PRD building\n\n"
            "For revisions, identify the target section from the user message.\n"
            "Look for section names, content references, or clear revision language.\n\n"
            "Few-shot examples:\n"
            "---\n"
            "Current section: problem_statement\n"
            "User: Change this section to focus on customer retention instead of acquisition.\n"
            "Output: {\"intent\": \"revision\", \"target_section\": \"problem_statement\", \"confidence\": 0.95}\n"
            "---\n"
            "Current section: goals\n"
            "User: Update the goals section to say 'achieve 60% growth' instead of '30%'.\n"
            "Output: {\"intent\": \"revision\", \"target_section\": \"goals\", \"confidence\": 0.94}\n"
            "---\n"
            "Current section: user_personas\n"
            "User: Please change the user personas section to include remote workers.\n"
            "Output: {\"intent\": \"revision\", \"target_section\": \"user_personas\", \"confidence\": 0.96}\n"
            "---\n"
            "Current section: problem_statement\n"
            "User: Our main challenge is that teams waste time on low-priority tasks.\n"
            "Output: {\"intent\": \"section_update\", \"target_section\": \"problem_statement\", \"confidence\": 0.95}\n"
            "---\n"
            "Current section: goals\n"
            "User: For the goals section, we want to aim for 40% growth.\n"
            "Output: {\"intent\": \"off_target_update\", \"target_section\": \"goals\", \"confidence\": 0.9}\n"
            "---\n"
            "Current section: solution_approach\n"
            "User: Replace 'automated reports' with 'real-time dashboards'.\n"
            "Output: {\"intent\": \"revision\", \"target_section\": \"solution_approach\", \"confidence\": 0.94}\n"
            "---\n"
            "Current section: metrics\n"
            "User: Our KPIs will focus on time saved per project and error reduction.\n"
            "Output: {\"intent\": \"section_update\", \"target_section\": \"metrics\", \"confidence\": 0.93}\n"
            "---\n"
            "Current section: any\n"
            "User: Please change the content of the goals section to be more ambitious.\n"
            "Output: {\"intent\": \"revision\", \"target_section\": \"goals\", \"confidence\": 0.93}\n"
            "---\n"
            "Current section: any\n"
            "User: I want to modify the problem statement section.\n"
            "Output: {\"intent\": \"revision\", \"target_section\": \"problem_statement\", \"confidence\": 0.95}\n"
        )

        human = f"Current section: {current_section}\nContext: {context}\nUser message: {user_message}"
        result = self.classifier_model.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        payload = self._json_from_text(str(result.content).strip(), {"intent": "section_update", "target_section": current_section, "confidence": 0.5})
        
        # Validate intent
        if payload.get("intent") not in {"section_update", "off_target_update", "revision", "meta_query", "off_topic"}:
            payload["intent"] = "section_update"
        
        # Validate target section
        if not payload.get("target_section"):
            payload["target_section"] = current_section
        
        # Additional validation for low-confidence classifications
        confidence = float(payload.get("confidence", 0.5))
        if confidence < 0.6:
            # For low confidence, be more conservative and treat as off-topic
            payload["intent"] = "off_topic"
            payload["confidence"] = 0.7
        
        return payload
        
    
    def generate_section_questions(self, section_key: str, context: Dict) -> str:
        section_info = PRD_TEMPLATE_SECTIONS[section_key]
        checklist = "\n".join('- ' + item for item in section_info['checklist'])
        system = (
            f"You are building the {section_info['title']} section of a PRD.\n"
            "Given the context, ask EXACTLY 2 targeted questions that will help gather the most important information for this section.\n\n"
            f"Section checklist to complete:\n{checklist}\n\n"
            "CRITICAL: Ask EXACTLY 2 questions, no more, no less. Be specific and actionable. Focus on the highest-impact questions."
        )
        rag = (context.get('rag_context','') or '')
        human = (
            f"PRD Context: {context.get('normalized_idea','')}\n"
            f"Current section content: {context.get('current_content','')}\n"
            f"Other sections completed: {context.get('completed_sections', [])}\n"
            f"Relevant document excerpts:\n{rag[:2000]}"
        )
        result = self.model.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        return str(result.content).strip()

    def update_section_content(self, section_key: str, user_input: str, current_content: str, context: Dict) -> Dict:
        section_info = PRD_TEMPLATE_SECTIONS[section_key]
        checklist = "\n".join('- ' + item for item in section_info['checklist'])
        system = (
            f"Update the {section_info['title']} section based on user input.\n"
            "IMPORTANT: Do NOT include section headers (## {title}) in the content.\n"
            "Return JSON only:\n"
            "{\n"
            '  "updated_content": "new section content without headers",\n'
            '  "completion_score": 0.0-1.0,\n'
            '  "next_questions": "what to ask next or \'complete\' if done"\n'
            "}\n"
            "Checklist:\n"
            f"{checklist}"
        )
        rag_context = (context.get("rag_context", "") or "")
        human = (
            f"User input: {user_input}\n"
            f"Current content: {current_content}\n"
            f"Context: {json.dumps(context, default=str)}\n"
            f"Relevant document excerpts:\n{rag_context[:2000]}"
        )

        result = self.model.invoke([SystemMessage(content=system), HumanMessage(content=human)])

        payload = self._json_from_text(str(result.content).strip())
        
        if payload and "updated_content" in payload and "completion_score" in payload:
            return {
                "updated_content": payload["updated_content"],
                "completion_score": float(payload.get("completion_score", 0.0)),
                "next_questions": payload.get("next_questions", "complete"),
            }
        # Heuristic fallback so tests progress
        # Don't append if user input contains section headers to prevent duplication
        if any(header in user_input.lower() for header in ["## ", "### ", "# "]):
            merged = user_input.strip()  # Use only user input if it contains headers
        else:
            merged = (current_content + ("\n" if current_content else "") + user_input).strip()
        text = merged.lower()
        score = 0.3  # Lower default score for random responses
        
        # Only give higher scores for clearly relevant content
        if section_key == "problem_statement":
            hits = sum(k in text for k in ["product", "users", "user", "value", "problem", "pain", "target"])
            if hits >= 3 and len(text) >= 120:
                score = 0.85
        elif section_key == "goals":
            hits = sum(k in text for k in ["goal", "target", "objective", "aim", "achieve", "increase", "reduce", "improve"])
            if hits >= 2 and len(text) >= 80:
                score = 0.75
        elif section_key == "user_personas":
            hits = sum(k in text for k in ["user", "persona", "customer", "target", "demographic", "role", "job", "needs"])
            if hits >= 2 and len(text) >= 80:
                score = 0.75
        
        # For random/unrelated responses, keep score low and ask for clarification
        if score < 0.5:
            return {
                "updated_content": current_content,  # Don't modify existing content
                "completion_score": score,
                "next_questions": "Your response doesn't seem to address the current section. Please answer the questions I asked to help build this section properly."
            }
        
        return {
            "updated_content": merged,
            "completion_score": score,
            "next_questions": "complete" if score >= 0.8 else "Please provide more detail addressing the checklist gaps."
        }

    def summarize_conversation(self, messages: List[BaseMessage], prev_summary: str = "") -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Summarize the conversation so far into 150-250 tokens focusing on decisions and facts relevant to the PRD."),
            ("human", f"Previous summary: {prev_summary}\nNew messages:\n" + "\n".join(f"{m.type}: {getattr(m,'content','')}" for m in messages[-6:]))
        ])
        result = self.model.invoke(prompt.format_messages())
        return str(result.content).strip()
    
    def is_substantive_section_answer(self, section_key: str, user_message: str, checklist: List[str]) -> Dict:
        system = (
            'Decide if the user message substantively answers the given PRD section using the checklist.\n'
            'Return JSON only:\n'
            '{ "substantive": true|false, "confidence": 0.0-1.0 }\n'
            'Be strict: only true if most checklist signals are present in the message.'
        )
        human = f"Section: {section_key}\nChecklist:\n- " + "\n- ".join(checklist) + f"\n\nUser message:\n{user_message}"
        result = self.classifier_model.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        payload = self._json_from_text(str(result.content).strip(), {"substantive": False, "confidence": 0.5})
        return {
            "substantive": bool(payload.get("substantive", False)),
            "confidence": float(payload.get("confidence", 0.5)),
        }

    def generate_technical_flowchart(self, prd_snapshot: str, flowchart_type: str = "system_architecture") -> str:
        """Generate Mermaid flowchart code based on PRD content"""
        
        system = (
            f"You are an expert technical architect. Generate a Mermaid flowchart for a {flowchart_type} "
            "based on the PRD content provided. Return ONLY the Mermaid code, no explanations.\n\n"
            "CRITICAL: Return ONLY the Mermaid code starting with 'flowchart TD' or 'flowchart LR'. "
            "DO NOT include any markdown formatting, code blocks, or explanations.\n\n"
            "Flowchart Requirements:\n"
            "- Use proper Mermaid syntax\n"
            "- Include all major system components\n"
            "- Show data flow and relationships\n"
            "- Use appropriate shapes (rectangles, diamonds, circles)\n"
            "- Include decision points where relevant\n"
            "- Make it technically accurate and implementable\n\n"
            "Mermaid Syntax:\n"
            "- Start with 'flowchart TD' or 'flowchart LR'\n"
            "- Use 'A[Label]' for rectangles\n"
            "- Use 'B{Decision?}' for diamonds\n"
            "- Use 'C((Process))' for circles\n"
            "- Use '-->' for arrows\n"
            "- Use '|text|' for labels on arrows\n\n"
            "Example Output Format:\n"
            "flowchart TD\n"
            "    A[Start] --> B{Decision?}\n"
            "    B -->|Yes| C[Process]\n"
            "    B -->|No| D[End]"
        )
        
        human = (
            f"PRD Content:\n{prd_snapshot}\n\n"
            f"Generate a {flowchart_type} flowchart in Mermaid format."
        )
        
        # Use gpt-4o-mini for cost efficiency
        result = self.classifier_model.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        return str(result.content).strip()

    def generate_er_diagram(self, prd_snapshot: str, diagram_type: str = "database_schema") -> str:
        """Generate Mermaid ER diagrams based on PRD content"""
        
        er_diagram_prompts = ER_DIAGRAM_PROMPTS
        
        system = (
            f"You are an expert database architect. Generate a Mermaid ER diagram for {diagram_type} "
            "based on the PRD content provided. Return ONLY the Mermaid code, no explanations.\n\n"
            "CRITICAL: Return ONLY the Mermaid code starting with 'erDiagram'. "
            "DO NOT include any markdown formatting, code blocks, or explanations.\n\n"
            f"Specific Requirements:\n{er_diagram_prompts.get(diagram_type, er_diagram_prompts['database_schema'])}\n\n"
            "Use proper Mermaid ER syntax:\n"
            "- Start with 'erDiagram'\n"
            "- Use 'EntityName {' for entities\n"
            "- Use 'attribute_name attribute_type' for attributes\n"
            "- Use 'EntityA ||--o{{ EntityB : relationship_description' for relationships\n"
            "- Include primary keys (PK) and foreign keys (FK)\n"
            "- Make relationships technically accurate\n\n"
            "Example Output Format:\n"
            "erDiagram\n"
            "    User {\n"
            "        id int PK\n"
            "        name string\n"
            "    }\n"
            "    Project {\n"
            "        id int PK\n"
            "        user_id int FK\n"
            "        name string\n"
            "    }\n"
            "    User ||--o{{ Project : creates"
        )
    
        
        human = f"PRD Content:\n{prd_snapshot}\n\nGenerate a {diagram_type} ER diagram in Mermaid format."
        
        result = self.classifier_model.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        return str(result.content).strip()

    def generate_professional_title(self, normalized_idea: str) -> str:
        """Use LLM to generate a professional, short title"""
        if not normalized_idea:
            return "Product Requirements Document"
        
        try:
            prompt = f"""Generate a professional, concise title (max 6-8 words) for this product idea. 
            The title should be:
            - Short and memorable
            - Professional and business-like
            - Capture the core value proposition
            - Suitable for a PRD document header
            
            Return only the title, nothing else. No quotes, no formatting.
            
            Product idea: {normalized_idea[:300]}..."""
            
            result = self.model.invoke([SystemMessage(content="You are a senior product manager. Generate concise, professional product titles that capture the essence of the product."), 
                                        HumanMessage(content=prompt)])
            
            title = str(result.content).strip()
            # Clean up any extra formatting
            title = title.replace('"', '').replace("'", "").replace("#", "").strip()
            
            # Validate title length
            if len(title) > 60:
                # Fallback to simple extraction
                words = normalized_idea.split()[:3]
                return " ".join(words)
            
            return title
        except Exception as e:
            print(f"[PRD][WARNING] Title generation failed: {e}")
            # Fallback to simple extraction
            words = normalized_idea.split()[:3]
            return " ".join(words)
    # ... existing code ...

    def generate_prd_answer(self, question: str, context: str) -> str:
        """Generate answers to questions about the PRD using provided context"""
        try:
            system = (
                "You are a helpful AI assistant that answers questions about Product Requirements Documents (PRDs). "
                "Use the provided PRD content and document context to answer questions accurately and comprehensively.\n\n"
                "Guidelines:\n"
                "- Answer based ONLY on the provided context\n"
                "- Be specific and reference relevant sections when possible\n"
                "- If the information isn't in the context, say so clearly\n"
                "- Provide actionable insights when relevant\n"
                "- Keep answers concise but thorough\n"
                "- Use markdown formatting for better readability when appropriate"
            )
            
            human = (
                f"Context:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Please provide a comprehensive answer based on the context above."
            )
            
            result = self.model.invoke([SystemMessage(content=system), HumanMessage(content=human)])
            return str(result.content).strip()
            
        except Exception as e:
            print(f"[LLM][ERROR] Failed to generate PRD answer: {e}")
            return f"I apologize, but I encountered an error while processing your question. Please try again or rephrase your question."