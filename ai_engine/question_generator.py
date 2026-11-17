"""Question generation using the shared Groq-backed AI service."""

from collections.abc import Sequence

from ai_engine.llm import AIService
from ai_engine.prompts import FOLLOW_UP_QUESTION_PROMPT, QUESTION_GENERATION_PROMPT
from langchain_core.messages import BaseMessage


def generate_question(
    ai_service: AIService,
    *,
    role: str,
    skills: str,
    experience_level: str,
    difficulty: str,
    interview_type: str,
    company_focus: str,
    question_number: int,
    question_count: int,
    previous_questions: str,
    chat_history: Sequence[BaseMessage],
    previous_answer: str,
    last_question: str = "",
    is_follow_up: bool = False,
) -> str:
    """Generate one fresh question or a context-grounded follow-up."""
    prompt = FOLLOW_UP_QUESTION_PROMPT if is_follow_up else QUESTION_GENERATION_PROMPT
    return ai_service.invoke(
        prompt,
        {
            "role": role,
            "skills": skills,
            "experience_level": experience_level,
            "difficulty": difficulty,
            "interview_type": interview_type,
            "company_focus": company_focus or "None specified",
            "question_number": question_number,
            "question_count": question_count,
            "previous_questions": previous_questions or "None",
            "chat_history": list(chat_history),
            "previous_answer": previous_answer or "No answer yet.",
            "last_question": last_question or "No preceding question.",
        },
    )
