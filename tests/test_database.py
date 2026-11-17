import json
import sqlite3

import pytest

from database.db import (
    create_session,
    create_session_with_confidence,
    create_user,
    create_question,
    finish_session,
    get_dashboard_data,
    get_confidence_history,
    get_interview_snapshot,
    get_session_confidence,
    get_sus_responses,
    get_latest_user,
    get_session,
    get_user,
    initialize_database,
    list_sessions,
    save_confidence,
    save_answer,
    save_evaluation,
    save_sus_responses,
    switch_session_to_demo,
    update_user,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "nested" / "interviewiq.sqlite3"
    initialize_database(path)
    return path


def test_profile_create_read_update(db_path):
    user_id = create_user(
        "  Alex  ",
        education="BSc",
        technical_skills=["Python", "SQL"],
        improvement_areas=["communication"],
        db_path=db_path,
    )

    user = get_user(user_id, db_path=db_path)
    assert user["name"] == "Alex"
    assert user["technical_skills"] == ["Python", "SQL"]
    assert user["improvement_areas"] == ["communication"]

    assert update_user(
        user_id,
        name="Alex Chen",
        experience_level="Intermediate",
        db_path=db_path,
    )
    assert get_user(user_id, db_path=db_path)["name"] == "Alex Chen"
    assert not update_user(999, name="Missing", db_path=db_path)


def test_latest_profile_is_loaded_for_local_single_user_app(db_path):
    first_id = create_user("First", db_path=db_path)
    latest_id = create_user("Latest", db_path=db_path)

    assert get_latest_user(db_path=db_path)["id"] == latest_id
    assert latest_id > first_id


def test_dashboard_metrics_use_real_database_records_only(db_path):
    user_id = create_user("Jordan", db_path=db_path)
    real_session = create_session(
        user_id,
        role="Data Analyst",
        experience_level="Intermediate",
        difficulty="Medium",
        question_count=5,
        interview_type="Technical",
        db_path=db_path,
    )
    demo_session = create_session(
        user_id,
        role="Data Analyst",
        experience_level="Intermediate",
        difficulty="Medium",
        question_count=5,
        interview_type="Technical",
        is_demo=True,
        db_path=db_path,
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE sessions SET status = 'completed' WHERE id IN (?, ?)",
            (real_session, demo_session),
        )
        for session_id, scores in (
            (
                real_session,
                [
                    (80, {"technical_accuracy": 90, "clarity": 70, "relevance": 80}),
                    (60, {"technical_accuracy": 70, "clarity": 80, "relevance": 50}),
                ],
            ),
            (
                demo_session,
                [(100, {"technical_accuracy": 100, "clarity": 100, "relevance": 100})],
            ),
        ):
            for sequence, (score, dimensions) in enumerate(scores, start=1):
                question_id = connection.execute(
                    """
                    INSERT INTO questions (session_id, sequence_number, question_text)
                    VALUES (?, ?, ?)
                    """,
                    (session_id, sequence, "A test question"),
                ).lastrowid
                answer_id = connection.execute(
                    "INSERT INTO answers (question_id, answer_text) VALUES (?, ?)",
                    (question_id, "A test answer"),
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO evaluations
                        (answer_id, overall_score, dimension_scores, feedback_json)
                    VALUES (?, ?, ?, '{}')
                    """,
                    (answer_id, score, json.dumps(dimensions)),
                )

    dashboard = get_dashboard_data(user_id, db_path=db_path)
    assert dashboard["interviews_completed"] == 1
    assert dashboard["questions_answered"] == 2
    assert dashboard["average_score"] == 70
    assert dashboard["strongest_skill"] == "technical_accuracy"
    assert dashboard["weak_areas"] == ["relevance", "clarity"]
    assert len(dashboard["recent_sessions"]) == 1
    assert len(dashboard["progress"]) == 1


def test_dashboard_empty_state_has_no_invented_scores(db_path):
    user_id = create_user("Casey", db_path=db_path)

    dashboard = get_dashboard_data(user_id, db_path=db_path)
    assert dashboard["interviews_completed"] == 0
    assert dashboard["questions_answered"] == 0
    assert dashboard["average_score"] is None
    assert dashboard["strongest_skill"] is None
    assert dashboard["weak_areas"] == []
    assert dashboard["progress"] == []


def test_session_configuration_and_pre_confidence_save_atomically(db_path):
    user_id = create_user("Morgan", db_path=db_path)
    options = {
        "role": "Product Designer",
        "experience_level": "Intermediate",
        "difficulty": "Hard",
        "question_count": 10,
        "interview_type": "Behavioral",
        "db_path": db_path,
    }

    with pytest.raises(ValueError):
        create_session_with_confidence(
            user_id,
            **options,
            confidence_rating=0,
        )
    assert list_sessions(user_id, db_path=db_path) == []

    session_id = create_session_with_confidence(
        user_id,
        **options,
        company_focus="Studio North",
        confidence_rating=4,
    )
    with sqlite3.connect(db_path) as connection:
        session = connection.execute(
            "SELECT role, difficulty, question_count, company_focus FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        confidence = connection.execute(
            "SELECT stage, rating FROM confidence_records WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    assert session == ("Product Designer", "Hard", 10, "Studio North")
    assert confidence == ("before", 4)


def test_sessions_can_exclude_demo_records(db_path):
    user_id = create_user("Sam", db_path=db_path)
    session_options = {
        "role": "Data Analyst",
        "experience_level": "Fresher",
        "difficulty": "Easy",
        "question_count": 5,
        "interview_type": "Technical",
        "db_path": db_path,
    }

    real_id = create_session(user_id, **session_options)
    demo_id = create_session(user_id, **session_options, is_demo=True)

    assert [s["id"] for s in list_sessions(user_id, db_path=db_path)] == [real_id]
    assert {
        s["id"] for s in list_sessions(user_id, include_demo=True, db_path=db_path)
    } == {real_id, demo_id}


def test_interview_progress_resumes_and_finishes(db_path):
    user_id = create_user("Jamie", db_path=db_path)
    session_id = create_session(
        user_id,
        role="Software Engineer",
        experience_level="Intermediate",
        difficulty="Medium",
        question_count=5,
        interview_type="Technical",
        db_path=db_path,
    )
    question_id = create_question(
        session_id,
        user_id,
        sequence_number=1,
        question_text="How would you debug a slow API endpoint?",
        db_path=db_path,
    )

    snapshot = get_interview_snapshot(session_id, user_id, db_path=db_path)
    assert snapshot["questions"][0]["id"] == question_id
    assert snapshot["questions"][0]["answer_id"] is None
    with pytest.raises(ValueError, match="Submit or skip"):
        create_question(
            session_id,
            user_id,
            sequence_number=2,
            question_text="How do you test a service?",
            db_path=db_path,
        )

    save_answer(
        session_id,
        user_id,
        question_id,
        answer_text="I would check traces and compare request timings.",
        duration_seconds=42,
        db_path=db_path,
    )
    resumed = get_interview_snapshot(session_id, user_id, db_path=db_path)
    assert resumed["questions"][0]["answer_text"] == (
        "I would check traces and compare request timings."
    )
    assert resumed["questions"][0]["duration_seconds"] == 42

    assert finish_session(session_id, user_id, db_path=db_path)
    assert get_session(session_id, user_id, db_path=db_path)["status"] == "completed"
    assert not finish_session(session_id, user_id, db_path=db_path)


def test_skips_are_persisted_but_not_counted_as_answers(db_path):
    user_id = create_user("Ari", db_path=db_path)
    session_id = create_session(
        user_id,
        role="Data Analyst",
        experience_level="Fresher",
        difficulty="Easy",
        question_count=5,
        interview_type="Technical",
        db_path=db_path,
    )
    question_id = create_question(
        session_id,
        user_id,
        sequence_number=1,
        question_text="What is a database index?",
        db_path=db_path,
    )
    save_answer(
        session_id,
        user_id,
        question_id,
        answer_text="",
        duration_seconds=8,
        was_skipped=True,
        db_path=db_path,
    )

    snapshot = get_interview_snapshot(session_id, user_id, db_path=db_path)
    dashboard = get_dashboard_data(user_id, db_path=db_path)
    assert snapshot["questions"][0]["was_skipped"] == 1
    assert dashboard["questions_answered"] == 0
    assert dashboard["recent_sessions"][0]["questions_answered"] == 0
    with pytest.raises(ValueError, match="Skipped questions"):
        save_evaluation(
            session_id,
            user_id,
            snapshot["questions"][0]["answer_id"],
            overall_score=0,
            dimension_scores={"clarity": 0},
            feedback={"suggestions": []},
            db_path=db_path,
        )


def test_evaluation_persists_structured_feedback_and_dashboard_score(db_path):
    user_id = create_user("Devon", db_path=db_path)
    session_id = create_session(
        user_id,
        role="Data Analyst",
        experience_level="Intermediate",
        difficulty="Medium",
        question_count=5,
        interview_type="Technical",
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
        answer_text="I checked missing values and ranges.",
        duration_seconds=35,
        db_path=db_path,
    )
    dimensions = {
        "relevance": 85,
        "technical_accuracy": 80,
        "depth": 70,
        "clarity": 90,
        "structure": 75,
        "completeness": 78,
    }
    feedback = {
        "what_went_well": ["You mentioned missing values."],
        "suggestions": ['Explain what you did after checking "ranges".'],
    }

    evaluation_id = save_evaluation(
        session_id,
        user_id,
        answer_id,
        overall_score=82,
        dimension_scores=dimensions,
        feedback=feedback,
        db_path=db_path,
    )
    assert save_evaluation(
        session_id,
        user_id,
        answer_id,
        overall_score=82,
        dimension_scores=dimensions,
        feedback=feedback,
        db_path=db_path,
    ) == evaluation_id

    snapshot = get_interview_snapshot(session_id, user_id, db_path=db_path)
    dashboard = get_dashboard_data(user_id, db_path=db_path)
    saved = snapshot["questions"][0]
    assert saved["evaluation_id"] == evaluation_id
    assert saved["overall_score"] == 82
    assert saved["dimension_scores"] == dimensions
    assert saved["feedback_json"] == feedback
    assert dashboard["average_score"] == 82
    assert dashboard["dimension_averages"]["clarity"] == 90


def test_demo_mode_is_isolated_and_cannot_be_enabled_mid_session(db_path):
    user_id = create_user("Robin", db_path=db_path)
    session_id = create_session(
        user_id,
        role="Product Designer",
        experience_level="Intermediate",
        difficulty="Medium",
        question_count=10,
        interview_type="Behavioral",
        db_path=db_path,
    )

    assert switch_session_to_demo(
        session_id, user_id, max_question_count=5, db_path=db_path
    ) == 5
    snapshot = get_interview_snapshot(session_id, user_id, db_path=db_path)
    assert snapshot["session"]["is_demo"] == 1
    assert snapshot["session"]["question_count"] == 5

    create_question(
        session_id,
        user_id,
        sequence_number=1,
        question_text="How do you test a design concept?",
        db_path=db_path,
    )
    with pytest.raises(ValueError, match="cannot switch to demo"):
        switch_session_to_demo(
            session_id, user_id, max_question_count=5, db_path=db_path
        )
    dashboard = get_dashboard_data(user_id, db_path=db_path)
    assert dashboard["questions_answered"] == 0
    assert dashboard["recent_sessions"] == []


def test_initialize_database_migrates_existing_answers_table(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL UNIQUE,
                answer_text TEXT NOT NULL,
                duration_seconds INTEGER,
                submitted_at TEXT NOT NULL DEFAULT ''
            )
            """
        )

    initialize_database(path)
    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(answers)")
        }
    assert "was_skipped" in columns


