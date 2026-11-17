"""Small facade for the single-model interview preparation workflow."""

from collections.abc import Sequence

from langchain_core.messages import BaseMessage

from ai_engine.answer_evaluator import evaluate_answer
from ai_engine.evaluation_schema import EvaluationResult
from ai_engine.llm import AIService
from ai_engine.question_generator import generate_question
from ai_engine.recommendation_engine import (
    generate_final_analysis,
    generate_learning_recommendations,
)
from ai_engine.report_models import FinalAnalysisResult, LearningPlan


class InterviewManager:
    """Coordinate prompt calls through one shared AIService instance."""

    def __init__(self, ai_service: AIService | None = None) -> None:
        self.ai_service = ai_service or AIService()

    def next_question(
        self,
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
        return generate_question(
            self.ai_service,
            role=role,
            skills=skills,
            experience_level=experience_level,
            difficulty=difficulty,
            interview_type=interview_type,
            company_focus=company_focus,
            question_number=question_number,
            question_count=question_count,
            previous_questions=previous_questions,
            chat_history=chat_history,
            previous_answer=previous_answer,
            last_question=last_question,
            is_follow_up=is_follow_up,
        )

    def evaluate(
        self,
        *,
        role: str,
        experience_level: str,
        interview_type: str,
        question: str,
        answer: str,
    ) -> EvaluationResult:
        return evaluate_answer(
            self.ai_service,
            role=role,
            experience_level=experience_level,
            interview_type=interview_type,
            question=question,
            answer=answer,
        )

    def analyze(
        self, *, role: str, experience_level: str, evaluations: str
    ) -> FinalAnalysisResult:
        return generate_final_analysis(
            self.ai_service,
            role=role,
            experience_level=experience_level,
            evaluations=evaluations,
        )

    def recommend(
        self, *, role: str, experience_level: str, answer_feedback: str
    ) -> LearningPlan:
        return generate_learning_recommendations(
            self.ai_service,
            role=role,
            experience_level=experience_level,
            answer_feedback=answer_feedback,
        )
