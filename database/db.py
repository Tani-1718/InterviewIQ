"""Database connections and persistence helpers."""

from collections.abc import Mapping
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Iterator, Sequence

from config.settings import Settings
from database.schema import SCHEMA_SQL


@contextmanager
def get_connection(
    db_path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """Yield a configured connection and commit or roll back its transaction."""
    path = Path(db_path) if db_path is not None else Settings.from_env().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: str | Path | None = None) -> None:
    """Create the database tables and indexes if they do not already exist."""
    with get_connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        answer_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(answers)")
        }
        if "was_skipped" not in answer_columns:
            connection.execute(
                """
                ALTER TABLE answers ADD COLUMN was_skipped INTEGER NOT NULL DEFAULT 0
                    CHECK (was_skipped IN (0, 1))
                """
            )


def create_user(
    name: str,
    *,
    education: str = "",
    experience_level: str = "Fresher",
    target_role: str = "",
    target_company: str | None = None,
    technical_skills: Sequence[str] = (),
    improvement_areas: Sequence[str] = (),
    db_path: str | Path | None = None,
) -> int:
    """Create an onboarding profile and return its database ID."""
    if not name.strip():
        raise ValueError("Name cannot be empty.")
    if experience_level not in {"Fresher", "Intermediate", "Experienced"}:
        raise ValueError("Unsupported experience level.")
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (
                name, education, experience_level, target_role, target_company,
                technical_skills, improvement_areas
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                education.strip(),
                experience_level,
                target_role.strip(),
                target_company.strip() if target_company and target_company.strip() else None,
                json.dumps(list(technical_skills)),
                json.dumps(list(improvement_areas)),
            ),
        )
        return int(cursor.lastrowid)


def get_user(user_id: int, *, db_path: str | Path | None = None) -> dict | None:
    """Load a user profile, decoding the list-valued profile fields."""
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    user = dict(row)
    user["technical_skills"] = json.loads(user["technical_skills"])
    user["improvement_areas"] = json.loads(user["improvement_areas"])
    return user


def get_latest_user(*, db_path: str | Path | None = None) -> dict | None:
    """Load the most recently created profile for the single-user workspace."""
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT id FROM users ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return get_user(int(row["id"]), db_path=db_path) if row else None