def test_foreign_keys_and_checks_are_enforced(db_path):
    user_id = create_user("Riley", db_path=db_path)
    with pytest.raises(sqlite3.IntegrityError):
        create_session(
            user_id,
            role="Developer",
            experience_level="Fresher",
            difficulty="Extreme",
            question_count=5,
            interview_type="Technical",
            db_path=db_path,
        )
    with pytest.raises(ValueError, match="session could not be found"):
        save_confidence(user_id, 999, stage="before", rating=4, db_path=db_path)


def test_confidence_and_sus_responses_persist(db_path):
    user_id = create_user("Taylor", db_path=db_path)
    session_id = create_session(
        user_id,
        role="Software Engineer",
        experience_level="Fresher",
        difficulty="Medium",
        question_count=5,
        interview_type="Mixed",
        db_path=db_path,
    )

    save_confidence(user_id, session_id, stage="before", rating=3, db_path=db_path)
    finish_session(session_id, user_id, status="completed", db_path=db_path)
    responses = [1, 5, 2, 4, 3, 5, 1, 4, 2, 5]
    save_sus_responses(
        session_id, responses, user_id=user_id, db_path=db_path
    )
    assert get_sus_responses(session_id, user_id, db_path=db_path) == responses
    with sqlite3.connect(db_path) as connection:
        confidence_count = connection.execute(
            "SELECT count(*) FROM confidence_records WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        sus_responses = connection.execute(
            "SELECT response FROM sus_responses WHERE session_id = ? ORDER BY item_number",
            (session_id,),
        ).fetchall()

    assert confidence_count == 1
    assert [row[0] for row in sus_responses] == [1, 5, 2, 4, 3, 5, 1, 4, 2, 5]
    assert get_sus_responses(
        session_id, user_id + 1, db_path=db_path
    ) is None


