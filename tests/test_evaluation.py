import json

import pytest

from ai_engine import answer_evaluator
from ai_engine.evaluation_schema import (
    EvaluationResult,
    EvaluationValidationError,
    validate_evaluation_response,
)


def valid_payload():
    return {
        "overall_score": 72,
        "scores": {
            "relevance": 80,
            "technical_accuracy": 70,
            "depth": 60,
            "clarity": 75,
            "structure": 70,
            "completeness": 65,
        },
        "what_went_well": ["You identified tracing as part of your investigation."],
        "what_was_missing": ["No before-and-after latency was stated."],
        "mistakes_or_inaccuracies": [],
        "suggestions": [
            'Quantify what changed after "tracing" and explain the impact.'
        ],
        "stronger_example_answer": (
            "I used tracing to locate the slow database call, then measured latency "
            "before and after the fix."
        ),
        "concepts_to_revise": ["Distributed tracing"],
    }


def test_evaluation_json_is_pydantic_validated_and_grounded():
    response = "```json\n" + json.dumps(valid_payload()) + "\n```"

    evaluation = validate_evaluation_response(response, "I used tracing.")

    assert isinstance(evaluation, EvaluationResult)
    assert evaluation.overall_score == 72
    assert evaluation.scores.technical_accuracy == 70
    assert evaluation.suggestions[0].startswith("Quantify")


@pytest.mark.parametrize(
    ("mutate", "answer", "message"),
    [
        (
            lambda payload: payload.update(overall_score=101),
            "I used tracing.",
            "required format",
        ),
        (
            lambda payload: payload.pop("scores"),
            "I used tracing.",
            "required format",
        ),
        (
            lambda payload: payload["suggestions"].__setitem__(
                0, "Add more detail to your answer."
            ),
            "I used tracing.",
            "quote exact wording",
        ),
    ],
)
def test_invalid_or_generic_evaluations_are_rejected(mutate, answer, message):
    payload = valid_payload()
    mutate(payload)

    with pytest.raises(EvaluationValidationError, match=message):
        validate_evaluation_response(json.dumps(payload), answer)


def test_empty_answers_are_not_sent_for_evaluation():
    class UnexpectedAIService:
        def invoke(self, *_args, **_kwargs):
            raise AssertionError("Empty answers must not reach the model.")

    with pytest.raises(EvaluationValidationError, match="empty answer"):
        answer_evaluator.evaluate_answer(
            UnexpectedAIService(),
            role="Data Analyst",
            experience_level="Fresher",
            interview_type="Technical",
            question="What would you analyze?",
            answer="   ",
        )


def test_invalid_model_json_retries_once_with_backoff(monkeypatch):
    corrected_payload = valid_payload()
    corrected_payload["suggestions"] = [
        'Explain what you did with "SQL" and what the result showed.'
    ]
    responses = ["not json", json.dumps(corrected_payload)]
    captured_values = []
    delays = []

    class FakeAIService:
        def invoke(self, _prompt, values):
            captured_values.append(values)
            return responses.pop(0)

    monkeypatch.setattr(answer_evaluator.time, "sleep", delays.append)
    evaluation = answer_evaluator.evaluate_answer(
        FakeAIService(),
        role="Data Analyst",
        experience_level="Fresher",
        interview_type="Technical",
        question="What did you do?",
        answer="I used SQL.",
    )

    assert evaluation.overall_score == 72
    assert delays == [answer_evaluator.EVALUATION_RETRY_DELAY_SECONDS]
    assert "very short" in captured_values[1]["short_answer_note"]
    assert "valid JSON" in captured_values[1]["format_feedback"]
