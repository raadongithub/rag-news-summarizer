import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --- Class 1: For Generating the Initial Summary ---

class SummaryGenerator:
    """
    Generates a concise, query-focused summary from text passages.
    """
    def __init__(self):
        # Using LangChain for the initial summary generation
        self.llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.0)
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert AI assistant. Your task is to provide a concise, single-sentence summary that directly answers the user's question based *only* on the provided text context. Do not add any introductory phrases.",
                ),
                (
                    "human",
                    """Please answer the following question: "{query}"

                    Use only the information from this context:
                    ---
                    {context}
                    ---
                    """,
                ),
            ]
        )
        self.chain = self.prompt_template | self.llm | StrOutputParser()

    def generate(self, query: str, retrieved_passages: List[Dict]) -> str:
        """
        Invokes the LLM chain to generate the summary string.
        """
        context = "\n---\n".join([p.get("text", "") for p in retrieved_passages])
        if not context.strip():
            raise ValueError("Retrieved passages are empty, cannot generate a summary.")

        summary = self.chain.invoke({"query": query, "context": context})
        return summary.strip()

# --- Class 2: For Performing the Self-Critique ---

# Pydantic model for the structured output of the critique
class Critique(BaseModel):
    is_faithful: bool = Field(..., description="Is the summary factually consistent with the provided context?")
    faithfulness_explanation: str = Field(..., description="A brief justification for the faithfulness score, citing specifics from the context.")
    is_relevant: bool = Field(..., description="Does the summary directly and completely answer the user's original query?")
    relevance_explanation: str = Field(..., description="A brief justification for the relevance score.")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in the overall assessment (0.0 to 1.0).")

class SelfCritique:
    """
    Evaluates a generated summary for faithfulness and relevance using a separate model call.
    """
    def __init__(self, openai_api_key: str):
        # Using instructor to guarantee structured JSON output for the critique
        self.client = instructor.patch(OpenAI(api_key=openai_api_key))

    def evaluate(self, query: str, context: str, summary: str) -> Critique:
        """
        Asks the LLM to act as a reviewer and critique the given summary.
        """
        system_prompt = """
        You are an expert AI fact-checker and editor. Your task is to evaluate a given summary based on a source text and a user query.
        Critically assess the summary for its factual consistency with the source text (faithfulness) and its directness in answering the user query (relevance).
        Provide your assessment in a structured JSON format.
        """

        user_message = f"""
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

        try:
            # The response_model parameter forces the LLM's output to conform to our Pydantic schema
            critique_response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                response_model=Critique,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
            )
            return critique_response
        except Exception as e:
            print(f"An error occurred during critique generation: {e}")
            raise

# --- Main block to demonstrate the two-step process ---
if __name__ == '__main__':
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the environment.")

    # 1. Sample data
    sample_url = "http://example.com/news/article"
    sample_query = "What were the key financial results?"
    sample_passages = [
        {"text": "The company reported a net profit of $150 million for the third quarter. Revenue grew to $1.2 billion."},
        {"text": "Earnings per share (EPS) stood at $1.25, beating analyst expectations. International sales were 40% of total revenue."},
    ]
    full_context = "\n---\n".join([p.get("text", "") for p in sample_passages])

    # 2. Instantiate the generator and create the summary
    print("--- Step 1: Generating Summary ---")
    summary_generator = SummaryGenerator()
    generated_summary = summary_generator.generate(sample_query, sample_passages)
    print(f"Generated Summary: {generated_summary}\n")

    # 3. Instantiate the critique and evaluate the summary
    print("--- Step 2: Evaluating Summary ---")
    critique_evaluator = SelfCritique(openai_api_key=api_key)
    critique_output = critique_evaluator.evaluate(
        query=sample_query,
        context=full_context,
        summary=generated_summary
    )
    print("Evaluation Complete.\n")

    # 4. Combine all parts into the final JSON output
    final_output = {
        "summary": generated_summary,
        "self_critique": critique_output.model_dump(), # Convert Pydantic model to dict
        "metadata": {
            "source_url": sample_url,
            "user_query": sample_query
        }
    }

    # 5. Print the final serialized JSON
    print("--- Final Combined JSON Output ---")
    print(json.dumps(final_output, indent=2))
    print("----------------------------------")