from typing import List, Dict
from dotenv import load_dotenv

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage


load_dotenv()


#Pydantic Model
class Critique(BaseModel):
    is_faithful: bool = Field(..., description="Is the summary factually consistent with the provided context?")
    faithfulness_explanation: str = Field(..., description="A brief justification for the faithfulness score, citing specifics from the context.")
    is_relevant: bool = Field(..., description="Does the summary directly and completely answer the user's original query?")
    relevance_explanation: str = Field(..., description="A brief justification for the relevance score.")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in the overall assessment (0.0 to 1.0).")



class SummaryGenerator:
    """
    Generates a concise, query-focused summary from text passages.
    """
    def __init__(self):
        
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.0)
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are an expert AI news summarizer. Your task is to provide a concise, single-sentence summary that directly answers the user's question based *only* on the provided text context. Do not add any introductory phrases and only focus on answering the query.
                    """,
                ),
                (
                    "human",
                    """Please answer the following question: "{query}"

                    Use only the information from this context:
                    {context}
                    """,
                ),
            ]
        )
        self.chain = self.prompt_template | self.llm | StrOutputParser()

    def generate(self, query: str, retrieved_passages: List[Dict]) -> str:
        """
        Invokes the LLM chain to generate the summary 
        """
        context = "\n---\n".join([p.get("text", "") for p in retrieved_passages])
        if not context.strip():
            raise ValueError("Retrieved passages are empty, cannot generate a summary.")

        summary = self.chain.invoke({"query": query, "context": context})
        return summary.strip()



# Separate LLM call for fair evaluation of response generated 
class SelfCritique:
    """
    Evaluates a generated summary for faithfulness and relevance using a separate LLM call
    """
    def __init__(self, openai_api_key: str):
        # Using ChatOpenAI with structured output to guarantee JSON for the critique
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.0,
            api_key=openai_api_key
        ).with_structured_output(Critique)

    def evaluate(self, query: str, context: str, summary: str) -> Critique:
        """
        Asks the LLM to act as a reviewer and critique the given summary.
        """
        system_prompt = """
        You are an expert AI fact-checker and editor. Your task is to evaluate given summary based on source text and user query.
        Critically assess the summary for its factual consistency with source text (faithfulness) and its directness in answering the user query (relevance).
        Provide your assessment in a structured JSON format.
        """

        user_message_prompt = f"""
        Please evaluate the following summary based on the provided user query and source context.

        **User Query:**
        "{query}"

        **Source Context:**
        ---
        {context}
        ---

        **Summary to Evaluate:**
        "{summary}"
        """
        
        # Create the prompt messages for the critique
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message_prompt),
        ]

        try:
            # The .with_structured_output() method ensures the output follows the Pydantic schema
            critique_response = self.llm.invoke(messages)
            return critique_response
        except Exception as e:
            print(f"Error occurred during critique generation: {e}")
            raise ValueError("Error Occured while evaluating summarized response.")