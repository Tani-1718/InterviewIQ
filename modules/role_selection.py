"""Role picker for the five currently supported interview tracks."""

import html
from pathlib import Path

import streamlit as st

from config.roles import ROLES


def _render_header() -> None:
    st.markdown(
        """
        <header class="topbar app-topbar">
          <a class="brand" href="?page=landing#top" target="_self"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="?page=dashboard" target="_self">Dashboard</a><a href="?page=onboarding" target="_self">Profile</a><a href="?page=history" target="_self">History</a><a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=dashboard" target="_self">Dashboard <span aria-hidden="true">↗</span></a>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_role_selection(profile: dict | None, db_path: str | Path) -> None:
    """Render role cards and route a selected role into configuration."""
    del db_path
    _render_header()
    if profile is None:
        st.markdown(
            """
            <div class="page-intro role-page-intro"><div class="eyebrow">CHOOSE YOUR PRACTICE</div><h1>Pick a role to begin.</h1><p>Set up your profile first so your practice can be tailored to you.</p></div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<a class="button-primary" href="?page=onboarding" target="_self">Set up your profile <span>→</span></a>', unsafe_allow_html=True)
        return

    st.markdown(
        """
        <div class="page-intro role-page-intro">
          <div class="eyebrow">YOUR NEXT STEP</div>
          <h1>What role are you preparing for?</h1>
          <p>Choose a track to get a focused practice setup. You can adjust the experience and interview style next.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    columns = st.columns(2, gap="medium")
    for index, role in enumerate(ROLES):
        column = columns[index % 2]
        with column:
            title = html.escape(role["title"])
            description = html.escape(role["description"])
            skills = " <span>·</span> ".join(html.escape(skill) for skill in role["skills"])
            st.markdown(
                f"""
                <article class="select-role-card">
                  <div class="select-role-top"><span class="role-card-icon {role['color']}">{role['icon']}</span><span class="role-difficulty">Suggested · {html.escape(role['difficulty'])}</span></div>
                  <h2>{title}</h2><p>{description}</p>
                  <div class="select-role-skills"><small>FOCUS AREAS</small><span>{skills}</span></div>
                      <a class="select-role-button" href="?page=configure&amp;role_id={html.escape(role['id'])}" target="_self">Start with {title} <span>→</span></a>
                </article>
                """,
                unsafe_allow_html=True,
            )
