"""Validated multi-step profile setup and editing."""

import sqlite3
from pathlib import Path

import streamlit as st

from database.db import create_user, update_user


EXPERIENCE_LEVELS = ("Fresher", "Intermediate", "Experienced")
STEPS = ("About you", "Your goal", "Your focus")


def parse_list_input(value: str, field_name: str) -> list[str]:
    """Parse a comma-separated profile field into unique, trimmed values."""
    items = list(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))
    if not items:
        raise ValueError(f"Add at least one {field_name.lower()}.")
    return items


def _initial_values(profile: dict | None) -> dict:
    if profile:
        return {
            "name": profile["name"],
            "education": profile["education"],
            "experience_level": profile["experience_level"],
            "target_role": profile["target_role"],
            "target_company": profile["target_company"] or "",
            "technical_skills": ", ".join(profile["technical_skills"]),
            "improvement_areas": ", ".join(profile["improvement_areas"]),
        }
    return {
        "name": "",
        "education": "",
        "experience_level": "Fresher",
        "target_role": "",
        "target_company": "",
        "technical_skills": "",
        "improvement_areas": "",
    }


def _ensure_form_state(profile: dict | None) -> None:
    profile_id = profile["id"] if profile else None
    if (
        "_onboarding_profile_id" in st.session_state
        and st.session_state["_onboarding_profile_id"] == profile_id
    ):
        return

    values = _initial_values(profile)
    st.session_state["_onboarding_profile_id"] = profile_id
    st.session_state["onboarding_values"] = values
    st.session_state["onboarding_step"] = 0
    for field, value in values.items():
        st.session_state[f"onboarding_{field}"] = value


def _store_values(**fields: str) -> None:
    st.session_state["onboarding_values"].update(fields)


def render_onboarding(profile: dict | None, db_path: str | Path) -> None:
    """Render the profile onboarding wizard or edit form."""
    _ensure_form_state(profile)
    values = st.session_state["onboarding_values"]
    step = st.session_state["onboarding_step"]

    st.markdown(
        """
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self">Dashboard</a><a href="?page=onboarding" target="_self" class="nav-current">Profile</a><a href="?page=history" target="_self">History</a><a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=landing" target="_self">Home <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="page-intro onboarding-intro">
          <div class="eyebrow">LET’S MAKE THIS YOURS</div>
          <h1>{'Edit your profile' if profile else 'A little about you.'}</h1>
          <p>We’ll use your goals to shape interview practice that fits where you are and where you want to go.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    step_cols = st.columns(len(STEPS))
    for index, (column, label) in enumerate(zip(step_cols, STEPS)):
        state_class = "step-active" if index == step else (
            "step-complete" if index < step else ""
        )
        column.markdown(
            f'<div class="onboarding-step {state_class}"><span>{index + 1:02d}</span> {label}</div>',
            unsafe_allow_html=True,
        )

    with st.form(f"onboarding_step_{step}", clear_on_submit=False):
        error = None
        if step == 0:
            st.markdown('<div class="form-step-title">First, the basics</div>', unsafe_allow_html=True)
            name = st.text_input("Your name", value=values["name"], key="onboarding_name")
            education = st.text_input(
                "Education", value=values["education"], key="onboarding_education",
                placeholder="e.g. BSc Computer Science, self-taught, MBA",
            )
            continue_clicked = st.form_submit_button("Continue", type="primary", use_container_width=True)
            if continue_clicked:
                _store_values(name=name, education=education)
                if not name.strip():
                    error = "Please enter your name."
                elif not education.strip():
                    error = "Please add your education or learning background."
                else:
                    st.session_state["onboarding_step"] = 1
                    st.rerun()

        elif step == 1:
            st.markdown('<div class="form-step-title">What are you working toward?</div>', unsafe_allow_html=True)
            experience_level = st.selectbox(
                "Experience level",
                EXPERIENCE_LEVELS,
                index=EXPERIENCE_LEVELS.index(values["experience_level"]),
                key="onboarding_experience_level",
            )
            target_role = st.text_input(
                "Target role", value=values["target_role"], key="onboarding_target_role",
                placeholder="e.g. Product Designer",
            )
            target_company = st.text_input(
                "Target company (optional)",
                value=values["target_company"],
                key="onboarding_target_company",
                placeholder="e.g. a company you’re interested in",
            )
            back, continue_col = st.columns(2)
            back_clicked = back.form_submit_button("Back", use_container_width=True)
            continue_clicked = continue_col.form_submit_button(
                "Continue", type="primary", use_container_width=True
            )
            if back_clicked:
                _store_values(
                    experience_level=experience_level,
                    target_role=target_role,
                    target_company=target_company,
                )
                st.session_state["onboarding_step"] = 0
                st.rerun()
            if continue_clicked:
                _store_values(
                    experience_level=experience_level,
                    target_role=target_role,
                    target_company=target_company,
                )
                if not target_role.strip():
                    error = "Please add the role you’re preparing for."
                else:
                    st.session_state["onboarding_step"] = 2
                    st.rerun()

        else:
            st.markdown('<div class="form-step-title">Choose your starting point</div>', unsafe_allow_html=True)
            technical_skills = st.text_input(
                "Technical skills",
                value=values["technical_skills"],
                key="onboarding_technical_skills",
                placeholder="Separate skills with commas, e.g. Python, SQL, Figma",
                help="Add one or more skills relevant to your target role.",
            )
            improvement_areas = st.text_input(
                "Areas you’d like to improve",
                value=values["improvement_areas"],
                key="onboarding_improvement_areas",
                placeholder="e.g. explaining decisions, system design, confidence",
                help="Choose one or more areas you’d like practice to focus on.",
            )
            st.caption("You can update these details any time from your profile.")
            back, save_col = st.columns(2)
            back_clicked = back.form_submit_button("Back", use_container_width=True)
            save_clicked = save_col.form_submit_button(
                "Save profile" if profile else "Finish setup",
                type="primary",
                use_container_width=True,
            )
            if back_clicked:
                _store_values(
                    technical_skills=technical_skills,
                    improvement_areas=improvement_areas,
                )
                st.session_state["onboarding_step"] = 1
                st.rerun()
            if save_clicked:
                _store_values(
                    technical_skills=technical_skills,
                    improvement_areas=improvement_areas,
                )
                try:
                    skills = parse_list_input(technical_skills, "technical skill")
                    improvement_list = parse_list_input(improvement_areas, "area to improve")
                    profile_fields = {
                        "name": values["name"],
                        "education": values["education"],
                        "experience_level": values["experience_level"],
                        "target_role": values["target_role"],
                        "target_company": values["target_company"] or None,
                        "technical_skills": skills,
                        "improvement_areas": improvement_list,
                    }
                    if profile:
                        update_user(profile["id"], db_path=db_path, **profile_fields)
                    else:
                        profile_id = create_user(db_path=db_path, **profile_fields)
                        st.session_state["user_id"] = profile_id
                    st.query_params["page"] = "dashboard"
                    st.rerun()
                except ValueError as exc:
                    error = str(exc)
                except sqlite3.Error as exc:
                    st.error(f"Couldn’t save your profile to the local database: {exc}")

        if error:
            st.error(error)
