"""LangChain message history built from persisted interview turns."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


def build_chat_history(
    turns: Sequence[tuple[str, str]],
) -> list[BaseMessage]:
    """Build ordered interviewer/candidate messages from question-answer pairs."""
    history: list[BaseMessage] = []
    for question, answer in turns:
        if not question.strip():
            raise ValueError("Interview history questions cannot be empty.")
        history.append(AIMessage(content=question.strip()))
        history.append(HumanMessage(content=answer.strip() or "I skipped that question."))
    return history
