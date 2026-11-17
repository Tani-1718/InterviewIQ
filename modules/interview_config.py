"""Interview configuration, summary, and pre-interview confidence capture."""

import html
import sqlite3
from pathlib import Path

import streamlit as st

from config.roles import ROLE_BY_ID
from config.surveys import CONFIDENCE_LABELS
from database.db import create_session_with_confidence


EXPERIENCE_LEVELS = ("Fresher", "Intermediate", "Experienced")
DIFFICULTIES = ("Easy", "Medium", "Hard")
QUESTION_COUNTS = (5, 10, 15)
INTERVIEW_TYPES = ("Technical", "HR", "Behavioral", "Mixed")
def _render_header(active: str = "Roles") -> None:
    st.markdown(
        f"""
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self">Dashboard</a><a href="?page=onboarding" target="_self">Profile</a><a href="?page=roles" target="_self" class="nav-current">{html.escape(active)}</a><a href="?page=history" target="_self">History</a><a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=dashboard" target="_self">Dashboard <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _get_role():
    role_id = st.query_params.get("role_id") or st.session_state.get("selected_role_id")
    if role_id in ROLE_BY_ID:
        st.session_state["selected_role_id"] = role_id
    return ROLE_BY_ID.get(role_id)


def _configuration_signature(config: dict) -> tuple:
    return (
        config["role_id"],
        config["experience_level"],
        config["difficulty"],
        config["question_count"],
        config["interview_type"],
        config["company_focus"],
    )


def render_interview_configuration(profile: dict | None) -> None:
    """Collect and validate interview parameters for the selected role."""
    _render_header()
    role = _get_role()
    if profile is None:
        st.warning("Set up your profile before configuring a practice session.")
        st.markdown(
            '<a class="button-primary" href="?page=onboarding" target="_self">Set up your profile <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return
    if role is None:
        st.warning("Choose a role before configuring your interview.")
        st.markdown(
            '<a class="button-primary" href="?page=roles" target="_self">Choose a role <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return

    config_role_id = st.session_state.get("_config_role_id")
    if config_role_id != role["id"]:
        default_level = profile["experience_level"]
        recommended_difficulty = role["difficulty"]
        if default_level == "Fresher" and recommended_difficulty == "Hard":
            recommended_difficulty = "Medium"
        st.session_state["_config_role_id"] = role["id"]
        st.session_state["config_experience_level"] = default_level
        st.session_state["config_difficulty"] = recommended_difficulty
        st.session_state["config_question_count"] = 5
        st.session_state["config_interview_type"] = "Mixed"
        st.session_state["config_company_focus"] = profile["target_company"] or ""

    st.markdown(
        f"""
        <div class="page-intro config-page-intro">
          <div class="eyebrow">BUILD YOUR PRACTICE</div>
          <h1>Make this interview yours.</h1>
          <p>Adjust the session for your experience and what you want to practice.</p>
        </div>
        <div class="chosen-role-banner"><span class="role-card-icon {role['color']}">{role['icon']}</span><div><small>SELECTED ROLE</small><strong>{html.escape(role['title'])}</strong></div><a href="?page=roles" target="_self">Change role</a></div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("interview_configuration_form"):
        level_col, difficulty_col = st.columns(2)
        with level_col:
            experience_level = st.selectbox(
                "Experience level",
                EXPERIENCE_LEVELS,
                key="config_experience_level",
            )
        with difficulty_col:
            difficulty = st.selectbox(
                "Difficulty",
                DIFFICULTIES,
                key="config_difficulty",
            )
        question_col, type_col = st.columns(2)
        with question_col:
            question_count = st.selectbox(
                "Number of questions",
                QUESTION_COUNTS,
                format_func=lambda value: f"{value} questions",
                key="config_question_count",
            )
        with type_col:
            interview_type = st.selectbox(
                "Interview type",
                INTERVIEW_TYPES,
                key="config_interview_type",
            )
        company_focus = st.text_input(
            "Company focus (optional)",
            value=st.session_state["config_company_focus"],
            key="config_company_focus",
            placeholder="Add a company to tailor the context",
        )
        st.caption("Company focus guides context; it does not imply access to private hiring information.")
        submitted = st.form_submit_button(
            "Review your setup", type="primary", use_container_width=True
        )

    if submitted:
        st.session_state["interview_configuration"] = {
            "role_id": role["id"],
            "role": role["title"],
            "experience_level": experience_level,
            "difficulty": difficulty,
            "question_count": question_count,
            "interview_type": interview_type,
            "company_focus": company_focus.strip(),
        }
        st.session_state.pop("started_configuration_signature", None)
        st.session_state.pop("current_session_id", None)
        st.session_state["pre_interview_confidence_rating"] = None
        st.query_params["page"] = "summary"
        st.rerun()


def render_interview_summary(
    profile: dict | None, db_path: str | Path
) -> None:
    """Review configuration, collect self-reported confidence, and save the session."""
    _render_header(active="Configuration")
    config = st.session_state.get("interview_configuration")
    if profile is None:
        st.warning("Set up your profile before starting an interview.")
        st.markdown(
            '<a class="button-primary" href="?page=onboarding" target="_self">Set up your profile <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return
    if not config or config["role_id"] not in ROLE_BY_ID:
        st.warning("Finish interview configuration before reviewing the summary.")
        st.markdown(
            f'<a class="button-primary" href="?page=configure&amp;role_id={html.escape(config["role_id"])}" target="_self">Configure interview <span>→</span></a>',
            unsafe_allow_html=True,
        )
        return
    current_session_id = st.session_state.get("current_session_id")
    if (
        current_session_id
        and st.session_state.get("started_configuration_signature")
        == _configuration_signature(config)
    ):
        st.query_params["page"] = "interview"
        st.query_params["session_id"] = str(current_session_id)
        st.rerun()

    safe_role = html.escape(config["role"])
    safe_company = html.escape(config["company_focus"]) if config["company_focus"] else "No company focus"
    st.markdown(
        f"""
        <div class="page-intro summary-page-intro">
          <div class="eyebrow">ONE LAST CHECK-IN</div>
          <h1>You’re setting the pace.</h1>
          <p>Review your practice setup, then tell us how confident you feel before you begin.</p>
        </div>
        <div class="config-summary-card">
          <div class="summary-card-heading"><span class="role-card-icon {ROLE_BY_ID[config['role_id']]['color']}">{ROLE_BY_ID[config['role_id']]['icon']}</span><div><small>INTERVIEW PRACTICE</small><h2>{safe_role}</h2></div><a href="?page=configure&amp;role_id={config['role_id']}" target="_self">Edit setup</a></div>
          <div class="summary-details">
            <div><small>EXPERIENCE</small><strong>{html.escape(config['experience_level'])}</strong></div>
            <div><small>DIFFICULTY</small><strong>{html.escape(config['difficulty'])}</strong></div>
            <div><small>QUESTIONS</small><strong>{config['question_count']}</strong></div>
            <div><small>TYPE</small><strong>{html.escape(config['interview_type'])}</strong></div>
            <div class="summary-company"><small>COMPANY FOCUS</small><strong>{safe_company}</strong></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="confidence-prompt">
          <div class="eyebrow">SELF-REPORTED CONFIDENCE · BEFORE PRACTICE</div>
          <h2>How confident do you feel about attending a real interview for this role?</h2>
          <p>This is your own reflection—not an assessment of your interview ability.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("pre_interview_confidence_form"):
        rating = st.radio(
            "Choose a confidence rating from 1 to 5",
            options=(1, 2, 3, 4, 5),
            format_func=lambda value: f"{value} · {CONFIDENCE_LABELS[value]}",
            horizontal=True,
            index=None,
            key="pre_interview_confidence_rating",
        )
        started = st.form_submit_button(
            "Confirm setup & start interview", type="primary", use_container_width=True
        )
        if started:
            if rating is None:
                st.error("Choose a confidence rating before starting.")
            else:
                try:
                    session_id = create_session_with_confidence(
                        profile["id"],
                        role=config["role"],
                        experience_level=config["experience_level"],
                        difficulty=config["difficulty"],
                        question_count=config["question_count"],
                        interview_type=config["interview_type"],
                        company_focus=config["company_focus"] or None,
                        confidence_rating=rating,
                        db_path=db_path,
                    )
                    st.session_state["current_session_id"] = session_id
                    st.session_state["started_configuration_signature"] = (
                        _configuration_signature(config)
                    )
                    st.query_params["page"] = "interview"
                    st.query_params["session_id"] = str(session_id)
                    st.rerun()
                except (ValueError, sqlite3.Error) as exc:
                    st.error(f"Couldn’t save your interview setup: {exc}")
