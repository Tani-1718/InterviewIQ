"""Pydantic contracts and grounding checks for answer evaluations."""

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ai_engine.llm import AIServiceError


class EvaluationValidationError(AIServiceError):
    """Raised when an evaluation response is invalid or not grounded in the answer."""


class EvaluationScores(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    relevance: int = Field(ge=0, le=100)
    technical_accuracy: int = Field(ge=0, le=100)
    depth: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    structure: int = Field(ge=0, le=100)
    completeness: int = Field(ge=0, le=100)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    overall_score: int = Field(ge=0, le=100)
    scores: EvaluationScores
    what_went_well: list[str] = Field(min_length=1)
    what_was_missing: list[str] = Field(min_length=1)
    mistakes_or_inaccuracies: list[str]
    suggestions: list[str] = Field(min_length=1)
    stronger_example_answer: str = Field(min_length=1)
    concepts_to_revise: list[str]

    @field_validator(
        "what_went_well",
        "what_was_missing",
        "mistakes_or_inaccuracies",
        "suggestions",
        "concepts_to_revise",
    )
    @classmethod
    def feedback_items_are_nonempty(cls, items: list[str]) -> list[str]:
        cleaned = [item.strip() for item in items]
        if any(not item for item in cleaned):
            raise ValueError("Feedback lists cannot contain empty items.")
        return cleaned

    @field_validator("stronger_example_answer")
    @classmethod
    def example_answer_is_nonempty(cls, answer: str) -> str:
        cleaned = answer.strip()
        if not cleaned:
            raise ValueError("The stronger example answer cannot be empty.")
        return cleaned


def _normalize_words(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", value.casefold()).split())


def _parse_json_object(response: str) -> Any:
    cleaned = response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise EvaluationValidationError(
                "The evaluation response contains an incomplete JSON code block."
            )
        cleaned = "\n".join(lines[1:-1]).strip()
        if cleaned.casefold().startswith("json\n"):
            cleaned = cleaned[5:].strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise EvaluationValidationError(
            "The evaluation response was not valid JSON."
        ) from exc
    if not isinstance(result, dict):
        raise EvaluationValidationError(
            "The evaluation response must be a JSON object."
        )
    return result


def validate_evaluation_response(response: str, candidate_answer: str) -> EvaluationResult:
    """Validate JSON shape, score ranges, and an exact wording reference."""
    if not candidate_answer.strip():
        raise EvaluationValidationError(
            "An empty answer cannot be evaluated. Write an answer or skip the question."
        )
    data = _parse_json_object(response)
    try:
        evaluation = EvaluationResult.model_validate(data)
    except ValidationError as exc:
        raise EvaluationValidationError(
            f"The evaluation response did not match the required format: {exc}"
        ) from exc

    normalized_answer = _normalize_words(candidate_answer)
    for suggestion in evaluation.suggestions:
        quoted_phrases = re.findall(r'"([^"]+)"', suggestion)
        if any(
            phrase and _normalize_words(phrase) in normalized_answer
            for phrase in quoted_phrases
        ):
            return evaluation
    raise EvaluationValidationError(
        'At least one suggestion must quote exact wording from the candidate answer in double quotes.'
    )
