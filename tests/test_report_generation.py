import json

from ai_engine.recommendation_engine import (
    generate_final_analysis,
    generate_learning_recommendations,
)
from ai_engine.report_models import FinalAnalysisResult, LearningPlan


def test_final_analysis_retries_invalid_json_and_returns_validated_result(monkeypatch):
    monkeypatch.setattr("ai_engine.recommendation_engine.time.sleep", lambda _: None)
    response = {
        "overall_summary": "The candidate gave evidence-based answers.",
        "strengths": ["Explained a concrete validation step."],
        "improvement_areas": ["Add measurable outcomes."],
        "technical_performance": "Good data validation fundamentals.",
        "communication_performance": "Answers were clear but brief.",
        "next_steps": ["Practice describing the result of each action."],
    }

    class FakeAIService:
        def __init__(self):
            self.values = []
            self.responses = ["not json", json.dumps(response)]

        def invoke(self, _prompt, values):
            self.values.append(values)
            return self.responses.pop(0)

    service = FakeAIService()
    result = generate_final_analysis(
        service,
        role="Data Analyst",
        experience_level="Intermediate",
        evaluations='[{"answer":"I checked missing values."}]',
    )

    assert isinstance(result, FinalAnalysisResult)
    assert result.strengths == ["Explained a concrete validation step."]
    assert len(service.values) == 2
    assert "previous attempt failed" in service.values[1]["format_feedback"]


def test_learning_plan_response_is_validated():
    response = {
        "topics": ["Data quality checks"],
        "concepts": ["Missing-value treatment"],
        "sample_questions": ["How would you validate a dataset?"],
        "next_practice_session": "Practice a data-quality scenario and state its outcome.",
    }

    class FakeAIService:
        def invoke(self, _prompt, _values):
            return json.dumps(response)

    result = generate_learning_recommendations(
        FakeAIService(),
        role="Data Analyst",
        experience_level="Intermediate",
        answer_feedback='[{"answer":"I checked missing values."}]',
    )

    assert isinstance(result, LearningPlan)
    assert result.concepts == ["Missing-value treatment"]