def get_dashboard_data(
    user_id: int, *, db_path: str | Path | None = None
) -> dict:
    """Return real, non-demo dashboard metrics and history for one user."""
    with get_connection(db_path) as connection:
        totals = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM sessions
                 WHERE user_id = ? AND is_demo = 0 AND status = 'completed')
                    AS interviews_completed,
                (SELECT COUNT(*) FROM answers a
                 JOIN questions q ON q.id = a.question_id
                 JOIN sessions s ON s.id = q.session_id
                 WHERE s.user_id = ? AND s.is_demo = 0 AND a.was_skipped = 0)
                    AS questions_answered,
                (SELECT AVG(e.overall_score) FROM evaluations e
                 JOIN answers a ON a.id = e.answer_id
                 JOIN questions q ON q.id = a.question_id
                 JOIN sessions s ON s.id = q.session_id
                 WHERE s.user_id = ? AND s.is_demo = 0)
                    AS average_score
            """,
            (user_id, user_id, user_id),
        ).fetchone()
        recent_rows = connection.execute(
            """
            SELECT s.id, s.role, s.status, s.started_at, s.completed_at,
                   COUNT(DISTINCT CASE WHEN a.was_skipped = 0 THEN a.id END)
                       AS questions_answered,
                   AVG(e.overall_score) AS average_score
            FROM sessions s
            LEFT JOIN questions q ON q.session_id = s.id
            LEFT JOIN answers a ON a.question_id = q.id
            LEFT JOIN evaluations e ON e.answer_id = a.id
            WHERE s.user_id = ? AND s.is_demo = 0
            GROUP BY s.id
            ORDER BY s.started_at DESC, s.id DESC
            LIMIT 5
            """,
            (user_id,),
        ).fetchall()
        evaluation_rows = connection.execute(
            """
            SELECT e.dimension_scores
            FROM evaluations e
            JOIN answers a ON a.id = e.answer_id
            JOIN questions q ON q.id = a.question_id
            JOIN sessions s ON s.id = q.session_id
            WHERE s.user_id = ? AND s.is_demo = 0
            """,
            (user_id,),
        ).fetchall()
        trend_rows = connection.execute(
            """
            SELECT s.id, s.role, COALESCE(s.completed_at, s.started_at) AS date,
                   AVG(e.overall_score) AS average_score
            FROM sessions s
            JOIN questions q ON q.session_id = s.id
            JOIN answers a ON a.question_id = q.id
            JOIN evaluations e ON e.answer_id = a.id
            WHERE s.user_id = ? AND s.is_demo = 0
            GROUP BY s.id
            ORDER BY date ASC, s.id ASC
            """,
            (user_id,),
        ).fetchall()

    dimension_totals: dict[str, list[float]] = {}
    for row in evaluation_rows:
        scores = json.loads(row["dimension_scores"])
        if not isinstance(scores, dict):
            raise ValueError("Stored evaluation dimension scores must be a JSON object.")
        for name, value in scores.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                dimension_totals.setdefault(name, []).append(float(value))

    dimension_averages = {
        name: sum(values) / len(values)
        for name, values in dimension_totals.items()
        if values
    }
    ranked_dimensions = sorted(
        dimension_averages.items(), key=lambda item: (-item[1], item[0])
    )
    return {
        "interviews_completed": int(totals["interviews_completed"]),
        "questions_answered": int(totals["questions_answered"]),
        "average_score": (
            float(totals["average_score"])
            if totals["average_score"] is not None
            else None
        ),
        "strongest_skill": ranked_dimensions[0][0] if ranked_dimensions else None,
        "weak_areas": [name for name, _ in ranked_dimensions[-2:]][::-1],
        "dimension_averages": dimension_averages,
        "recent_sessions": [dict(row) for row in recent_rows],
        "progress": [dict(row) for row in trend_rows],
    }


def update_user(
    user_id: int,
    *,
    name: str,
    education: str = "",
    experience_level: str = "Fresher",
    target_role: str = "",
    target_company: str | None = None,
    technical_skills: Sequence[str] = (),
    improvement_areas: Sequence[str] = (),
    db_path: str | Path | None = None,
) -> bool:
    """Replace editable profile fields; return False if the user does not exist."""
    if not name.strip():
        raise ValueError("Name cannot be empty.")
    if experience_level not in {"Fresher", "Intermediate", "Experienced"}:
        raise ValueError("Unsupported experience level.")
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET name = ?, education = ?, experience_level = ?, target_role = ?,
                target_company = ?, technical_skills = ?, improvement_areas = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (
                name.strip(),
                education.strip(),
                experience_level,
                target_role.strip(),
                target_company.strip() if target_company and target_company.strip() else None,
                json.dumps(list(technical_skills)),
                json.dumps(list(improvement_areas)),
                user_id,
            ),
        )
        return cursor.rowcount == 1


def create_session(
    user_id: int,
    *,
    role: str,
    experience_level: str,
    difficulty: str,
    question_count: int,
    interview_type: str,
    company_focus: str | None = None,
    is_demo: bool = False,
    db_path: str | Path | None = None,
) -> int:
    """Create an interview session and return its database ID."""
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO sessions (
                user_id, role, experience_level, difficulty, question_count,
                interview_type, company_focus, is_demo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                role,
                experience_level,
                difficulty,
                question_count,
                interview_type,
                company_focus.strip() if company_focus and company_focus.strip() else None,
                int(is_demo),
            ),
        )
        return int(cursor.lastrowid)


def create_session_with_confidence(
    user_id: int,
    *,
    role: str,
    experience_level: str,
    difficulty: str,
    question_count: int,
    interview_type: str,
    confidence_rating: int,
    company_focus: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Create a session and its pre-interview confidence record atomically."""
    if (
        not isinstance(confidence_rating, int)
        or isinstance(confidence_rating, bool)
        or confidence_rating not in range(1, 6)
    ):
        raise ValueError("Confidence rating must be an integer from 1 to 5.")

    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO sessions (
                user_id, role, experience_level, difficulty, question_count,
                interview_type, company_focus
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                role,
                experience_level,
                difficulty,
                question_count,
                interview_type,
                company_focus.strip() if company_focus and company_focus.strip() else None,
            ),
        )
        session_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO confidence_records (user_id, session_id, stage, rating)
            VALUES (?, ?, 'before', ?)
            """,
            (user_id, session_id, confidence_rating),
        )
        return session_id


def get_session(
    session_id: int,
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> dict | None:
    """Load a session only when it belongs to the requested user."""
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def get_interview_snapshot(
    session_id: int,
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> dict | None:
    """Load a session and its question/answer progress for its owner."""
    with get_connection(db_path) as connection:
        session_row = connection.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if session_row is None:
            return None
        question_rows = connection.execute(
            """
            SELECT q.id, q.sequence_number, q.question_text, q.generated_at,
                   a.id AS answer_id, a.answer_text, a.duration_seconds,
                   a.was_skipped, a.submitted_at, e.id AS evaluation_id,
                   e.overall_score, e.dimension_scores, e.feedback_json
            FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id
            LEFT JOIN evaluations e ON e.answer_id = a.id
            WHERE q.session_id = ?
            ORDER BY q.sequence_number
            """,
            (session_id,),
        ).fetchall()
    questions = []
    for row in question_rows:
        question = dict(row)
        if question["dimension_scores"] is not None:
            question["dimension_scores"] = json.loads(question["dimension_scores"])
        if question["feedback_json"] is not None:
            question["feedback_json"] = json.loads(question["feedback_json"])
        questions.append(question)
    return {
        "session": dict(session_row),
        "questions": questions,
    }


def create_question(
    session_id: int,
    user_id: int,
    *,
    sequence_number: int,
    question_text: str,
    db_path: str | Path | None = None,
) -> int:
    """Persist one question in order, returning its database ID."""
    if not question_text.strip():
        raise ValueError("A generated interview question cannot be empty.")
    if (
        not isinstance(sequence_number, int)
        or isinstance(sequence_number, bool)
        or sequence_number < 1
    ):
        raise ValueError("Question sequence number must be a positive integer.")

    with get_connection(db_path) as connection:
        session = connection.execute(
            "SELECT status, question_count FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if session is None:
            raise ValueError("The interview session could not be found.")
        if session["status"] != "in_progress":
            raise ValueError("This interview session is no longer active.")
        if sequence_number > session["question_count"]:
            raise ValueError("The configured number of interview questions is complete.")

        existing = connection.execute(
            """
            SELECT id, question_text FROM questions
            WHERE session_id = ? AND sequence_number = ?
            """,
            (session_id, sequence_number),
        ).fetchone()
        if existing is not None:
            if existing["question_text"] == question_text.strip():
                return int(existing["id"])
            raise ValueError("A different question already exists at this position.")

        previous_count = connection.execute(
            "SELECT COUNT(*) FROM questions WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        if sequence_number != previous_count + 1:
            raise ValueError("Interview questions must be saved in sequence.")
        pending = connection.execute(
            """
            SELECT 1 FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id
            WHERE q.session_id = ? AND a.id IS NULL
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if pending is not None:
            raise ValueError("Submit or skip the current question before continuing.")

        cursor = connection.execute(
            """
            INSERT INTO questions (session_id, sequence_number, question_text)
            VALUES (?, ?, ?)
            """,
            (session_id, sequence_number, question_text.strip()),
        )
        return int(cursor.lastrowid)


