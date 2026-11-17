"""SQLite schema for INTERVIEWIQ."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    education TEXT NOT NULL DEFAULT '',
    experience_level TEXT NOT NULL DEFAULT 'Fresher'
        CHECK (experience_level IN ('Fresher', 'Intermediate', 'Experienced')),
    target_role TEXT NOT NULL DEFAULT '',
    target_company TEXT,
    technical_skills TEXT NOT NULL DEFAULT '[]',
    improvement_areas TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    experience_level TEXT NOT NULL
        CHECK (experience_level IN ('Fresher', 'Intermediate', 'Experienced')),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('Easy', 'Medium', 'Hard')),
    question_count INTEGER NOT NULL CHECK (question_count IN (5, 10, 15)),
    interview_type TEXT NOT NULL
        CHECK (interview_type IN ('Technical', 'HR', 'Behavioral', 'Mixed')),
    company_focus TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    question_text TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (session_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    duration_seconds INTEGER CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    was_skipped INTEGER NOT NULL DEFAULT 0 CHECK (was_skipped IN (0, 1)),
    submitted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id INTEGER NOT NULL UNIQUE REFERENCES answers(id) ON DELETE CASCADE,
    overall_score INTEGER NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    dimension_scores TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS session_reports (
    session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    final_analysis_json TEXT,
    learning_plan_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS confidence_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    stage TEXT NOT NULL CHECK (stage IN ('before', 'after')),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (session_id, stage)
);

CREATE TABLE IF NOT EXISTS sus_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    item_number INTEGER NOT NULL CHECK (item_number BETWEEN 1 AND 10),
    response INTEGER NOT NULL CHECK (response BETWEEN 1 AND 5),
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (session_id, item_number)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_started
    ON sessions (user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_questions_session_sequence
    ON questions (session_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_confidence_user_recorded
    ON confidence_records (user_id, recorded_at DESC);
"""
