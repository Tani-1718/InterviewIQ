"""Pydantic contracts for final analysis and learning plans."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ai_engine.llm import AIServiceError


class ReportValidationError(AIServiceError):
    """Raised when a report response cannot be parsed into its required schema."""


class FinalAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    overall_summary: str = Field(min_length=1)
    strengths: list[str] = Field(min_length=1)
    improvement_areas: list[str]
    technical_performance: str | None
    communication_performance: str | None
    next_steps: list[str] = Field(min_length=1)

    @field_validator("strengths", "improvement_areas", "next_steps")
    @classmethod
    def analysis_items_are_nonempty(cls, items: list[str]) -> list[str]:
        cleaned = [item.strip() for item in items]
        if any(not item for item in cleaned):
            raise ValueError("Analysis lists cannot contain empty items.")
        return cleaned

    @field_validator("overall_summary")
    @classmethod
    def summary_is_nonempty(cls, summary: str) -> str:
        cleaned = summary.strip()
        if not cleaned:
            raise ValueError("The overall summary cannot be empty.")
        return cleaned

    @field_validator("technical_performance", "communication_performance")
    @classmethod
    def optional_performance_is_nonempty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Performance summaries must be non-empty or null.")
        return cleaned


class LearningPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    topics: list[str] = Field(min_length=1)
    concepts: list[str] = Field(min_length=1)
    sample_questions: list[str] = Field(min_length=1)
    next_practice_session: str = Field(min_length=1)

    @field_validator("topics", "concepts", "sample_questions")
    @classmethod
    def plan_items_are_nonempty(cls, items: list[str]) -> list[str]:
        cleaned = [item.strip() for item in items]
        if any(not item for item in cleaned):
            raise ValueError("Learning-plan lists cannot contain empty items.")
        return cleaned

    @field_validator("next_practice_session")
    @classmethod
    def next_session_is_nonempty(cls, session: str) -> str:
        cleaned = session.strip()
        if not cleaned:
            raise ValueError("The next-practice plan cannot be empty.")
        return cleaned


ModelT = TypeVar("ModelT", bound=BaseModel)


def parse_report_response(response: str, model_type: type[ModelT]) -> ModelT:
    """Parse strict JSON (optionally fenced) and validate its Pydantic model."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            raise ReportValidationError("The report response has an incomplete JSON fence.")
        cleaned = "\n".join(lines[1:-1]).strip()
        if cleaned.casefold().startswith("json\n"):
            cleaned = cleaned[5:].strip()

    try:
        payload: Any = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ReportValidationError("The report response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ReportValidationError("The report response must be a JSON object.")
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise ReportValidationError(
            f"The report response did not match the required format: {exc}"
        ) from exc