def save_answer(
    session_id: int,
    user_id: int,
    question_id: int,
    *,
    answer_text: str,
    duration_seconds: int,
    was_skipped: bool = False,
    db_path: str | Path | None = None,
) -> int:
    """Save an answer or skip marker for an active session question."""
    if not isinstance(answer_text, str):
        raise ValueError("Interview answers must be text.")
    if not isinstance(was_skipped, bool):
        raise ValueError("Skip status must be a boolean.")
    if was_skipped and answer_text.strip():
        raise ValueError("Skipped questions cannot also contain an answer.")
    if not was_skipped and not answer_text.strip():
        raise ValueError("Write an answer or use Skip question.")
    if (
        not isinstance(duration_seconds, int)
        or isinstance(duration_seconds, bool)
        or duration_seconds < 0
    ):
        raise ValueError("Answer duration must be a non-negative integer.")

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT s.status
            FROM questions q
            JOIN sessions s ON s.id = q.session_id
            WHERE q.id = ? AND q.session_id = ? AND s.user_id = ?
            """,
            (question_id, session_id, user_id),
        ).fetchone()
        if row is None:
            raise ValueError("This question does not belong to the active interview.")
        if row["status"] != "in_progress":
            raise ValueError("This interview session is no longer active.")
        cursor = connection.execute(
            """
            INSERT INTO answers (
                question_id, answer_text, duration_seconds, was_skipped
            ) VALUES (?, ?, ?, ?)
            """,
            (
                question_id,
                answer_text.strip(),
                duration_seconds,
                int(was_skipped),
            ),
        )
        return int(cursor.lastrowid)


def save_evaluation(
    session_id: int,
    user_id: int,
    answer_id: int,
    *,
    overall_score: int,
    dimension_scores: dict[str, int],
    feedback: Mapping[str, object],
    db_path: str | Path | None = None,
) -> int:
    """Persist validated evaluation output for an answer owned by the active session."""
    if (
        not isinstance(overall_score, int)
        or isinstance(overall_score, bool)
        or not 0 <= overall_score <= 100
    ):
        raise ValueError("Overall score must be an integer from 0 to 100.")
    if not isinstance(dimension_scores, dict) or not dimension_scores:
        raise ValueError("Dimension scores must be a non-empty object.")
    if any(
        not isinstance(name, str)
        or not isinstance(score, int)
        or isinstance(score, bool)
        or not 0 <= score <= 100
        for name, score in dimension_scores.items()
    ):
        raise ValueError("Each dimension score must be an integer from 0 to 100.")
    if not isinstance(feedback, Mapping) or not feedback:
        raise ValueError("Evaluation feedback must be a non-empty object.")

    dimension_json = json.dumps(dimension_scores)
    feedback_json = json.dumps(dict(feedback), ensure_ascii=False)
    with get_connection(db_path) as connection:
        answer = connection.execute(
            """
            SELECT s.status, a.was_skipped
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            JOIN sessions s ON s.id = q.session_id
            WHERE a.id = ? AND q.session_id = ? AND s.user_id = ?
            """,
            (answer_id, session_id, user_id),
        ).fetchone()
        if answer is None:
            raise ValueError("The answer could not be found in this interview.")
        if answer["was_skipped"]:
            raise ValueError("Skipped questions cannot be evaluated.")
        existing = connection.execute(
            "SELECT id FROM evaluations WHERE answer_id = ?", (answer_id,)
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        if answer["status"] != "in_progress":
            raise ValueError("This interview session is no longer active.")
        cursor = connection.execute(
            """
            INSERT INTO evaluations (
                answer_id, overall_score, dimension_scores, feedback_json
            ) VALUES (?, ?, ?, ?)
            """,
            (answer_id, overall_score, dimension_json, feedback_json),
        )
        return int(cursor.lastrowid)


def get_session_report(
    session_id: int,
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> dict | None:
    """Load cached report sections only for a completed real session owner."""
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT r.final_analysis_json, r.learning_plan_json, r.updated_at
            FROM session_reports r
            JOIN sessions s ON s.id = r.session_id
            WHERE r.session_id = ? AND s.user_id = ? AND s.is_demo = 0
                AND s.status = 'completed'
            """,
            (session_id, user_id),
        ).fetchone()
    if row is None:
        return None
    return {
        "final_analysis": (
            json.loads(row["final_analysis_json"])
            if row["final_analysis_json"] is not None
            else None
        ),
        "learning_plan": (
            json.loads(row["learning_plan_json"])
            if row["learning_plan_json"] is not None
            else None
        ),
        "updated_at": row["updated_at"],
    }


