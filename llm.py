import json
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from prompts import PRD_TEMPLATE_SECTIONS

class LLMInterface:
    def __init__(self, model_name : str = "gpt-4o"):
        self.model = ChatOpenAI(model=model_name, temperature=0.1)
        self.classifier_model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    def normalize_idea(self, raw_idea: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are helping create a PRD. Take the user's raw product idea and:
                1. Ask 1-2 clarifying questions if the idea is too vague
                2. Create a 2-3 sentence normalized summary that includes:
                - What the product does
                - Who the target users are  
                - The core value proposition
   
            Be concise and specific. If the idea is clear enough, provide the normalized version directly."""),

            ("human", f"Product idea: {raw_idea}")
        ])
        result = self.model.invoke(prompt.format_messages())
        return result.content

    def classify_intent(self, user_message: str, current_section: str, context: str) -> Dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Classify the user's intent. Return JSON only with these fields:
            {
            "intent": "section_update|off_target_update|revision|meta_query|off_topic",
            "target_section": "section_key_if_applicable",
            "confidence": 0.0-1.0
            }

            Intent definitions:
            - section_update: Answering current section questions  
            - off_target_update: Providing info for different section
            - revision: Wants to change/update existing content
            - meta_query: Asking about status/progress
            - off_topic: Unrelated to PRD building"""),
                        ("human", f"""Current section: {current_section}
            Context: {context}
            User message: {user_message}""")
        ])
        
        result = self.classifier_model.invoke(prompt.format_messages())

        try:
            # return json.loads(result.content)
            print(result.content)
            return {}
        except:
            return {"intent": "section_update", "target_section": current_section, "confidence": 0.5}
    
    def generate_section_questions(self, section_key: str, context: Dict) -> str:
        section_info = PRD_TEMPLATE_SECTIONS[section_key]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are building the {section_info['title']} section of a PRD.
            Given the context, ask 1-2 targeted questions that will help gather the most important information for this section.

            Section checklist to complete:
            {chr(10).join('- ' + item for item in section_info['checklist'])}

            Be specific and actionable. Focus on the highest-impact questions."""),

            ("human", f"""PRD Context: {context.get('normalized_idea', '')}

            Current section content: {context.get('current_content', '')}
            Other sections completed: {context.get('completed_sections', [])}""")
        ])

        result = self.model.invoke(prompt.format_messages())        
        # return result.content
        print(result.content)
        return ""
    
    def update_section_content(self, section_key: str, user_input: str, current_content: str, context: Dict) -> Dict:
        section_info = PRD_TEMPLATE_SECTIONS[section_key]
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Update the {section_info['title']} section based on user input.
            Return JSON with:
            {{
                "updated_content": "new section content",
                "completion_score": 0.0-1.0,
                "next_questions": "what to ask next or 'complete' if done"
            }}

            Checklist to achieve:
            {chr(10).join('- ' + item for item in section_info['checklist'])}"""),
                        ("human", f"""User input: {user_input}
            Current content: {current_content}
            Context: {json.dumps(context, default=str)}""")
                    ])
        result = self.model.invoke(prompt.format_messages())
        try:
            # return json.loads(result.content)
            print(result.content)
            return {}
        except:
            return {
                "updated_content": current_content + f"\n{user_input}",
                "completion_score": 0.5,
                "next_questions": "Please provide more details."
            }