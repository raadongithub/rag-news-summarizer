from typing import Dict, List

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


load_dotenv()
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


class Critique(BaseModel):
    is_faithful: bool = Field(
        ...,
        description="Is the summary factually consistent with the provided context?",
    )
    faithfulness_explanation: str = Field(
        ...,
        description="A brief justification for the faithfulness score, citing specifics from the context.",
    )
    is_relevant: bool = Field(
        ...,
        description="Does the summary directly and completely answer the user's original query?",
    )
    relevance_explanation: str = Field(
        ...,
        description="A brief justification for the relevance score.",
    )
    confidence_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in the overall assessment (0.0 to 1.0).",
    )


class SummaryGenerator:
    """Generate a concise answer from retrieved passages.

    Notes
    -----
    Uses a lightweight chat model with a deterministic temperature.
    """

    def __init__(self, anthropic_api_key: str | None = None):
        self.llm = ChatAnthropic(
            model=DEFAULT_ANTHROPIC_MODEL,
            temperature=0.0,
            api_key=anthropic_api_key,
        )
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
                    You are an expert AI news summarizer. Your task is to provide a concise, single-sentence summary that directly answers the user's question based only on the provided text context. Do not add any introductory phrases and only focus on answering the query.
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
        """Generate an answer grounded in retrieved passages.

        Parameters
        ----------
        query:
            User question to answer.
        retrieved_passages:
            Ranked retrieval results containing text snippets.

        Returns
        -------
        str
            Concise answer to the user query.

        Raises
        ------
        ValueError
            If the retrieved context is empty.
        """
        context = "\n---\n".join(
            passage.get("text", "") for passage in retrieved_passages
        )
        if not context.strip():
            raise ValueError("Retrieved passages are empty, cannot generate a summary.")

        summary = self.chain.invoke({"query": query, "context": context})
        return summary.strip()


class ArticleSummarizer:
    """Generate a high-level summary of the full article.

    Notes
    -----
    Produces a broader article-level summary than the query answer generator.
    """

    def __init__(self, anthropic_api_key: str | None = None):
        self.llm = ChatAnthropic(
            model=DEFAULT_ANTHROPIC_MODEL,
            temperature=0.7,
            api_key=anthropic_api_key,
        )
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert news editor. Your task is to create a comprehensive and well-structured summary of the provided news article. The summary should only be 5-7 lines long only capturing the main events, key figures, and overall significance of the story. You must strictly not to use em-dashes or any sort of styling. Only return in plain-text.",
                ),
                ("human", "Please summarize the following article:\n\n{content}"),
            ]
        )
        self.chain = self.prompt_template | self.llm | StrOutputParser()

    def generate(self, content: str) -> str:
        """Summarize a full article body.

        Parameters
        ----------
        content:
            Full article text.

        Returns
        -------
        str
            Multi-line article summary.

        Raises
        ------
        ValueError
            If the article content is empty.
        """
        if not content.strip():
            raise ValueError("Article content is empty, cannot generate a summary.")

        full_summary = self.chain.invoke({"content": content})
        return full_summary.strip()


class SelfCritique:
    """Evaluate a generated answer for faithfulness and relevance.

    Parameters
    ----------
    anthropic_api_key:
        API key used for the structured critique model call.
    """

    def __init__(self, anthropic_api_key: str | None = None):
        self.llm = ChatAnthropic(
            model=DEFAULT_ANTHROPIC_MODEL,
            temperature=0.0,
            api_key=anthropic_api_key,
        ).with_structured_output(Critique)

    def evaluate(self, query: str, context: str, summary: str) -> Critique:
        """Evaluate a generated answer against the source context.

        Parameters
        ----------
        query:
            Original user question.
        context:
            Retrieved source passages used to answer the question.
        summary:
            Generated answer to review.

        Returns
        -------
        Critique
            Structured critique result.

        Raises
        ------
        ValueError
            If the critique call fails.
        """
        system_prompt = """
        You are an expert AI fact-checker and editor. Your task is to evaluate a generated summary based on source text and a user query.

        Critically assess the summary on two dimensions:
        1. **Faithfulness** - Is every claim in the summary directly supported by the source context? Flag any hallucinations or unsupported extrapolations.
        2. **Relevance** - Does the summary directly and completely answer the user's question? Penalise vague or off-topic answers.

        For **confidence_score** (0.0-1.0), reason carefully about your own certainty:
        - Use high scores (0.85-1.0) only when the source context is unambiguous, the summary is clearly grounded, and you have no doubts.
        - Use mid-range scores (0.5-0.84) when the context is partially relevant, the summary addresses the query with minor gaps, or there is moderate ambiguity.
        - Use low scores (0.0-0.49) when the context is sparse, the query is only loosely addressed, or factual accuracy is unclear.
        - **Never default to a fixed value.** Your confidence_score must reflect the actual quality of evidence and the clarity of the evaluation for this specific case.

        Provide your assessment in the required structured format.
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

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message_prompt),
        ]

        try:
            return self.llm.invoke(messages)
        except Exception as error:
            print(f"Error occurred during critique generation: {error}")
            raise ValueError(
                "Error Occured while evaluating summarized response."
            ) from error
