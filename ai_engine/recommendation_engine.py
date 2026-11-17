"""Final analysis and learning-plan prompt invocation."""

import time

from langchain_core.prompts import ChatPromptTemplate

from ai_engine.llm import AIConfigurationError, AIService, AIServiceError
from ai_engine.prompts import FINAL_ANALYSIS_PROMPT, LEARNING_RECOMMENDATIONS_PROMPT
from ai_engine.report_models import (
    FinalAnalysisResult,
    LearningPlan,
    ModelT,
    parse_report_response,
)


def _invoke_validated(
    ai_service: AIService,
    prompt: ChatPromptTemplate,
    values: dict[str, str],
    model_type: type[ModelT],
) -> ModelT:
    format_feedback = "This is the first attempt; return the requested JSON object."
    for attempt in range(2):
        if attempt:
            time.sleep(0.5 * (2 ** (attempt - 1)))
        try:
            response = ai_service.invoke(
                prompt,
                {**values, "format_feedback": format_feedback},
            )
            return parse_report_response(response, model_type)
        except AIConfigurationError:
            raise
        except AIServiceError as exc:
            if attempt == 1:
                raise
            format_feedback = (
                f"The previous attempt failed validation or provider processing: {exc}. "
                "Correct the response to match the required JSON schema."
            )
    raise AIServiceError("The report could not be generated.")


def generate_final_analysis(
    ai_service: AIService,
    *,
    role: str,
    experience_level: str,
    evaluations: str,
) -> FinalAnalysisResult:
    """Summarize a completed session using only its supplied evidence."""
    return _invoke_validated(
        ai_service,
        FINAL_ANALYSIS_PROMPT,
        {
            "role": role,
            "experience_level": experience_level,
            "evaluations": evaluations,
        },
        FinalAnalysisResult,
    )


def generate_learning_recommendations(
    ai_service: AIService,
    *,
    role: str,
    experience_level: str,
    answer_feedback: str,
) -> LearningPlan:
    """Generate a learning plan grounded in real candidate answers."""
    return _invoke_validated(
        ai_service,
        LEARNING_RECOMMENDATIONS_PROMPT,
        {
            "role": role,
            "experience_level": experience_level,
            "answer_feedback": answer_feedback,
        },
        LearningPlan,
    )
