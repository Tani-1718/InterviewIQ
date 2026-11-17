import pytest

from database.db import (
    create_question,
    create_session,
    create_user,
    finish_session,
    get_interview_snapshot,
    get_session_report,
    initialize_database,
    save_session_report,
    save_answer,
    save_evaluation,
)
from config.settings import Settings
from modules.results import _ensure_ai_report, build_report_metrics
from utils.pdf_generator import generate_report_pdf


def _create_report_snapshot(db_path, *, is_demo=False):
    initialize_database(db_path)
    user_id = create_user("Taylor", db_path=db_path)
    session_id = create_session(
        user_id,
        role="Data Analyst",
        experience_level="Intermediate",
        difficulty="Medium",
        question_count=5,
        interview_type="Technical",
        is_demo=is_demo,
        db_path=db_path,
    )
    dimensions = {
        "relevance": 75,
        "technical_accuracy": 70,
        "depth": 65,
        "clarity": 80,
        "structure": 60,
        "completeness": 72,
    }
    for sequence, score in ((1, 72), (2, 86)):
        question_id = create_question(
            session_id,
            user_id,
            sequence_number=sequence,
            question_text=f"How do you approach analysis task {sequence}?",
            db_path=db_path,
        )
        answer_id = save_answer(
            session_id,
            user_id,
            question_id,
            answer_text=f"I start by checking the input data for case {sequence}.",
            duration_seconds=40 + sequence,
            db_path=db_path,
        )
        save_evaluation(
            session_id,
            user_id,
            answer_id,
            overall_score=score,
            dimension_scores=dimensions,
            feedback={
                "what_went_well": ["You mentioned checking input data."],
                "what_was_missing": ["Add a measurable result."],
                "mistakes_or_inaccuracies": [],
                "suggestions": [
                    'Explain what you did after "checking the input data".'
                ],
                "stronger_example_answer": "I first validated the data.",
                "concepts_to_revise": ["Data validation"],
            },
            db_path=db_path,
        )
    finish_session(session_id, user_id, status="completed", db_path=db_path)
    return get_interview_snapshot(session_id, user_id, db_path=db_path)


def test_report_metrics_are_derived_from_saved_evaluations(tmp_path):
    snapshot = _create_report_snapshot(tmp_path / "report.sqlite3")

    metrics = build_report_metrics(snapshot)

    assert metrics["questions_answered"] == 2
    assert metrics["evaluated_answers"] == 2
    assert metrics["average_score"] == 79
    assert metrics["overall_score"] == 79
    assert metrics["best_answer"]["sequence_number"] == 2
    assert metrics["worst_answer"]["sequence_number"] == 1
    assert metrics["technical_performance"] == 67.5
    assert metrics["communication_performance"] == 70


def test_demo_report_never_exposes_saved_evaluations_as_scores(tmp_path):
    snapshot = _create_report_snapshot(
        tmp_path / "demo-report.sqlite3", is_demo=True
    )

    metrics = build_report_metrics(snapshot)

    assert metrics["questions_answered"] == 2
    assert metrics["evaluated_answers"] == 0
    assert metrics["overall_score"] is None
    assert metrics["question_scores"] == []


def test_pdf_report_is_generated_and_handles_non_ascii_content(tmp_path):
    snapshot = _create_report_snapshot(tmp_path / "pdf-report.sqlite3")
    report = {
        "session": snapshot["session"],
        "metrics": build_report_metrics(snapshot),
        "questions": snapshot["questions"],
        "final_analysis": None,
        "learning_plan": None,
    }
    report["questions"][0]["answer_text"] += " Café and λ."

    pdf = generate_report_pdf(report)

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


def test_report_sections_are_cached_incrementally_for_the_session_owner(tmp_path):
    snapshot = _create_report_snapshot(tmp_path / "cache-report.sqlite3")
    session_id = snapshot["session"]["id"]
    user_id = snapshot["session"]["user_id"]
    first_analysis = {"overall_summary": "Grounded summary."}
    learning_plan = {"topics": ["Data validation"]}

    partial = save_session_report(
        session_id,
        user_id,
        final_analysis=first_analysis,
        db_path=tmp_path / "cache-report.sqlite3",
    )
    saved = save_session_report(
        session_id,
        user_id,
        final_analysis={"overall_summary": "Replacement must not overwrite."},
        learning_plan=learning_plan,
        db_path=tmp_path / "cache-report.sqlite3",
    )

    assert partial["learning_plan"] is None
    assert saved["final_analysis"] == first_analysis
    assert saved["learning_plan"] == learning_plan
    assert get_session_report(
        session_id, user_id, db_path=tmp_path / "cache-report.sqlite3"
    ) == saved
    assert get_session_report(
        session_id, user_id + 1, db_path=tmp_path / "cache-report.sqlite3"
    ) is None


def test_demo_sessions_cannot_cache_ai_report_sections(tmp_path):
    db_path = tmp_path / "demo-cache.sqlite3"
    snapshot = _create_report_snapshot(db_path, is_demo=True)

    assert get_session_report(
        snapshot["session"]["id"],
        snapshot["session"]["user_id"],
        db_path=db_path,
    ) is None
    with pytest.raises(ValueError, match="completed real sessions"):
        save_session_report(
            snapshot["session"]["id"],
            snapshot["session"]["user_id"],
            final_analysis={"overall_summary": "Should not persist."},
            db_path=db_path,
        )


def test_cached_report_is_available_without_an_api_key(tmp_path):
    db_path = tmp_path / "cached-report.sqlite3"
    snapshot = _create_report_snapshot(db_path)
    user_id = snapshot["session"]["user_id"]
    expected = save_session_report(
        snapshot["session"]["id"],
        user_id,
        final_analysis={"overall_summary": "Saved analysis."},
        learning_plan={"topics": ["Saved topic"]},
        db_path=db_path,
    )
    settings = Settings(
        groq_api_key=None,
        groq_model="llama-3.3-70b-versatile",
        database_path=db_path,
        groq_request_timeout=10,
        groq_max_retries=0,
    )

    report, error = _ensure_ai_report(
        snapshot, {"id": user_id}, settings, db_path
    )

    assert report == expected
    assert error is None