def save_session_report(
    session_id: int,
    user_id: int,
    *,
    final_analysis: Mapping[str, object] | None = None,
    learning_plan: Mapping[str, object] | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Cache completed report sections without overwriting existing results."""
    if final_analysis is None and learning_plan is None:
        raise ValueError("Provide at least one report section to save.")
    if final_analysis is not None and (
        not isinstance(final_analysis, Mapping) or not final_analysis
    ):
        raise ValueError("Final analysis must be a non-empty object.")
    if learning_plan is not None and (
        not isinstance(learning_plan, Mapping) or not learning_plan
    ):
        raise ValueError("Learning plan must be a non-empty object.")

    analysis_json = (
        json.dumps(dict(final_analysis), ensure_ascii=False)
        if final_analysis is not None
        else None
    )
    learning_json = (
        json.dumps(dict(learning_plan), ensure_ascii=False)
        if learning_plan is not None
        else None
    )
    with get_connection(db_path) as connection:
        session = connection.execute(
            """
            SELECT status, is_demo FROM sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
        if session is None:
            raise ValueError("The interview session could not be found.")
        if session["status"] != "completed" or session["is_demo"]:
            raise ValueError("Reports can only be saved for completed real sessions.")
        evaluation_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM evaluations e
            JOIN answers a ON a.id = e.answer_id
            JOIN questions q ON q.id = a.question_id
            WHERE q.session_id = ?
            """,
            (session_id,),
        ).fetchone()[0]
        if not evaluation_count:
            raise ValueError("A report requires at least one evaluated answer.")

        connection.execute(
            "INSERT INTO session_reports (session_id) VALUES (?) ON CONFLICT DO NOTHING",
            (session_id,),
        )
        connection.execute(
            """
            UPDATE session_reports
            SET final_analysis_json = COALESCE(final_analysis_json, ?),
                learning_plan_json = COALESCE(learning_plan_json, ?),
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE session_id = ?
            """,
            (analysis_json, learning_json, session_id),
        )
        saved = connection.execute(
            """
            SELECT final_analysis_json, learning_plan_json, updated_at
            FROM session_reports WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    return {
        "final_analysis": (
            json.loads(saved["final_analysis_json"])
            if saved["final_analysis_json"] is not None
            else None
        ),
        "learning_plan": (
            json.loads(saved["learning_plan_json"])
            if saved["learning_plan_json"] is not None
            else None
        ),
        "updated_at": saved["updated_at"],
    }


def switch_session_to_demo(
    session_id: int,
    user_id: int,
    *,
    max_question_count: int,
    db_path: str | Path | None = None,
) -> int:
    """Mark a not-yet-started session as demo-only and return its question limit."""
    if (
        not isinstance(max_question_count, int)
        or isinstance(max_question_count, bool)
        or max_question_count not in {5, 10, 15}
    ):
        raise ValueError("Demo question limit must be 5, 10, or 15.")
    with get_connection(db_path) as connection:
        session = connection.execute(
            "SELECT status, question_count FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if session is None:
            raise ValueError("The interview session could not be found.")
        if session["status"] != "in_progress":
            raise ValueError("Only an active interview can switch to demo mode.")
        existing_question = connection.execute(
            "SELECT 1 FROM questions WHERE session_id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
        if existing_question is not None:
            raise ValueError(
                "This interview already has questions; it cannot switch to demo mode."
            )
        question_count = min(session["question_count"], max_question_count)
        connection.execute(
            """
            UPDATE sessions
            SET is_demo = 1, question_count = ?
            WHERE id = ? AND user_id = ?
            """,
            (question_count, session_id, user_id),
        )
    return question_count


def finish_session(
    session_id: int,
    user_id: int,
    *,
    status: str = "completed",
    db_path: str | Path | None = None,
) -> bool:
    """Finish an active session as completed or abandoned."""
    if status not in {"completed", "abandoned"}:
        raise ValueError("A session can only be completed or abandoned.")
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE sessions
            SET status = ?, completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ? AND user_id = ? AND status = 'in_progress'
            """,
            (status, session_id, user_id),
        )
        return cursor.rowcount == 1


def list_sessions(
    user_id: int,
    *,
    include_demo: bool = False,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Return a user's sessions, excluding demo records unless explicitly requested."""
    demo_filter = "" if include_demo else "AND is_demo = 0"
    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM sessions
            WHERE user_id = ? {demo_filter}
            ORDER BY started_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_session_history(
    user_id: int,
    *,
    include_demo: bool = True,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Return one user's sessions with answer, score, and survey summaries."""
    demo_filter = "" if include_demo else "AND s.is_demo = 0"
    with get_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT s.*,
                (SELECT COUNT(*)
                 FROM questions q
                 JOIN answers a ON a.question_id = q.id
                 WHERE q.session_id = s.id AND a.was_skipped = 0)
                    AS questions_answered,
                (SELECT COUNT(*)
                 FROM questions q
                 JOIN answers a ON a.question_id = q.id
                 WHERE q.session_id = s.id AND a.was_skipped = 1)
                    AS questions_skipped,
                (SELECT AVG(e.overall_score)
                 FROM questions q
                 JOIN answers a ON a.question_id = q.id
                 JOIN evaluations e ON e.answer_id = a.id
                 WHERE q.session_id = s.id AND a.was_skipped = 0)
                    AS average_score,
                (SELECT c.rating FROM confidence_records c
                 WHERE c.session_id = s.id AND c.stage = 'before')
                    AS confidence_before,
                (SELECT c.rating FROM confidence_records c
                 WHERE c.session_id = s.id AND c.stage = 'after')
                    AS confidence_after,
                (SELECT COUNT(*) FROM sus_responses r
                 WHERE r.session_id = s.id)
                    AS sus_response_count
            FROM sessions s
            WHERE s.user_id = ? {demo_filter}
            ORDER BY s.started_at DESC, s.id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_session(
    session_id: int,
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> bool:
    """Delete an owned session and its dependent records; return whether it existed."""
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        return cursor.rowcount == 1


def save_confidence(
    user_id: int,
    session_id: int,
    *,
    stage: str,
    rating: int,
    db_path: str | Path | None = None,
) -> int:
    """Persist one pre- or post-interview self-reported confidence rating."""
    if not isinstance(stage, str) or stage not in {"before", "after"}:
        raise ValueError("Confidence stage must be 'before' or 'after'.")
    if (
        not isinstance(rating, int)
        or isinstance(rating, bool)
        or rating not in range(1, 6)
    ):
        raise ValueError("Confidence rating must be an integer from 1 to 5.")
    with get_connection(db_path) as connection:
        session = connection.execute(
            "SELECT status FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if session is None:
            raise ValueError("The interview session could not be found.")
        if stage == "after" and session["status"] != "completed":
            raise ValueError("Post-interview confidence requires a completed session.")
        existing = connection.execute(
            """
            SELECT id, rating FROM confidence_records
            WHERE session_id = ? AND stage = ?
            """,
            (session_id, stage),
        ).fetchone()
        if existing is not None:
            if existing["rating"] != rating:
                raise ValueError("This confidence rating has already been recorded.")
            return int(existing["id"])
        cursor = connection.execute(
            """
            INSERT INTO confidence_records (user_id, session_id, stage, rating)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, session_id, stage, rating),
        )
        return int(cursor.lastrowid)


def get_session_confidence(
    session_id: int,
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    """Return saved self-reported ratings for a session owned by the user."""
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT c.stage, c.rating
            FROM confidence_records c
            JOIN sessions s ON s.id = c.session_id
            WHERE c.session_id = ? AND s.user_id = ?
            """,
            (session_id, user_id),
        ).fetchall()
    return {row["stage"]: int(row["rating"]) for row in rows}


def get_confidence_history(
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Return completed real-session confidence pairs, excluding Demo Mode."""
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT s.id AS session_id, s.role, s.started_at, s.completed_at,
                   MAX(CASE WHEN c.stage = 'before' THEN c.rating END) AS before_rating,
                   MAX(CASE WHEN c.stage = 'after' THEN c.rating END) AS after_rating
            FROM sessions s
            JOIN confidence_records c ON c.session_id = s.id
            WHERE s.user_id = ? AND s.status = 'completed' AND s.is_demo = 0
            GROUP BY s.id
            HAVING before_rating IS NOT NULL AND after_rating IS NOT NULL
            ORDER BY s.completed_at, s.id
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            **dict(row),
            "change": int(row["after_rating"]) - int(row["before_rating"]),
        }
        for row in rows
    ]


def get_sus_responses(
    session_id: int,
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> list[int] | None:
    """Load a completed session's ten saved usability responses for its owner."""
    with get_connection(db_path) as connection:
        session = connection.execute(
            """
            SELECT status FROM sessions WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
        if session is None or session["status"] != "completed":
            return None
        rows = connection.execute(
            """
            SELECT r.item_number, r.response
            FROM sus_responses r
            JOIN sessions s ON s.id = r.session_id
            WHERE r.session_id = ? AND s.user_id = ?
            ORDER BY r.item_number
            """,
            (session_id, user_id),
        ).fetchall()
    if not rows:
        return None
    if len(rows) != 10 or [row["item_number"] for row in rows] != list(range(1, 11)):
        raise ValueError("The saved SUS response set is incomplete.")
    return [int(row["response"]) for row in rows]


def get_research_export_data(
    user_id: int,
    *,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Return completed real-session confidence and SUS records for export."""
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            WITH confidence AS (
                SELECT session_id,
                    MAX(CASE WHEN stage = 'before' THEN rating END) AS before_rating,
                    MAX(CASE WHEN stage = 'after' THEN rating END) AS after_rating
                FROM confidence_records
                GROUP BY session_id
            )
            SELECT s.id AS session_id, c.before_rating, c.after_rating,
                   r.item_number, r.response
            FROM sessions s
            LEFT JOIN confidence c ON c.session_id = s.id
            LEFT JOIN sus_responses r ON r.session_id = s.id
            WHERE s.user_id = ? AND s.status = 'completed' AND s.is_demo = 0
            ORDER BY s.completed_at, s.id, r.item_number
            """,
            (user_id,),
        ).fetchall()

    exports: dict[int, dict] = {}
    for row in rows:
        session_id = int(row["session_id"])
        record = exports.setdefault(
            session_id,
            {
                "session_id": session_id,
                "confidence_before": row["before_rating"],
                "confidence_after": row["after_rating"],
                "sus_responses": [],
            },
        )
        if row["item_number"] is not None:
            record["sus_responses"].append(int(row["response"]))

    result = []
    for record in exports.values():
        responses = record["sus_responses"]
        if responses and len(responses) != 10:
            raise ValueError(
                f"Session {record['session_id']} has an incomplete SUS response set."
            )
        if (
            record["confidence_before"] is not None
            or record["confidence_after"] is not None
            or responses
        ):
            result.append(record)
    return result


def save_sus_responses(
    session_id: int,
    responses: Sequence[int],
    *,
    user_id: int,
    db_path: str | Path | None = None,
) -> None:
    """Persist the ten SUS item responses atomically."""
    if len(responses) != 10 or any(
        not isinstance(value, int) or isinstance(value, bool) or value not in range(1, 6)
        for value in responses
    ):
        raise ValueError("SUS responses must contain exactly 10 integers from 1 to 5.")
    with get_connection(db_path) as connection:
        session = connection.execute(
            """
            SELECT status FROM sessions WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
        if session is None:
            raise ValueError("The interview session could not be found.")
        if session["status"] != "completed":
            raise ValueError("SUS responses can only be saved after a completed session.")
        existing = connection.execute(
            """
            SELECT item_number, response FROM sus_responses
            WHERE session_id = ? ORDER BY item_number
            """,
            (session_id,),
        ).fetchall()
        if existing:
            if (
                len(existing) == 10
                and [row["response"] for row in existing] == list(responses)
            ):
                return
            raise ValueError("SUS responses have already been recorded.")
        connection.executemany(
            """
            INSERT INTO sus_responses (session_id, item_number, response)
            VALUES (?, ?, ?)
            """,
            [
                (session_id, item_number, response)
                for item_number, response in enumerate(responses, start=1)
            ],
        )