@pytest.mark.parametrize("responses", [[], [3] * 9, [3] * 9 + [6], [True] * 10])
def test_invalid_sus_responses_are_rejected(db_path, responses):
    with pytest.raises(ValueError):
        save_sus_responses(1, responses, user_id=1, db_path=db_path)


def test_confidence_history_requires_both_ratings_and_excludes_demo_sessions(db_path):
    user_id = create_user("Jordan", db_path=db_path)
    real_session = create_session_with_confidence(
        user_id,
        role="Software Engineer",
        experience_level="Fresher",
        difficulty="Medium",
        question_count=5,
        interview_type="Technical",
        confidence_rating=2,
        db_path=db_path,
    )
    finish_session(real_session, user_id, status="completed", db_path=db_path)
    after_id = save_confidence(
        user_id, real_session, stage="after", rating=4, db_path=db_path
    )
    assert save_confidence(
        user_id, real_session, stage="after", rating=4, db_path=db_path
    ) == after_id
    unpaired_session = create_session_with_confidence(
        user_id,
        role="Data Analyst",
        experience_level="Intermediate",
        difficulty="Easy",
        question_count=5,
        interview_type="Technical",
        confidence_rating=3,
        db_path=db_path,
    )
    finish_session(
        unpaired_session, user_id, status="completed", db_path=db_path
    )

    demo_session = create_session(
        user_id,
        role="Product Designer",
        experience_level="Fresher",
        difficulty="Easy",
        question_count=5,
        interview_type="Behavioral",
        is_demo=True,
        db_path=db_path,
    )
    save_confidence(
        user_id, demo_session, stage="before", rating=5, db_path=db_path
    )
    finish_session(demo_session, user_id, status="completed", db_path=db_path)
    save_confidence(
        user_id, demo_session, stage="after", rating=1, db_path=db_path
    )

    history = get_confidence_history(user_id, db_path=db_path)

    assert len(history) == 1
    assert history[0]["session_id"] == real_session
    assert history[0]["before_rating"] == 2
    assert history[0]["after_rating"] == 4
    assert history[0]["change"] == 2
    assert get_session_confidence(
        real_session, user_id, db_path=db_path
    ) == {"before": 2, "after": 4}


def test_post_confidence_requires_completed_session_and_valid_rating(db_path):
    user_id = create_user("Sam", db_path=db_path)
    session_id = create_session(
        user_id,
        role="Marketing Associate",
        experience_level="Intermediate",
        difficulty="Easy",
        question_count=5,
        interview_type="HR",
        db_path=db_path,
    )

    with pytest.raises(ValueError, match="completed session"):
        save_confidence(
            user_id, session_id, stage="after", rating=4, db_path=db_path
        )
    finish_session(session_id, user_id, status="completed", db_path=db_path)
    with pytest.raises(ValueError, match="1 to 5"):
        save_confidence(
            user_id, session_id, stage="after", rating=6, db_path=db_path
        )
