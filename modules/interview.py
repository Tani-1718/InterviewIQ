"""Persistent interview simulator with live and explicitly labeled demo modes."""

from datetime import datetime
import html
import re
import sqlite3
import time
from pathlib import Path

import streamlit as st

from ai_engine.answer_evaluator import SHORT_ANSWER_WORD_LIMIT
from ai_engine.chat_history import build_chat_history
from ai_engine.interview_manager import InterviewManager
from ai_engine.llm import AIResponseError, AIService, AIServiceError
from config.demo_questions import DEMO_QUESTION_LIMIT, get_demo_question
from config.roles import ROLES
from config.settings import Settings
from database.db import (
    create_question,
    finish_session,
    get_interview_snapshot,
    save_answer,
    save_evaluation,
    switch_session_to_demo,
)
from modules.confidence import render_post_interview_confidence
from modules.sus import render_sus_questionnaire


def _render_header() -> None:
    st.markdown(
        """
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self">Dashboard</a><a href="?page=onboarding" target="_self">Profile</a><a href="?page=roles" target="_self" class="nav-current">Interview</a><a href="?page=history" target="_self">History</a><a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=dashboard" target="_self">Dashboard <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _question_key(question: str) -> str:
    return re.sub(r"\W+", " ", question.casefold()).strip()


def _generate_question(
    snapshot: dict,
    *,
    profile: dict,
    settings: Settings,
    db_path: str | Path,
) -> int:
    session = snapshot["session"]
    questions = snapshot["questions"]
    sequence_number = len(questions) + 1

    if session["is_demo"]:
        role_config = next(
            (role for role in ROLES if role["title"] == session["role"]), None
        )
        if role_config is None:
            raise ValueError("No demo question set is configured for this role.")
        question_text = get_demo_question(role_config["id"], sequence_number)
    else:
        role_config = next(
            (role for role in ROLES if role["title"] == session["role"]), None
        )
        if role_config is None:
            raise ValueError("No role configuration was found for this interview.")

        answered_questions = [item for item in questions if item["answer_id"] is not None]
        turns = [
            (item["question_text"], item["answer_text"])
            for item in answered_questions
        ]
        latest_answer = answered_questions[-1] if answered_questions else None
        chat_history = build_chat_history(turns[:-1] if turns else [])
        previous_questions = "\n".join(
            f"{item['sequence_number']}. {item['question_text']}" for item in questions
        )
        skill_context = list(role_config["skills"])
        skill_context.extend(profile.get("technical_skills", []))
        skill_context.extend(profile.get("improvement_areas", []))

        manager = InterviewManager(AIService(settings))
        question_text = manager.next_question(
            role=session["role"],
            skills=", ".join(dict.fromkeys(skill_context)),
            experience_level=session["experience_level"],
            difficulty=session["difficulty"],
            interview_type=session["interview_type"],
            company_focus=session["company_focus"] or "",
            question_number=sequence_number,
            question_count=session["question_count"],
            previous_questions=previous_questions,
            chat_history=chat_history,
            previous_answer=latest_answer["answer_text"] if latest_answer else "",
            last_question=latest_answer["question_text"] if latest_answer else "",
        )
        new_key = _question_key(question_text)
        if any(_question_key(item["question_text"]) == new_key for item in questions):
            raise AIResponseError(
                "The model repeated an earlier question. Retry to generate a fresh one."
            )

    return create_question(
        session["id"],
        profile["id"],
        sequence_number=sequence_number,
        question_text=question_text,
        db_path=db_path,
    )


def _elapsed_seconds(generated_at: str) -> int:
    started = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).timestamp()
    return max(0, int(time.time() - started))


def _render_timer(generated_at: str) -> None:
    started_at = int(
        datetime.fromisoformat(generated_at.replace("Z", "+00:00")).timestamp()
    )
    st.html(
        f"""
        <div class="interview-timer">
          <span class="timer-dot"></span>
          <span>TIME ON QUESTION</span>
          <strong id="interview-timer-value">00:00</strong>
        </div>
        <style>
          html, body {{ margin: 0; background: transparent; }}
          .interview-timer {{
            display: flex; align-items: center; gap: 8px; height: 38px;
            color: #858da0; font: 700 9px 'DM Sans', sans-serif; letter-spacing: .8px;
          }}
          .timer-dot {{
            width: 6px; height: 6px; border-radius: 50%; background: #66d9e8;
            box-shadow: 0 0 9px rgba(102,217,232,.55);
          }}
          .interview-timer strong {{
            margin-left: 5px; color: #e6e8f1; font: 600 12px 'Manrope', sans-serif;
            letter-spacing: 0;
          }}
        </style>
        <script>
          (function () {{
            const startedAt = {started_at};
            const timer = document.getElementById("interview-timer-value");
            function updateTimer() {{
              const elapsed = Math.max(0, Math.floor(Date.now() / 1000 - startedAt));
              const minutes = String(Math.floor(elapsed / 60)).padStart(2, "0");
              const seconds = String(elapsed % 60).padStart(2, "0");
              timer.textContent = minutes + ":" + seconds;
            }}
            if (window.__interviewIqTimer) {{
              window.clearInterval(window.__interviewIqTimer);
            }}
            updateTimer();
            window.__interviewIqTimer = window.setInterval(updateTimer, 1000);
          }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _show_demo_option(
    session_id: int,
    user_id: int,
    db_path: str | Path,
) -> None:
    st.info(
        "Demo Mode uses clearly labeled sample questions (not AI-generated output). "
        "Demo sessions and answers are excluded from real dashboard statistics."
    )
    if st.button(
        "Start clearly labeled Demo Mode",
        type="primary",
        use_container_width=True,
        key=f"start-demo-{session_id}",
    ):
        try:
            switch_session_to_demo(
                session_id,
                user_id,
                max_question_count=DEMO_QUESTION_LIMIT,
                db_path=db_path,
            )
        except (ValueError, sqlite3.Error) as exc:
            st.error(f"Couldn’t start Demo Mode: {exc}")
        else:
            st.rerun()


def _end_interview(
    session_id: int,
    user_id: int,
    questions: list[dict],
    db_path: str | Path,
) -> None:
    status = (
        "completed"
        if any(item["answer_id"] is not None for item in questions)
        else "abandoned"
    )
    finish_session(session_id, user_id, status=status, db_path=db_path)


def _show_generation_error(
    session_id: int,
    user_id: int,
    questions: list[dict],
    db_path: str | Path,
    error: str,
) -> None:
    st.error(error)
    error_key = f"interview-question-error-{session_id}"
    if st.button("Retry question generation", type="primary", key=f"retry-{session_id}"):
        st.session_state.pop(error_key, None)
        st.rerun()
    if not questions:
        _show_demo_option(session_id, user_id, db_path)
    else:
        st.caption(
            "This session already contains live interview activity, so it cannot "
            "switch to Demo Mode without mixing real and sample data."
        )
    if st.button("End interview", key=f"end-after-error-{session_id}"):
        _end_interview(session_id, user_id, questions, db_path)
        st.rerun()


def _render_ended(
    session: dict,
    questions: list[dict],
    user_id: int,
    db_path: str | Path,
) -> None:
    answered = sum(
        item["answer_id"] is not None and not item["was_skipped"] for item in questions
    )
    skipped = sum(
        item["answer_id"] is not None and item["was_skipped"] for item in questions
    )
    mode = "DEMO SESSION" if session["is_demo"] else "SESSION SAVED"
    ended_title = (
        "Practice complete."
        if session["status"] == "completed"
        else "Session saved."
    )
    ended_message = (
        "Your progress is saved. Review your answer feedback and session report."
        if session["status"] == "completed"
        else "This session ended before you submitted an answer. Your saved progress has been retained."
    )
    st.markdown(
        f"""
        <section class="interview-ended-card">
          <span class="ended-spark">✦</span>
          <div class="eyebrow">{mode}</div>
          <h1>{ended_title}</h1>
          <p>{ended_message}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    left.metric("Answers submitted", answered)
    right.metric("Questions skipped", skipped)
    if session["is_demo"]:
        st.caption("Demo activity is excluded from real dashboard statistics.")
    if session["status"] == "completed":
        render_post_interview_confidence(
            session=session,
            user_id=user_id,
            db_path=db_path,
        )
        render_sus_questionnaire(
            session=session,
            user_id=user_id,
            db_path=db_path,
        )
        st.markdown(
            f'<a class="button-primary" href="?page=results&session_id={int(session["id"])}" target="_self">View session report <span>→</span></a>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<a class="button-primary" href="?page=dashboard" target="_self">Back to dashboard <span>→</span></a>',
            unsafe_allow_html=True,
        )


def _render_evaluation(evaluation: dict) -> None:
    st.markdown(
        '<div class="evaluation-section-heading"><div class="eyebrow">ANSWER REVIEW</div><h2>Feedback grounded in your response</h2></div>',
        unsafe_allow_html=True,
    )
    st.metric("Overall score", f"{evaluation['overall_score']} / 100")
    dimension_labels = {
        "relevance": "Relevance",
        "technical_accuracy": "Technical accuracy",
        "depth": "Depth",
        "clarity": "Clarity",
        "structure": "Structure",
        "completeness": "Completeness",
    }
    columns = st.columns(3)
    for index, (dimension, label) in enumerate(dimension_labels.items()):
        columns[index % len(columns)].metric(
            label, f"{evaluation['scores'][dimension]} / 100"
        )

    feedback_sections = (
        ("What went well", "what_went_well"),
        ("What was missing", "what_was_missing"),
        ("Mistakes or inaccuracies", "mistakes_or_inaccuracies"),
        ("Specific suggestions", "suggestions"),
        ("Concepts to revise", "concepts_to_revise"),
    )
    for title, key in feedback_sections:
        items = evaluation[key]
        if not items and key in {"mistakes_or_inaccuracies", "concepts_to_revise"}:
            continue
        st.markdown(f"#### {title}")
        for item in items:
            st.markdown(f"- {item}")

    st.markdown("#### A stronger example answer")
    st.caption("This is an example, not a claim about what you said.")
    st.write(evaluation["stronger_example_answer"])


def _evaluate_saved_answer(
    snapshot: dict,
    question: dict,
    *,
    profile: dict,
    settings: Settings,
    db_path: str | Path,
) -> tuple[dict | None, str | None]:
    session = snapshot["session"]
    try:
        with st.spinner("Reviewing your answer against the question..."):
            result = InterviewManager(AIService(settings)).evaluate(
                role=session["role"],
                experience_level=session["experience_level"],
                interview_type=session["interview_type"],
                question=question["question_text"],
                answer=question["answer_text"],
            )
        save_evaluation(
            session["id"],
            profile["id"],
            question["answer_id"],
            overall_score=result.overall_score,
            dimension_scores=result.scores.model_dump(),
            feedback=result.model_dump(),
            db_path=db_path,
        )
    except AIServiceError as exc:
        return None, str(exc)
    except (ValueError, sqlite3.Error) as exc:
        return None, f"Couldn’t save the answer evaluation: {exc}"

    updated = get_interview_snapshot(session["id"], profile["id"], db_path=db_path)
    if updated is None:
        return None, "The interview could not be reloaded after saving the evaluation."
    return updated, None


def _attempt_next_question(
    snapshot: dict,
    *,
    profile: dict,
    settings: Settings,
    db_path: str | Path,
) -> None:
    session_id = snapshot["session"]["id"]
    error_key = f"interview-question-error-{session_id}"
    try:
        with st.spinner("Preparing your next role-focused question..."):
            _generate_question(
                snapshot,
                profile=profile,
                settings=settings,
                db_path=db_path,
            )
    except AIServiceError as exc:
        st.session_state[error_key] = str(exc)
    except (ValueError, sqlite3.Error) as exc:
        st.session_state[error_key] = f"Couldn’t save the next interview question: {exc}"
    else:
        st.session_state.pop(error_key, None)
    st.rerun()


def _render_answer_review(
    snapshot: dict,
    question: dict,
    *,
    profile: dict,
    settings: Settings,
    db_path: str | Path,
) -> None:
    session = snapshot["session"]
    session_id = session["id"]
    st.markdown(
        f'<section class="reviewed-answer-card"><div class="question-label">QUESTION {question["sequence_number"]:02d}</div><h3>{html.escape(question["question_text"])}</h3><div class="review-answer-label">YOUR ANSWER</div><p>{html.escape(question["answer_text"])}</p></section>',
        unsafe_allow_html=True,
    )

    evaluation = question["feedback_json"]
    evaluation_error_key = f"answer-evaluation-error-{question['answer_id']}"
    evaluation_error = st.session_state.get(evaluation_error_key)
    if question["evaluation_id"] is not None:
        st.session_state.pop(evaluation_error_key, None)
        evaluation_error = None
    if question["was_skipped"]:
        st.info("This question was skipped and has no answer to evaluate.")
    elif session["is_demo"]:
        st.info(
            "Demo answers are saved for practice, but Demo Mode does not run the LLM "
            "or provide AI evaluation."
        )
    elif question["evaluation_id"] is None and not evaluation_error:
        if not settings.groq_api_key:
            evaluation_error = (
                "GROQ_API_KEY is not configured, so this answer could not be evaluated."
            )
        else:
            updated, evaluation_error = _evaluate_saved_answer(
                snapshot,
                question,
                profile=profile,
                settings=settings,
                db_path=db_path,
            )
            if updated is not None:
                snapshot = updated
                question = snapshot["questions"][-1]
                evaluation = question["feedback_json"]
                st.session_state.pop(evaluation_error_key, None)
            elif evaluation_error:
                st.session_state[evaluation_error_key] = evaluation_error

    if evaluation_error and not question["was_skipped"] and not session["is_demo"]:
        st.error(evaluation_error)
        retry_label = (
            "Check API key and retry evaluation"
            if not settings.groq_api_key
            else "Retry evaluation"
        )
        if st.button(retry_label, type="primary", key=f"retry-evaluation-{session_id}"):
            st.session_state.pop(evaluation_error_key, None)
            st.rerun()
        if st.button("End interview", key=f"end-review-{session_id}"):
            _end_interview(session_id, profile["id"], snapshot["questions"], db_path)
            st.rerun()
        return

    if evaluation:
        if len(question["answer_text"].split()) < SHORT_ANSWER_WORD_LIMIT:
            st.info(
                "This was a very short answer. The evaluation is limited to evidence "
                "in the words you provided."
            )
        _render_evaluation(evaluation)

    has_more = len(snapshot["questions"]) < session["question_count"]
    question_error_key = f"interview-question-error-{session_id}"
    question_error = st.session_state.get(question_error_key)
    if question_error:
        st.error(question_error)

    next_col, end_col = st.columns(2)
    next_label = "Next question" if has_more else "Finish interview"
    if question_error:
        next_label = "Retry question generation"
    if next_col.button(
        next_label,
        type="primary",
        use_container_width=True,
        key=f"advance-interview-{session_id}",
    ):
        if question_error:
            st.session_state.pop(question_error_key, None)
        if has_more:
            _attempt_next_question(
                snapshot,
                profile=profile,
                settings=settings,
                db_path=db_path,
            )
        else:
            finish_session(
                session_id, profile["id"], status="completed", db_path=db_path
            )
            st.rerun()
    if end_col.button(
        "End interview",
        use_container_width=True,
        key=f"end-review-{session_id}",
    ):
        _end_interview(session_id, profile["id"], snapshot["questions"], db_path)
        st.rerun()


def render_interview_simulator(
    profile: dict | None,
    settings: Settings,
) -> None:
    """Render a resumable single-question-at-a-time interview session."""
    _render_header()
    if profile is None:
        st.warning("Set up your profile before starting an interview.")
        st.markdown(
            '<a class="button-primary" href="?page=onboarding" target="_self">Set up your profile <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return

    raw_session_id = st.query_params.get("session_id")
    try:
        session_id = int(raw_session_id) if raw_session_id else 0
    except (TypeError, ValueError):
        session_id = 0
    if session_id < 1:
        st.warning("No saved interview setup was found.")
        st.markdown(
            '<a class="button-primary" href="?page=roles" target="_self">Choose a role <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return

    db_path = settings.database_path
    snapshot = get_interview_snapshot(session_id, profile["id"], db_path=db_path)
    if snapshot is None:
        st.warning("No saved interview setup was found for this profile.")
        st.markdown(
            '<a class="button-primary" href="?page=roles" target="_self">Choose a role <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return

    session = snapshot["session"]
    st.markdown(
        f'<div class="interview-title-row"><div><div class="eyebrow">YOUR PRACTICE SESSION</div><h1>{html.escape(session["role"])}</h1></div><div class="interview-meta">{html.escape(session["experience_level"])} · {html.escape(session["difficulty"])} · {html.escape(session["interview_type"])}</div></div>',
        unsafe_allow_html=True,
    )
    if session["is_demo"]:
        st.warning(
            "DEMO MODE · Sample questions only. This session is not AI-generated "
            "and will not be included in real statistics."
        )

    if session["status"] != "in_progress":
        _render_ended(
            session,
            snapshot["questions"],
            profile["id"],
            db_path,
        )
        return

    questions = snapshot["questions"]
    if questions and questions[-1]["answer_id"] is not None:
        _render_answer_review(
            snapshot,
            questions[-1],
            profile=profile,
            settings=settings,
            db_path=db_path,
        )
        return

    pending = next((item for item in questions if item["answer_id"] is None), None)
    if pending is None and len(questions) < session["question_count"]:
        if not session["is_demo"] and not settings.groq_api_key:
            st.warning(
                "GROQ_API_KEY is not configured, so live question generation is unavailable."
            )
            st.caption(
                "Add your key to .env and reload to use AI-generated questions, or "
                "switch this unused setup into clearly labeled Demo Mode."
            )
            if not questions:
                _show_demo_option(session_id, profile["id"], db_path)
            else:
                st.caption(
                    "This live session already has questions and cannot switch to "
                    "Demo Mode without mixing sample and real activity."
                )
                if st.button("End interview", key=f"end-no-key-{session_id}"):
                    _end_interview(
                        session_id, profile["id"], questions, db_path
                    )
                    st.rerun()
            return

        error_key = f"interview-question-error-{session_id}"
        previous_error = st.session_state.get(error_key)
        if previous_error:
            _show_generation_error(
                session_id,
                profile["id"],
                questions,
                db_path,
                previous_error,
            )
            return
        try:
            with st.spinner(
                "Choosing a role-focused follow-up..." if questions else "Preparing your first question..."
            ):
                _generate_question(
                    snapshot,
                    profile=profile,
                    settings=settings,
                    db_path=db_path,
                )
        except AIServiceError as exc:
            st.session_state[error_key] = str(exc)
            _show_generation_error(
                session_id, profile["id"], questions, db_path, str(exc)
            )
            return
        except (ValueError, sqlite3.Error) as exc:
            message = f"Couldn’t save the next interview question: {exc}"
            st.session_state[error_key] = message
            _show_generation_error(
                session_id, profile["id"], questions, db_path, message
            )
            return

        snapshot = get_interview_snapshot(session_id, profile["id"], db_path=db_path)
        if snapshot is None:
            st.error("The interview session could not be reloaded after saving its question.")
            return
        session = snapshot["session"]
        questions = snapshot["questions"]
        pending = next((item for item in questions if item["answer_id"] is None), None)

    if pending is None:
        if len(questions) >= session["question_count"]:
            finish_session(
                session_id, profile["id"], status="completed", db_path=db_path
            )
            st.rerun()
        st.error("No active question is available. Refresh to resume this session.")
        return

    resolved_count = sum(item["answer_id"] is not None for item in questions)
    answered_count = sum(
        item["answer_id"] is not None and not item["was_skipped"] for item in questions
    )
    skipped_count = sum(
        item["answer_id"] is not None and item["was_skipped"] for item in questions
    )
    st.progress(resolved_count / session["question_count"])
    st.caption(
        f"{resolved_count} of {session['question_count']} questions complete · "
        f"{answered_count} answered · {skipped_count} skipped"
    )

    left, right = st.columns([1.5, 1])
    with left:
        st.markdown(
            f'<div class="question-count">QUESTION {pending["sequence_number"]:02d} <span>OF {session["question_count"]:02d}</span></div>',
            unsafe_allow_html=True,
        )
    with right:
        _render_timer(pending["generated_at"])

    if session["is_demo"]:
        st.markdown(
            '<div class="sample-question-label">DEMO SAMPLE · NOT AI-GENERATED</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<section class="simulator-question-card"><div class="question-label">YOUR QUESTION</div><div class="simulator-question-text">{html.escape(pending["question_text"])}</div></section>',
        unsafe_allow_html=True,
    )

    with st.form(key=f"answer-form-{pending['id']}"):
        answer = st.text_area(
            "Your answer",
            height=230,
            placeholder="Take a moment to think, then write your answer here...",
            key=f"answer-text-{pending['id']}",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "Submit answer", type="primary", use_container_width=True
        )

    skip_col, end_col = st.columns(2)
    skipped = skip_col.button(
        "Skip question", use_container_width=True, key=f"skip-{pending['id']}"
    )
    ended = end_col.button(
        "End interview", use_container_width=True, key=f"end-interview-{session_id}"
    )

    if submitted:
        try:
            save_answer(
                session_id,
                profile["id"],
                pending["id"],
                answer_text=answer,
                duration_seconds=_elapsed_seconds(pending["generated_at"]),
                db_path=db_path,
            )
        except (ValueError, sqlite3.Error) as exc:
            st.error(f"Couldn’t save your answer: {exc}")
        else:
            st.rerun()
    elif skipped:
        try:
            save_answer(
                session_id,
                profile["id"],
                pending["id"],
                answer_text="",
                duration_seconds=_elapsed_seconds(pending["generated_at"]),
                was_skipped=True,
                db_path=db_path,
            )
        except (ValueError, sqlite3.Error) as exc:
            st.error(f"Couldn’t skip this question: {exc}")
        else:
            st.rerun()
    if ended:
        _end_interview(session_id, profile["id"], questions, db_path)
        st.rerun()
