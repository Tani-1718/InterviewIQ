"""Answer evaluation prompt invocation."""

import time

from ai_engine.evaluation_schema import (
    EvaluationResult,
    EvaluationValidationError,
    validate_evaluation_response,
)
from ai_engine.llm import AIConfigurationError, AIService, AIServiceError
from ai_engine.prompts import ANSWER_EVALUATION_PROMPT

SHORT_ANSWER_WORD_LIMIT = 4
EVALUATION_RETRY_DELAY_SECONDS = 0.5


def evaluate_answer(
    ai_service: AIService,
    *,
    role: str,
    experience_level: str,
    interview_type: str,
    question: str,
    answer: str,
) -> EvaluationResult:
    """Request and validate grounded evaluation JSON, retrying once with backoff."""
    if not answer.strip():
        raise EvaluationValidationError(
            "An empty answer cannot be evaluated. Write an answer or skip the question."
        )

    short_answer_note = (
        "This answer is very short. Evaluate only the evidence actually stated; "
        "do not infer missing detail."
        if len(answer.split()) < SHORT_ANSWER_WORD_LIMIT
        else "This answer has enough words for a regular evidence-based evaluation."
    )
    format_feedback = "This is the first attempt; return the requested JSON object."
    for attempt in range(2):
        if attempt:
            time.sleep(EVALUATION_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)))
        try:
            response = ai_service.invoke(
                ANSWER_EVALUATION_PROMPT,
                {
                    "role": role,
                    "experience_level": experience_level,
                    "interview_type": interview_type,
                    "question": question,
                    "answer": answer.strip(),
                    "short_answer_note": short_answer_note,
                    "format_feedback": format_feedback,
                },
            )
            return validate_evaluation_response(response, answer)
        except AIConfigurationError:
            raise
        except AIServiceError as exc:
            if attempt == 1:
                raise
            format_feedback = (
                f"The previous attempt failed validation or provider processing: {exc}. "
                "Return a corrected response that follows the exact schema."
            )
    raise EvaluationValidationError("The answer could not be evaluated.")
