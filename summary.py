import os
from typing import List, Dict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


load_dotenv()


def generate_summary(query: str, retrieved_passages: List[Dict]) -> str:
    
    # Combine the text from retrieved passages into a single context string.
    context = "\n---\n".join([p.get("text", "") for p in retrieved_passages])

    if not context.strip():
        raise ValueError("Retrieved passages are empty, cannot generate a summary.")

    # A focused prompt template for generating a direct answer.
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert AI assistant. Your task is to provide a concise, single-sentence summary that directly answers the user's question based *only* on the provided text context.",
            ),
            (
                "human",
                """
                Please answer the following question: "{query}"

                Use only the information from this context:
                ---
                {context}
                ---
                """,
            ),
        ]
    )

    # Initialize the ChatOpenAI model.
    llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.7)

    # Define the generation chain using LangChain Expression Language (LCEL).
    # The StrOutputParser ensures the output is a simple string.
    chain = prompt_template | llm | StrOutputParser()

    # Invoke the chain with the necessary inputs.
    summary = chain.invoke({"query": query, "context": context})

    return summary

# Main block for testing purposes
if __name__ == '__main__':
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the environment.")

    # Sample data mimicking the output from the retriever.
    sample_query = "What were the key financial results?"
    sample_passages = [
        {
            "text": """The company reported a net profit of $150 million for the third quarter, a 15% increase year-over-year. Revenue grew to $1.2 billion, driven by strong performance in the cloud computing division.""",
        },
        {
            "text": "Earnings per share (EPS) stood at $1.25, beating analyst expectations of $1.10. The report highlighted that international sales accounted for 40% of the total revenue.",
        }
    ]

    try:
        # Generate the summary.
        generated_summary = generate_summary(
            query=sample_query,
            retrieved_passages=sample_passages
        )

        print("--- Generated Summary ---")
        print(generated_summary)
        print("-------------------------")

    except Exception as e:
        print(f"Summary generation failed: {e}")