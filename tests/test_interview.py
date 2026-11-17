from contextlib import nullcontext

import pytest

from ai_engine.evaluation_schema import EvaluationResult, EvaluationScores
from ai_engine.llm import AIResponseError
from config.settings import Settings
from database.db import (
    create_question,
    create_session,
    create_user,
    get_interview_snapshot,
    initialize_database,
    save_answer,
)
from modules import interview


@pytest.fixture
def interview_context(tmp_path, monkeypatch):
    db_path = tmp_path / "interview.sqlite3"
    initialize_database(db_path)
    user_id = create_user(
        "Quinn",
        technical_skills=["Python", "SQL"],
        improvement_areas=["communication"],
        db_path=db_path,
    )
    session_id = create_session(
        user_id,
        role="Data Analyst",
        experience_level="Intermediate",
        difficulty="Hard",
        question_count=5,
        interview_type="Technical",
        company_focus="Northwind",
        db_path=db_path,
    )
    first_question = create_question(
        session_id,
        user_id,
        sequence_number=1,
        question_text="How would you validate a dataset before analysis?",
        db_path=db_path,
    )
    save_answer(
        session_id,
        user_id,
        first_question,
        answer_text="I check missing values and compare ranges with the source.",
        duration_seconds=30,
        db_path=db_path,
    )
    second_question = create_question(
        session_id,
        user_id,
        sequence_number=2,
        question_text="How do you decide which missing values to investigate?",
        db_path=db_path,
    )
    save_answer(
        session_id,
        user_id,
        second_question,
        answer_text="I check whether missingness follows a pattern before choosing a treatment.",
        duration_seconds=45,
        db_path=db_path,
    )
    profile = {
        "id": user_id,
        "technical_skills": ["Python", "SQL"],
        "improvement_areas": ["communication"],
    }
    snapshot = get_interview_snapshot(session_id, user_id, db_path=db_path)
    settings = Settings(
        groq_api_key="test-key",
        groq_model="llama-3.3-70b-versatile",
        database_path=db_path,
        groq_request_timeout=10,
        groq_max_retries=0,
    )
    captured = {}

    class FakeAIService:
        def __init__(self, _settings):
            pass

        def invoke(self, prompt, values):
            captured["prompt"] = prompt
            captured["values"] = values
            return "What quality checks would you automate first?"

    monkeypatch.setattr(interview, "AIService", FakeAIService)
    return db_path, profile, snapshot, settings, captured


def test_next_question_uses_persisted_interview_context(interview_context):
    db_path, profile, snapshot, settings, captured = interview_context

    question_id = interview._generate_question(
        snapshot, profile=profile, settings=settings, db_path=db_path
    )

    values = captured["values"]
    assert values["role"] == "Data Analyst"
    assert values["experience_level"] == "Intermediate"
    assert values["difficulty"] == "Hard"
    assert values["interview_type"] == "Technical"
    assert values["company_focus"] == "Northwind"
    assert values["question_number"] == 3
    assert values["question_count"] == 5
    assert values["previous_answer"] == (
        "I check whether missingness follows a pattern before choosing a treatment."
    )
    assert "How do you decide which missing values to investigate?" in values[
        "previous_questions"
    ]
    assert [
        (message.type, message.content) for message in values["chat_history"]
    ] == [
        ("ai", "How would you validate a dataset before analysis?"),
        ("human", "I check missing values and compare ranges with the source."),
    ]

    updated = get_interview_snapshot(snapshot["session"]["id"], profile["id"], db_path=db_path)
    assert updated["questions"][-1]["id"] == question_id
    assert updated["questions"][-1]["question_text"] == (
        "What quality checks would you automate first?"
    )


def test_repeated_model_question_is_not_saved(interview_context, monkeypatch):
    db_path, profile, snapshot, settings, _captured = interview_context
    repeated = "  How do you decide which missing values to investigate?  "

    class RepeatingAIService:
        def __init__(self, _settings):
            pass

        def invoke(self, _prompt, _values):
            return repeated

    monkeypatch.setattr(interview, "AIService", RepeatingAIService)
    with pytest.raises(AIResponseError, match="repeated an earlier question"):
        interview._generate_question(
            snapshot, profile=profile, settings=settings, db_path=db_path
        )

    unchanged = get_interview_snapshot(snapshot["session"]["id"], profile["id"], db_path=db_path)
    assert len(unchanged["questions"]) == 2


def test_evaluation_result_is_persisted_before_interview_can_advance(
    interview_context, monkeypatch
):
    db_path, profile, snapshot, settings, _captured = interview_context
    expected_result = EvaluationResult(
        overall_score=78,
        scores=EvaluationScores(
            relevance=80,
            technical_accuracy=75,
            depth=70,
            clarity=82,
            structure=78,
            completeness=74,
        ),
        what_went_well=["You described checking for a pattern."],
        what_was_missing=["No example of an automated check was included."],
        mistakes_or_inaccuracies=[],
        suggestions=['Explain how "missingness follows a pattern" changed your next step.'],
        stronger_example_answer=(
            "I checked whether missingness followed a pattern, then selected a "
            "validation step that matched the source data."
        ),
        concepts_to_revise=["Missing-data analysis"],
    )
    captured = {}

    class FakeInterviewManager:
        def __init__(self, _service):
            pass

        def evaluate(self, **values):
            captured.update(values)
            return expected_result

    monkeypatch.setattr(interview, "InterviewManager", FakeInterviewManager)
    monkeypatch.setattr(interview.st, "spinner", lambda _message: nullcontext())

    updated, error = interview._evaluate_saved_answer(
        snapshot,
        snapshot["questions"][-1],
        profile=profile,
        settings=settings,
        db_path=db_path,
    )

    assert error is None
    assert captured["answer"] == snapshot["questions"][-1]["answer_text"]
    assert updated["questions"][-1]["evaluation_id"] is not None
    assert updated["questions"][-1]["feedback_json"]["overall_score"] == 78
    assert updated["questions"][-1]["dimension_scores"]["technical_accuracy"] == 75
