import csv
from io import StringIO
import sqlite3

from database.db import (
    create_question,
    create_session,
    create_session_with_confidence,
    create_user,
    delete_session,
    finish_session,
    get_research_export_data,
    get_session_history,
    initialize_database,
    save_answer,
    save_confidence,
    save_evaluation,
    save_session_report,
    save_sus_responses,
)
from modules.settings_export import build_research_csvs


def _session_options():
    return {
        "role": "Data Analyst",
        "experience_level": "Intermediate",
        "difficulty": "Medium",
        "question_count": 5,
        "interview_type": "Technical",
    }


def test_history_summaries_and_owned_delete_cascade(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    initialize_database(db_path)
    user_id = create_user("Private Name", db_path=db_path)
    session_id = create_session_with_confidence(
        user_id,
        **_session_options(),
        confidence_rating=2,
        db_path=db_path,
    )
    question_id = create_question(
        session_id,
        user_id,
        sequence_number=1,
        question_text="How would you validate a dataset?",
        db_path=db_path,
    )
    answer_id = save_answer(
        session_id,
        user_id,
        question_id,
        answer_text="I check missing values and ranges.",
        duration_seconds=35,
        db_path=db_path,
    )
    save_evaluation(
        session_id,
        user_id,
        answer_id,
        overall_score=84,
        dimension_scores={"clarity": 80},
        feedback={"what_went_well": ["Named a concrete check."]},
        db_path=db_path,
    )
    finish_session(session_id, user_id, status="completed", db_path=db_path)
    save_confidence(
        user_id, session_id, stage="after", rating=4, db_path=db_path
    )
    save_session_report(
        session_id,
        user_id,
        final_analysis={"overall_summary": "Saved."},
        db_path=db_path,
    )
    save_sus_responses(
        session_id,
        [5, 1, 5, 1, 5, 1, 5, 1, 5, 1],
        user_id=user_id,
        db_path=db_path,
    )

    history = get_session_history(user_id, db_path=db_path)

    assert len(history) == 1
    assert history[0]["questions_answered"] == 1
    assert history[0]["average_score"] == 84
    assert history[0]["confidence_before"] == 2
    assert history[0]["confidence_after"] == 4
    assert history[0]["sus_response_count"] == 10
    assert not delete_session(session_id, user_id + 1, db_path=db_path)
    assert delete_session(session_id, user_id, db_path=db_path)
    assert get_session_history(user_id, db_path=db_path) == []
    with sqlite3.connect(db_path) as connection:
        for table, column, record_id in (
            ("sessions", "id", session_id),
            ("questions", "session_id", session_id),
            ("answers", "question_id", question_id),
            ("evaluations", "answer_id", answer_id),
            ("confidence_records", "session_id", session_id),
            ("sus_responses", "session_id", session_id),
            ("session_reports", "session_id", session_id),
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
                (record_id,),
            ).fetchone()[0] == 0


def test_research_csvs_anonymize_ids_and_exclude_demo_records(tmp_path):
    db_path = tmp_path / "export.sqlite3"
    initialize_database(db_path)
    user_id = create_user("Not exported", db_path=db_path)
    real_id = create_session_with_confidence(
        user_id,
        **_session_options(),
        confidence_rating=3,
        db_path=db_path,
    )
    finish_session(real_id, user_id, status="completed", db_path=db_path)
    save_confidence(user_id, real_id, stage="after", rating=4, db_path=db_path)
    real_responses = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]
    save_sus_responses(
        real_id, real_responses, user_id=user_id, db_path=db_path
    )

    demo_id = create_session(
        user_id, **_session_options(), is_demo=True, db_path=db_path
    )
    save_confidence(user_id, demo_id, stage="before", rating=5, db_path=db_path)
    finish_session(demo_id, user_id, status="completed", db_path=db_path)
    save_confidence(user_id, demo_id, stage="after", rating=1, db_path=db_path)
    save_sus_responses(
        demo_id, [1] * 10, user_id=user_id, db_path=db_path
    )

    records = get_research_export_data(user_id, db_path=db_path)
    confidence_csv, sus_csv = build_research_csvs(
        records,
        "P-anonymous",
        {real_id: "S-anonymous"},
    )
    confidence_row = next(csv.DictReader(StringIO(confidence_csv)))
    sus_row = next(csv.DictReader(StringIO(sus_csv)))

    assert len(records) == 1
    assert records[0]["session_id"] == real_id
    assert confidence_row["anonymous_session_id"] == "S-anonymous"
    assert confidence_row["confidence_before"] == "3"
    assert confidence_row["confidence_after"] == "4"
    assert sus_row["anonymous_session_id"] == confidence_row["anonymous_session_id"]
    assert sus_row["sus_score"] == "100.0"
    assert sus_row["benchmark"] == "68"
    assert sus_row["sus_item_10"] == "1"
    assert "Not exported" not in confidence_csv + sus_csv
    assert str(real_id) not in confidence_row["anonymous_session_id"]
