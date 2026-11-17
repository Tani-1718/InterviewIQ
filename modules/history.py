"""Session history, saved feedback, score comparisons, and deletion."""

import html
import sqlite3
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from database.db import (
    delete_session,
    get_interview_snapshot,
    get_session_confidence,
    get_session_history,
    get_sus_responses,
)
from modules.sus import calculate_sus_score


def _render_header() -> None:
    st.markdown(
        """
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self">Dashboard</a>
            <a href="?page=history" target="_self" class="nav-current">History</a>
            <a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=roles" target="_self">Practice <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _score_comparison(sessions: list[dict]) -> None:
    scored = [
        session
        for session in sessions
        if not session["is_demo"] and session["average_score"] is not None
    ]
    st.markdown(
        """
        <div class="dashboard-section-heading">
          <div><div class="eyebrow">REAL SESSIONS ONLY</div><h2>Compare evaluated scores</h2></div>
          <span class="chart-caption">Average score per saved session</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not scored:
        st.info("Evaluated real-session scores will appear here when available.")
        return

    labels = [
        f"{session['role']} · {session['started_at'][:10]}"
        for session in scored
    ]
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=[session["average_score"] for session in scored],
            marker_color="#a78bfa",
            customdata=[
                [session["status"].replace("_", " ").title(), session["questions_answered"]]
                for session in scored
            ],
            hovertemplate=(
                "%{x}<br>Score: %{y:.1f}/100"
                "<br>Status: %{customdata[0]}"
                "<br>Answers: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        template="plotly_dark",
        height=300,
        margin={"l": 12, "r": 12, "t": 20, "b": 70},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#c8cede"},
        xaxis={"tickangle": -25, "showgrid": False},
        yaxis={"range": [0, 100], "title": "Average evaluated score"},
        showlegend=False,
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    st.caption("Demo Mode sessions are excluded from score comparisons.")


def _render_session_detail(
    session_id: int,
    user_id: int,
    db_path: str | Path,
) -> None:
    snapshot = get_interview_snapshot(session_id, user_id, db_path=db_path)
    if snapshot is None:
        st.warning("This session is not available for the current profile.")
        st.session_state.pop("history_selected_session_id", None)
        return
    session = snapshot["session"]
    st.markdown(
        f'<div class="dashboard-section-heading"><div><div class="eyebrow">SAVED SESSION</div><h2>{html.escape(session["role"])}</h2></div><span class="chart-caption">{html.escape(session["started_at"][:10])}</span></div>',
        unsafe_allow_html=True,
    )
    if session["is_demo"]:
        st.warning("DEMO SESSION · Sample questions and answers are not real AI results.")

    confidence = get_session_confidence(session_id, user_id, db_path=db_path)
    if confidence:
        st.markdown("**SELF-REPORTED confidence (not performance)**")
        before, after = confidence.get("before"), confidence.get("after")
        if before is not None and after is not None:
            left, middle, right = st.columns(3)
            left.metric("Before", f"{before}/5")
            middle.metric("After", f"{after}/5")
            right.metric("Change", f"{after - before:+d}")
        elif before is not None:
            st.metric("Before practice", f"{before}/5")
        elif after is not None:
            st.metric("After practice", f"{after}/5")

    if session["status"] == "completed":
        responses = get_sus_responses(session_id, user_id, db_path=db_path)
        if responses is not None:
            st.metric("SUS score", f"{calculate_sus_score(responses):.1f}/100")

    if session["status"] == "in_progress":
        st.markdown(
            f'<a class="button-primary" href="?page=interview&amp;session_id={session_id}" target="_self">Continue interview <span>→</span></a>',
            unsafe_allow_html=True,
        )
    elif session["status"] == "completed":
        st.markdown(
            f'<a class="button-primary" href="?page=results&amp;session_id={session_id}" target="_self">View report <span>→</span></a>',
            unsafe_allow_html=True,
        )

    for question in snapshot["questions"]:
        with st.expander(
            f"Question {question['sequence_number']}: {question['question_text']}"
        ):
            if question["was_skipped"]:
                st.caption("Skipped")
            elif question["answer_id"] is not None:
                st.markdown("**Candidate answer**")
                st.text(question["answer_text"])
            if question["evaluation_id"] is not None and not session["is_demo"]:
                st.markdown(f"**Score: {question['overall_score']}/100**")
                feedback = question["feedback_json"] or {}
                for field, label in (
                    ("what_went_well", "What went well"),
                    ("what_was_missing", "What was missing"),
                    ("mistakes_or_inaccuracies", "Mistakes or inaccuracies"),
                    ("suggestions", "Suggestions"),
                    ("concepts_to_revise", "Concepts to revise"),
                ):
                    items = feedback.get(field, [])
                    if items:
                        st.markdown(f"**{label}**")
                        for item in items:
                            st.markdown(f"- {item}")

    if st.button("Close session details", key=f"close-history-detail-{session_id}"):
        st.session_state.pop("history_selected_session_id", None)
        st.rerun()


def render_history_page(profile: dict | None, db_path: str | Path) -> None:
    """Render a profile's real and demo sessions with owned deletion actions."""
    _render_header()
    if profile is None:
        st.info("Create a profile before viewing interview history.")
        return

    st.markdown(
        """
        <div class="page-intro dashboard-intro">
          <div class="eyebrow">YOUR SAVED PRACTICE</div>
          <h1>Interview history.</h1>
          <p>Revisit questions and feedback, compare evaluated scores, or remove sessions you no longer need.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    sessions = get_session_history(profile["id"], db_path=db_path)
    _score_comparison(sessions)

    selected_id = st.session_state.get("history_selected_session_id")
    if selected_id is not None:
        _render_session_detail(int(selected_id), profile["id"], db_path)

    st.markdown(
        """
        <div class="dashboard-section-heading recent-heading">
          <div><div class="eyebrow">ALL SAVED SESSIONS</div><h2>History</h2></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not sessions:
        st.info("No interview sessions have been saved yet.")
        return

    for session in sessions:
        is_demo = bool(session["is_demo"])
        label = "DEMO" if is_demo else "REAL SESSION"
        score = (
            f"{session['average_score']:.1f}/100"
            if session["average_score"] is not None and not is_demo
            else "Not scored"
        )
        with st.container(border=True):
            role_column, detail_column, action_column = st.columns([3, 3, 2])
            role_column.markdown(f"**{html.escape(session['role'])}**")
            role_column.caption(f"{label} · {session['status'].replace('_', ' ').title()}")
            detail_column.caption(
                f"{session['started_at'][:10]} · "
                f"{session['questions_answered']} answered · "
                f"{session['questions_skipped']} skipped · {score}"
            )
            open_column, delete_column = action_column.columns(2)
            if open_column.button("Open", key=f"history-open-{session['id']}"):
                st.session_state["history_selected_session_id"] = int(session["id"])
                st.rerun()
            if delete_column.button("Delete", key=f"history-delete-{session['id']}"):
                st.session_state["pending_delete_session_id"] = int(session["id"])
                st.rerun()

    pending_id = st.session_state.get("pending_delete_session_id")
    if pending_id is not None:
        pending = next(
            (session for session in sessions if session["id"] == pending_id), None
        )
        if pending is None:
            st.session_state.pop("pending_delete_session_id", None)
        else:
            st.warning(
                f"Delete the {pending['role']} session and all saved answers, feedback, and survey records? This cannot be undone."
            )
            confirm, cancel = st.columns(2)
            if confirm.button(
                "Delete session permanently",
                type="primary",
                key=f"history-confirm-delete-{pending_id}",
            ):
                try:
                    deleted = delete_session(pending_id, profile["id"], db_path=db_path)
                except sqlite3.Error as exc:
                    st.error(f"Couldn’t delete this session: {exc}")
                else:
                    if deleted:
                        if st.session_state.get("history_selected_session_id") == pending_id:
                            st.session_state.pop("history_selected_session_id", None)
                        st.session_state.pop("pending_delete_session_id", None)
                        st.rerun()
                    else:
                        st.error("This session was not found for the current profile.")
            if cancel.button("Keep session", key=f"history-cancel-delete-{pending_id}"):
                st.session_state.pop("pending_delete_session_id", None)
                st.rerun()
